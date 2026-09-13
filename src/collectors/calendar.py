"""Shared parsing for explicit calendar dates, never inferred publication dates."""
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import RawEvent
from .common import tag_topics


def text(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


def numeric_date(value: str) -> str:
    match = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})\b", value)
    if not match:
        raise ValueError(f"Kein explizites Datum: {value}")
    day, month, year = map(int, match.groups())
    if year < 100:
        year += 2000
    return datetime(year, month, day).date().isoformat()


def date_times(value: str) -> tuple[str, str | None, bool]:
    dates = re.findall(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b", value)
    if not dates:
        raise ValueError(f"Kein explizites Datum: {value}")
    start = numeric_date(dates[0])
    if len(dates) > 1:
        return start, numeric_date(dates[1]), True
    remainder = value.split(dates[0], 1)[1]
    times = re.findall(r"\b(\d{1,2})[.:](\d{2})\b", remainder)
    if not times:
        return start, None, True
    start_time = datetime.fromisoformat(start).replace(hour=int(times[0][0]), minute=int(times[0][1]))
    end = None
    if len(times) > 1:
        end_time = start_time.replace(hour=int(times[1][0]), minute=int(times[1][1]))
        if end_time < start_time:
            end_time += timedelta(days=1)
        end = end_time.isoformat()
    return start_time.isoformat(), end, False


def event(config: dict, title: str, url: str, start: str, *, labels: str = "", fallback="culture", **kwargs) -> RawEvent:
    category, tags = tag_topics([labels], fallback)
    # “Highlights of the collection” in a tour title is not a major city event.
    tags = [tag for tag in tags if tag != "major_event"]
    # An exhibition tour is a timed museum activity, not a newly opened exhibition.
    if any(word in labels.casefold() for word in ("führung", "rundgang", "guided tour")):
        category = "museum" if fallback == "museum" else fallback
        tags = [tag for tag in tags if tag != "exhibition"]
    if category == "museum":
        tags.append("museum")
    return RawEvent(title=title, source_name=config["name"], source_url=url,
                    start=start, category=category, tags=sorted(set(tags)),
                    source_priority=config.get("priority", 10), series_id=title.casefold(),
                    family_friendly=True if "family" in tags else None, **kwargs)


def pages(collector, urls: list[str], next_selector: str | None = None) -> list[RawEvent]:
    result = []
    visited = set()
    for first in urls:
        url = first
        for _ in range(collector.config.get("max_pages", 1)):
            if not url or url in visited:
                break
            visited.add(url)
            try:
                html = collector.client.get(url)
                result.extend(collector.parse(html, url))
                link = BeautifulSoup(html, "html.parser").select_one(next_selector) if next_selector else None
                url = urljoin(url, link["href"]) if link else None
            except Exception as exc:
                collector.warn(f"Kalenderseite nicht verarbeitet: {exc}")
                break
    if not result:
        raise ValueError("Keine datierten Kalendereinträge gefunden")
    unique = {(e.source_url, e.start, e.title): e for e in result}
    return list(unique.values())
