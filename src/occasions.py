"""Calendar context is separate from permanent personal interests."""
import re
from datetime import date

from .models import Event
from .normalize import key
from .views import occurs_on


def matches(event: Event, occasion: dict) -> bool:
    title = key(event.title)
    return (any(key(word) in title for word in occasion.get("keywords", []))
            or bool(set(event.tags) & set(occasion.get("tags", []))))


def active_occasions(rules: list[dict], events: list[Event], today: date) -> list[dict]:
    active = []
    for rule in rules:
        window = rule.get("window")
        if window:
            # Annual windows can cross New Year, without fixing a particular year.
            month_day = today.strftime("%m-%d")
            start, end = window["start"], window["end"]
            enabled = start <= month_day <= end if start <= end else month_day >= start or month_day <= end
        else:
            anchors = {key(title) for title in rule.get("anchor_titles", [])}
            enabled = any(not event.stale and event.status == "scheduled"
                          and event.category in {"festival", "street_festival", "seasonal"}
                          and key(re.sub(r"\b20\d{2}\b", "", event.title)) in anchors
                          and occurs_on(event, today) for event in events)
        if enabled:
            active.append(rule)
    return active


def context_ids(events: list[Event], occasions: list[dict]) -> set[str]:
    return {event.id for event in events if any(matches(event, rule) for rule in occasions)}
