import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Protocol

from ..models import RawEvent

logger = logging.getLogger(__name__)


class HttpClient(Protocol):
    def get(self, url: str) -> str: ...
    def post(self, url: str, *, json: dict, headers: dict) -> str: ...


class EventCollector(ABC):
    def __init__(self, config: dict, client: HttpClient, now: datetime):
        self.config = config
        self.client = client
        self.now = now
        self.warnings: list[str] = []
        self.empty_is_valid = False

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        logger.warning("%s: %s", self.config["name"], message)

    @abstractmethod
    def collect(self) -> list[RawEvent]: ...
