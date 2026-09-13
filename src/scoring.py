from datetime import datetime, timedelta

from .models import Event
from .normalize import BERLIN, parse_datetime
from .views import occurs_on, weekend

INTEREST_LABELS = {"museum": "Museen", "exhibition": "Ausstellungen", "family": "Familie", "street_festival": "Straßenfeste", "market": "Märkte", "culture": "Kultur", "concert": "Musik", "science": "Wissenschaft", "technology": "Technik"}


def score(event: Event, config: dict, now: datetime) -> Event:
    weights = config["weights"]
    total = weights["base"]
    reasons = []

    def add(rule: str, reason: str) -> None:
        nonlocal total
        total += weights[rule]
        if weights[rule] > 0:
            reasons.append(reason)

    topics = set(event.tags) | {event.category}
    interests = config["interests"]
    interest = max(topics & interests.keys(), key=lambda t: (interests[t], t), default=None)
    if interest:
        total += interests[interest] * weights["interest"]
        reasons.append(f"Dein Schwerpunkt: {INTEREST_LABELS.get(interest, interest)}")
    if "major_event" in topics:
        add("major_event", "Highlight des Veranstalters")
    if topics & {"science", "technology"}:
        add("science_technology", "Technik & Wissenschaft")
    if event.family_friendly:
        add("family", "Für Familien")
    if event.is_free:
        add("free", "Kostenlos")
    if "seasonal" in topics:
        add("seasonal", "Saisonales Programm")
    today = now.astimezone(BERLIN).date()
    if occurs_on(event, today):
        add("today", "Heute im Programm")
    if event.start:
        start = parse_datetime(event.start).date()
        end = parse_datetime(event.end).date() if event.end else start
        if event.category == "exhibition" and today - timedelta(days=7) <= start <= today and "recurring" not in topics:
            add("new_exhibition", "Kürzlich eröffnete Ausstellung")
        sat, sun = weekend(today)
        if sat <= start <= end <= sun and "recurring" not in topics:
            add("weekend_only", "Termin an diesem Wochenende")
    age = now - parse_datetime(event.discovered_at)
    if timedelta(0) <= age <= timedelta(hours=config["selection"]["new_hours"]):
        add("discovered", "Neu im Radar")
    for rule in ("recurring", "commercial"):
        if rule in topics:
            add(rule, "")
    event.relevance_score = round(max(0, min(100, total)), 1)
    event.relevance_reasons = reasons
    return event


def heads_up(events: list[Event], config: dict, now: datetime) -> list[dict]:
    result = []
    seen = set()
    for event in events:
        if not event.start or event.stale or "recurring" in event.tags:
            continue
        days = (parse_datetime(event.start).date() - now.astimezone(BERLIN).date()).days
        thresholds = config["heads_up"]["major_days" if "major_event" in event.tags else "other_days"]
        series = event.series_id or event.title.casefold()
        if days in thresholds and event.relevance_score >= config["selection"]["min_score"] and series not in seen:
            result.append({"event_id": event.id, "days_until": days})
            seen.add(series)
    return result[:config["heads_up"]["limit"]]
