"""Exercise temporary occasions independently of permanent interests and device time zone."""
import copy
import hashlib
import threading
from datetime import datetime
from functools import partial
from http.server import ThreadingHTTPServer

import yaml
from playwright.sync_api import sync_playwright

from browser_features import ROOT, TILE, QuietHandler, fixtures, launch, settled
from src.build import build


def main():
    originals, metadata = fixtures()
    config = yaml.safe_load((ROOT / "config/relevance.yaml").read_text(encoding="utf-8"))
    metadata.update(occasions=config["occasions"], interests=[
        {"id": "science", "label": "Wissenschaft", "points": 20},
        {"id": "concert", "label": "Musik", "points": 6}],
        last_updated="2026-10-31T12:00:00+01:00")
    metadata["selection"]["occasion_slots"] = 2
    events = []
    for i in range(8):
        event = copy.deepcopy(originals[i])
        event.update(title=f"Wissenschaft {i}", category="science", tags=["science"],
                     start="2026-10-31T16:00:00+01:00", end="2026-10-31T17:00:00+01:00",
                     relevance_score=90-i, source_name=f"Quelle {i}", series_id=str(i), is_free=True,
                     discovered_at="2026-10-31T10:00:00+01:00", relevance_reasons=["Dein Schwerpunkt: Wissenschaft"])
        events.append(event)
    for i in range(2):
        events[i].update(title=f"Halloween Party {i}", category="culture", tags=["nightlife"],
                         relevance_score=10+i, is_free=None, family_friendly=None, source_name="Club",
                         start="2026-10-31T21:00:00+01:00", end="2026-11-01T02:00:00+01:00")
    # More than five matches from one source must all be reachable via the banner.
    for i in range(4):
        event = copy.deepcopy(events[0])
        event.update(id=hashlib.sha256(f"extra-halloween-{i}".encode()).hexdigest()[:20], title=f"Halloween Extra {i}", series_id=f"extra-{i}")
        events.append(event)
    tomorrow = copy.deepcopy(events[0])
    tomorrow.update(id=hashlib.sha256(b"halloween-tomorrow").hexdigest()[:20], title="Halloween morgen", series_id="tomorrow",
                    start="2026-11-01T21:00:00+01:00", end="2026-11-01T23:00:00+01:00")
    events.append(tomorrow)
    events[2].update(title="Weihnachtskonzert", start="2026-12-25T16:00:00+01:00", end="2026-12-25T17:00:00+01:00")
    events[3].update(title="Oktoberfest 2027", category="festival", start="2027-09-18T00:00:00+02:00",
                     end="2027-10-03T23:59:59+02:00", all_day=True)
    events[4].update(title="Silvesterparty", start="2026-12-31T21:00:00+01:00", end="2027-01-01T02:00:00+01:00")
    with ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(build(ROOT)))) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = launch(p)
                page = browser.new_page(viewport={"width": 390, "height": 844}, timezone_id="America/Los_Angeles", has_touch=True, is_mobile=True, reduced_motion="reduce")
                page.clock.install(time=datetime.fromisoformat("2026-10-31T12:00:00+01:00"))
                page.route("**/data/events.json", lambda route: route.fulfill(json=events))
                page.route("**/data/metadata.json", lambda route: route.fulfill(json=metadata))
                page.route("https://tile.openstreetmap.org/**", lambda route: route.fulfill(body=TILE, content_type="image/png"))
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}/"); settled(page)
                assert page.locator("#occasion-title").inner_text() == "Halloween in München"
                assert "6 Termine heute" in page.locator("#occasion-buttons").inner_text()
                assert all("Halloween" in title for title in page.locator(".event-card h3").all_text_contents()[:2])
                assert page.locator(".occasion-reason").count() == 2
                assert "21:00–02:00 Uhr (+1 Tag)" in page.locator(".event-facts").first.inner_text()
                assert "+20 Pkt." in page.locator("#interest-bars").inner_text()
                interest_text = page.locator("#interest-bars").inner_text()
                page.locator("[data-filter=free]").click()
                assert "Halloween" not in page.locator("#events").inner_text()
                # The CTA must leave the previous period, theme, filter and saved map.
                page.locator("[data-view=tomorrow]").click()
                page.locator("[data-topic=music]").click()
                page.locator("[data-display=map]").click()
                page.locator("#map-saved-only").check()
                page.locator("[data-occasion-id=halloween]").tap()
                assert page.locator(".event-card").count() == 6
                assert all("morgen" not in title for title in page.locator(".event-card h3").all_text_contents())
                assert page.locator("#selection-title").inner_text() == "Halloween · Heute"
                for attribute,value in [("view","today"),("filter","all"),("display","list")]:
                    assert page.locator(f"[data-{attribute}={value}]").get_attribute("aria-pressed") == "true"
                assert not page.locator("#map-saved-only").is_checked()
                assert page.evaluate("document.activeElement.id") == "selection"
                assert 0 <= page.locator("#selection").bounding_box()["y"] <= 20
                assert page.locator("[data-occasion-id=halloween]").get_attribute("aria-controls") == "selection"
                # Repeated taps continue to show the promised result, without toggling it off.
                page.locator("[data-occasion-id=halloween]").tap()
                assert page.locator(".event-card").count() == 6
                assert "Nur Empfehlungen" in page.locator("#all-results").inner_text()
                page.locator("[data-display=map]").click()
                page.wait_for_function("document.querySelector('#event-map').dataset.eventCount === '6'")
                page.locator("[data-display=list]").click()
                page.locator(".event-card [data-save-id]").first.click()
                with page.expect_download() as download:
                    page.locator(".event-card [data-calendar-id]").first.click()
                assert download.value.suggested_filename.endswith(".ics")
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                page.set_viewport_size({"width": 320, "height": 700})
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                # Midnight in Berlin, even though the device is still on October 31.
                page.clock.set_system_time(datetime.fromisoformat("2026-11-01T00:01:00+01:00"))
                page.clock.run_for(60001)
                assert page.locator("#occasion-panel").is_hidden()
                assert page.locator("[data-topic=all]").get_attribute("aria-pressed") == "true"
                assert page.locator(".occasion-reason").count() == 0
                for date, title in [("2026-12-25", "Weihnachtszeit in München"),
                                    ("2026-12-31", "München zum Jahreswechsel"),
                                    ("2027-09-18", "Die Wiesn ist auf dem Radar")]:
                    page.clock.set_system_time(datetime.fromisoformat(f"{date}T12:00:00+01:00"))
                    page.clock.run_for(60001)
                    assert page.locator("#occasion-title").inner_text() == title
                    assert page.locator("#interest-bars").inner_text() == interest_text
                page.clock.set_system_time(datetime.fromisoformat("2027-10-04T12:00:00+02:00"))
                page.clock.run_for(60001)
                assert page.locator("#occasion-panel").is_hidden()
                assert not errors, errors
                browser.close()
                print("Occasion checks passed: banner touch navigation, all matches beyond source/selection limits, previous filters, scroll/focus, repeated taps, temporary priority, map, ICS, Berlin midnight, Christmas, New Year, confirmed Oktoberfest.")
        finally:
            server.shutdown()


if __name__ == "__main__":
    main()
