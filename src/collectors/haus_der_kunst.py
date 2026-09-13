import re
from urllib.parse import parse_qs, urljoin, urlsplit
from datetime import date

from bs4 import BeautifulSoup

from .base import EventCollector
from .calendar import event, numeric_date, pages, text


class HausDerKunstCollector(EventCollector):
    def collect(self):
        return pages(self, [self.config["url"]], "a[hx-get][href*='/kalender/p']")

    def parse(self, html, url):
        sections = BeautifulSoup(html, "html.parser").select("section.list")
        if not sections:
            raise ValueError("Kunstkalender nicht erkannt")
        result = []
        continuation = parse_qs(urlsplit(url).query).get("from", [None])[0]
        day = date.fromisoformat(continuation).isoformat() if continuation else None
        for section in sections:
            heading = text(section.select_one(".list__title"))
            if heading:
                day = numeric_date(heading)
            if not day:
                raise ValueError("Kalenderdatum für Fortsetzung fehlt")
            for card in section.select(".list-item__link[href]"):
                try:
                    title = text(card.select_one(".list-item__title"))
                    label = text(card.select_one(".list-item__subline"))
                    match = re.match(r"(\d{1,2}:\d{2})\b", label)
                    if not title or not match:
                        raise ValueError("Titel oder Uhrzeit fehlt")
                    free = "eintritt frei" in label.casefold()
                    result.append(event(self.config, title, urljoin(url, card["href"]),
                                        f"{day}T{match[1].zfill(5)}:00", labels=label + " " + title,
                                        fallback="museum", location_name="Haus der Kunst",
                                        address="Prinzregentenstraße 1, München", description=label,
                                        is_free=True if free else None, price_text="Eintritt frei" if free else None))
                except (ValueError, TypeError) as exc:
                    self.warn(f"Kunsttermin ausgelassen: {exc}")
        return result
