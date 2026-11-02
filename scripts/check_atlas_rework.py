"""Inspect a complete unpublished atlas release at native zoom and on mobile."""
import argparse
from datetime import datetime
from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright
from src.map_pipeline.core import Workspace, digest, load, save
from src.map_pipeline.server import Handler, Server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release')
    args = parser.parse_args()
    workspace = Workspace()
    manifest = load(workspace.path(f'releases/{args.release}/manifest.json'))
    output = workspace.root / 'reports/rework-2026-11-02'
    output.mkdir(parents=True, exist_ok=True)
    pointer = load(workspace.root / 'current.json')
    integrity = load(workspace.root / 'app-integrity.json')
    changed = [p for p, h in integrity.items() if digest(workspace.root.parent / p) != h]
    assert not changed, changed
    workspace.inspect()
    server = Server(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    errors, missing = [], []
    positions, recommendations = [], []
    try:
        with sync_playwright() as playwright:
            options = {'headless': True}
            if not Path(playwright.chromium.executable_path).exists():
                options['executable_path'] = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
            browser = playwright.chromium.launch(**options)
            page = browser.new_page(viewport={'width':1448,'height':1086}, timezone_id='Europe/Berlin')
            page.clock.install(time=datetime.fromisoformat('2026-11-01T10:00:00+01:00'))
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('response', lambda response: missing.append(response.url) if response.status >= 400 and '/atlas/' in response.url else None)
            base = f'http://127.0.0.1:{server.server_port}'

            def ready():
                page.wait_for_function("window.__atlasReady && !__atlasTiles.isLoading() && document.querySelector('#event-map').dataset.artReady==='true'")

            for query, expected in [('map=baseline','baseline'), ('release='+args.release,'preview')]:
                page.goto(base+'/?'+query)
                ready()
                assert page.evaluate('__atlasState.id') == expected
                positions.append(page.evaluate("[{id:'museum',lat:48.1300409,lon:11.582909},{id:'riem',lat:48.128,lon:11.705}].map(RadarAtlas.position)"))
                recommendations.append(page.evaluate('__isarSelection.recommendations.map(e=>e.id)'))
            assert positions[0] == positions[1], 'Artwork changed geographic marker positions'
            assert recommendations[0] == recommendations[1], 'Artwork changed event recommendations'
            assert page.evaluate('__atlasConfig.frame.version') == manifest['frame']['version']
            assert page.evaluate('__atlasConfig.sourcePixelScale') == 1
            page.get_by_role('button', name='Karte pur', exact=True).click()
            page.get_by_role('button', name='München', exact=True).click()
            ready()
            page.screenshot(path=str(output/'browser-overview.png'))
            tiles = {t['id']: t for t in workspace.plan()['tiles']}
            for key in ('r04c08','r08c13','r09c12'):
                ox, oy = tiles[key]['renderOrigin']
                page.evaluate('point=>__atlasMap.setView(point,0,{animate:false})', [-oy-625,ox+625])
                ready()
                assert page.evaluate('__atlasMap.getZoom()') == 0
                assert page.locator('img.leaflet-tile-loaded').evaluate_all("images=>images.every(i=>i.naturalWidth===256 && i.getBoundingClientRect().width===256)")
                page.screenshot(path=str(output/f'browser-{key}.png'))
            page.set_viewport_size({'width':390,'height':844})
            page.wait_for_function("__atlasMap.getSize().x===document.querySelector('#event-map').clientWidth")
            page.get_by_role('button', name='München', exact=True).click()
            ready()
            page.screenshot(path=str(output/'browser-mobile.png'))
            camera=page.evaluate('({zoom:__atlasMap.getZoom(),minimum:__atlasMap.getMinZoom(),size:__atlasMap.getSize(),bounds:__atlasMap.getBounds(),world:__atlasConfig.worldBounds})')
            assert page.evaluate('__atlasMap.getBounds().contains(L.latLngBounds(__atlasConfig.worldBounds))'), 'Mobile overview clipped: '+str(camera)
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    assert not errors, errors
    assert not missing, missing
    assert load(workspace.root/'current.json') == pointer, 'Preview changed the live selection'
    save(output/'browser-check.json', {'status':'passed','release':args.release,
         'appFilesUnchanged':len(integrity),'markerProjectionUnchanged':True,
         'recommendationsUnchanged':True,'nativePixelsUnstretched':True,
         'desktopAndMobile':True,'pageErrors':errors,'missingAssets':missing})
    print('PASS: preview, native neighbors, desktop/mobile, event parity and 112 preserved application files.')


if __name__ == '__main__':
    main()
