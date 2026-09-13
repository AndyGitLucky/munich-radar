from datetime import date, datetime, time, timedelta

from .models import Event
from .normalize import BERLIN, key, parse_datetime


def weekend(today: date) -> tuple[date, date]:
    saturday = today + timedelta(days=5 - today.weekday())
    return saturday, saturday + timedelta(days=1)


def occurs_on(event: Event, day: date) -> bool:
    if not event.start:
        return False
    start = parse_datetime(event.start)
    end = parse_datetime(event.end) if event.end else datetime.combine(start.date(), time(23, 59, 59), BERLIN)
    lower = datetime.combine(day, time.min, BERLIN)
    upper = datetime.combine(day + timedelta(days=1), time.min, BERLIN)
    return start < upper and (end > lower or start == end == lower)


def classify(event: Event, now: datetime, new_hours: int = 72, horizon: int = 30) -> list[str]:
    today = now.astimezone(BERLIN).date()
    sat, sun = weekend(today)
    views = []
    if occurs_on(event, today):
        views.append("today")
    if occurs_on(event, today + timedelta(days=1)):
        views.append("tomorrow")
    if occurs_on(event, sat) or occurs_on(event, sun):
        views.append("weekend")
    if event.start and today < parse_datetime(event.start).date() <= today + timedelta(days=horizon):
        views.append("upcoming")
    age = now - parse_datetime(event.discovered_at)
    if timedelta(0) <= age <= timedelta(hours=new_hours):
        views.append("new")
    return views


def select(events: list[Event], config: dict) -> list[Event]:
    chosen: list[Event] = []
    source_counts: dict[str, int] = {}
    series_counts: dict[str, int] = {}
    for event in sorted(events, key=lambda e: (-e.relevance_score, e.start or "", e.id)):
        series = event.series_id or key(event.title)
        if event.relevance_score < config["min_score"]:
            continue
        if source_counts.get(event.source_name, 0) >= config["max_per_source"]:
            continue
        if series_counts.get(series, 0) >= config["max_per_series"]:
            continue
        chosen.append(event)
        source_counts[event.source_name] = source_counts.get(event.source_name, 0) + 1
        series_counts[series] = series_counts.get(series, 0) + 1
        if len(chosen) >= config["limit"]:
            break
    return chosen
