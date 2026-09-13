import hashlib
import json
import logging
import os
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from .collectors import COLLECTORS
from .deduplicate import deduplicate
from .http import PoliteHttpClient
from .models import Event
from .normalize import BERLIN, normalize_event, parse_datetime
from .scoring import heads_up, score
from .views import classify, select

logger = logging.getLogger(__name__)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def load_json(path: Path, fallback):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback


def in_horizon(event: Event, now: datetime, horizon: int) -> bool:
    if event.status != "scheduled" or not event.start:
        return False
    start = parse_datetime(event.start).date()
    end = parse_datetime(event.end).date() if event.end else start
    return end >= now.date() and start <= now.date() + timedelta(days=horizon)


def mark_recurring(events: list[Event]) -> None:
    """Infer repeated occurrences only from multiple observed dates in one series."""
    dates: dict[tuple[str, str], set] = {}
    for event in events:
        if event.series_id and event.start:
            dates.setdefault((event.source_name, event.series_id), set()).add(parse_datetime(event.start).date())
    for event in events:
        if event.series_id and "festival_day" not in event.tags and len(dates.get((event.source_name, event.series_id), set())) > 1:
            event.tags = sorted(set(event.tags) | {"recurring"})


def run(root: Path, *, now: datetime | None = None, client=None, registry=None) -> dict:
    now = (now or datetime.now(BERLIN)).astimezone(BERLIN)
    stamp = now.isoformat(timespec="seconds")
    sources_config = yaml.safe_load((root / "config/sources.yaml").read_text(encoding="utf-8"))
    relevance = yaml.safe_load((root / "config/relevance.yaml").read_text(encoding="utf-8"))
    sources = [s for s in sources_config["sources"] if s.get("enabled", True)]
    if not sources:
        raise ValueError("No sources enabled")
    registry = registry if registry is not None else COLLECTORS
    origins = {f"{urlsplit(s['url']).scheme}://{urlsplit(s['url']).netloc}" for s in sources}
    origins.update(origin for s in sources for origin in s.get("api_origins", []))
    client = client or PoliteHttpClient(sources_config["http"], origins)
    data_dir = root / "data"
    previous_state = load_json(data_dir / "source-state.json", {})
    state = {}
    collected: list[Event] = []
    statuses = []
    raw_count = 0
    successes = 0
    horizon = relevance["selection"]["horizon_days"]
    for source in sources:
        logger.info("Collector start: %s", source["name"])
        prior = [Event.from_dict(e) for e in previous_state.get(source["id"], [])]
        prior_by_id = {e.id: e for e in prior}
        normalized = []
        status = {"id": source["id"], "name": source["name"], "url": source["url"], "status": "ok", "events": 0, "warnings": []}
        try:
            collector = registry[source["id"]]({**source, "horizon_days": horizon}, client, now)
            raw = collector.collect()
            raw_count += len(raw)
            write_json(data_dir / "raw" / f"{source['id']}.json", {"fetched_at": stamp, "events": [asdict(e) for e in raw]})
            for item in raw:
                try:
                    event = normalize_event(item, now)
                    if event.id in prior_by_id:
                        event.discovered_at = prior_by_id[event.id].discovered_at
                    normalized.append(event)
                except (ValueError, TypeError) as exc:
                    collector.warn(f"Termin verworfen: {exc}")
            status["warnings"] = collector.warnings
            if not normalized and not (not raw and collector.empty_is_valid and not collector.warnings):
                raise ValueError("Keine gültigen Termine geliefert; vorherigen Stand beibehalten")
            successes += 1
            status["events"] = len(normalized)
            if collector.warnings:
                status["status"] = "partial"
            logger.info("Collector success: %s (%s events)", source["name"], len(normalized))
        except Exception as exc:
            logger.warning("Collector failed: %s (%s: %s)", source["name"], type(exc).__name__, exc)
            status["status"] = "error"
            status["warnings"].append(f"{type(exc).__name__}: {exc}")
        if status["status"] != "ok":
            seen = {e.id for e in normalized}
            for event in prior:
                if event.id not in seen and now - parse_datetime(event.updated_at) <= timedelta(days=7):
                    event.stale = True
                    normalized.append(event)
        # Keep only relevant dates in persistent source state; canceled entries remain
        # excluded even when another part of the source failed.
        normalized = [e for e in normalized if in_horizon(e, now, horizon)]
        mark_recurring(normalized)
        state[source["id"]] = [e.to_dict() for e in normalized]
        collected.extend(normalized)
        statuses.append(status)
    if successes == 0:
        # Do not overwrite the last successful public dataset or its metadata.
        write_json(data_dir / "last-failure.json", {"attempted_at": stamp, "sources": statuses})
        raise RuntimeError("All collectors failed; previous public dataset preserved")
    events = deduplicate(collected)
    for event in events:
        score(event, relevance, now)
    events.sort(key=lambda e: (-e.relevance_score, e.start or "", e.id))
    view_ids = {}
    for view in ("today", "tomorrow", "weekend", "upcoming", "new"):
        matching = [e for e in events if view in classify(e, now, relevance["selection"]["new_hours"], horizon)]
        view_ids[view] = [e.id for e in select(matching, relevance["selection"])]
    payload = [e.to_dict() for e in events]
    metadata = {"schema_version": 1, "last_updated": stamp, "timezone": "Europe/Berlin",
        "sources_checked": len(sources), "sources_successful": successes,
        "events_collected": raw_count, "events_after_deduplication": len(events),
        "stale_events": sum(e.stale for e in events), "sources": statuses,
        "selection": relevance["selection"], "views": view_ids, "heads_up": heads_up(events, relevance, now), "heads_up_rules": relevance["heads_up"],
        "data_hash": hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
    write_json(data_dir / "events.json", payload)
    write_json(data_dir / "metadata.json", metadata)
    write_json(data_dir / "source-state.json", state)
    failure = data_dir / "last-failure.json"
    if failure.exists():
        failure.unlink()
    logger.info("Deduplicated %s -> %s; wrote data/events.json", len(collected), len(events))
    return metadata
