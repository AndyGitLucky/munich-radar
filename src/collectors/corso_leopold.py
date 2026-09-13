import re
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from .base import EventCollector
from ..models import RawEvent

MONTHS = {month: number for number, month in enumerate(
    "Januar Februar März April Mai Juni Juli August September Oktober November Dezember".split(), 1)}


class CorsoLeopoldCollector(EventCollector):
    """Read the current festival's published daily opening hours, not stage acts."""

    @staticmethod
    def program_url(html: str, base: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select('a[href]'):
            if not re.fullmatch(r"Corso Leopold \w+ 20\d{2}", link.get_text(" ", strip=True)):
                continue
            target = urlsplit(urljoin(base, link["href"]))
            if target.netloc == urlsplit(base).netloc and target.path.startswith("/cl/programm/"):
                return urlunsplit((target.scheme, target.netloc, target.path, "", ""))
        raise ValueError("Kein aktueller Corso-Programmlink gefunden")

    def parse(self, html: str, url: str) -> list[RawEvent]:
        soup = BeautifulSoup(html, "html.parser")
        heading = soup.select_one("h1")
        title = heading.get_text(" ", strip=True) if heading else ""
        edition = re.fullmatch(r"Corso Leopold (\w+) (20\d{2})", title)
        if not edition:
            raise ValueError("Keine eindeutige Festival-Ausgabe im Seitentitel")
        edition_month, year = edition.groups()
        intro = next((node for node in soup.select(".elementText")
                      if "Leopoldstraße" in node.get_text(" ", strip=True)), None)
        intro_text = intro.get_text(" ", strip=True) if intro else ""
        schedule = next((node for node in soup.select(".elementText")
                         if node.select_one("strong") and "Musik Ende" in node.get_text(" ", strip=True)), None)
        if not schedule:
            raise ValueError("Festival-Öffnungszeiten nicht gefunden; Parser prüfen")
        # Work only inside the opening-hours block. Stage times and music-end
        # notes must never become the opening/closing time of the entire festival.
        text = schedule.get_text(" ", strip=True)
        pattern = (r"(?:Mo|Di|Mi|Do|Fr|Sa|So)\s+(\d{1,2})\.\s+(\w+)\s+"
                   r"(?:20\d{2}\s+)?(?:Mo|Di|Mi|Do|Fr|Sa|So)?\s*"
                   r"(\d{1,2})[.:](\d{2})\s*(?:Uhr\s*)?bis\s*"
                   r"(?:Mo|Di|Mi|Do|Fr|Sa|So)?\s*(\d{1,2})[.:](\d{2})\s*Uhr")
        matches = list(re.finditer(pattern, text))
        dated_headings = [node for node in schedule.select("strong")
                          if re.match(r"(?:Mo|Di|Mi|Do|Fr|Sa|So)\s+\d", node.get_text(strip=True))]
        if not matches or len(matches) != len(dated_headings):
            raise ValueError("Nicht alle Festivaltage haben eindeutige Öffnungszeiten")
        result = []
        for match in matches:
            day, month, hour, minute, end_hour, end_minute = match.groups()
            if month != edition_month:
                raise ValueError("Öffnungszeiten passen nicht zur Festival-Ausgabe")
            start = datetime(int(year), MONTHS[month], int(day), int(hour), int(minute))
            end = start.replace(hour=int(end_hour), minute=int(end_minute))
            if end < start:
                end += timedelta(days=1)
            result.append(RawEvent(
                title="Corso Leopold", source_name=self.config["name"], source_url=url,
                start=start.isoformat(), end=end.isoformat(),
                location_name="Leopoldstraße" if "Leopoldstraße" in intro_text else None,
                description=" ".join(p.get_text(" ", strip=True) for p in intro.select("p")[:2]) if intro else None,
                category="street_festival", tags=["street_festival", "culture", "outdoor", "major_event", "festival_day"],
                family_friendly=True if "Kinderprogramm" in intro_text else None,
                source_priority=self.config.get("priority", 10), series_id=url,
                # Admission is not stated on this program page: preserve unknown.
            ))
        return result

    def collect(self) -> list[RawEvent]:
        home = self.client.get(self.config["url"])
        url = self.program_url(home, self.config["url"])
        return self.parse(self.client.get(url), url)
