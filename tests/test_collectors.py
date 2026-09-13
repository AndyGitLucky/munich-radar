from pathlib import Path

import pytest

from src.collectors.deutsches_museum import DeutschesMuseumCollector
from src.collectors.gasteig import GasteigCollector
from src.collectors.lenbachhaus import LenbachhausCollector, german_date_range

FIXTURES=Path(__file__).parent/"fixtures"


def config(name):
    return {"name":name,"url":"https://example.org/calendar","priority":10}


def test_gasteig_jsonld_preserves_source_facts(now):
    collector=GasteigCollector(config("Gasteig"),None,now)
    events=collector.parse((FIXTURES/"gasteig.html").read_text(encoding="utf-8"),"https://www.gasteig.de/veranstaltungen/we-are-video-spark-2/",["Ausstellung","Gratis"])
    assert len(events)==1
    assert events[0].start=="2026-07-27T00:00:00+02:00"
    assert events[0].is_free is True
    assert events[0].all_day
    assert events[0].category=="exhibition"


def test_museum_fixture_has_real_dates_and_unknown_prices(now):
    events=DeutschesMuseumCollector(config("Deutsches Museum"),None,now).parse((FIXTURES/"deutsches_museum.html").read_text(encoding="utf-8"))
    assert len(events)==4
    assert events[0].start=="2026-09-13T09:00:00"
    assert events[0].is_free is None
    assert "recurring" in events[0].tags
    assert events[-1].title=="Bergbau-VR-Erlebnis"


def test_lenbachhaus_omits_undated_and_marks_canceled(now):
    events=LenbachhausCollector(config("Lenbachhaus"),None,now).parse((FIXTURES/"lenbachhaus.html").read_text(encoding="utf-8"))
    assert events
    assert all(e.start for e in events)
    assert any(e.status=="cancelled" for e in events)
    assert any(e.title=="Up in die Laterne!" and e.start=="2026-09-13T13:00:00" for e in events)


@pytest.mark.parametrize("value,start,end",[("So, 13. September 2026, 13–16 Uhr","2026-09-13T13:00:00","2026-09-13T16:00:00"),("Do, 10. September 2026, 18–19.30 Uhr","2026-09-10T18:00:00","2026-09-10T19:30:00"),("Sa, 17. Oktober 2026, 18–1 Uhr","2026-10-17T18:00:00","2026-10-18T01:00:00")])
def test_german_date_ranges(value,start,end):
    assert german_date_range(value)==(start,end,False)


def test_changed_html_does_not_silently_succeed(now):
    with pytest.raises(ValueError):
        DeutschesMuseumCollector(config("Museum"),None,now).parse("<html>Oops</html>")


def test_malformed_jsonld_does_not_hide_valid_event(now):
    html='<script type="application/ld+json">oops</script>'+(FIXTURES/"gasteig.html").read_text(encoding="utf-8")
    assert len(GasteigCollector(config("Gasteig"),None,now).parse(html,"https://example.org/e",[]))==1
