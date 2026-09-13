from dataclasses import asdict, dataclass, field

CATEGORIES = frozenset("festival street_festival museum exhibition science technology family children market flea_market culture concert theatre food seasonal outdoor city_event public_event other".split())


@dataclass
class RawEvent:
    title: str
    source_name: str
    source_url: str
    start: str | None = None
    end: str | None = None
    description: str | None = None
    location_name: str | None = None
    address: str | None = None
    district: str | None = None
    category: str = "other"
    tags: list[str] = field(default_factory=list)
    price_text: str | None = None
    is_free: bool | None = None
    family_friendly: bool | None = None
    image_url: str | None = None
    # Explicit additions to PROJECT.md: preserve date precision and provenance.
    all_day: bool = False
    source_priority: int = 100
    series_id: str | None = None
    status: str = "scheduled"


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    priority: int = 100


@dataclass
class Event(RawEvent):
    id: str = ""
    discovered_at: str = ""
    updated_at: str = ""
    relevance_score: float = 0
    relevance_reasons: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    stale: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        values = dict(data)
        values["sources"] = [Source(**s) for s in values.get("sources", [])]
        return cls(**values)
