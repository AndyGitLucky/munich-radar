"""The city portal's explicitly dated Oktoberfest edition, never a guessed rule."""
import re
from datetime import date

from bs4 import BeautifulSoup

from .base import EventCollector
from .calendar import event, text


class OktoberfestCollector(EventCollector):
    def collect(self):
        return self.parse(self.client.get(self.config["url"]), self.config["url"])

    def parse(self, html, url):
        content = text(BeautifulSoup(html, "html.parser"))
        periods = set(re.findall(r"Vom\s+(\d{1,2})\.\s*September\s+bis\s+(\d{1,2})\.\s*Oktober\s+(20\d{2})", content, re.I))
        if not periods:
            raise ValueError("Expliziter Oktoberfestzeitraum fehlt; Datum wird nicht geraten")
        result = []
        for first, last, year in sorted(periods):
            start, end = date(int(year), 9, int(first)), date(int(year), 10, int(last))
            if not 14 <= (end-start).days <= 20:
                raise ValueError("Unplausibler Oktoberfestzeitraum")
            item = event(self.config, f"Oktoberfest {year}", url, start.isoformat(),
                         end=end.isoformat(), all_day=True, labels="Festival", location_name="Theresienwiese, München",
                         description="Offizieller Festivalzeitraum. Öffnungszeiten, einzelne Angebote und Preise bitte beim Veranstalter prüfen.")
            item.tags.extend(["major_event", "seasonal"])
            result.append(item)
        return result
