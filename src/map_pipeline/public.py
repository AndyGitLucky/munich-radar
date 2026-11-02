"""Publish reviewed native atlas tiles as a static GitHub Pages package."""
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import threading
from urllib.request import urlopen
from zipfile import ZipFile, ZIP_STORED

from .core import Workspace, digest, load, save


def bundle(workspace, output):
    from .render import validate_release
    workspace.inspect()
    current = load(workspace.root/'current.json')['release']
    baseline = load(workspace.root/'baseline-release.json')['release']
    paths = {}
    generated = {}
    for release in dict.fromkeys([current, baseline]):
        folder = validate_release(workspace, release)
        workspace.validate_state(load(folder/'state.json'), require_review=True)
        manifest = load(folder/'manifest.json')
        manifest['artwork'] = f'releases/{release}/preview.png'
        manifest['artworkSha256'] = digest(folder/'preview.png')
        generated[f'releases/{release}/manifest.json'] = json.dumps(manifest, ensure_ascii=False).encode('utf-8')
        paths[f'releases/{release}/preview.png'] = folder/'preview.png'
        for key in manifest['tileKeys']:
            paths[f'releases/{release}/tiles/{key}.png'] = folder/f'tiles/{key}.png'
    # Public review files are deliberately selected, not an export of the project.
    review = workspace.root/'reports/rework-2026-11-02'
    for p in review.iterdir():
        if p.is_file() and p.suffix in ('.html','.json','.png'):
            paths[p.relative_to(workspace.root).as_posix()] = p
    for tile, item in workspace.state()['tiles'].items():
        if item['version']=='original' or tile=='r03c05':
            continue
        folder = workspace.candidate(tile,item['version'])
        request = load(folder/'request.json')
        original = next(i for i in workspace.baseline()['items'] if i['id']==tile)
        for p in folder.iterdir():
            if p.is_file():paths[p.relative_to(workspace.root).as_posix()] = p
        for name in ['baseline/'+original['image'],'baseline/'+original['guide']['path'],request['base']['path']]:
            paths[name] = workspace.path(name)
    for p in (workspace.root/'frames').rglob('*'):
        if p.is_file() and p.suffix in ('.png','.json','.md'):
            paths[p.relative_to(workspace.root).as_posix()] = p
    for name,p in paths.items():
        if p.suffix=='.html':
            text=p.read_text(encoding='utf-8')
            # Root-relative links must retain a Pages project subdirectory.
            prefix='../'*len(PurePosixPath('atlas/'+name).parent.parts)
            text=re.sub(r'((?:href|src)=")/([^"/]*)',lambda m:m[1]+prefix+m[2],text)
            text=text.replace('/master.png','/preview.png')
            generated[name]=text.encode('utf-8')
    files={name:digest(p) for name,p in paths.items() if name not in generated}
    files.update({name:sha256(data).hexdigest() for name,data in generated.items()})
    output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():raise ValueError('Distribution already exists; choose a new output path')
    with ZipFile(output,'w',compression=ZIP_STORED) as archive:
        for name,p in sorted(paths.items()):
            if name not in generated:archive.write(p,name)
        for name,data in sorted(generated.items()):archive.writestr(name,data)
        archive.writestr('catalog.json',json.dumps({'release':current,'baseline':baseline,'files':files},ensure_ascii=False).encode('utf-8'))
    tag=output.stem
    metadata={'release':current,'baseline':baseline,'assetName':output.name,'tag':tag,
              'sha256':digest(output),'bytes':output.stat().st_size,
              'url':f'https://github.com/AndyGitLucky/munich-radar/releases/download/{tag}/{output.name}'}
    save(workspace.root/'distribution.json',metadata)
    return metadata


def install_bundle(root, destination, archive_path=None):
    metadata=load(root/'atlas/distribution.json')
    if archive_path is None:
        archive_path=root/'.cache/map-pipeline'/metadata['assetName']
        if not archive_path.exists():
            archive_path.parent.mkdir(parents=True,exist_ok=True)
            temporary=archive_path.with_suffix('.part')
            with urlopen(metadata['url'],timeout=120) as response,temporary.open('wb') as stream:
                shutil.copyfileobj(response,stream,1024*1024)
            if digest(temporary)!=metadata['sha256']:
                temporary.unlink();raise ValueError('Downloaded atlas archive checksum mismatch')
            temporary.replace(archive_path)
    archive_path=Path(archive_path)
    if digest(archive_path)!=metadata['sha256']:raise ValueError('Atlas archive checksum mismatch')
    destination=destination.resolve()
    with ZipFile(archive_path) as archive:
        catalog=json.loads(archive.read('catalog.json'))
        if catalog['release']!=metadata['release'] or catalog['baseline']!=metadata['baseline']:
            raise ValueError('Distribution selection mismatch')
        for name,expected in catalog['files'].items():
            path=PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
                raise ValueError('Unsafe atlas archive path')
            target=destination.joinpath(*path.parts)
            target.parent.mkdir(parents=True,exist_ok=True)
            with archive.open(name) as source,target.open('wb') as stream:
                shutil.copyfileobj(source,stream,1024*1024)
            if digest(target)!=expected:raise ValueError('Distribution file checksum mismatch: '+name)
    return metadata


@contextmanager
def presentation_server():
    from .server import Handler,Server
    server=Server(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:yield f'http://127.0.0.1:{server.server_port}'
    finally:server.shutdown();server.server_close()


def export_site(root, destination, archive_path=None):
    metadata=install_bundle(root,destination/'atlas',archive_path)
    # Retain the complete original event application under the same origin so
    # existing saved events continue to use the same browser storage.
    original=destination/'original';original.mkdir(exist_ok=True)
    original_html=(destination/'index.html').read_text(encoding='utf-8')
    (original/'index.html').write_text(original_html.replace('<head>','<head><base href="../">',1),encoding='utf-8')
    with presentation_server() as base:
        def source(path):
            with urlopen(base+path,timeout=30) as response:return response.read().decode('utf-8')
        page=source('/').replace('<base href="/app/">','<base href="./">')
        for before,after in [('/prototype/app.js','./atlas/event-app.js'),('/prototype/prototype.css','./atlas/prototype.css'),('/atlas/prototype.js','./atlas/presentation.js'),('/atlas/atlas.css','./atlas/atlas.css'),('/atlas/map-packages.js','./atlas/map-packages.js')]:
            page=page.replace('"'+before+'"','"'+after+'"')
        assets={'event-app.js':source('/prototype/app.js'),'presentation.js':source('/atlas/prototype.js'),
                'prototype.css':source('/prototype/prototype.css'),'atlas.css':source('/atlas/atlas.css'),
                'map-packages.js':source('/atlas/map-packages.js')}
    text=assets['presentation.js']
    text=text.replace('originalLink.href = "/original/"','originalLink.href = "./original/"')
    text=text.replace('$(".brand").href = "/"','$(".brand").href = "./"')
    text=text.replace('$(".skip-link").href = "/#selection"','$(".skip-link").href = "./#selection"')
    text=text.replace('"/?map=painted"','"./?map=painted"').replace('"/?map=baseline"','"./?map=baseline"')
    text=text.replace('Illustrationsprototyp · Lage vereinfacht. Die Kiesel zeigen Orte, keine bestätigten Eingänge.','Illustrierte Karte · Lage vereinfacht. Die Markierungen zeigen Orte, keine bestätigten Eingänge.')
    text=text.replace('Lokaler Designprototyp. Diese Browseradresse hat ihre eigene Merkliste; die veröffentlichte App bleibt unverändert.','Deine Merkliste bleibt in diesem Browser gespeichert.')
    assets['presentation.js']=text
    registry=f'maps/registry-{metadata["release"]}.json'
    text=assets['map-packages.js']
    needle='const assetURL=path=>`/atlas/${safePath(path)}`;'
    if text.count(needle)!=1:raise ValueError('Static atlas URL adapter needs updating')
    text=text.replace(needle,'const assetURL=path=>new URL(`atlas/${safePath(path)}`,document.baseURI).href;')
    assets['map-packages.js']=text.replace('json("maps/registry.json")',f'json("{registry}")')
    for name,text in assets.items():(destination/'atlas'/name).write_text(text,encoding='utf-8')
    maps={'default':'painted','maps':[{'id':'painted','title':'München · aktuelle Karte','manifest':f'releases/{metadata["release"]}/manifest.json'},
                                     {'id':'baseline','title':'München · Originalkarte','manifest':f'releases/{metadata["baseline"]}/manifest.json'}]}
    save(destination/'atlas'/registry,maps)
    save(destination/'atlas/deployment.json',metadata)
    def version(match):
        path=destination/match[2][2:]
        return match[1]+match[2]+'?v='+digest(path)[:12]+match[3] if path.is_file() else match[0]
    page=re.sub(r'((?:src|href)=")(\./[^"?]+)(")',version,page)
    (destination/'index.html').write_text(page,encoding='utf-8')
    return metadata
