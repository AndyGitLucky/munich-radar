import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import EventCollector
from ..models import RawEvent

MONTHS = {name: index for index, name in enumerate("Januar Februar März April Mai Juni Juli August September Oktober November Dezember".split(), 1)}


def german_date_range(value: str) -> tuple[str, str | None, bool]:
    match = re.search(r"(\d{1,2})\.\s+(\w+)\s+(\d{4})(?:,\s*(\d{1,2})(?:[.:](\d{2}))?(?:\s*[–−-]\s*(\d{1,2})(?:[.:](\d{2}))?)?\s*Uhr)?", value)
    if not match:
        raise ValueError("No explicit German date")
    day, month, year, hour, minute, end_hour, end_minute = match.groups()
    stamp = datetime(int(year), MONTHS[month], int(day), int(hour or 0), int(minute or 0))
    end_stamp = stamp.replace(hour=int(end_hour), minute=int(end_minute or 0)) if end_hour else None
    if end_stamp and end_stamp < stamp:
        end_stamp += timedelta(days=1)
    end = end_stamp.isoformat() if end_stamp else None
    return stamp.isoformat() if hour else stamp.date().isoformat(), end, hour is None


class LenbachhausCollector(EventCollector):
    """Read explicitly dated calendar cards; omit undated permanent offers."""

    def parse(self, html: str) -> list[RawEvent]:
        soup = BeautifulSoup(html, "html.parser")
        if not soup.select_one(".card-event-teaser"):
            raise ValueError("Lenbachhaus-Kalenderstruktur nicht gefunden")
        result = []
        for node in soup.select(".card-event-teaser"):
            date_node = node.select_one(".event_list_date .time")
            if not date_node:
                continue
            try:
                link = node.select_one("h3 a.eventteaser")
                start, end, all_day = german_date_range(date_node.get_text(" ", strip=True))
                subtitle = node.select_one(".event_list_title")
                title = link.get_text(" ", strip=True)
                image = node.select_one("img[src]")
                url = urljoin(self.config["url"], link["href"].split("?")[0])
                text = node.get_text(" ", strip=True)
                result.append(RawEvent(title=title, source_name=self.config["name"], source_url=url,
                    start=start, end=end, all_day=all_day,
                    description=subtitle.get_text(" ", strip=True) if subtitle else None,
                    category="museum", tags=["museum", "culture"], location_name="Lenbachhaus",
                    is_free=True if "Kostenlos" in text else None,
                    price_text="Kostenlos" if "Kostenlos" in text else None,
                    source_priority=self.config.get("priority", 100), series_id=title.casefold(),
                    status="cancelled" if "abgesagt" in text.casefold() else "scheduled",
                    image_url=urljoin(url, image["src"]) if image else None))
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                self.warn(f"Ungültiger Kalendertermin: {type(exc).__name__}")
        return result

    def collect(self) -> list[RawEvent]:
        html = self.client.get(self.config["url"])
        result = self.parse(html)
        # Follow the site's actual next-month link; do not construct TYPO3 hashes.
        next_month = BeautifulSoup(html, "html.parser").select_one('button[aria-label="nächster Monat"][data-link]')
        if next_month:
            try:
                result.extend(self.parse(self.client.get(urljoin(self.config["url"], next_month["data-link"]))))
            except Exception as exc:
                self.warn(f"Nächster Monat nicht abrufbar: {type(exc).__name__}")
        return result
