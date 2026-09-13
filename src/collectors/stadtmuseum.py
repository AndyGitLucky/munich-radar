from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import EventCollector
from .calendar import date_times, event, pages, text


class StadtmuseumCollector(EventCollector):
    def collect(self):
        return pages(self, [self.config["url"]])

    def parse(self, html, url):
        cards = BeautifulSoup(html, "html.parser").select("a.event-element.event-list[href]")
        if not cards:
            raise ValueError("Stadtmuseumskalender nicht erkannt")
        result = []
        for card in cards:
            try:
                title = text(card.select_one("h3"))
                description = text(card.select_one(".event-teaser p"))
                if "ausgebucht" in description.casefold():
                    continue
                start, end, all_day = date_times(text(card.select_one("time")))
                link = urljoin(url, card["href"])
                film = "/filmmuseum/" in link
                result.append(event(self.config, title, link, start, end=end, all_day=all_day,
                                    description=description or None, labels=title + " " + description,
                                    fallback="culture" if film else "museum",
                                    location_name="Filmmuseum München" if film else None))
            except (ValueError, TypeError) as exc:
                self.warn(f"Stadtmuseumstermin ausgelassen: {exc}")
        return result
