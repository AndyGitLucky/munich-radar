from datetime import date, datetime, timedelta

import pytest

from src.normalize import BERLIN
from src.views import classify, occurs_on, select, weekend


@pytest.mark.parametrize("day,saturday",[("2026-09-11","2026-09-12"),("2026-09-12","2026-09-12"),("2026-09-13","2026-09-12"),("2026-09-14","2026-09-19")])
def test_weekend_includes_current_sunday(day,saturday):
    assert weekend(date.fromisoformat(day))[0]==date.fromisoformat(saturday)


def test_multiday_and_overnight_overlap(make_event,now):
    event=make_event(start="2026-09-12T22:00:00+02:00",end="2026-09-13T02:00:00+02:00")
    assert "today" in classify(event,now)
    assert "tomorrow" not in classify(event,now)
    assert occurs_on(event,date(2026,9,12))


def test_midnight_end_exclusive(make_event):
    event=make_event(start="2026-09-12T22:00:00+02:00",end="2026-09-13T00:00:00+02:00")
    assert not occurs_on(event,date(2026,9,13))


def test_all_day_inclusive_end(make_event):
    assert occurs_on(make_event(start="2026-09-12",end="2026-09-13",all_day=True),date(2026,9,13))


def test_discovery_window_and_horizon(make_event,now):
    event=make_event(start="2026-09-14T12:00:00",end=None)
    assert set(classify(event,now))=={"tomorrow","upcoming","new"}
    event.discovered_at=(now-timedelta(hours=73)).isoformat()
    assert "new" not in classify(event,now)
    far=make_event(start="2026-11-01",end=None)
    assert "upcoming" not in classify(far,now)


def test_selection_limits_sources_and_series(make_event):
    events=[]
    for i in range(10):
        event=make_event(title=f"Termin {i}",source_name="A" if i<7 else "B",series_id="repeat" if i<3 else str(i))
        event.relevance_score=90-i
        events.append(event)
    chosen=select(events,{"min_score":25,"limit":5,"max_per_source":3,"max_per_series":1})
    assert len(chosen)==5
    assert sum(e.source_name=="A" for e in chosen)==3
    assert sum(e.series_id=="repeat" for e in chosen)==1


def test_dst_weekend_boundaries(make_event):
    event=make_event(start="2026-10-25T01:30:00+02:00",end="2026-10-25T03:30:00+01:00")
    assert occurs_on(event,date(2026,10,25))
    assert not occurs_on(event,date(2026,10,26))
