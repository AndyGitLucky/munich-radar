"""Published weekly opening times from the City of Munich's own market pages."""
import re
from datetime import datetime, time, timedelta
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from .base import EventCollector
from .calendar import text
from ..local_dates import munich_holidays
from ..models import RawEvent


class WeeklyMarketsCollector(EventCollector):
    def collect(self):
        url = self.config['url']
        soup = BeautifulSoup(self.client.get(url),'html.parser')
        links = list(dict.fromkeys(urljoin(url,a['href']) for a in soup.select('a[href]')
                    if re.search(r'/service/info/(?:wochenmarkt|bauernmarkt)-',a['href'])
                    and urlsplit(urljoin(url,a['href'])).netloc == urlsplit(url).netloc))
        if not links:
            raise ValueError('Keine städtischen Wochenmarkt-Detailseiten erkannt')
        result = []
        limit = self.config.get('max_details',40)
        if len(links) > limit:
            self.warn('Weitere Marktseiten außerhalb des Abruflimits')
        for link in links[:limit]:
            try:
                result.extend(self.parse(self.client.get(link),link))
            except Exception as exc:
                self.warn(f'Marktseite nicht verarbeitet: {exc}')
        self.empty_is_valid = not self.warnings
        return result

    def parse(self, html, url):
        soup = BeautifulSoup(html,'html.parser')
        title = text(soup.select_one('h1'))
        fields = {text(g.select_one('dt')):text(g.select_one('dd')) for g in soup.select('.definition-group')}
        address, hours = fields.get('Adresse',''), fields.get('Öffnungszeiten','')
        if not title.startswith(('Wochenmarkt','Bauernmarkt')) or not address:
            raise ValueError('Marktname oder Adresse fehlt')
        weekdays = ['Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag','Sonntag']
        pattern = r'('+'|'.join(weekdays)+r')\s+(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})'
        matches = re.findall(pattern,hours)
        if not matches or re.sub(pattern,'',hours).strip(' ,;/'):
            raise ValueError('Öffnungszeiten nicht eindeutig; Sonderregelung manuell prüfen')
        today = self.now.date()
        last = today+timedelta(days=self.config.get('horizon_days',30))
        holidays = set().union(*(munich_holidays(y) for y in range(today.year,last.year+1)))
        result = []
        for weekday, start, end in matches:
            start_time, end_time = time.fromisoformat(start), time.fromisoformat(end)
            if end_time <= start_time:
                raise ValueError('Unplausible Marktzeiten')
            day = today+timedelta(days=(weekdays.index(weekday)-today.weekday())%7)
            while day <= last:
                # Special holiday shifts / Christmas Eve / New Year's Eve require explicit dates.
                if day not in holidays and (day.month,day.day) not in {(12,24),(12,31)}:
                    result.append(RawEvent(title=title,source_name=self.config['name'],source_url=url,
                        start=datetime.combine(day,start_time).isoformat(),end=datetime.combine(day,end_time).isoformat(),
                        location_name=address,address=f'{address}, München',category='market',tags=['food','market','recurring'],
                        series_id=url,source_priority=self.config.get('priority',10),
                        description='Regulärer Wochenmarkt nach den veröffentlichten Öffnungszeiten der Stadt. Feiertagsverlegungen und kurzfristige Änderungen beim Veranstalter prüfen.'))
                day += timedelta(days=7)
        return result
