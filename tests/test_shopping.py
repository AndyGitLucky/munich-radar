from pathlib import Path
from datetime import datetime
import pytest
from src.collectors.shopping import ShoppingCollector
from src.normalize import BERLIN, normalize_event

LAW=(Path(__file__).parent/'fixtures/shopping_law.html').read_text(encoding='utf-8')
OVERVIEW='<h1>Shopping-Nächte München 2026</h1><ul><li>Freitag, 30. Oktober 2026 | Freitag vor den Herbstferien</li><li>Freitag, 27. November 2026</li><li>Samstag, 12. Dezember 2026</li></ul>'
CONFIG={'name':'München Shopping','url':'https://www.muenchen.de/shopping','law_url':'https://stadt.muenchen.de/law','festival_url':'https://www.muenchen.de/veranstaltungen/oktoberfest','horizon_days':30}

def source(day):return ShoppingCollector(CONFIG,None,datetime.fromisoformat(day).replace(tzinfo=BERLIN))

def test_shopping_night_actual_date_exclusive_midnight_and_caveat():
    s=source('2026-10-01'); events=s.parse(OVERVIEW,LAW)
    event=next(e for e in events if 'Shoppingnacht' in e.title)
    assert event.start=='2026-10-30T20:00:00' and event.end=='2026-10-31T00:00:00'
    assert normalize_event(event,s.now).start.endswith('+01:00')
    assert 'Teilnahme einzelner Geschäfte nicht bestätigt' in event.description
    assert event.address is None and event.is_free is None and event.tags==['shopping']

def test_only_munich_and_restricted_goods_not_general_open_sunday():
    events=source('2026-09-26').parse(OVERVIEW,LAW)
    tourism=[e for e in events if e.start.startswith('2026-09-27')]
    assert len(tourism)==2
    assert all('Nur' in e.description and 'Kein allgemeiner' in e.description for e in tourism)
    assert all('shopping' in e.tags and 'food' not in e.tags for e in events)
    assert not any('Altstadt' in e.title and e.start.startswith('2026-10-18') for e in events)
    assert any('Olympiapark' in e.title and e.start.startswith('2026-10-18') for e in events)
    assert any(e.title.startswith('3. Oktober') and 'Maxvorstadt' in e.description for e in events)

def test_advent_christmas_eve_and_good_friday_exceptions():
    events=source('2028-12-01').parse(OVERVIEW,LAW)
    event=next(e for e in events if 'Altstadt' in e.title and e.start.startswith('2028-12-24'))
    assert event.end=='2028-12-24T14:00:00'
    assert not any(e.start.startswith('2028-12-25') for e in events)
    events=source('2026-04-01').parse(OVERVIEW,LAW)
    assert not any(e.start.startswith('2026-04-03') for e in events)
    assert any(e.start.startswith('2026-04-06') for e in events)

def test_changed_law_or_undated_overview_fails_closed():
    with pytest.raises(ValueError,match='geändert'):
        source('2026-09-26').parse(OVERVIEW,LAW.replace('11.00 bis 19.00','11.00 bis 20.00'))
    with pytest.raises(ValueError,match='expliziten'):
        source('2026-09-26').parse('<h1>Shopping-Nächte</h1><p>Veröffentlicht am 30. Oktober 2026</p>',LAW)

def test_fasching_and_horizon():
    events=source('2026-02-01').parse(OVERVIEW,LAW)
    assert len(events)==1 and events[0].start=='2026-02-15T12:00:00'
    assert 'Scherzartikel' in events[0].description


def test_first_oktoberfest_sunday_requires_published_festival_dates():
    s=source('2026-09-01')
    events=s.parse(OVERVIEW,LAW,'<p>Vom 19. September bis 4. Oktober 2026 feiert München.</p>')
    event=next(e for e in events if 'Erster Oktoberfestsonntag' in e.title)
    assert event.start=='2026-09-20T11:00:00'
    assert 'Datumsquelle:' in event.description
    events=s.parse(OVERVIEW,LAW,'<p>Die nächsten Termine sind noch offen.</p>')
    assert not any('Erster Oktoberfestsonntag' in e.title for e in events)
    assert s.warnings
