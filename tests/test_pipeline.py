import json
import shutil
from datetime import timedelta
from pathlib import Path

import pytest
import yaml

from src.collectors.base import EventCollector
from src.models import RawEvent
from src.pipeline import mark_recurring, run


class Good(EventCollector):
    def collect(self):
        return [RawEvent(title=self.config["name"]+" Event",source_name=self.config["name"],source_url=self.config["url"],start="2026-09-13T18:00:00+02:00",category="science")]


class Bad(EventCollector):
    def collect(self):
        raise TimeoutError("simulated timeout")


@pytest.fixture
def root(tmp_path):
    shutil.copytree(Path(__file__).parents[1]/"config",tmp_path/"config")
    # These failure scenarios intentionally use three controlled test collectors.
    config_path = tmp_path / "config/sources.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["sources"] = [s for s in config["sources"] if s["id"] in {"gasteig", "deutsches_museum", "lenbachhaus"}]
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    return tmp_path


def test_failure_isolated_and_discovery_preserved(root,now):
    registry={name:Good for name in ["gasteig","deutsches_museum","lenbachhaus"]}
    first=run(root,now=now,client=object(),registry=registry)
    assert first["sources_successful"]==3
    registry["gasteig"]=Bad
    second=run(root,now=now+timedelta(hours=1),client=object(),registry=registry)
    assert second["sources_successful"]==2
    events=json.loads((root/"data/events.json").read_text(encoding="utf-8"))
    stale=next(e for e in events if e["source_name"]=="Gasteig")
    assert stale["stale"] is True
    assert stale["updated_at"]==now.isoformat(timespec="seconds")
    assert all(e["discovered_at"]==now.isoformat(timespec="seconds") for e in events)


def test_all_fail_preserves_public_files(root,now):
    registry={name:Good for name in ["gasteig","deutsches_museum","lenbachhaus"]}
    run(root,now=now,client=object(),registry=registry)
    before=(root/"data/events.json").read_bytes(),(root/"data/metadata.json").read_bytes()
    with pytest.raises(RuntimeError,match="All collectors failed"):
        run(root,now=now+timedelta(hours=1),client=object(),registry=dict.fromkeys(registry,Bad))
    assert before==((root/"data/events.json").read_bytes(),(root/"data/metadata.json").read_bytes())
    assert (root/"data/last-failure.json").exists()


def test_pipeline_reproducible_at_fixed_time(root,now):
    registry={name:Good for name in ["gasteig","deutsches_museum","lenbachhaus"]}
    first=run(root,now=now,client=object(),registry=registry)
    second=run(root,now=now,client=object(),registry=registry)
    assert first==second


def test_malformed_event_does_not_break_valid_siblings(root,now):
    class Mixed(Good):
        def collect(self):
            return super().collect()+[RawEvent(title="Broken",source_name="Gasteig",source_url="javascript:bad")]
    result=run(root,now=now,client=object(),registry={"gasteig":Mixed,"deutsches_museum":Good,"lenbachhaus":Good})
    assert result["sources_successful"]==3
    assert result["events_after_deduplication"]==3
    assert result["sources"][0]["status"]=="partial"


def test_repeated_occurrences_marked_without_confusing_long_exhibitions(make_event):
    first=make_event(series_id="series")
    second=make_event(series_id="series",start="2026-09-14T13:00:00+02:00",end=None)
    exhibition=make_event(series_id="long-show",start="2026-08-01",end="2026-10-01",all_day=True)
    mark_recurring([first,second,exhibition])
    assert "recurring" in first.tags and "recurring" in second.tags
    assert "recurring" not in exhibition.tags


def test_verified_empty_clears_previous_events_but_unverified_empty_does_not(root, now):
    class Empty(EventCollector):
        def collect(self):
            return []

    class VerifiedEmpty(Empty):
        def collect(self):
            self.empty_is_valid = True
            return []

    registry = dict.fromkeys(["gasteig", "deutsches_museum", "lenbachhaus"], Good)
    run(root, now=now, client=object(), registry=registry)
    registry.update(gasteig=VerifiedEmpty, deutsches_museum=Empty)
    result = run(root, now=now + timedelta(hours=1), client=object(), registry=registry)
    statuses = {s["id"]: s for s in result["sources"]}
    assert statuses["gasteig"]["status"] == "ok"
    assert statuses["gasteig"]["events"] == 0
    assert statuses["deutsches_museum"]["status"] == "error"
    state = json.loads((root / "data/source-state.json").read_text(encoding="utf-8"))
    assert state["gasteig"] == []
    assert state["deutsches_museum"][0]["stale"] is True
