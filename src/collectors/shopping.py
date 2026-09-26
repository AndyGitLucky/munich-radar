"""Munich opening permissions, explicitly distinguished from participating shops."""
import hashlib
import re
from datetime import date, datetime, time, timedelta
from bs4 import BeautifulSoup
from .base import EventCollector
from .calendar import text
from ..local_dates import easter, munich_holidays
from ..models import RawEvent

# Reviewed sections of the official statute dated 14 January 2026.
# Refuse silent legal-rule changes; whitespace/soft hyphens are insignificant.
REVIEWED = {
    2:'7663d1393c7fcc16cc6e884876ed730eb0d2df0ab3befe9974b402cfc4b288f3',
    4:'162c55590c2205f51202f49fa84f48dea5147ca91a07bb204d01b1dfb065abc3',
    5:'904a04b26e2c50a0d6ae947090dcf5203dcfb398b2c31701551314179664ad33',
    6:'22b2e4d8f01998384df6f53065c82815001e6e2922159cbd08a571b88cfcd6f2',
    8:'69328b4a9d2dc7a8ab640cd7f2795371eadedf91d6bea17145b4f1ad19e5b044',
}


class ShoppingCollector(EventCollector):
    def collect(self):
        overview = self.client.get(self.config['url'])
        law = self.client.get(self.config['law_url'])
        festival = None
        if any((self.now.date()+timedelta(days=n)).month==9 for n in range(self.config.get('horizon_days',30)+1)):
            try: festival = self.client.get(self.config['festival_url'])
            except Exception as exc: self.warn(f'Oktoberfest-Datumsquelle nicht gelesen: {exc}')
        return self.parse(overview,law,festival)

    def parse(self, overview, law, festival=None):
        sections = {}; number = None
        for p in BeautifulSoup(law,'html.parser').find_all('p'):
            value = ' '.join(text(p).replace('\u00ad','').split())
            heading = re.match(r'^§\s*(\d+)\b',value)
            if heading: number=int(heading[1]); sections[number]=[]
            if number is not None and value: sections[number].append(value)
        for number,digest in REVIEWED.items():
            if hashlib.sha256(' '.join(sections.get(number,[])).encode()).hexdigest() != digest:
                raise ValueError(f'Ladenschlussverordnung § {number} geändert oder nicht lesbar; erneute Prüfung erforderlich')
        today = self.now.date(); last = today+timedelta(days=self.config.get('horizon_days',30))
        events = []
        def add(day,title,start_hour,end_hour,location,description,series,recurring=False,source=None):
            if not today <= day <= last: return
            start = datetime.combine(day,time(start_hour))
            end = datetime.combine(day,time.min)+timedelta(hours=end_hour)
            events.append(RawEvent(title=title,source_name=self.config['name'],source_url=source or self.config['law_url'],
                start=start.isoformat(),end=end.isoformat(),category='public_event',tags=['shopping']+(['recurring'] if recurring else []),
                location_name=location,series_id=series,source_priority=self.config.get('priority',10),
                description='Öffnung erlaubt, Teilnahme einzelner Geschäfte nicht bestätigt. '+description+' Öffnungszeiten beim jeweiligen Geschäft prüfen.'))
        # Only explicitly dated shopping nights from the current city overview, not publication dates.
        months = {'Januar':1,'Februar':2,'März':3,'April':4,'Mai':5,'Juni':6,'Juli':7,'August':8,'September':9,'Oktober':10,'November':11,'Dezember':12}
        soup = BeautifulSoup(overview,'html.parser')
        if 'Shopping-Nächte' not in text(soup): raise ValueError('Shopping-Übersicht nicht erkannt')
        night_dates = set()
        for li in soup.select('li'):
            match = re.match(r'^(Freitag|Samstag),\s*(\d{1,2})\.\s*('+'|'.join(months)+r')\s+(20\d{2})\b',text(li))
            if not match: continue
            weekday,day,month,year=match.groups()
            day=date(int(year),months[month],int(day))
            if day.weekday() != {'Freitag':4,'Samstag':5}[weekday]: raise ValueError('Shoppingdatum widerspricht Wochentag')
            night_dates.add(day)
        if not night_dates: raise ValueError('Keine expliziten Shoppingnacht-Daten erkannt')
        for day in sorted(night_dates):
            add(day,'Shoppingnacht München – Öffnung bis 24 Uhr möglich',20,24,'Verschiedene Geschäfte im Münchner Stadtgebiet',
                'Stadtweite Erlaubnis für interessierte Handelsunternehmen von 20 bis 24 Uhr; keine Zusage für alle Läden.',
                'shopping-night',source=self.config['url'])
        district_description = ('Nur Lebens- und Genussmittel, Tabakwaren, Schreibwaren und Reiseandenken. '
            'Gebiete: Altstadt-Lehel südlich der Prinzregentenstraße, Ludwigvorstadt-Isarvorstadt, Maxvorstadt, '
            'Sendling und Schwanthalerhöhe östlich der Bahnlinie. Verbindliche Grenzen: Lageplan in § 6.')
        if festival:
            matches = re.findall(r'Vom\s+(\d{1,2})\.\s*September\s+bis\s+(\d{1,2})\.\s*Oktober\s+(20\d{2})',text(BeautifulSoup(festival,'html.parser')),re.I)
            if not matches: self.warn('Oktoberfestzeitraum nicht erkannt; erster Wiesn-Sonntag wird nicht geraten')
            for first,last_day,year in set(matches):
                start=date(int(year),9,int(first)); end=date(int(year),10,int(last_day))
                if not 14 <= (end-start).days <= 20:
                    self.warn('Oktoberfestzeitraum unplausibel'); continue
                day=start+timedelta(days=(6-start.weekday())%7)
                add(day,'Erster Oktoberfestsonntag – eingeschränkte Ladenöffnung möglich',11,16,
                    'Ausgewählte Bereiche in München (siehe Quelle)',district_description+' Datumsquelle: '+self.config['festival_url'], 'oktoberfest-shopping')
        # Carefully scoped recurring permissions; no assumed retail participation or map point.
        for year in range(today.year,last.year+1):
            holidays = munich_holidays(year); good_friday=easter(year)-timedelta(days=2)
            fourth_advent = date(year,12,24)-timedelta(days=(date(year,12,24).weekday()+1)%7)
            advents={fourth_advent-timedelta(days=7*n) for n in range(4)}
            day=max(today,date(year,1,1)); until=min(last,date(year,12,31))
            while day <= until:
                if (day.weekday()==6 or day in holidays) and day!=good_friday:
                    if date(year,4,1)<=day<=date(year,10,15) or day in advents:
                        add(day,'Tourismusbedarf in der Altstadt – Sonntags-/Feiertagsöffnung möglich',11,14 if day==date(year,12,24) else 19,
                            'Fußgängerbereiche der Münchner Altstadt',
                            'Nur Tourismusbedarf, ohne Bade- und Sportzubehör, in den festgelegten Altstadt-Fußgängerbereichen (§ 4). Kein allgemeiner verkaufsoffener Sonntag.',
                            'tourism-altstadt',True)
                    if date(year,4,1)<=day<=date(year,10,31):
                        add(day,'Tourismusbedarf im Olympiapark – Sonntags-/Feiertagsöffnung möglich',11,18,'Olympiapark München',
                            'Nur Verkaufsstellen für Tourismusbedarf im Olympiapark (§ 2). Kein allgemeiner verkaufsoffener Sonntag.',
                            'tourism-olympiapark',True)
                day += timedelta(days=1)
            add(easter(year)-timedelta(days=49),'Faschingssonntag – eingeschränkte Ladenöffnung möglich',12,17,'Verschiedene Geschäfte im Münchner Stadtgebiet',
                'Anlässlich des Faschingstreibens: nur Konditoreiwaren, Süßwaren, Tabakwaren, Scherzartikel, Papier- und Schreibwaren (§ 5).', 'fasching-shopping')
            add(date(year,10,3),'3. Oktober – eingeschränkte Ladenöffnung möglich',11,16,'Ausgewählte Bereiche in München (siehe Quelle)',
                district_description, 'unity-shopping')
        self.empty_is_valid = True
        return events
