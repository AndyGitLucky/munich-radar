"""Check the atlas in a real browser: local tiles, gestures, limits and app parity."""
import argparse
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import threading

from playwright.sync_api import expect, sync_playwright
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.map_pipeline.server import Handler, HERE, ROOT, Server

NOW="2026-11-01T10:00:00+01:00"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser",choices=["webkit","chromium"],default="webkit")
    parser.add_argument("--variant",choices=["painted","baseline"],default="painted")
    args=parser.parse_args()
    output_dir=ROOT/"atlas/reports/browser"
    output_dir.mkdir(parents=True,exist_ok=True)
    server=Server(("127.0.0.1",0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            options={"headless":True}
            if args.browser=="chromium" and not Path(p.chromium.executable_path).exists():
                options["executable_path"]=r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            browser=getattr(p,args.browser).launch(**options)
            context=browser.new_context(viewport={"width":1448,"height":1086},has_touch=True,timezone_id="Europe/Berlin",accept_downloads=True)
            page,baseline=context.new_page(),context.new_page()
            errors,external,missing_assets=[],[],[]
            for tab in (page,baseline):
                tab.clock.install(time=datetime.fromisoformat(NOW))
                tab.on("pageerror",lambda error:errors.append(str(error)))
            page.on("request",lambda request:external.append(request.url) if not request.url.startswith(("http://127.0.0.1:","data:")) else None)
            page.on("response",lambda response:missing_assets.append(response.url) if response.status>=400 and "/atlas/" in response.url else None)
            base=f"http://127.0.0.1:{server.server_port}"
            viewer=base+f"/?map={args.variant}"
            baseline.goto(base+"/original/")
            page.goto(viewer)
            page.wait_for_function("window.__atlasReady && document.querySelector('#event-map').dataset.artReady==='true'")
            page.wait_for_selector("#event-map[aria-busy=false]")
            baseline.wait_for_selector("#events[aria-busy=false]",state="attached")

            def parity():
                actual=page.evaluate("__isarSelection.recommendations.map(e=>e.id)")
                expected=baseline.locator("#events > .event-card [data-save-id]").evaluate_all("nodes=>nodes.map(n=>n.dataset.saveId)")
                assert actual==expected,"Recommendation selection changed"

            parity()
            assert page.evaluate("__atlasState.id")==args.variant,"Requested map package was not loaded"
            page.get_by_role("button",name="Innenstadt",exact=True).click()
            page.wait_for_function("!__atlasTiles.isLoading() && document.querySelector('#event-map').dataset.artReady==='true'")
            def screenshot(name):
                page.wait_for_function("!__atlasTiles.isLoading() && document.querySelector('#event-map').dataset.artReady==='true'")
                engine="" if args.browser=="webkit" else "-chromium"
                page.screenshot(path=str(output_dir/f"preview-{args.variant}{engine}-{name}.png"))
            assert page.evaluate("__atlasState.rotationEnabled===false && __atlasState.bearing===0")
            assert page.evaluate("__atlasConfig.tileKeys.length>100 && __atlasConfig.orientation==='north-up'")
            assert page.locator(".leaflet-tile-loaded").count()>0
            assert page.evaluate("__atlasConfig.sourcePixelScale===1 && __atlasMap.getZoom()===0 && __atlasConfig.tileFormat==='png'")
            assert page.evaluate("__atlasConfig.quality.maxChannelDifference===0 && __atlasConfig.quality.channelsCompared>15000000")
            assert page.evaluate("__atlasConfig.patchOrigin.every(Number.isInteger)")
            assert page.locator("img.leaflet-tile-loaded").evaluate_all("images=>images.every(i=>i.naturalWidth===256 && i.naturalHeight===256 && i.getBoundingClientRect().width===256 && i.getBoundingClientRect().height===256 && i.src.endsWith('.png'))"),"Native pixels stretched in browser"
            assert page.evaluate("document.querySelector('.leaflet-tile-pane').getBoundingClientRect().width>=0")
            page.evaluate("__atlasMap.setZoom(99,{animate:false})")
            assert page.evaluate("__atlasMap.getZoom()===__atlasMap.getMaxZoom()"),"Closest zoom not clamped"
            page.get_by_role("button",name="München",exact=True).click()
            assert page.evaluate("__atlasMap.getBounds().contains(L.latLngBounds(__atlasConfig.worldBounds))"),"City overview clipped"
            assert page.locator(".atlas-outside").is_visible() == page.evaluate("__atlasConfig.coverage!=='full-city'")
            screenshot("overview")
            page.get_by_role("button",name="Innenstadt",exact=True).click()

            if args.browser=="chromium":
                # Browser-level two-finger input exercises Leaflet's touch path;
                # tapping a button or calling setZoom would not verify pinch.
                client=context.new_cdp_session(page)
                cx,cy=1100,500
                client.send("Input.dispatchTouchEvent",{"type":"touchStart","touchPoints":[{"x":cx-120,"y":cy},{"x":cx+120,"y":cy}]})
                for distance in (100,80,60,40):
                    client.send("Input.dispatchTouchEvent",{"type":"touchMove","touchPoints":[{"x":cx-distance,"y":cy},{"x":cx+distance,"y":cy}]})
                    page.wait_for_timeout(30)
                client.send("Input.dispatchTouchEvent",{"type":"touchEnd","touchPoints":[]})
                page.wait_for_timeout(300)
                assert page.evaluate("__atlasMap.getZoom()<__atlasMap.getMaxZoom()"),"Two-finger pinch did not zoom out"
                page.get_by_role("button",name="Innenstadt",exact=True).click()
            assert page.evaluate("__atlasMap.getZoom()===__atlasMap.getMaxZoom()")
            before=page.evaluate("__atlasMap.getCenter()")
            box=page.locator("#event-map").bounding_box()
            x,y=box["width"]*.6,box["y"]+box["height"]*.8
            page.mouse.move(x,y);page.mouse.down();page.mouse.move(x-150,y+70,steps=12);page.mouse.up()
            page.wait_for_timeout(250)
            after=page.evaluate("__atlasMap.getCenter()")
            assert before!=after,"Mouse pan failed"
            point=page.evaluate("""()=>{
              const r=document.querySelector('#event-map').getBoundingClientRect();
              for(const fx of [.8,.7,.4,.6,.3])for(const fy of [.4,.3,.7,.85]){
                const x=r.x+r.width*fx,y=r.y+r.height*fy,e=document.elementFromPoint(x,y);
                if(e?.closest('#event-map')&&!e.closest('.leaflet-control'))return{x,y};
              }throw Error('No unobstructed map target');
            }""")
            page.mouse.move(point['x'],point['y']);page.mouse.wheel(0,500)
            page.wait_for_function("__atlasMap.getZoom()<__atlasMap.getMaxZoom()",timeout=5000)
            page.get_by_role("button",name="Innenstadt",exact=True).click()

            for view in ("tomorrow","weekend","upcoming","new","today"):
                page.locator(f"[data-view={view}]").click();baseline.locator(f"[data-view={view}]").click();parity()
            topics=page.locator("[data-topic]").evaluate_all("buttons=>buttons.map(b=>b.dataset.topic)")
            for topic in [t for t in topics if t!="all"]+["all"]:
                page.locator(f"[data-topic={topic}]").click();baseline.locator(f"[data-topic={topic}]").click();parity()
            page.get_by_role("button",name="Filter",exact=True).click()
            for kind in ("free","family","all"):
                page.locator(f"[data-filter={kind}]").click();baseline.locator(f"[data-filter={kind}]").click();parity()
            page.get_by_role("button",name="Fertig",exact=True).click()
            screenshot("desktop")
            page.get_by_role("button",name="Karte pur",exact=True).click()
            expect(page.locator(".prototype-labels")).not_to_be_visible()
            screenshot("artwork")
            page.get_by_role("button",name="Termine zeigen",exact=True).click()
            # Same atlas and anchors at every viewport; no horizontal/page scrolling.
            original=page.evaluate("__atlasConfig.patchOrigin")
            for width,height in ((390,844),(320,720),(430,932),(1024,768)):
                page.set_viewport_size({"width":width,"height":height})
                page.wait_for_function("w=>__atlasMap.getSize().x===w",arg=width)
                assert page.evaluate("document.documentElement.scrollWidth<=innerWidth && document.documentElement.scrollHeight<=innerHeight")
                assert page.evaluate("__atlasConfig.patchOrigin")==original
                rect=page.locator("#event-map").bounding_box()
                assert abs(rect["y"]+rect["height"]-height)<2 and rect["height"]>=height*.65
            page.set_viewport_size({"width":390,"height":844})
            page.wait_for_function("__atlasMap.getSize().x===390")
            page.get_by_role("button",name="Innenstadt",exact=True).click()
            screenshot("mobile")
            # Use controlled events to exercise known and unknown coordinates,
            # repeated venues, real downloads and local persistence deterministically.
            template=json.loads((ROOT/"data/events.json").read_text(encoding="utf-8"))[0]
            fixtures=[]
            for i,venue in enumerate(("Lenbachhaus","Deutsches Museum, Museumsinsel","Deutsches Museum, Museumsinsel","Ort noch unbekannt","Filmmuseum München")):
                event=copy.deepcopy(template)
                event.update(id=hashlib.sha256(f"atlas-{i}".encode()).hexdigest()[:20],title=f"Atlas Testveranstaltung {i}",
                    location_name=venue,start=NOW,end="2026-11-01T13:00:00+01:00",discovered_at=NOW,source_name=f"Quelle {i}",series_id=str(i),
                    relevance_score=100-i,status="scheduled",tags=[],is_free=True,family_friendly=True)
                fixtures.append(event)
            page.route("**/data/events.json",lambda route:route.fulfill(json=fixtures))
            page.goto(viewer);page.wait_for_selector("#event-map[aria-busy=false]")
            assert page.locator("#event-map").get_attribute("data-event-count")=="4"
            assert page.locator("#event-map").get_attribute("data-place-count")=="3"
            label=page.locator(".prototype-label[data-place=museum]")
            label.tap();expect(page.locator("#prototype-detail")).to_be_visible()
            assert page.locator("#prototype-detail .event-card").count()==2
            save=page.locator("#prototype-detail [data-save-id]").first
            save.tap();expect(save).to_have_attribute("aria-pressed","true")
            with page.expect_download() as download:
                page.locator("#prototype-detail [data-gpx-id]").first.tap()
            assert download.value.suggested_filename.endswith(".gpx")
            gpx=Path(download.value.path()).read_text(encoding="utf-8")
            assert "48.1300409" in gpx and "11.582909" in gpx,"Export leaked illustration coordinates"
            with page.expect_download() as download:
                page.locator("#prototype-detail [data-calendar-id]").first.tap()
                if page.locator("#calendar-dialog").is_visible():page.locator("#calendar-whole").tap()
            assert download.value.suggested_filename.endswith(".ics")
            screenshot("detail")
            page.locator("#prototype-detail .sheet-close").tap()
            page.locator(".prototype-label[data-place=missing]").tap()
            expect(page.locator("#prototype-detail [data-gpx-id]")).to_be_disabled()
            page.locator("#prototype-detail .sheet-close").tap()
            screenshot("fixture")
            page.reload();page.wait_for_selector("#event-map[aria-busy=false]")
            expect(page.locator("#saved-count")).to_have_text("1")
            # Shared illustration anchors move with the map, independently of text.
            page.evaluate("__atlasMap.setZoom(0,{animate:false}); __atlasMap.panTo(RadarAtlas.position({id:'museum',lat:48.1300409,lon:11.582909}),{animate:false})")
            page.wait_for_timeout(60)
            wire=page.locator(".prototype-wire").first.get_attribute("d")
            page.evaluate("__atlasMap.panBy([90,0],{animate:false})")
            page.wait_for_timeout(60)
            assert page.locator(".prototype-wire").first.get_attribute("d")!=wire
            page.route("**/data/events.json",lambda route:route.fulfill(json=[]))
            page.reload();page.wait_for_selector("#event-map[aria-busy=false]")
            expect(page.locator(".prototype-state")).to_be_visible()
            assert not errors,errors
            assert not external,external
            assert not missing_assets,missing_assets
            browser.close()
            print(f"PASS ({args.browser}, {args.variant}): native-size lossless tiles; pan/wheel; zoom cap; complete city overview; fixed orientation; responsive anchors/tethers; recommendation parity; saved events; ICS/GPX; unknown venues; empty state.",flush=True)
    finally:
        server.shutdown();server.server_close()


if __name__=="__main__":
    main()
