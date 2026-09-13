import json
from datetime import timedelta
from urllib.parse import urlencode, urljoin

from .base import EventCollector
from .calendar import event
from ..normalize import clean_text


class PinakothekenCollector(EventCollector):
    def collect(self):
        result = []
        completed = 0
        for offset in range(self.config.get("days", 7)):
            day = (self.now.date() + timedelta(days=offset)).isoformat()
            url = urljoin(self.config["url"], "/_proxy_calendar") + "?" + urlencode({"date": day, "locale": "de"})
            try:
                result.extend(self.parse(self.client.get(url), day))
                completed += 1
            except Exception as exc:
                self.warn(f"Pinakotheken-Kalendertag {day} nicht verarbeitet: {exc}")
        self.empty_is_valid = completed > 0 and not self.warnings
        if not completed:
            raise ValueError("Kein Pinakotheken-Kalendertag abrufbar")
        return result

    def parse(self, payload, requested_day):
        groups = json.loads(payload)
        if not isinstance(groups, list):
            raise ValueError("Unerwartetes Pinakotheken-Datenformat")
        result = []
        for group in groups:
            if group.get("date") != requested_day or not isinstance(group.get("entries"), list):
                raise ValueError("Kalenderdatum oder Eintragsliste stimmt nicht")
            for entry in group["entries"]:
                try:
                    if entry.get("isRemoved"):
                        continue
                    location = entry.get("location", "")
                    if location not in self.config["locations"]:
                        continue
                    start = entry.get("startTime")
                    if not start or not entry.get("title"):
                        raise ValueError("Titel oder Uhrzeit fehlt")
                    end = entry.get("endTime")
                    item = event(self.config, entry["title"], self.config["url"], f"{requested_day}T{start}",
                                 end=f"{requested_day}T{end}" if end else None,
                                 location_name=location, description=clean_text(entry.get("richText")),
                                 labels=entry["title"] + " " + str(entry.get("category", "")), fallback="museum")
                    # The API's zero entryFee often excludes the required museum ticket.
                    fee = entry.get("entryFee")
                    if isinstance(fee, (int, float)) and fee > 0:
                        item.is_free = False
                        item.price_text = f"Teilnahme {fee:g} €; Museumseintritt ggf. zusätzlich"
                    item.series_id = str(entry.get("eventId") or item.title.casefold())
                    result.append(item)
                except (ValueError, TypeError) as exc:
                    self.warn(f"Pinakotheken-Termin ausgelassen: {exc}")
        return result
