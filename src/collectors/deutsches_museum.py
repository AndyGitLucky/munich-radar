from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import EventCollector
from ..models import RawEvent


class DeutschesMuseumCollector(EventCollector):
    """Follow the public calendar's HTML endpoint and its own pagination links."""

    def parse(self, html: str) -> list[RawEvent]:
        soup = BeautifulSoup(html, "html.parser")
        result = []
        for node in soup.select(".calendar-teaser[data-datetime]"):
            try:
                link = node.select_one("h3 a[href]")
                day = node["data-datetime"]
                times = [t.get_text(strip=True) for t in node.select(".calendar-teaser__date time")]
                subtitle = node.select_one(".subtitle")
                label = subtitle.get_text(" ", strip=True) if subtitle else ""
                description = node.select_one(".calendar-teaser__text > p:not(.subtitle)")
                pin = node.select_one(".icon-pin")
                place = pin.parent.get_text(" ", strip=True) if pin else None
                image = node.select_one("img[src]")
                title = link.get_text(" ", strip=True)
                category = "exhibition" if "ausstellung" in label.casefold() else "science"
                tags = ["museum", "science"]
                # The calendar exposes individual occurrences, not opening dates.
                if "programm-heute" in link["href"] or category == "exhibition":
                    tags.append("recurring")
                family = "Familie und Kinder" in node.get_text(" ", strip=True)
                result.append(RawEvent(title=title, source_name=self.config["name"], source_url=urljoin(self.config["url"], link["href"]),
                    start=f"{day}T{times[0]}:00" if times else day,
                    end=f"{day}T{times[1]}:00" if len(times) > 1 else None,
                    all_day=not times, description=description.get_text(" ", strip=True) if description else None,
                    location_name=f"Deutsches Museum · {place}" if place else "Deutsches Museum, Museumsinsel",
                    category=category, tags=tags, family_friendly=True if family else None,
                    image_url=urljoin(self.config["url"], image["src"]) if image else None,
                    source_priority=self.config.get("priority", 100), series_id=link["href"].split("#")[0],
                    status="cancelled" if "abgesagt" in title.casefold() else "scheduled"))
            except (ValueError, TypeError, AttributeError, KeyError, IndexError) as exc:
                self.warn(f"Ungültiger Kalendertermin: {type(exc).__name__}")
        if not result and not soup.select_one(".result-count"):
            raise ValueError("Kalenderstruktur nicht gefunden")
        return result

    def collect(self) -> list[RawEvent]:
        root = self.config["url"].rstrip("/") + "/search.html"
        url = root
        result = []
        visited = set()
        for _ in range(self.config.get("max_pages", 6)):
            if url in visited:
                break
            visited.add(url)
            try:
                html = self.client.get(url)
                result.extend(self.parse(html))
                more = BeautifulSoup(html, "html.parser").select_one(".load-more-button[data-url]")
                if not more:
                    break
                url = urljoin(root, more["data-url"])
            except Exception as exc:
                self.warn(f"Kalenderseite fehlgeschlagen: {type(exc).__name__}")
                break
        return result
