"""Native Canvas assembly and immutable, verified local map releases."""
import base64
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import platform
from pathlib import Path
import threading
import time
import uuid

from .core import digest, identity, load, now, safe_id, save


def png(path,uri):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(base64.b64decode(uri.split(',',1)[1]))


@contextmanager
def browser_page(workspace,master=None):
    from playwright.sync_api import sync_playwright
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            if self.path!='/write-master' or master is None:return self.send_error(404)
            remaining=int(self.headers.get('Content-Length',0))
            if not 0<remaining<1_000_000_000:return self.send_error(400)
            with master.open('wb') as stream:
                while remaining:
                    block=self.rfile.read(min(1024*1024,remaining))
                    if not block:raise ValueError('Incomplete PNG stream')
                    stream.write(block);remaining-=len(block)
            self.send_response(200);self.end_headers();self.wfile.write(b'OK')
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(workspace.root)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            options={'args':['--js-flags=--max-old-space-size=8192']}
            if not Path(p.chromium.executable_path).exists():options['executable_path']=r'C:\Program Files\Google\Chrome\Application\chrome.exe'
            browser=p.chromium.launch(**options)
            try:
                page=browser.new_page();page.set_default_timeout(180_000)
                page.goto(f'http://127.0.0.1:{server.server_port}/renderer/index.html')
                yield page
            finally:browser.close()
    finally:server.shutdown();server.server_close()


def compose_candidate(workspace,folder,request):
    job={'base':'/'+request['base']['path'],'raw':'/'+(folder/'raw.png').relative_to(workspace.root).as_posix(),
        'rect':request['editRect'],'feather':16}
    with browser_page(workspace) as page:
        result=page.evaluate('job=>composeCandidate(job)',job)
        png(folder/'image.png',result)


def build(workspace,state=None,fresh=False):
    from .quality import compare_masters,verify_release
    started=time.monotonic();workspace.inspect(selected=False)
    state=state or workspace.state();workspace.validate_state(state)
    plan=workspace.plan();renderer_hash=identity({p.name:digest(p) for p in (workspace.root/'renderer').iterdir() if p.is_file()})
    exporter_hash=digest(Path(__file__))
    state_hash=identity(state);key=identity({'state':state_hash,'plan':digest(workspace.root/'plan.json'),'renderer':renderer_hash,'exporter':exporter_hash})[:16]
    id=key+('-'+uuid.uuid4().hex[:6] if fresh else '')
    folder=workspace.path('releases/'+id)
    if (folder/'release.json').exists():
        validate_release(workspace,id)
        if state==workspace.original_state():save(workspace.root/'baseline-release.json',{'release':id})
        print('Verified cached release '+id,flush=True);return id
    folder.mkdir(parents=True,exist_ok=True);save(folder/'state.json',state)
    tiles={t['id']:t for t in plan['tiles']}
    items=[{'id':id,'tile':tiles[id],'url':'/'+item['path'],'outputSha256':item['sha256'],
        'nativeRegistrationMatches':True,'state':'generated'} for id,item in state['tiles'].items()]
    joins=workspace.root/'baseline/joins.json'
    job={'plan':plan,'items':items,'fixedSeams':load(joins)['seams'] if joins.exists() else None}
    with browser_page(workspace,folder/'master.png') as page:
        browser_version=page.context.browser.version
        print('Assembling 75 native source sections; no image generation.',flush=True)
        page.evaluate('job=>window.job=job',job)
        result=page.evaluate('''async()=>{
          const result=await assembleProduction(true,false);
          const blob=await new Promise(resolve=>productionMaster.toBlob(resolve,'image/png'));
          if(!blob)throw Error('PNG encoding failed');
          const response=await fetch('/write-master',{method:'POST',body:blob});
          if(!response.ok)throw Error('PNG stream failed');
          delete result.master;return result;
        }''')
        png(folder/'preview.png',result.pop('preview'));save(folder/'assembly.json',result)
        keys=[];width,height=plan['imageSize'];minimum=-math.ceil(math.log2(max(width,height)/256))
        for z in range(minimum,1):
            for row in range(math.ceil(height*2**z/256)):
                images=page.evaluate('([z,row])=>productionTiles(z,row)',[z,row])
                for key,uri in images.items():png(folder/f'tiles/{key}.png',uri)
                keys.extend(images)
            print(f'Exported zoom {z}; {len(keys)} PNG tiles.',flush=True)
    config={'packageVersion':1,'version':3,'id':'painted','title':'München · gemalter Atlas',
        'coverage':'full-city','initialView':'overview','cityBounds':plan['bounds'],
        'axisScale':[plan['scale']]*2,'scale':plan['scale'],'imageSize':[width,height],
        'worldBounds':[[-height,0],[0,width]],'patchOrigin':[0,0],'patchSize':width,
        'cityOutline':plan['cityOutline'],'anchors':{},'context':[],'closestZoom':0,'tileMinZoom':minimum,
        'tileBase':f'releases/{id}/tiles','tileFormat':'png','tileKeys':keys,'sourcePixelScale':1,
        'orientation':'north-up','rotation':False,'home':{'lon':11.576,'lat':48.137},
        'artwork':f'releases/{id}/master.png','artworkSha256':digest(folder/'master.png'),
        'attribution':'Geographic source © OpenStreetMap contributors (ODbL). Artwork: built-in image_gen.'}
    print('Verifying every native delivery tile, source cores, protected landmarks and city coverage.',flush=True)
    quality,hashes=verify_release(workspace,folder,state,result,config)
    config['quality']=quality;save(folder/'quality.json',quality);save(folder/'manifest.json',config)
    if state==workspace.original_state():
        record=workspace.root/'baseline/reproduction.json'
        if record.exists():
            original=load(record);previous=workspace.path('releases/'+original['release']+'/master.png')
            if quality['masterSha256']!=original['masterSha256']:
                if not previous.exists():raise ValueError('Original reproduction digest differs and reference master is absent')
                comparison=compare_masters(previous,folder/'master.png')
                if comparison['maxChannelDifference']:raise ValueError('Original-map reproduction changed pixels')
            else:comparison={'maxChannelDifference':0,'channelsCompared':quality['channelsCompared'],'pngBytesIdentical':True}
            save(folder/'reproduction.json',comparison)
        else:
            save(joins,{'seams':result['seams'],'planSha256':digest(workspace.root/'plan.json'),'blendPixels':4})
            save(record,{'release':id,'masterSha256':quality['masterSha256'],'sourceStateSha256':state_hash,'recorded':now(),
                'joinsSha256':digest(joins),'note':'First reconstruction from the hash-verified original 75 paintings; subsequent builds must reproduce it.'})
    save(folder/'release.json',{'id':id,'stateSha256':state_hash,'rendererSha256':renderer_hash,'exporterSha256':exporter_hash,'planSha256':digest(workspace.root/'plan.json'),
        'manifestSha256':digest(folder/'manifest.json'),'masterSha256':quality['masterSha256'],'tiles':hashes,
        'complete':True,'created':now(),'durationSeconds':round(time.monotonic()-started,2),'runtime':{'python':platform.python_version(),'browser':browser_version}})
    if state==workspace.original_state():save(workspace.root/'baseline-release.json',{'release':id})
    print('Verified release '+id,flush=True);return id


def validate_release(workspace,id):
    safe_id(id);folder=workspace.path('releases/'+id);record=load(folder/'release.json')
    if not record.get('complete') or record['id']!=id:raise ValueError('Incomplete release')
    if digest(folder/'manifest.json')!=record['manifestSha256'] or digest(folder/'master.png')!=record['masterSha256']:raise ValueError('Release was modified')
    state=load(folder/'state.json')
    if identity(state)!=record['stateSha256']:raise ValueError('Release state changed')
    workspace.validate_state(state)
    for key,expected in record['tiles'].items():
        if digest(folder/f'tiles/{key}.png')!=expected:raise ValueError('Delivery tile changed: '+key)
    return folder


def publish(workspace,id):
    folder=validate_release(workspace,id)
    workspace.validate_state(load(folder/'state.json'),require_review=True)
    state=load(folder/'state.json');state_hash=identity(state)
    save(workspace.root/f'states/{state_hash}.json',state)
    previous=load(workspace.root/'current.json') if (workspace.root/'current.json').exists() else None
    pointer={'release':id,'stateSha256':state_hash,'previous':previous.get('release') if previous else None,'published':now()}
    save(workspace.root/f'history/{id}.json',pointer)
    save(workspace.root/'current.json',pointer)
    return {'release':id,'previous':previous.get('release') if previous else None,'status':'published locally'}
