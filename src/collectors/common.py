import json
import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import RawEvent
from ..normalize import clean_text

logger = logging.getLogger(__name__)


def structured_events(html: str) -> list[dict]:
    def walk(value):
        if isinstance(value, list):
            for item in value:
                yield from walk(item)
        elif isinstance(value, dict):
            types = value.get("@type", [])
            if isinstance(types, str):
                types = [types]
            if any(t.endswith("Event") for t in types):
                yield value
            else:
                for item in value.values():
                    if isinstance(item, (dict, list)):
                        yield from walk(item)

    result = []
    for script in BeautifulSoup(html, "html.parser").select('script[type="application/ld+json"]'):
        try:
            result.extend(walk(json.loads(script.get_text())))
        except (ValueError, TypeError):
            logger.warning("Malformed JSON-LD block skipped")
    return result


def from_jsonld(item: dict, config: dict, url: str) -> RawEvent:
    location = item.get("location") or {}
    if isinstance(location, list):
        location = location[0] if location else {}
    if isinstance(location, str):
        location = {"name": location}
    address = location.get("address") or {}
    if isinstance(address, dict):
        address = ", ".join(str(address[k]) for k in ("streetAddress", "postalCode", "addressLocality") if address.get(k)) or None
    image = item.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    if isinstance(image, dict):
        image = image.get("url")
    offers = item.get("offers") or []
    if isinstance(offers, dict):
        offers = [offers]
    prices = [str(o["price"]) for o in offers if isinstance(o, dict) and o.get("price") is not None]
    free = item.get("isAccessibleForFree")
    free = free if isinstance(free, bool) else None
    price_text = None
    if prices:
        # A free ticket tier does not make a mixed-price event free for everyone.
        free = all(float(p) == 0 for p in prices)
        currencies = {o.get("priceCurrency") for o in offers if o.get("price") is not None}
        if free:
            price_text = "Kostenlos"
        elif currencies == {"EUR"}:
            price_text = f"Ab {min(float(p) for p in prices):g} €"
    start = item.get("startDate")
    end = item.get("endDate")
    all_day = bool(start and (len(start) == 10 or ("T00:00:00" in start and end and "T23:59" in end)))
    status = "cancelled" if str(item.get("eventStatus", "")).endswith("EventCancelled") else "scheduled"
    if str(item.get("eventStatus", "")).endswith("EventPostponed"):
        status = "postponed"
    return RawEvent(title=clean_text(item.get("name")) or "", source_name=config["name"], source_url=item.get("url") or url,
                    start=start, end=end, all_day=all_day, description=clean_text(item.get("description")),
                    location_name=location.get("name"), address=address, is_free=free, price_text=price_text,
                    image_url=urljoin(url, image) if image else None, source_priority=config.get("priority", 100), status=status)


def tag_topics(labels: list[str], fallback: str = "culture") -> tuple[str, list[str]]:
    text = " ".join(labels).casefold()
    rules = [("street_festival", ("straßenfest", "strassenfest")), ("festival", ("festival",)),
             ("market", ("markt", "dult")), ("exhibition", ("ausstellung", "installation")),
             ("science", ("wissenschaft", "wissen", "science")), ("technology", ("technik", "technologie", "robotik", "robotics")),
             ("family", ("familie", "kinder", "jugend")), ("concert", ("musik", "konzert", "klassik")),
             ("theatre", ("theater",)), ("outdoor", ("outdoor",))]
    tags = [category for category, words in rules if any(word in text for word in words)]
    if "highlight" in text:
        tags.append("major_event")
    return next((category for category, _ in rules if category in tags), fallback), tags
