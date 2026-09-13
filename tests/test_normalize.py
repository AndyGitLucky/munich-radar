from dataclasses import replace

import pytest

from src.normalize import normalize_event, parse_datetime


def test_naive_dates_use_berlin_in_summer_and_winter():
    assert parse_datetime("2026-09-13T11:00:00").isoformat().endswith("+02:00")
    assert parse_datetime("2026-12-13T11:00:00").isoformat().endswith("+01:00")
    assert parse_datetime("2026-09-13T09:00:00Z").hour == 11


def test_date_only_end_is_inclusive():
    assert parse_datetime("2026-09-13", end_of_day=True).hour == 23


def test_dst_gap_rejected():
    with pytest.raises(ValueError, match="Nonexistent"):
        parse_datetime("2026-03-29T02:30:00")


def test_stable_ids_ignore_whitespace_but_preserve_performances(make_event):
    assert make_event(title=" Science  Show ").id == make_event(title="science show").id
    assert make_event().id != make_event(start="2026-09-13T14:00:00+02:00").id


def test_sanitizes_untrusted_text(make_event):
    event = make_event(title="<b>Science</b><script>alert(1)</script>", description="Hallo &amp; willkommen")
    assert event.title == "Science"
    assert event.description == "Hallo & willkommen"


@pytest.mark.parametrize("changes", [{"title":" "}, {"source_name":""}, {"source_url":"javascript:alert(1)"}, {"source_url":"https://user:password@example.org"}, {"category":"fake"}, {"start":"gestern"}, {"end":"2026-09-12"}, {"start":None}])
def test_invalid_events_rejected(make_event, changes):
    with pytest.raises(ValueError):
        make_event(**changes)


def test_round_trip_schema(make_event):
    event=make_event()
    assert type(event).from_dict(event.to_dict()) == event
