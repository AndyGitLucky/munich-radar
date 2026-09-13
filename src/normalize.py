import hashlib
import re
import unicodedata
from dataclasses import asdict
from datetime import datetime, time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from .models.event import CATEGORIES, Event, RawEvent, Source

BERLIN = ZoneInfo("Europe/Berlin")


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    soup = BeautifulSoup(str(value), "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()
    return " ".join(soup.get_text(" ", strip=True).split()) or None


def key(value: str | None) -> str:
    return re.sub(r"[^\w]+", " ", unicodedata.normalize("NFKC", value or "").casefold()).strip()


def safe_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("URL must be an absolute public HTTP(S) URL")
    return value


def parse_datetime(value: str, *, end_of_day: bool = False) -> datetime:
    value = value.strip()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if len(value) == 10 and end_of_day:
        parsed = datetime.combine(parsed.date(), time(23, 59, 59))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BERLIN)
        # Reject nonexistent local times during the spring DST transition.
        if parsed.astimezone(ZoneInfo("UTC")).astimezone(BERLIN).replace(tzinfo=None) != parsed.replace(tzinfo=None):
            raise ValueError("Nonexistent local time")
    return parsed.astimezone(BERLIN)


def normalize_event(raw: RawEvent, now: datetime) -> Event:
    values = asdict(raw)
    for name in ("title", "description", "source_name", "location_name", "address", "district", "price_text"):
        values[name] = clean_text(values[name])
    if not values["title"] or not values["source_name"] or not raw.source_url:
        raise ValueError("Title, source name and source URL are required")
    values["source_url"] = safe_url(raw.source_url)
    values["image_url"] = safe_url(raw.image_url)
    if raw.category not in CATEGORIES:
        raise ValueError(f"Invalid category: {raw.category}")
    values["tags"] = sorted({text for tag in raw.tags if (text := clean_text(tag))})
    start = parse_datetime(raw.start) if raw.start else None
    end = parse_datetime(raw.end, end_of_day=raw.all_day) if raw.end else None
    if end and not start:
        raise ValueError("End date without start date")
    if start and end and end < start:
        raise ValueError("Event ends before it starts")
    values["start"] = start.isoformat() if start else None
    values["end"] = end.isoformat() if end else None
    # Full time prevents same-day performances from overwriting each other.
    identity = "|".join((key(values["title"]), values["start"] or "", key(values["location_name"]), key(values["source_name"])))
    stable_id = hashlib.sha256(identity.encode()).hexdigest()[:20]
    stamp = now.astimezone(BERLIN).isoformat(timespec="seconds")
    return Event(**values, id=stable_id, discovered_at=stamp, updated_at=stamp,
                 sources=[Source(values["source_name"], values["source_url"], raw.source_priority)])
