from datetime import datetime
from urllib.parse import urljoin, urlsplit, parse_qs

from bs4 import BeautifulSoup

from .base import EventCollector
from .calendar import event, pages, text


class MuenchenCollector(EventCollector):
    def collect(self):
        urls = [urljoin(self.config["url"], category) for category in self.config["categories"]]
        return pages(self, urls, "a[rel='next'][href], .pager__item--next a[href]")

    def parse(self, html, url):
        cards = BeautifulSoup(html, "html.parser").select(".m-event-list-item")
        if not cards:
            raise ValueError("Stadtportal-Kalender nicht erkannt")
        result = []
        for card in cards:
            try:
                link = card.select_one(".m-event-list-item__headline a[href]")
                heading = card.select_one(".m-event-list-item__headline")
                times = card.select(".m-event-list-item__detail time[datetime]")
                if not text(heading) or not times:
                    raise ValueError("Titel oder datierte Vorstellung fehlt")
                dates = [datetime.strptime(t["datetime"], "%d.%m.%Y - %H:%M:%S").isoformat() for t in times]
                title = text(heading)
                labels = title + " " + text(card.select_one(".m-event-list-item__category"))
                if "familie-kinder" in url:
                    labels += " Familie Kinder"
                if "27886" in parse_qs(urlsplit(url).query).get("field_category_one_target_id[]", []):
                    labels += " Konzert"
                fallback = "festival" if "feste-festivals" in url else "culture"
                item = event(self.config, title, urljoin(url, link["href"]) if link else url, dates[0],
                             end=dates[1] if len(dates) > 1 else None,
                             location_name=text(card.select_one('[itemprop="location"]')) or None,
                             labels=labels, fallback=fallback)
                # The portal's explicit exhibition section outranks incidental title words
                # such as "Fotografie auf dem Jahrmarkt".
                if "/ausstellung-museen/" in urlsplit(item.source_url).path:
                    item.category = "museum" if any(word in title.casefold() for word in ("führung", "rundgang")) else "exhibition"
                    item.tags = sorted(set(item.tags) - {"market", "exhibition"} | {item.category})
                if item.category in {"festival", "street_festival"}:
                    item.tags.append("festival_day")
                result.append(item)
            except (ValueError, TypeError) as exc:
                self.warn(f"Stadtportal-Termin ausgelassen: {exc}")
        return result
