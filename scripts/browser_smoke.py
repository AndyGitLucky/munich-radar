"""Offline browser checks against a temporary local server and the checked-in data."""
import json
import os
import threading
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.build import build


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    directory=build(ROOT)
    metadata=json.loads((directory/"data/metadata.json").read_text(encoding="utf-8"))
    handler=partial(QuietHandler,directory=str(directory))
    with ThreadingHTTPServer(("127.0.0.1",0),handler) as server:
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                options={"headless":True}
                if os.environ.get("RADAR_BROWSER_PATH"):
                    options["executable_path"]=os.environ["RADAR_BROWSER_PATH"]
                browser=p.chromium.launch(**options)
                page=browser.new_page(viewport={"width":1440,"height":1100},timezone_id="America/New_York")
                errors=[];page.on("pageerror",lambda error:errors.append(str(error)))
                # Browser location must not affect Munich's date calculations.
                page.clock.install(time=datetime.fromisoformat(metadata["last_updated"]))
                base=f"http://127.0.0.1:{server.server_port}"
                page.goto(base)
                page.wait_for_selector("#events[aria-busy=false]")
                assert page.locator(".source-list li").count()==metadata["sources_checked"]
                for view, ids in metadata["views"].items():
                    page.locator(f'[data-view="{view}"]').click()
                    assert page.locator(".event-card").count()==len(ids),(view,ids)
                page.locator('[data-view="today"]').click()
                page.locator('[data-filter="free"]').click()
                for card in page.locator(".event-card").all():
                    assert "Kostenlos" in card.locator(".event-facts").inner_text()
                page.locator('[data-filter="family"]').click()
                for card in page.locator(".event-card").all():
                    assert "Für Familien" in card.inner_text()
                page.locator('[data-filter="all"]').click()
                page.clock.run_for(350)
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                screenshots=ROOT/".scratch";screenshots.mkdir(exist_ok=True)
                page.screenshot(path=str(screenshots/"desktop.png"),full_page=True)
                page.set_viewport_size({"width":390,"height":844})
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                page.screenshot(path=str(screenshots/"mobile.png"),full_page=True)
                page.set_viewport_size({"width":320,"height":700})
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                page.locator(".about summary").click()
                assert page.locator(".about").get_attribute("open") is not None
                assert not errors,errors
                # Source text must never become executable markup in the frontend.
                payload=json.loads((directory/"data/events.json").read_text(encoding="utf-8"))
                for event in payload:
                    event["title"]='<img src=x onerror="window.injected=true">'
                    event["source_url"]="javascript:window.injected=true"
                page.route("**/data/events.json",lambda route:route.fulfill(json=payload))
                page.reload();page.wait_for_selector("#events[aria-busy=false]")
                assert page.locator(".event-card img").count()==0
                assert page.evaluate("window.injected") is None
                assert page.locator('a[href^="javascript:"]').count()==0
                # Network failure is recoverable, with no endless loading message.
                page.unroute("**/data/events.json")
                page.route("**/data/events.json",lambda route:route.fulfill(status=503,body="Unavailable"))
                page.reload();page.wait_for_selector("#events[aria-busy=false]")
                assert page.get_by_role("button",name="Erneut versuchen").is_visible()
                page.unroute("**/data/events.json")
                page.get_by_role("button",name="Erneut versuchen").click()
                page.wait_for_selector(".source-list li")
                page.wait_for_selector(".event-card")
                browser.close()
                print("Browser checks passed: five views, filters, Berlin timezone, desktop/mobile, unsafe source text, fetch failure/retry.")
        finally:
            server.shutdown()


if __name__=="__main__":
    main()
