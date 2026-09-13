import time
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests


class PoliteHttpClient:
    """Same-origin redirects, robots checks, timeouts and one request per second."""

    def __init__(self, config: dict, origins: set[str]):
        self.session = requests.Session()
        self.user_agent = config["user_agent"]
        self.session.headers["User-Agent"] = self.user_agent
        self.timeout = config["timeout"]
        self.interval = config["min_interval"]
        self.origins = origins
        self.robots: dict[str, RobotFileParser] = {}
        self.last_request: dict[str, float] = {}

    def _request(self, url: str, interval: float, *, method="GET", json=None, headers=None) -> requests.Response:
        for _ in range(5):
            parsed = urlsplit(url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            if origin not in self.origins or parsed.username or parsed.password:
                raise ValueError("Request outside configured source origins")
            time.sleep(max(0, interval - (time.monotonic() - self.last_request.get(origin, 0))))
            self.last_request[origin] = time.monotonic()
            if method == "GET":
                response = self.session.get(url, timeout=self.timeout, allow_redirects=False)
            else:
                response = self.session.post(url, json=json, headers=headers, timeout=self.timeout, allow_redirects=False)
            if response.is_redirect:
                if method != "GET":
                    raise ValueError("Search POST redirects refused")
                target = urljoin(url, response.headers["Location"])
                if urlsplit(target).netloc != parsed.netloc:
                    raise ValueError("Cross-origin redirect refused")
                rules = self.robots.get(origin)
                if rules and not rules.can_fetch(self.user_agent, target):
                    raise PermissionError("Redirect blocked by robots.txt")
                url = target
                continue
            return response
        raise ValueError("Too many redirects")

    def get(self, url: str) -> str:
        return self._fetch(url)

    def post(self, url: str, *, json: dict, headers: dict) -> str:
        """Public search only; identical origin, robots and throttling checks as GET."""
        return self._fetch(url, method="POST", json=json, headers=headers)

    def _fetch(self, url: str, *, method="GET", json=None, headers=None) -> str:
        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self.robots:
            response = self._request(f"{origin}/robots.txt", self.interval)
            rules = RobotFileParser()
            if response.status_code == 404:
                rules.parse([])
            elif response.status_code in {401, 403}:
                rules.disallow_all = True
            else:
                response.raise_for_status()
                rules.parse(response.text.splitlines())
            self.robots[origin] = rules
        rules = self.robots[origin]
        if not rules.can_fetch(self.user_agent, url):
            raise PermissionError("Blocked by robots.txt")
        delay = max(self.interval, rules.crawl_delay(self.user_agent) or 0)
        rate = rules.request_rate(self.user_agent)
        if rate:
            delay = max(delay, rate.seconds / rate.requests)
        response = self._request(url, delay, method=method, json=json, headers=headers)
        response.raise_for_status()
        if not response.content:
            raise ValueError("Empty HTTP response")
        # These official sources declare UTF-8; requests otherwise defaults to Latin-1.
        response.encoding = "utf-8"
        return response.text
