"""Inspect an unpublished section in its actual viewer image space and neighbors."""
import argparse
from datetime import datetime
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright
from src.map_pipeline.core import Workspace,load,save


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8015);args=parser.parse_args()
    workspace=Workspace();request=load(workspace.candidate('r03c05','shape-01')/'request.json')
    tile=next(t for t in workspace.plan()['tiles'] if t['id']=='r03c05');ox,oy=tile['renderOrigin']
    folder=workspace.root/'reports/browser';folder.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        options={}
        if not Path(p.chromium.executable_path).exists():options['executable_path']=r'C:\Program Files\Google\Chrome\Application\chrome.exe'
        browser=p.chromium.launch(**options);page=browser.new_page(viewport={'width':1448,'height':1086})
        page.clock.install(time=datetime.fromisoformat('2026-11-01T10:00:00+01:00'))
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        positions=[];recommendations=[]
        for name,query,expected in [('before','map=baseline','baseline'),('after','release='+request['previewRelease'],'preview')]:
            page.goto(f'http://127.0.0.1:{args.port}/?{query}')
            page.wait_for_function("window.__atlasReady && !__atlasTiles.isLoading()")
            assert page.evaluate('__atlasState.id')==expected
            positions.append(page.evaluate("RadarAtlas.position({id:'museum',lat:48.1300409,lon:11.582909})"))
            recommendations.append(page.evaluate('__isarSelection.recommendations.map(e=>e.id)'))
            page.get_by_role('button',name='Karte pur',exact=True).click()
            page.evaluate('p=>__atlasMap.setView(p,0,{animate:false})',[-oy-450,ox+410])
            page.wait_for_function('!__atlasTiles.isLoading()')
            page.screenshot(path=str(folder/f'example-{name}.png'))
        assert positions[0]==positions[1],'Section version changed event projection'
        assert recommendations[0]==recommendations[1],'Section version changed recommendations'
        assert not errors,errors
        page.goto(f'http://127.0.0.1:{args.port}/atlas/candidates/r03c05/shape-01/')
        assert page.locator('main img').count()==5
        page.locator('main img').evaluate_all('images=>Promise.all(images.map(i=>i.decode()))')
        page.screenshot(path=str(folder/'example-review.png'),full_page=True)
        browser.close()
    save(workspace.root/'reports/viewer-example.json',{'status':'passed','projectionUnchanged':True,'recommendationsUnchanged':True,'images':['browser/example-before.png','browser/example-after.png','browser/example-review.png']})
    print('PASS: original and unpublished candidate in the same native viewer; identical event projection/ranking; review images load.')


if __name__=='__main__':main()
