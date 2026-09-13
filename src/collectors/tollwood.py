import re
from datetime import date

from bs4 import BeautifulSoup

from .base import EventCollector
from .calendar import event, text
from .lenbachhaus import MONTHS


class TollwoodCollector(EventCollector):
    def collect(self):
        return self.parse(self.client.get(self.config["url"]), self.config["url"])

    def parse(self, html, url):
        for box in BeautifulSoup(html, "html.parser").select(".meta-infobox-block"):
            heading = text(box.select_one("h4"))
            edition = re.search(r"(Winterfestival|Sommerfestival)\s+(\d{4})", heading)
            if not edition:
                continue
            period = text(box.select_one("p > strong"))
            match = re.fullmatch(r"(\d{1,2})\.\s+(\w+)\s*[–-]\s*(\d{1,2})\.\s+(\w+)", period)
            if not match:
                raise ValueError("Tollwood-Festivalzeitraum nicht erkannt")
            day1, month1, day2, month2 = match.groups()
            year = int(edition[2])
            start = date(year, MONTHS[month1], int(day1))
            end = date(year + (MONTHS[month2] < start.month), MONTHS[month2], int(day2))
            item = event(self.config, f"Tollwood {edition[1]} {year}", url, start.isoformat(),
                         end=end.isoformat(), all_day=True, labels="Festival", location_name=self.config["location"],
                         description="Festivalzeitraum; Öffnungszeiten und einzelne Veranstaltungen siehe Veranstalter.")
            item.tags.extend(["seasonal", "major_event"])
            # Free festival admission does not include every show: no blanket free flag.
            return [item]
        raise ValueError("Datierter Tollwood-Festivalblock fehlt")
