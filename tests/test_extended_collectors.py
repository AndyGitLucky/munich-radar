import json
from pathlib import Path

import pytest
import yaml

from src.collectors import COLLECTORS
from src.collectors.calendar import date_times
from src.normalize import normalize_event

FIXTURES = Path(__file__).parent / "fixtures"
SOURCES = {s["id"]: s for s in yaml.safe_load((Path(__file__).parents[1] / "config/sources.yaml").read_text(encoding="utf-8"))["sources"]}


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def collector(name, now, client=None):
    return COLLECTORS[name](SOURCES[name], client, now)


@pytest.mark.parametrize("name,filename", [
    ("muenchen", "muenchen.html"), ("stadtbibliothek", "stadtbibliothek.html"),
    ("stadtmuseum", "stadtmuseum.html"), ("haus_der_kunst", "haus_der_kunst.html"),
    ("olympiapark", "olympiapark.html"), ("tollwood", "tollwood.html"),
])
def test_official_calendar_fixtures_normalize(name, filename, now):
    source = collector(name, now)
    events = source.parse(fixture(filename), SOURCES[name]["url"])
    assert events
    assert not source.warnings
    assert all(normalize_event(event, now).id for event in events)


def test_city_uses_actual_occurrence_not_outer_series_dates(now):
    source = collector("muenchen", now)
    events = source.parse(fixture("muenchen.html"), SOURCES["muenchen"]["url"])
    assert events[0].title == "Zamanand Festival"
    assert events[0].start == "2026-09-13T11:00:00"
    assert events[0].end == "2026-09-13T21:00:00"
    assert events[0].location_name == "Ludwigstraße"
    assert events[0].is_free is None


def test_city_without_detail_link_keeps_verifiable_calendar_source(now):
    source = collector("muenchen", now)
    url = SOURCES["muenchen"]["url"] + "familie-kinder"
    item = source.parse(fixture("muenchen_family.html"), url)[0]
    assert item.title == "Kalif Storch"
    assert item.source_url == url
    assert item.end == "2026-09-13T12:00:00"
    assert item.family_friendly is True


def test_city_concert_category_is_preserved_even_with_an_opaque_title(now):
    source = collector("muenchen", now)
    url = SOURCES["muenchen"]["url"] + "?field_category_one_target_id%5B%5D=27886&search=true"
    item = source.parse(fixture("muenchen.html"), url)[0]
    assert "concert" in item.tags


def test_library_keeps_long_exhibition_and_unknown_prices(now):
    events = collector("stadtbibliothek", now).parse(fixture("stadtbibliothek.html"), SOURCES["stadtbibliothek"]["url"])
    assert events[0].start == "2024-10-27"
    assert events[0].end == "2030-09-30"
    assert events[0].all_day
    assert events[0].location_name == "Monacensia im Hildebrandhaus"
    assert events[0].is_free is None
    assert any(not event.all_day for event in events)


def test_museum_relocation_is_not_assumed_to_be_main_building(now):
    events = collector("stadtmuseum", now).parse(fixture("stadtmuseum.html"), SOURCES["stadtmuseum"]["url"])
    assert all("ausgebucht" not in (e.description or "").casefold() for e in events)
    assert any(e.location_name is None for e in events)


def test_kunst_pagination_inherits_explicit_date_from_link(now):
    source = collector("haus_der_kunst", now)
    events = source.parse(fixture("haus_der_kunst_continuation.html"), "https://www.hausderkunst.de/kalender/p3?from=2026-09-26")
    assert events[0].start == "2026-09-26T14:00:00"
    assert all(e.start.startswith("2026-09-26") for e in events)
    with pytest.raises(ValueError):
        source.parse(fixture("haus_der_kunst_continuation.html"), SOURCES["haus_der_kunst"]["url"])


def test_pinakotheken_zero_fee_does_not_mean_free_admission(now):
    events = collector("pinakotheken", now).parse(fixture("pinakotheken.json"), "2026-09-13")
    assert events
    assert all(e.is_free is None for e in events)
    assert all("major_event" not in e.tags for e in events)
    assert all(normalize_event(e, now).id for e in events)
    data = json.loads(fixture("pinakotheken.json"))
    data[0]["entries"][0]["location"] = "Staatsgalerie außerhalb Münchens"
    assert len(collector("pinakotheken", now).parse(json.dumps(data), "2026-09-13")) == len(events) - 1


def test_pinakotheken_rejects_wrong_day_and_missing_schema(now):
    source = collector("pinakotheken", now)
    with pytest.raises(ValueError):
        source.parse(fixture("pinakotheken.json"), "2026-09-14")
    with pytest.raises(ValueError):
        source.parse('{"error":"unavailable"}', "2026-09-13")


def test_olympiapark_trims_json_title_and_uses_detail_links(now):
    events = collector("olympiapark", now).parse(fixture("olympiapark.html"), SOURCES["olympiapark"]["url"])
    assert len(events) == 2
    assert all(e.source_url != SOURCES["olympiapark"]["url"] for e in events)
    festival = next(e for e in events if e.title == "Outdoorsportfestival")
    assert festival.is_free is True
    assert festival.family_friendly is True


def test_tollwood_not_confused_with_silvester_or_free_shows(now):
    item = collector("tollwood", now).parse(fixture("tollwood.html"), SOURCES["tollwood"]["url"])[0]
    assert item.start == "2026-11-24"
    assert item.end == "2026-12-23"
    assert item.is_free is None
    assert item.all_day


def test_messe_filters_international_locations_preserves_inclusive_dates(now):
    source = collector("messe", now)
    events = source.parse(json.loads(fixture("messe.json")))
    assert {e.title for e in events} == {"expopharm 2026", "INTERGEO 2026"}
    assert all(e.all_day and len(e.end) == 10 for e in events)
    assert all(normalize_event(e, now).end.endswith("T23:59:59+02:00") for e in events)
    assert all("commercial" in e.tags for e in events)
    with pytest.raises(ValueError):
        source.parse({"error": "unavailable"})


def test_meetup_explicitly_empty_is_valid_but_missing_data_is_failure(now):
    source = collector("meetup_robotics", now)
    assert source.parse(fixture("meetup.html")) == []
    assert source.empty_is_valid
    with pytest.raises(ValueError):
        source.parse("<html>Login required</html>")


@pytest.mark.parametrize("name", ["muenchen", "stadtbibliothek", "stadtmuseum", "haus_der_kunst", "olympiapark", "tollwood"])
def test_changed_source_markup_is_not_silently_accepted(name, now):
    with pytest.raises(ValueError):
        collector(name, now).parse("<html>Unexpected maintenance page</html>", SOURCES[name]["url"])


def test_library_overnight_and_single_time_precision():
    assert date_times("14.09.2026, 23.00 - 01.00 Uhr") == ("2026-09-14T23:00:00", "2026-09-15T01:00:00", False)
    assert date_times("14.09.2026, 16.30 Uhr") == ("2026-09-14T16:30:00", None, False)
