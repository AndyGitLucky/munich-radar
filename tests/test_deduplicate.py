from src.deduplicate import deduplicate


def test_merges_sources_and_prefers_organizer(make_event):
    portal=make_event(source_name="Stadtportal",source_url="https://example.org/portal",source_priority=100)
    organizer=make_event(source_name="Veranstalter",source_priority=10)
    events=deduplicate([portal,organizer])
    assert len(events)==1
    assert events[0].source_name=="Veranstalter"
    assert len(events[0].sources)==2


def test_keeps_distinct_sessions_dates_and_locations(make_event):
    a=make_event()
    assert len(deduplicate([a,make_event(start="2026-09-13T14:00:00+02:00")]))==2
    assert len(deduplicate([a,make_event(start="2026-09-14T13:00:00+02:00",end=None)]))==2
    assert len(deduplicate([a,make_event(location_name="Olympiapark")]))==2


def test_missing_locations_do_not_merge_unrelated_sources(make_event):
    assert len(deduplicate([make_event(location_name=None),make_event(location_name=None,source_url="https://other.example/event")]))==2


def test_fresh_source_preferred_over_stale(make_event):
    stale=make_event(source_name="A",source_priority=1);stale.stale=True
    fresh=make_event(source_name="B",source_priority=10)
    result=deduplicate([stale,fresh])
    assert result[0].source_name=="B"
    assert not result[0].stale
