import json

from bs4 import BeautifulSoup

from .base import EventCollector
from .calendar import event


class MeetupCollector(EventCollector):
    """Only public upcoming entries of the configured group, no member data."""
    def collect(self):
        return self.parse(self.client.get(self.config["url"]))

    def parse(self, html):
        script = BeautifulSoup(html, "html.parser").select_one("script#__NEXT_DATA__")
        if not script:
            raise ValueError("Öffentliche Meetup-Gruppendaten fehlen")
        state = json.loads(script.string)["props"]["pageProps"]["__APOLLO_STATE__"]
        group = next((v for v in state.values() if v.get("__typename") == "Group"
                      and v.get("urlname", "").casefold() == self.config["group"].casefold()), None)
        if not group or group.get("isPrivate") is not False:
            raise ValueError("Konfigurierte öffentliche Meetup-Gruppe nicht erkannt")
        connection = next((value for key, value in group.items() if key.startswith("events(") and '"ACTIVE"' in key), None)
        if not isinstance(connection, dict) or not isinstance(connection.get("edges"), list):
            raise ValueError("Liste kommender Meetup-Termine fehlt")
        result = []
        for edge in connection["edges"]:
            entry = state[edge["node"]["__ref"]]
            if entry.get("status") != "ACTIVE" or entry.get("eventType") not in {"PHYSICAL", "HYBRID"}:
                continue
            venue = state.get((entry.get("venue") or {}).get("__ref"), {})
            if venue.get("city", "").casefold() not in {"münchen", "munich", "muenchen"}:
                continue
            if not entry.get("title") or not entry.get("dateTime") or not entry.get("eventUrl"):
                raise ValueError("Meetup-Termin ohne Titel, Datum oder Link")
            result.append(event(self.config, entry["title"], entry["eventUrl"], entry["dateTime"],
                                end=entry.get("endTime"), location_name=venue.get("name"),
                                address=venue.get("address"), labels=entry["title"]))
        # An explicit empty ACTIVE connection is legitimate, unlike a missing calendar.
        self.empty_is_valid = not connection["edges"] and connection.get("totalCount") == 0
        return result
