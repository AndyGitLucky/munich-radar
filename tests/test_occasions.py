from datetime import date
from pathlib import Path

import pytest
import yaml

from src.collectors.oktoberfest import OktoberfestCollector
from src.collectors.muenchen import MuenchenCollector
from src.occasions import active_occasions, context_ids, matches
from src.views import select

CONFIG = yaml.safe_load((Path(__file__).parents[1] / "config/relevance.yaml").read_text(encoding="utf-8"))
RULES = CONFIG["occasions"]


@pytest.mark.parametrize("day,expected", [
    ("2026-10-23", []), ("2026-10-24", ["halloween"]),
    ("2026-10-31", ["halloween"]), ("2026-11-01", []),
    ("2027-10-31", ["halloween"]),
    ("2026-11-20", ["christmas"]), ("2026-12-25", ["christmas"]),
    ("2026-12-26", ["christmas"]), ("2026-12-27", ["new_year"]),
    ("2027-01-01", ["new_year"]), ("2027-01-02", []),
])
def test_annual_context_boundaries_and_year_rollover(day, expected):
    assert [rule["id"] for rule in active_occasions(RULES, [], date.fromisoformat(day))] == expected


def test_oktoberfest_uses_confirmed_event_dates_only(make_event):
    fest = make_event(title="Oktoberfest 2026", category="festival", start="2026-09-19", end="2026-10-04", all_day=True)
    assert not active_occasions(RULES, [], date(2026, 9, 20))
    assert not active_occasions(RULES, [fest], date(2026, 9, 18))
    assert active_occasions(RULES, [fest], date(2026, 9, 19))[0]["id"] == "oktoberfest"
    assert active_occasions(RULES, [fest], date(2026, 10, 4))[0]["id"] == "oktoberfest"
    assert not active_occasions(RULES, [fest], date(2026, 10, 5))
    fest.stale = True
    assert not active_occasions(RULES, [fest], date(2026, 9, 20))
    fest.stale = False
    fest.category = "museum"
    assert not active_occasions(RULES, [fest], date(2026, 9, 20))
    fest.category = "festival"
    fest.status = "cancelled"
    assert not active_occasions(RULES, [fest], date(2026, 9, 20))


def test_matching_uses_titles_and_tags_without_incidental_description(make_event):
    rule = RULES[0]
    assert matches(make_event(title="HALLOWEEN im Museum"), rule)
    assert not matches(make_event(title="Museumstag", description="Auch an Halloween geöffnet"), rule)
    assert not matches(make_event(title="Kürbissuppe im Café"), rule)


def test_context_gets_two_leading_slots_without_changing_interests_or_scores(make_event):
    events = [make_event(title=f"Museum {i}", source_name=f"Museum {i}", series_id=str(i)) for i in range(5)]
    for event in events:
        event.relevance_score = 90
    parties = [make_event(title=f"Halloween {i}", source_name="Club", series_id=f"party{i}") for i in range(4)]
    for event in parties:
        event.relevance_score = 10
    all_events = events + parties
    before = [event.relevance_score for event in all_events]
    context = context_ids(all_events, [RULES[0]])
    selected = select(all_events, CONFIG["selection"], context=context)
    assert len(selected) == 5
    assert all(event.id in context for event in selected[:2])
    assert all(event.id not in context for event in selected[2:])
    assert [event.relevance_score for event in all_events] == before
    assert select(all_events, CONFIG["selection"]) == sorted(events, key=lambda e: e.id)
    # An extra occurrence must not fill a second slot in the same series.
    parties[1].series_id = parties[0].series_id
    selected = select(all_events, CONFIG["selection"], context=context)
    assert len({event.series_id for event in selected}) == 5


def test_source_parser_refuses_guessed_festival_dates(now):
    collector = OktoberfestCollector({"name": "München", "priority": 10}, None, now)
    items = collector.parse("<p>Vom 19. September bis 4. Oktober 2026</p>", "https://www.muenchen.de/veranstaltungen/oktoberfest")
    assert items[0].start == "2026-09-19"
    assert items[0].end == "2026-10-04"
    assert items[0].is_free is None
    with pytest.raises(ValueError, match="fehlt"):
        collector.parse("<p>Das nächste Oktoberfest kommt!</p>", "https://example.org")


def test_city_halloween_fixture_preserves_overnight_dates_and_unknown_prices(now):
    html = (Path(__file__).parent / "fixtures/muenchen_halloween.html").read_text(encoding="utf-8")
    collector = MuenchenCollector({"name": "muenchen.de"}, None, now)
    items = collector.parse(html, "https://www.muenchen.de/veranstaltungen/event/?title=Halloween&search=true")
    assert len(items) == 2
    assert items[0].title == "Halloween Supreme"
    assert items[0].start == "2026-10-31T19:00:00"
    assert items[0].end == "2026-11-01T05:00:00"
    assert items[0].is_free is None
