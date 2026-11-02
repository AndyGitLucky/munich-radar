"""Verify the published static atlas under a GitHub Pages project subpath."""
import argparse
from contextlib import contextmanager
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import sys
import threading

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright
from src.map_pipeline.core import load,save


@contextmanager
def endpoint(directory,url):
    if url:
        yield url.rstrip('/')+'/'
        return
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if not self.path.startswith('/munich-radar/'):
                return self.send_error(404,'Project subpath required')
            self.path=self.path[len('/munich-radar'):]
            super().do_GET()
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(directory)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:yield f'http://127.0.0.1:{server.server_port}/munich-radar/'
    finally:server.shutdown();server.server_close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=Path('dist'))
    parser.add_argument('--browser',choices=('chromium','webkit'),default='chromium')
    parser.add_argument('--url')
    args=parser.parse_args()
    expected=load(args.directory/'atlas/deployment.json')
    data=load(args.directory/'data/metadata.json')
    output=Path('.scratch/public-atlas');output.mkdir(parents=True,exist_ok=True)
    errors=[];missing=[]
    with endpoint(args.directory,args.url) as base,sync_playwright() as playwright:
        options={'headless':True}
        engine=getattr(playwright,args.browser)
        if args.browser=='chromium' and not Path(engine.executable_path).exists():
            options['executable_path']=r'C:\Program Files\Google\Chrome\Application\chrome.exe'
        browser=engine.launch(**options)
        context=browser.new_context(viewport={'width':1448,'height':1086},has_touch=True,timezone_id='Europe/Berlin')
        page=context.new_page();page.clock.install(time=datetime.fromisoformat(data['last_updated']))
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('response',lambda r:missing.append({'url':r.url,'status':r.status}) if r.status>=400 and r.url.startswith(base) else None)

        def ready():
            page.wait_for_function("window.__atlasReady && !__atlasTiles.isLoading() && document.querySelector('#event-map').dataset.artReady==='true'")

        page.goto(base+'original/')
        page.wait_for_selector('#events[aria-busy=false]',state='attached')
        recommendations=page.locator('#events > .event-card [data-save-id]').evaluate_all('nodes=>nodes.map(n=>n.dataset.saveId)')
        page.goto(base+'?v='+expected['release']);ready()
        assert page.evaluate('__atlasState.id')=='painted','Public page silently fell back to another map'
        assert page.evaluate('__atlasConfig.tileBase')==f'releases/{expected["release"]}/tiles'
        assert page.evaluate('__atlasConfig.frame.version')=='clouds-02'
        assert page.evaluate('__isarSelection.recommendations.map(e=>e.id)')==recommendations
        assert page.evaluate('__atlasConfig.quality.cloudFrame.rectangularOpaque')
        assert page.evaluate('__atlasConfig.quality.cloudFrame.cityMaxChannelDifference')==0
        page.get_by_role('button',name='Innenstadt',exact=True).click();ready()
        assert page.evaluate('__atlasMap.getZoom()')==0
        assert page.locator('img.leaflet-tile-loaded').evaluate_all('nodes=>nodes.every(i=>i.naturalWidth===256 && i.getBoundingClientRect().width===256)')
        page.screenshot(path=str(output/f'{args.browser}-desktop.png'))
        for width in (390,320):
            page.set_viewport_size({'width':width,'height':844})
            page.wait_for_function("__atlasMap.getSize().x===document.querySelector('#event-map').clientWidth")
            page.get_by_role('button',name='München',exact=True).click();ready()
            assert page.evaluate('__atlasMap.getBounds().contains(L.latLngBounds(__atlasConfig.worldBounds))')
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            page.screenshot(path=str(output/f'{args.browser}-mobile-{width}.png'))
        page.get_by_role('button',name='Info',exact=True).click()
        page.locator('#atlas-package-select').select_option('baseline')
        page.wait_for_function("__atlasState.id==='baseline'");ready()
        page.locator('#atlas-package-select').select_option('painted')
        page.wait_for_function("__atlasState.id==='painted'");ready()
        page.goto(base+'atlas/reports/rework-2026-11-02/')
        assert page.locator('h1').inner_text()=='München · rechteckige Karte mit gemaltem Wolkenrand'
        assert not page.locator('body').evaluate("node=>/[A-Za-z]\\?[A-Za-z]|\\ufffd/.test(node.innerText)")
        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
        assert not errors,errors
        assert not missing,missing
        browser.close()
    save(output/f'{args.browser}-checks.json',{'status':'passed','url':args.url,'release':expected['release'],
         'projectSubpath':True,'originalEventViewAndRecommendations':True,'nativeTiles':True,
         'mobileWidths':[390,320],'originalAndCurrentMaps':True,'reviewTextUtf8':True,'errors':errors,'missing':missing})
    print(f'PASS ({args.browser}): public atlas, project subpath, mobile overview, native tiles, original view, recommendations, map switch and UTF-8 report.')


if __name__=='__main__':main()
