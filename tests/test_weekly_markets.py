from datetime import datetime, date
import pytest
from src.collectors.weekly_markets import WeeklyMarketsCollector
from src.local_dates import easter, munich_holidays
from src.normalize import BERLIN, normalize_event

HTML = '''<h1>Wochenmarkt Giesing</h1><div class="definition-group"><dt>Adresse</dt><dd>Giesinger Bahnhofsplatz</dd></div>
<div class="definition-group"><dt>Öffnungszeiten</dt><dd>Freitag 13:00 - 18:00</dd></div>'''
URL = 'https://maerkte-muenchen.de/service/info/wochenmarkt-giesing/M00343446/'

def collector(now):
    return WeeklyMarketsCollector({'name':'Märkte München','horizon_days':30},None,now)

def test_weekly_dates_and_dst():
    now=datetime(2026,10,1,tzinfo=BERLIN)
    events=collector(now).parse(HTML,URL)
    assert len(events)==5
    assert events[0].start=='2026-10-02T13:00:00'
    assert normalize_event(events[-1],now).start=='2026-10-30T13:00:00+01:00'
    assert all('food' in e.tags and 'recurring' in e.tags for e in events)
    assert all(e.is_free is None for e in events)

def test_no_invented_holiday_market_or_replacement_day():
    events=collector(datetime(2026,9,26,tzinfo=BERLIN)).parse(HTML.replace('Freitag','Samstag'),URL)
    assert [e.start[:10] for e in events]==['2026-09-26','2026-10-10','2026-10-17','2026-10-24']
    events=collector(datetime(2026,3,27,tzinfo=BERLIN)).parse(HTML,URL)
    assert not any(e.start.startswith('2026-04-03') for e in events)

@pytest.mark.parametrize('hours',['Freitag nach Vereinbarung','Freitag 18:00 - 13:00','Freitag 13:00 - 18:00 außer im Winter'])
def test_unknown_or_conditional_schedule_rejected(hours):
    with pytest.raises(ValueError): collector(datetime(2026,9,26,tzinfo=BERLIN)).parse(HTML.replace('Freitag 13:00 - 18:00',hours),URL)

def test_munich_holiday_calendar():
    assert easter(2026)==date(2026,4,5)
    assert easter(2027)==date(2027,3,28)
    assert len(munich_holidays(2026))==13
    assert date(2026,8,15) in munich_holidays(2026)
    assert date(2026,8,8) not in munich_holidays(2026)
