"""Exercise temporary occasions independently of permanent interests and device time zone."""
import copy
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
                         relevance_score=10+i, is_free=None, family_friendly=None,
                         start="2026-10-31T21:00:00+01:00", end="2026-11-01T02:00:00+01:00")
    events[2].update(title="Weihnachtskonzert", start="2026-12-25T16:00:00+01:00", end="2026-12-25T17:00:00+01:00")
    events[3].update(title="Oktoberfest 2027", category="festival", start="2027-09-18T00:00:00+02:00",
                     end="2027-10-03T23:59:59+02:00", all_day=True)
    events[4].update(title="Silvesterparty", start="2026-12-31T21:00:00+01:00", end="2027-01-01T02:00:00+01:00")
    with ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(build(ROOT)))) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = launch(p)
                page = browser.new_page(viewport={"width": 390, "height": 844}, timezone_id="America/Los_Angeles")
                page.clock.install(time=datetime.fromisoformat("2026-10-31T12:00:00+01:00"))
                page.route("**/data/events.json", lambda route: route.fulfill(json=events))
                page.route("**/data/metadata.json", lambda route: route.fulfill(json=metadata))
                page.route("https://tile.openstreetmap.org/**", lambda route: route.fulfill(body=TILE, content_type="image/png"))
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}/"); settled(page)
                assert page.locator("#occasion-title").inner_text() == "Halloween in München"
                assert "2 Termine heute" in page.locator("#occasion-buttons").inner_text()
                assert all("Halloween" in title for title in page.locator(".event-card h3").all_text_contents()[:2])
                assert page.locator(".occasion-reason").count() == 2
                assert "21:00–02:00 Uhr (+1 Tag)" in page.locator(".event-facts").first.inner_text()
                assert "+20 Pkt." in page.locator("#interest-bars").inner_text()
                interest_text = page.locator("#interest-bars").inner_text()
                page.locator("[data-filter=free]").click()
                assert "Halloween" not in page.locator("#events").inner_text()
                page.locator("[data-filter=all]").click()
                page.locator("[data-occasion-id=halloween]").click()
                assert page.locator(".event-card").count() == 2
                assert page.locator("[data-occasion-id=halloween]").get_attribute("aria-pressed") == "true"
                page.locator("[data-display=map]").click()
                page.wait_for_function("document.querySelector('#event-map').dataset.eventCount === '2'")
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
                print("Occasion checks passed: temporary priority, interests, filters, map, ICS, Berlin midnight, Christmas, New Year, confirmed Oktoberfest, mobile.")
        finally:
            server.shutdown()


if __name__ == "__main__":
    main()
