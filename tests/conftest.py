from datetime import datetime

import pytest

from src.models import RawEvent
from src.normalize import BERLIN, normalize_event


@pytest.fixture
def now():
    return datetime(2026, 9, 13, 12, tzinfo=BERLIN)


@pytest.fixture
def make_event(now):
    def make(**changes):
        fields = dict(title="Wissenschaft zum Anfassen", source_name="Museum", source_url="https://example.org/event",
                      start="2026-09-13T13:00:00+02:00", end="2026-09-13T16:00:00+02:00", location_name="Museumsinsel", category="science")
        fields.update(changes)
        return normalize_event(RawEvent(**fields), now)
    return make
