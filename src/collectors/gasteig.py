from datetime import timedelta
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from .base import EventCollector
from .common import from_jsonld, structured_events, tag_topics
from ..models import RawEvent


class GasteigCollector(EventCollector):
    """Discover official teasers, then read factual Event JSON-LD on detail pages."""

    @staticmethod
    def links(html: str, latest_date: str | None = None) -> dict[str, list[str]]:
        result = {}
        soup = BeautifulSoup(html, "html.parser")
        for teaser in soup.select('[data-component="teaser"]'):
            link = teaser.select_one('a[href]')
            if not link or not teaser.select_one('time[datetime]'):
                continue
            url = link["href"]
            if urlsplit(url).hostname != "www.gasteig.de" or not urlsplit(url).path.startswith(("/veranstaltungen/", "/festivals/")):
                continue
            if latest_date and teaser.select_one('time[datetime]')["datetime"][:10] > latest_date:
                continue
            labels = [a.get_text(" ", strip=True) for a in teaser.select('[data-component="tags"] a')]
            result[url] = labels
        return result

    def parse(self, html: str, url: str, labels: list[str]) -> list[RawEvent]:
        result = []
        for item in structured_events(html):
            try:
                event = from_jsonld(item, self.config, url)
                event.category, event.tags = tag_topics(labels)
                event.family_friendly = True if "family" in event.tags else None
                event.series_id = url
                if "Entfällt" in labels:
                    event.status = "cancelled"
                result.append(event)
            except (ValueError, TypeError, AttributeError, KeyError) as exc:
                self.warn(f"Ungültiger strukturierter Termin: {type(exc).__name__}")
        return result

    def collect(self) -> list[RawEvent]:
        latest = (self.now.date() + timedelta(days=self.config.get("horizon_days", 30))).isoformat()
        links = self.links(self.client.get(self.config["url"]), latest)
        if not links:
            raise ValueError("Keine datierten Gasteig-Teaser gefunden; Parser prüfen")
        result = []
        # Main page is curated by the venue; bounded detail requests, no full crawl.
        for url, labels in list(links.items())[:self.config.get("max_details", 14)]:
            try:
                events = self.parse(self.client.get(url), url, labels)
                if not events:
                    self.warn("Detailseite ohne Event-JSON-LD")
                result.extend(events)
            except Exception as exc:
                self.warn(f"Detailseite nicht abrufbar: {type(exc).__name__}")
        return result
