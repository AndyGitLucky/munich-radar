"""Local atlas viewer over the existing event application and immutable releases."""
from http.server import ThreadingHTTPServer
import importlib.util
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit
from .core import ATLAS,ROOT,Workspace,load

HERE=ATLAS
VIEWER=ATLAS/'viewer'
spec=importlib.util.spec_from_file_location('radar_atlas_app_server',VIEWER/'app_server.py')
app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)


class Server(ThreadingHTTPServer):allow_reuse_address=False


class Handler(app.Handler):
    def json(self,value):
        import json
        return self.send_bytes(json.dumps(value,ensure_ascii=False).encode(),'application/json; charset=utf-8')

    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/':
            source=(ROOT/'web/index.html').read_text(encoding='utf-8')
            source=source.replace('<head>','<head><base href="/app/">',1)
            source=source.replace('src="./app.js"','src="/prototype/app.js"')
            source=source.replace('</head>','<link rel="stylesheet" href="/prototype/prototype.css"><link rel="stylesheet" href="/atlas/atlas.css"><script src="/atlas/map-packages.js" defer></script><script src="/atlas/prototype.js" defer></script></head>')
            return self.send_bytes(source.encode(),'text/html; charset=utf-8')
        if path=='/atlas/maps/registry.json':
            return self.json({'default':'painted','maps':[{'id':'painted','title':'München · aktuelle Karte','manifest':'maps/painted/manifest.json'},
                {'id':'baseline','title':'München · Originalkarte','manifest':'maps/baseline/manifest.json'}]})
        if path in ['/atlas/maps/painted/manifest.json','/atlas/maps/baseline/manifest.json']:
            pointer=ATLAS/('baseline-release.json' if '/baseline/' in path else 'current.json')
            if not pointer.is_file():return self.send_error(503,'Build a verified atlas release first')
            release=load(pointer)['release'];candidate=Workspace().path('releases/'+release+'/manifest.json')
            return self.send_bytes(candidate.read_bytes(),'application/json')
        if path=='/atlas/prototype.js':
            source=(VIEWER/'prototype-base.js').read_text(encoding='utf-8')
            source=source.replace('  // ATLAS_PRESENTATION\n',(VIEWER/'presentation.js').read_text(encoding='utf-8'))
            source=source.replace('"Ausschnitt", "prototype-map-button"','"Innenstadt", "prototype-map-button"').replace('"Alle Orte", "prototype-map-button"','"München", "prototype-map-button"')
            source=source.replace('"Entwurf · Lage vereinfacht"','"München · illustriert · Lage vereinfacht"')
            source=source.replace('wires.replaceChildren();\n    const mobile','wires.replaceChildren();\n    window.RadarAtlas.sync();\n    const mobile')
            source=source.replace('const w=item.el.offsetWidth,h=item.el.offsetHeight;','item.el.hidden = Boolean(item.group.place) && (p.x < -20 || p.y < -20 || p.x > r.width+20 || p.y > r.height+20);\nconst w=item.el.offsetWidth,h=item.el.offsetHeight;')
            source=source.replace('} else for (const {el} of labelItems) {el.style.removeProperty("left");el.style.removeProperty("top");}','} else for (const {el} of labelItems) {el.hidden=false;el.style.removeProperty("left");el.style.removeProperty("top");}')
            source=source.replace('if (!group.place) continue;','if (!group.place || el.hidden) continue;')
            source=source.replace('const p=map.latLngToContainerPoint(position(group.place));\n      const sx=','const p=map.latLngToContainerPoint(position(group.place));\n      if(p.x < 0 || p.y < 0 || p.x > r.width || p.y > r.height) continue;\n      const sx=')
            return self.send_bytes(source.encode(),'text/javascript; charset=utf-8')
        if path=='/atlas/places.json':return self.send_bytes((ROOT/'config/places.json').read_bytes(),'application/json')
        if path.startswith('/atlas/'):
            relative=path.removeprefix('/atlas/')
            if relative in ['atlas.css','map-packages.js']:candidate=VIEWER/relative
            else:
                try:candidate=Workspace().path(relative)
                except ValueError:return self.send_error(404)
            if candidate.is_dir():candidate=candidate/'index.html'
            if candidate.is_file():return self.send_bytes(candidate.read_bytes(),mimetypes.guess_type(candidate)[0] or 'application/octet-stream')
            return self.send_error(404)
        return super().do_GET()


def serve(port=8015):
    with Server(('127.0.0.1',port),Handler) as server:
        print(f'München Atlas: http://127.0.0.1:{port}/',flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
