import json
from datetime import timedelta
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from .base import EventCollector
from .calendar import event


class MesseCollector(EventCollector):
    def collect(self):
        soup = BeautifulSoup(self.client.get(self.config["url"]), "html.parser")
        calendar = soup.select_one("#event-calendar[data-api-endpoint][data-api-token][data-engine]")
        if not calendar:
            raise ValueError("Öffentliche Messesuche nicht gefunden")
        endpoint = calendar["data-api-endpoint"] + calendar["data-engine"] + "/search"
        parsed = urlsplit(endpoint)
        if f"{parsed.scheme}://{parsed.netloc}" not in self.config["api_origins"]:
            raise ValueError("Unbekannter Ursprung der Messesuche")
        # This read-only search token is supplied by the public calendar, never stored.
        headers = {"Authorization": "Bearer " + calendar["data-api-token"]}
        query = {"query": "", "filters": {"all": [
            {"document_type": "event-de"},
            {"event_end_date": {"from": self.now.date().isoformat() + "T00:00:00Z"}},
            {"event_start_date": {"to": (self.now.date() + timedelta(days=self.config.get("horizon_days", 30) + 1)).isoformat() + "T00:00:00Z"}}
        ]}, "sort": [{"event_start_date": "asc"}], "page": {"size": 100, "current": 1}}
        result = []
        for page in range(1, self.config.get("max_pages", 2) + 1):
            query["page"]["current"] = page
            data = json.loads(self.client.post(endpoint, json=query, headers=headers))
            result.extend(self.parse(data))
            if page >= data["meta"]["page"]["total_pages"]:
                break
        self.empty_is_valid = not self.warnings
        return result

    def parse(self, data):
        if not isinstance(data.get("results"), list) or not isinstance(data.get("meta", {}).get("page", {}).get("total_pages"), int):
            raise ValueError("Messesuche lieferte kein gültiges Ergebnis")
        result = []
        for record in data["results"]:
            try:
                fields = {key: value.get("raw") for key, value in record.items() if isinstance(value, dict)}
                # The organizer also runs international and online fairs.
                if (fields.get("location_abbreviation") not in self.config["locations"]
                        and fields.get("location_name") not in self.config.get("location_names", [])):
                    continue
                title = fields.get("event_name")
                start, end = fields.get("event_start_date"), fields.get("event_end_date")
                if not title or not start or not end or not fields.get("url"):
                    raise ValueError("Messetitel, Zeitraum oder Link fehlt")
                state = fields.get("event_status")
                if state != "as_scheduled":
                    if state not in {"cancelled", "canceled", "postponed"}:
                        self.warn("Unbekannter Messestatus; Termin ausgelassen")
                    continue
                item = event(self.config, title, fields["url"], start[:10], end=end[:10], all_day=True,
                             location_name=fields.get("location_name"), description=fields.get("event_subtitle"),
                             labels=title + " " + (fields.get("event_subtitle") or ""), fallback="public_event")
                item.tags.append("commercial")
                result.append(item)
            except (ValueError, TypeError) as exc:
                self.warn(f"Messetermin ausgelassen: {exc}")
        return result
