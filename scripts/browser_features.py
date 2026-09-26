"""Offline integration checks: personal bookmarks, ICS, maps, and mobile performance.

OSM tiles are mocked: automated tests must never pan/zoom against community tile servers.
"""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from datetime import datetime
from functools import partial
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer
import shutil
import time
import xml.etree.ElementTree as ET

from playwright.sync_api import sync_playwright

from browser_smoke import ROOT, QuietHandler
from src.build import build


TILE = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9Y0AAAAASUVORK5CYII=")
NOW = "2026-09-25T12:00:00+02:00"


def fixtures():
    original = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))[0]
    locations = ["Haus der Kunst", "Gasteig HP8", "Alte Pinakothek", "Münchner Theater für Kinder", "Ort noch unbekannt"]
    events = []
    for index in range(40):
        event = copy.deepcopy(original)
        event.update(id=hashlib.sha256(str(index).encode()).hexdigest()[:20], title=f"Kartentest {index:02d}",
                     start=NOW, end="2026-09-25T14:00:00+02:00", all_day=False,
                     source_name=f"Quelle {index % 5}", source_url=f"https://example.org/event/{index}",
                     location_name=locations[index % len(locations)], address=None,
                     relevance_score=100-index*3, series_id=str(index), is_free=index % 2 == 0,
                     family_friendly=index % 3 == 0, tags=[], status="scheduled", stale=False,
                     discovered_at=NOW, updated_at=NOW, relevance_reasons=["Testtermin"])
        events.append(event)
    metadata = json.loads((ROOT / "data/metadata.json").read_text(encoding="utf-8"))
    metadata.update(last_updated=NOW, heads_up=[])
    return events, metadata


def launch(p):
    name = os.environ.get("RADAR_BROWSER", "chromium")
    options = {"headless": True}
    if name == "chromium" and os.environ.get("RADAR_BROWSER_PATH"):
        options["executable_path"] = os.environ["RADAR_BROWSER_PATH"]
    return getattr(p, name).launch(**options)


def configure(page, events, metadata):
    page.clock.install(time=datetime.fromisoformat(NOW))
    page.route("**/data/events.json", lambda route: route.fulfill(json=events))
    page.route("**/data/metadata.json", lambda route: route.fulfill(json=metadata))
    page.route("https://tile.openstreetmap.org/**", lambda route: route.fulfill(body=TILE, content_type="image/png"))


def settled(page):
    page.wait_for_selector("#events[aria-busy=false]", state="attached")


def main():
    built = build(ROOT)
    events, metadata = fixtures()
    with tempfile.TemporaryDirectory() as tmp:
        # Verify relative paths under the same project prefix as GitHub Pages.
        shutil.copytree(built, Path(tmp) / "munich-radar")
        handler = partial(QuietHandler, directory=tmp)
        with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{server.server_port}/munich-radar/"
            try:
                with sync_playwright() as p:
                    browser = launch(p)
                    context = browser.new_context(viewport={"width":390,"height":844}, timezone_id="America/New_York", has_touch=True)
                    page = context.new_page()
                    configure(page,events,metadata)
                    errors, requests = [], []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.on("request", lambda request: requests.append(request.url))
                    page.goto(base); settled(page)
                    assert page.locator(".event-card").count() == 5
                    # Routes use named venues/addresses, never overview-map coordinates.
                    target = page.evaluate("() => RadarMap.directions({location_name:'Olympiahalle',address:'Spiridon-Louis-Ring 21, 80809 München'})")
                    parsed = urlparse(target['url']); params = parse_qs(parsed.query)
                    assert parsed.path == '/maps/dir/' and params['travelmode'] == ['transit']
                    assert params['destination'] == ['Olympiahalle, Spiridon-Louis-Ring 21, 80809 München']
                    park = page.evaluate("() => RadarMap.directions({location_name:'Olympiapark München'})")
                    assert park['approximate'] and urlparse(park['url']).path == '/maps/search/'
                    assert parse_qs(urlparse(park['url']).query)['query'] == ['Olympiapark München']
                    unknown = page.evaluate("() => RadarMap.directions({location_name:'Verschiedene Orte'})")
                    assert unknown is None
                    assert not any("vendor/" in url or "tile.openstreetmap.org" in url for url in requests)
                    page.locator(".event-card [data-save-id]").nth(0).click()
                    page.locator(".event-card [data-save-id]").nth(1).click()
                    assert page.locator("#saved-count").inner_text() == "2"
                    page.reload(); settled(page)
                    assert page.locator("#saved-count").inner_text() == "2"
                    page.locator('[data-view="saved"]').click()
                    assert page.locator(".event-card").count() == 2
                    # Actual download, not just a helper return value.
                    with page.expect_download() as download:
                        page.locator(".event-card [data-calendar-id]").first.click()
                    calendar_bytes = Path(download.value.path()).read_bytes()
                    assert b"DTSTART:20260925T100000Z\r\n" in calendar_bytes
                    assert b"DTEND:20260925T120000Z\r\n" in calendar_bytes
                    assert b"BEGIN:VALARM" not in calendar_bytes
                    assert download.value.suggested_filename.endswith(".ics")
                    assert b"TRANSP:TRANSPARENT" in calendar_bytes
                    with page.expect_download() as gpx_download:
                        page.locator(".event-card [data-gpx-id]").first.click()
                    assert gpx_download.value.suggested_filename.endswith('.gpx')
                    root = ET.fromstring(Path(gpx_download.value.path()).read_bytes())
                    ns = {'g':'http://www.topografix.com/GPX/1/1'}
                    point = root.find('g:wpt',ns)
                    assert root.attrib['version'] == '1.1' and point is not None
                    assert 47 < float(point.attrib['lat']) < 49.5
                    assert 10 < float(point.attrib['lon']) < 13
                    assert 'Haus der Kunst' in point.find('g:name',ns).text
                    assert root.find('g:trk',ns) is None
                    special = dict(events[0],title='Musik & Kunst <Live> "München"')
                    xml = page.evaluate("e => RadarPersonal.gpx(e, RadarMap.locate(e))",special)
                    assert special['title'] in ET.fromstring(xml).find('g:wpt/g:name',ns).text
                    park_event = dict(events[0],location_name='Olympiapark München')
                    xml = page.evaluate("e => RadarPersonal.gpx(e, RadarMap.locate(e))",park_event)
                    assert 'Ungefährer Bereich' in ET.fromstring(xml).find('g:wpt/g:desc',ns).text

                    # Each visitor has a separate device-local collection.
                    other = browser.new_context(viewport={"width":390,"height":844})
                    other_page = other.new_page(); configure(other_page,events,metadata)
                    other_page.goto(base); settled(other_page)
                    assert other_page.locator("#saved-count").inner_text() == "0"
                    other.close()
                    # Same-browser tabs receive removal updates without reloading.
                    tab = context.new_page(); configure(tab,events,metadata)
                    tab.goto(base); settled(tab)
                    page.locator(".event-card [data-save-id]").first.click()
                    tab.wait_for_function("document.querySelector('#saved-count').textContent === '1'")
                    tab.close()

                    # Saved snapshots survive a term falling out of the current dataset.
                    page.unroute("**/data/events.json")
                    page.route("**/data/events.json", lambda route: route.fulfill(json=events[2:]))
                    page.reload(); settled(page); page.locator('[data-view="saved"]').click()
                    assert page.locator(".event-card").count() == 1
                    assert "Nicht im aktuellen Datenstand" in page.locator(".event-card").inner_text()
                    page.unroute("**/data/events.json")
                    page.route("**/data/events.json", lambda route: route.fulfill(json=events))
                    page.reload(); settled(page)

                    # Map includes low-ranked events beyond the five recommendations.
                    page.locator('[data-display="map"]').click()
                    page.wait_for_selector('#event-map[aria-busy="false"]')
                    assert page.locator("#event-map").get_attribute("data-event-count") == "32"
                    assert page.locator("#event-map").get_attribute("data-place-count") == "4"
                    assert "40 Termine" in page.locator("#selection-count").inner_text()
                    assert "8 Termine" in page.locator("#map-missing-title").inner_text()
                    assert page.locator('#map-missing-events [data-gpx-id]:disabled').count() == 8
                    assert page.locator('.leaflet-control-attribution a[href*="openstreetmap.org"]').is_visible()
                    page.locator('[data-filter="free"]').click()
                    page.wait_for_function("document.querySelector('#event-map').dataset.eventCount === '16'")
                    assert "20 Termine" in page.locator("#selection-count").inner_text()
                    page.locator('[data-filter="all"]').click()
                    page.locator("#map-saved-only").check()
                    page.wait_for_function("document.querySelector('#event-map').dataset.eventCount === '1'")
                    marker = page.locator(".radar-marker").first
                    marker.click()
                    assert page.locator(".leaflet-popup .map-event").count() == 1
                    route = page.locator('.leaflet-popup a[href*="google.com/maps/dir/"]').get_attribute("href")
                    assert "travelmode=transit" in route and "destination=" in route
                    assert parse_qs(urlparse(route).query)['destination'] == ['Gasteig HP8, München']
                    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                    page.set_viewport_size({"width":320,"height":700})
                    page.clock.run_for(500)
                    page.wait_for_function("""() => {
                        const close = document.querySelector('.leaflet-popup-close-button').getBoundingClientRect();
                        const map = document.querySelector('#event-map').getBoundingClientRect();
                        return close.left >= map.left && close.right <= map.right;
                    }""")
                    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                    page.locator(".leaflet-popup-close-button").click()
                    page.locator("#map-saved-only").uncheck()
                    page.wait_for_function("document.querySelector('#event-map').dataset.eventCount === '32'")
                    page.set_viewport_size({"width":390,"height":844})
                    page.clock.run_for(350)
                    screenshots = ROOT / ".scratch"; screenshots.mkdir(exist_ok=True)
                    page.screenshot(path=str(screenshots / "map-mobile.png"), full_page=True)

                    # Multi-day events default to a chosen visit day instead of a long calendar block.
                    long_event = dict(events[0], id="a"*20, title="Lange Ausstellung",
                                      start="2026-09-01T00:00:00+02:00",end="2026-11-01T23:59:59+01:00",all_day=True)
                    page.evaluate("event => RadarPersonal.toggle(event)",long_event)
                    page.locator('[data-display="list"]').click(); page.locator('[data-view="saved"]').click()
                    page.locator('[data-calendar-id="'+"a"*20+'"]').click()
                    assert page.locator("#calendar-dialog").is_visible()
                    page.locator("#calendar-day").fill("2026-10-25")
                    with page.expect_download() as download:
                        page.get_by_role("button",name="Besuchstag übernehmen",exact=True).click()
                    result = Path(download.value.path()).read_text(encoding="utf-8")
                    assert "DTSTART;VALUE=DATE:20261025" in result and "DTEND;VALUE=DATE:20261026" in result
                    assert "DTEND;VALUE=DATE:20261102" not in result

                    # iCalendar escaping, UTF-8 folding, timezone changes and inclusive date ranges.
                    tricky = dict(events[0],title="Äpfel 🥨; Komma, \\ Zeile\nBEGIN:VEVENT\n"*5,
                                  description="Test\r\nATTENDEE:injected@example.org",source_url="javascript:alert(1)",
                                  start="2026-10-25T02:30:00+02:00",end="2026-10-25T02:30:00+01:00")
                    raw = page.evaluate("event => RadarPersonal.calendar(event)",tricky)
                    unfolded = raw.replace("\r\n ","")
                    assert "DTSTART:20261025T003000Z\r\n" in unfolded
                    assert "DTEND:20261025T013000Z\r\n" in unfolded
                    assert all(len(line.encode("utf-8")) <= 75 for line in raw.split("\r\n"))
                    assert "\r\nATTENDEE:" not in unfolded and "\r\nURL:" not in unfolded
                    assert unfolded.split("\r\n").count("BEGIN:VEVENT") == 1
                    assert r"\; Komma\, \\ Zeile\nBEGIN:VEVENT\n" in unfolded
                    single = dict(events[0],all_day=True,start="2026-12-31T00:00:00+01:00",end="2026-12-31T23:59:59+01:00")
                    result = page.evaluate("event => RadarPersonal.calendar(event)",single)
                    assert "DTEND;VALUE=DATE:20270101" in result
                    exclusive = dict(single,end="2027-01-01T00:00:00+01:00")
                    assert "DTEND;VALUE=DATE:20270101" in page.evaluate("event => RadarPersonal.calendar(event)",exclusive)
                    unknown_end = dict(events[0],end=None)
                    assert "DTEND" not in page.evaluate("event => RadarPersonal.calendar(event)",unknown_end)
                    assert not errors,errors

                    # Thousands of events still produce one marker per venue, not thousands of DOM cards.
                    large = [dict(events[i%40],id=hashlib.sha256(f'large-{i}'.encode()).hexdigest()[:20]) for i in range(2000)]
                    page.unroute("**/data/events.json")
                    page.route("**/data/events.json", lambda route: route.fulfill(json=large))
                    page.reload(); settled(page)
                    started = time.perf_counter()
                    page.locator('[data-display="map"]').click()
                    page.wait_for_function("document.querySelector('#event-map').dataset.eventCount === '1600'")
                    elapsed = time.perf_counter()-started
                    assert elapsed < 10,elapsed
                    assert page.locator("#event-map").get_attribute("data-place-count") == "4"
                    print(f"Map with 2,000 events: {elapsed:.2f}s (mock tiles, four venues, 400 explicitly unmapped).")

                    # Blocked storage must not break reading, mapping or session-only bookmarks.
                    blocked = browser.new_context()
                    blocked.add_init_script("Storage.prototype.setItem = function(){throw new DOMException('quota','QuotaExceededError')}")
                    blocked_page=blocked.new_page();configure(blocked_page,events,metadata)
                    blocked_page.goto(base);settled(blocked_page)
                    blocked_page.locator(".event-card [data-save-id]").first.click()
                    assert "nur in dieser Sitzung" in blocked_page.locator("#personal-status").inner_text()
                    blocked_page.locator('[data-view="saved"]').click()
                    assert blocked_page.locator(".event-card").count() == 1
                    blocked.close()

                    # Missing map assets have an explicit retry; lists stay usable.
                    failed = browser.new_context(); fail_page = failed.new_page(); configure(fail_page,events,metadata)
                    fail_page.route("**/vendor/leaflet/leaflet.js",lambda route:route.fulfill(status=503,body="Unavailable"))
                    fail_page.goto(base);settled(fail_page);fail_page.locator('[data-display="map"]').click()
                    fail_page.get_by_role("button",name="Karte erneut laden").wait_for()
                    fail_page.unroute("**/vendor/leaflet/leaflet.js")
                    fail_page.get_by_role("button",name="Karte erneut laden").click()
                    fail_page.wait_for_function("document.querySelector('#event-map').dataset.eventCount === '32'")
                    failed.close()
                    browser.close()
                    print("Feature checks passed: bookmarks, isolation, persistence, missing events, ICS, all-results map, mobile, failures.")
            finally:
                server.shutdown()


if __name__ == "__main__":
    main()
