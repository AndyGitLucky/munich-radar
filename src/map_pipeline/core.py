"""Immutable originals, candidate provenance, review and atomic release pointers."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]
ATLAS = ROOT / 'atlas'


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.new')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    os.replace(temporary,path)


def identity(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()


def safe_id(value):
    if not re.fullmatch('[a-zA-Z0-9_-]+',value):raise ValueError('Invalid identifier')
    return value


class Workspace:
    def __init__(self, root=ATLAS):self.root=Path(root).resolve()

    def path(self, relative):
        if not isinstance(relative,str) or '\\' in relative or ':' in relative or Path(relative).is_absolute():raise ValueError('Expected relative atlas path')
        result=(self.root/relative).resolve()
        if not result.is_relative_to(self.root):raise ValueError('Path escapes atlas workspace')
        return result

    @contextmanager
    def lock(self):
        self.root.mkdir(parents=True,exist_ok=True)
        with (self.root/'.lock').open('a+b') as stream:
            stream.seek(0);stream.write(b'0');stream.flush();stream.seek(0)
            try:
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError as error:raise RuntimeError('Another map command is writing; retry after it finishes') from error
            try:yield
            finally:
                stream.seek(0)
                if os.name=='nt':msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
                else:fcntl.flock(stream.fileno(),fcntl.LOCK_UN)

    def baseline(self):return load(self.root/'baseline/manifest.json')
    def plan(self):return load(self.root/'plan.json')

    def original_state(self):
        return {'version':1,'tiles':{i['id']:{'path':'baseline/'+i['image'],'sha256':i['sha256'],'version':'original'} for i in self.baseline()['items']}}

    def state(self):
        pointer=self.root/'current.json'
        if not pointer.exists():return self.original_state()
        current=load(pointer)
        if current.get('stateSha256'):
            state=load(self.path('states/'+current['stateSha256']+'.json'))
            if identity(state)!=current['stateSha256']:raise ValueError('Selected source state changed')
            return state
        return load(self.path('releases/'+current['release']+'/state.json'))

    def candidate(self,tile,version):
        safe_id(tile);safe_id(version)
        if tile not in self.original_state()['tiles']:raise ValueError('Unknown geographic section')
        return self.path(f'candidates/{tile}/{version}')

    def checked_candidate(self,tile,version):
        folder=self.candidate(tile,version);request=load(folder/'request.json')
        for name,key in [(request['prompt'],'promptSha256'),('raw.png','rawSha256'),('image.png','imageSha256'),('quality.json','qualitySha256')]:
            if not request.get(key) or not (folder/name).is_file() or digest(folder/name)!=request[key]:raise ValueError('Candidate provenance changed or incomplete: '+name)
        for ref in request['references']:
            if digest(self.path(ref['path']))!=ref['sha256']:raise ValueError('Candidate reference changed')
        return request

    def validate_state(self,state,require_review=False):
        if state.get('frame'):
            from .frame import check_frame
            check_frame(self,state['frame'],require_review)
        originals=self.original_state()['tiles']
        if set(state['tiles'])!=set(originals):raise ValueError('Sections differ from the fixed original plan')
        for tile,item in state['tiles'].items():
            path=self.path(item['path'])
            if not path.is_file() or digest(path)!=item['sha256']:raise ValueError('Missing or modified image: '+tile)
            if item['version']=='original':
                if item!=originals[tile]:raise ValueError('Original section changed: '+tile)
            else:
                folder=self.candidate(tile,item['version']);request=self.checked_candidate(tile,item['version'])
                if path!=folder/'image.png' or item['sha256']!=request.get('imageSha256'):raise ValueError('Candidate image mismatch')
                if require_review and (request.get('review',{}).get('decision')!='accept' or request['review'].get('imageSha256')!=item['sha256']):
                    raise ValueError('Visual review required: '+tile)

    def inspect(self,selected=True):
        baseline=self.baseline()
        if digest(self.root/'plan.json')!=baseline['planSha256'] or digest(self.root/'base-prompt.md')!=baseline['basePromptSha256']:raise ValueError('Frozen geographic plan or prompt changed')
        reproduction=self.root/'baseline/reproduction.json'
        if reproduction.exists() and load(reproduction).get('joinsSha256'):
            if digest(self.root/'baseline/joins.json')!=load(reproduction)['joinsSha256']:raise ValueError('Frozen overlap ownership changed')
        for item in baseline['items']:
            for path,expected in [(item['image'],item['sha256']),(item['prompt'],item['promptSha256'])]+[(r['path'],r['sha256']) for r in item['references']+[item['guide'],item['targets'],item['input']]]:
                if digest(self.path('baseline/'+path))!=expected:raise ValueError('Frozen input changed: '+path)
        if selected:self.validate_state(self.state(),require_review=True)
        return {'originalSections':len(baseline['items']),'imageSize':baseline['imageSize'],'nativeSize':baseline['nativeSize'],'status':'original sources and selected versions intact'}

    def prepare(self,tile,version,task,rect=None,allow_landmarks=False):
        folder=self.candidate(tile,version)
        if folder.exists():raise ValueError('Candidate already exists; use a new version identifier')
        if not task.strip():raise ValueError('Describe the intended local change')
        size=self.baseline()['nativeSize'][0];rect=rect or [179,179,size-179,size-179]
        if len(rect)!=4 or not (0<=rect[0]<rect[2]<=size and 0<=rect[1]<rect[3]<=size) or rect[2]-rect[0]<64 or rect[3]-rect[1]<64:raise ValueError('Edit rectangle outside native image or smaller than 64 pixels')
        tile_plan=next(t for t in self.plan()['tiles'] if t['id']==tile)
        ox,oy=tile_plan['renderOrigin']
        if not allow_landmarks:
            for mark in self.plan()['landmarks']:
                a,b,c,d=mark['protectedRect']
                if mark['owner']==tile and min(c,ox+rect[2])>max(a,ox+rect[0]) and min(d,oy+rect[3])>max(b,oy+rect[1]):
                    raise ValueError('Edit intersects an owned landmark; use --allow-landmarks for an intentional landmark change')
        base=self.state()['tiles'][tile]
        selected=self.state()['tiles']
        original=next(i for i in self.baseline()['items'] if i['id']==tile)
        references=[{'path':base['path'],'sha256':base['sha256']},
                    {'path':'baseline/'+original['guide']['path'],'sha256':original['guide']['sha256']}]
        for other in self.plan()['tiles']:
            if len(references)<5 and all(k in tile_plan and k in other for k in ('row','col')) and other['id'] in selected and abs(other['row']-tile_plan['row'])+abs(other['col']-tile_plan['col'])==1:
                references.append({'path':selected[other['id']]['path'],'sha256':selected[other['id']]['sha256']})
        text=(self.root/'base-prompt.md').read_text(encoding='utf-8')
        text+=f'\n\nEDIT THE SUPPLIED ORIGINAL PAINTING. Image 1 is the edit target and binding palette/detail reference, never a stamp for a different place.\nTask: {task}\n'
        text+='Image 2 is this section’s original geographic guide. Any following images are only direct geographic neighbors, for matching shared transitions and miniature scale; do not copy their compositions.\n'
        text+=f'Change only x={rect[0]}..{rect[2]}, y={rect[1]}..{rect[3]} in this exact {size}-square frame. Keep everything outside it visually unchanged and connect streets/vegetation at its edges.\n'
        text+='Preserve the rich olive and sage greens, terracotta/clay roofs, cream architecture, turquoise water, fine dark outlines, miniature architectural scale and dense detail of the supplied original. Do not reinterpret its colors as pale beige countryside, enlarge its buildings or add a new style/material board. Preserve north-up ground, existing river/canal courses, bridges, crop and shadow direction. No copied radial neighborhood or palace stamp, no text, UI, labels, watermark or blank margins.\n'
        text+=f'Return one full edited image at exactly {size} by {size} native pixels.\n'
        folder.mkdir(parents=True);(folder/'prompt.md').write_text(text,encoding='utf-8')
        data={'id':version,'tile':tile,'status':'prepared','task':task,'editRect':rect,'allowLandmarks':allow_landmarks,
            'base':base,'references':references,
            'prompt':'prompt.md','promptSha256':digest(folder/'prompt.md'),'created':now()}
        save(folder/'request.json',data)
        return {'candidate':str(folder),'prompt':str(folder/'prompt.md'),'references':[str(self.path(r['path'])) for r in references]}

    def import_image(self,tile,version,source):
        from PIL import Image
        from .render import compose_candidate
        folder=self.candidate(tile,version);request=load(folder/'request.json')
        if digest(folder/request['prompt'])!=request['promptSha256']:raise ValueError('Recorded prompt changed')
        if digest(self.path(request['base']['path']))!=request['base']['sha256']:raise ValueError('Edit target changed')
        for ref in request['references']:
            if digest(self.path(ref['path']))!=ref['sha256']:raise ValueError('Generation reference changed')
        if request.get('imageSha256'):raise ValueError('Candidate output is immutable; create a new candidate')
        source=Path(source).resolve()
        with Image.open(source) as image:
            if image.format!='PNG':raise ValueError('Expected original PNG output')
            if list(image.size)!=self.baseline()['nativeSize']:raise ValueError('Wrong native size; no silent rescaling')
            if image.convert('RGBA').getchannel('A').getextrema()!=(255,255):raise ValueError('Transparent pixels in generated section')
        raw=folder/'raw.png'
        if raw.exists() and digest(raw)!=digest(source):raise ValueError('Different raw output already recorded')
        if source!=raw.resolve():shutil.copyfile(source,raw)
        compose_candidate(self,folder,request)
        from .quality import candidate_quality
        report=candidate_quality(self,folder,request)
        save(folder/'quality.json',report)
        request.update(status='awaiting visual review',generatedSource=str(source),rawSha256=digest(raw),imageSha256=digest(folder/'image.png'),qualitySha256=digest(folder/'quality.json'),imported=now())
        save(folder/'request.json',request);self.review_page(tile,version)
        return report

    def review(self,tile,version,decision,note,allow_warnings=False):
        folder=self.candidate(tile,version);request=self.checked_candidate(tile,version)
        if decision not in ['accept','reject'] or not note.strip():raise ValueError('Record decision and visual observations')
        if decision=='reject' and self.state()['tiles'][tile]['version']==version:raise ValueError('Roll back the active version before rejecting it')
        if not request.get('imageSha256') or digest(folder/'image.png')!=request['imageSha256']:raise ValueError('Import an intact candidate first')
        quality=load(folder/'quality.json')
        if decision=='accept' and quality['warnings'] and not allow_warnings:raise ValueError('Quality warnings require investigation or explicit --allow-warnings with a reason')
        request['review']={'decision':decision,'note':note,'imageSha256':request['imageSha256'],'allowWarnings':allow_warnings,'at':now()}
        request['status']='visually '+('accepted' if decision=='accept' else 'rejected');save(folder/'request.json',request)
        self.review_page(tile,version)
        return request['review']

    def proposed_state(self,tile,version):
        folder=self.candidate(tile,version);request=self.checked_candidate(tile,version);state=self.state()
        if state['tiles'][tile]['sha256'] not in [request['base']['sha256'],request.get('imageSha256')]:raise ValueError('Stale candidate: this section changed since preparation')
        state['tiles'][tile]={'path':(folder/'image.png').relative_to(self.root).as_posix(),'sha256':request['imageSha256'],'version':version}
        self.validate_state(state)
        return state

    def review_page(self,tile,version,release=None):
        folder=self.candidate(tile,version);request=load(folder/'request.json');baseline=next(i for i in self.baseline()['items'] if i['id']==tile)
        if release:
            request['previewRelease']=release;save(folder/'request.json',request)
        else:release=request.get('previewRelease')
        pictures=[('Vorher',request['base']['path']),('Imagegen-Ausgabe',(folder/'raw.png').relative_to(self.root).as_posix()),('Kandidat mit geschütztem Umfeld',(folder/'image.png').relative_to(self.root).as_posix()),('Verbindliches Original','baseline/'+baseline['image']),('Geografische Vorlage','baseline/'+baseline['guide']['path'])]
        cards=''.join(f'<figure><a href="/atlas/{html.escape(path)}"><img src="/atlas/{html.escape(path)}"></a><figcaption>{label}</figcaption></figure>' for label,path in pictures)
        quality=load(folder/'quality.json') if (folder/'quality.json').exists() else {}
        extra=f'<h2>Einfügung in die Gesamtkarte</h2><p><a href="/?release={release}">Vorschau interaktiv mit Nachbarkacheln öffnen</a></p><a href="/atlas/releases/{release}/master.png"><img class="overview" src="/atlas/releases/{release}/preview.png"></a>' if release else ''
        document='''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Kachelvergleich</title><style>body{background:#f2efe6;color:#173e3a;font:16px system-ui;margin:24px}main{display:grid;grid-template-columns:repeat(2,minmax(200px,1fr));gap:20px}figure{margin:0}img{display:block;width:100%}figcaption{padding:8px}pre{white-space:pre-wrap}a{color:inherit}.overview{max-width:1600px}@media(max-width:700px){main{grid-template-columns:1fr}}</style>'''
        document+=f'<h1>{html.escape(tile)} · {html.escape(version)}</h1><p>{html.escape(request["task"])}</p><p>{html.escape(request["status"])}</p><p><a href="/">Zur Karte</a> · <a href="prompt.md">Vollständiger Prompt</a> · <a href="request.json">Protokoll</a></p><main>{cards}</main><h2>Messwerte</h2><pre>{html.escape(json.dumps(quality,ensure_ascii=False,indent=2))}</pre>'+extra
        (folder/'index.html').write_text(document,encoding='utf-8')

