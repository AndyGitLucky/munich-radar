from pathlib import Path

import pytest
import yaml

from src.collectors.corso_leopold import CorsoLeopoldCollector
from src.normalize import normalize_event
from src.pipeline import mark_recurring
from src.scoring import score
from src.views import classify, select

ROOT = Path(__file__).parents[1]
URL = "https://www.corso-leopold.de/cl/programm/2026-September.php"


@pytest.fixture
def html():
    return (Path(__file__).parent / "fixtures/corso_leopold.html").read_text(encoding="utf-8")


@pytest.fixture
def collector(now):
    return CorsoLeopoldCollector({"name": "Corso Leopold", "priority": 10}, None, now)


def test_daily_hours_do_not_use_music_end_time(collector, html):
    events = collector.parse(html, URL)
    assert [(e.start, e.end) for e in events] == [
        ("2026-09-12T16:00:00", "2026-09-12T23:00:00"),
        ("2026-09-13T11:00:00", "2026-09-13T21:00:00"),
    ]
    assert events[1].title == "Corso Leopold"
    assert events[1].location_name == "Leopoldstraße"
    assert events[1].family_friendly is True
    assert events[1].is_free is None  # No admission claim on the program page.


def test_discovers_current_edition_without_fixed_year_or_archive():
    home = '''<a href="/cl/programm/2023September.php">Corso Leopold - September 2023</a>
    <a href="/cl/programm/2027-Mai.php?navid=123">Corso Leopold Mai 2027</a>'''
    assert CorsoLeopoldCollector.program_url(home, "https://www.corso-leopold.de/") == "https://www.corso-leopold.de/cl/programm/2027-Mai.php"


def test_rejects_external_program_link():
    with pytest.raises(ValueError):
        CorsoLeopoldCollector.program_url('<a href="https://other.example/cl/programm/fake.php">Corso Leopold Mai 2027</a>', "https://www.corso-leopold.de/")


def test_partial_schedule_fails_instead_of_inventing_hours(collector, html):
    with pytest.raises(ValueError):
        collector.parse(html.replace("11.00 Uhr bis 21:00 Uhr", "Zeiten folgen"), URL)


def test_festival_days_not_recurring_and_sunday_recommended(collector, html, now, make_event):
    config = yaml.safe_load((ROOT / "config/relevance.yaml").read_text(encoding="utf-8"))
    events = [normalize_event(e, now) for e in collector.parse(html, URL)]
    mark_recurring(events)
    assert all("recurring" not in e.tags for e in events)
    sunday = score(events[1], config, now)
    assert {"today", "weekend"} <= set(classify(sunday, now))
    museum = score(make_event(family_friendly=True), config, now)
    chosen = select([museum, sunday], config["selection"])
    assert chosen[0].title == "Corso Leopold"
    assert "Termin an diesem Wochenende" in sunday.relevance_reasons
