from datetime import timedelta
from pathlib import Path

import yaml

from src.scoring import heads_up, score

CONFIG=yaml.safe_load((Path(__file__).parents[1]/"config/relevance.yaml").read_text(encoding="utf-8"))


def test_scoring_explains_free_family_science(make_event,now):
    event=score(make_event(is_free=True,family_friendly=True),CONFIG,now)
    assert "Kostenlos" in event.relevance_reasons
    assert "Für Familien" in event.relevance_reasons
    assert "Technik & Wissenschaft" in event.relevance_reasons
    assert 0 <= event.relevance_score <= 100


def test_recurring_penalty_and_configurable_interests(make_event,now):
    now = now + timedelta(days=1)  # Isolate the recurring penalty from weekend bonuses.
    base=score(make_event(),CONFIG,now).relevance_score
    recurring=score(make_event(tags=["recurring"]),CONFIG,now).relevance_score
    assert recurring==base+CONFIG["weights"]["recurring"]
    changed={**CONFIG,"interests":{"science":0}}
    assert score(make_event(),changed,now).relevance_score < base


def test_discovery_does_not_imply_exhibition_opening(make_event,now):
    old=make_event(category="exhibition",start="2026-08-01",end="2026-10-01",all_day=True)
    assert "Kürzlich eröffnete Ausstellung" not in score(old,CONFIG,now).relevance_reasons
    occurrence=make_event(category="exhibition",tags=["recurring"])
    assert "Kürzlich eröffnete Ausstellung" not in score(occurrence,CONFIG,now).relevance_reasons


def test_heads_up_thresholds_and_excludes_stale(make_event,now):
    event=score(make_event(start="2026-09-14T13:00:00+02:00",end=None),CONFIG,now)
    assert heads_up([event],CONFIG,now)==[{"event_id":event.id,"days_until":1}]
    event.stale=True
    assert heads_up([event],CONFIG,now)==[]


def test_future_discovery_has_no_novelty_bonus(make_event,now):
    event=make_event(); event.discovered_at=(now+timedelta(days=1)).isoformat()
    assert "Neu im Radar" not in score(event,CONFIG,now).relevance_reasons
