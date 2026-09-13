from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import EventCollector
from .calendar import text
from .common import from_jsonld, structured_events, tag_topics
from ..normalize import clean_text


class OlympiaparkCollector(EventCollector):
    def collect(self):
        return self.parse(self.client.get(self.config["url"]), self.config["url"])

    def parse(self, html, url):
        cards = {}
        for card in BeautifulSoup(html, "html.parser").select(".content-body"):
            link = card.select_one(".body-actions a[href*='/de/veranstaltungen/']")
            if link:
                cards[text(card.select_one(".title"))] = (urljoin(url, link["href"]), text(card.select_one(".description")))
        result = []
        entries = structured_events(html)
        if not entries:
            raise ValueError("Olympiapark-Veranstaltungsdaten fehlen")
        for entry in entries:
            try:
                name = clean_text(entry.get("name"))
                if name not in cards:
                    raise ValueError("Offizieller Detail-Link fehlt")
                link, description = cards[name]
                item = from_jsonld(entry, self.config, link)
                item.description = item.description or description
                item.category, item.tags = tag_topics([item.title, description])
                item.tags = [tag for tag in item.tags if tag != "major_event"]
                item.family_friendly = True if "family" in item.tags else None
                # Only explicit statements attached to this event, never page-wide banners.
                if "kostenlos" in description.casefold() and "nicht kostenlos" not in description.casefold():
                    item.is_free = True
                    item.price_text = "Kostenlos laut Veranstalter"
                item.series_id = link
                result.append(item)
            except (ValueError, TypeError) as exc:
                self.warn(f"Olympiapark-Termin ausgelassen: {exc}")
        return result
