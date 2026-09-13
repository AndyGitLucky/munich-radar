from difflib import SequenceMatcher

from .models import Event
from .normalize import key, parse_datetime


def matches(a: Event, b: Event) -> bool:
    if not a.start or not b.start:
        return a.source_url == b.source_url and key(a.title) == key(b.title)
    sa, sb = parse_datetime(a.start), parse_datetime(b.start)
    if sa.date() != sb.date():
        return False
    if not a.all_day and not b.all_day and sa != sb:
        return False
    if not a.location_name or not b.location_name:
        return a.source_url == b.source_url and key(a.title) == key(b.title)
    return (SequenceMatcher(None, key(a.title), key(b.title)).ratio() >= .9
            and SequenceMatcher(None, key(a.location_name), key(b.location_name)).ratio() >= .85)


def deduplicate(events: list[Event]) -> list[Event]:
    result: list[Event] = []
    for event in sorted(events, key=lambda e: (e.stale, e.source_priority, e.source_name, e.id)):
        duplicate = next((e for e in result if matches(e, event)), None)
        if duplicate is None:
            result.append(event)
            continue
        duplicate.sources = sorted(set(duplicate.sources + event.sources), key=lambda s: (s.priority, s.name, s.url))
        duplicate.tags = sorted(set(duplicate.tags + event.tags))
        duplicate.discovered_at = min(duplicate.discovered_at, event.discovered_at)
        # The preferred source owns facts; only fill absent descriptive fields.
        for field in ("description", "address", "district", "image_url"):
            if not getattr(duplicate, field):
                setattr(duplicate, field, getattr(event, field))
    return result
