from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import EventCollector
from .calendar import date_times, event, pages, text


class StadtbibliothekCollector(EventCollector):
    def collect(self):
        return pages(self, [self.config["url"]], "a.load-more-items[href]")

    def parse(self, html, url):
        cards = BeautifulSoup(html, "html.parser").select(".event-contents")
        if not cards:
            raise ValueError("Bibliothekskalender nicht erkannt")
        result = []
        for card in cards:
            try:
                link = card.select_one(".event-list__title a[href]")
                if not link:
                    raise ValueError("Titel oder Terminlink fehlt")
                start, end, all_day = date_times(text(card.select_one(".eventdate")))
                title = text(link)
                description = text(card.select_one(".event-list__subtitle"))
                marker = card.select_one(".fa-map-marker-alt")
                result.append(event(self.config, title, urljoin(url, link["href"]), start,
                                    end=end, all_day=all_day, description=description or None,
                                    location_name=text(marker.parent) if marker else None,
                                    labels=title + " " + description + " " + text(card.select_one(".rubrik"))))
            except (ValueError, TypeError) as exc:
                self.warn(f"Bibliothekstermin ausgelassen: {exc}")
        return result
