from unittest.mock import Mock

import pytest
import requests

from src.http import PoliteHttpClient


def response(status=200, body="{}", location=None):
    item = requests.Response()
    item.status_code = status
    item._content = body.encode()
    item.url = "https://calendar.example/search"
    if location:
        item.headers["Location"] = location
    return item


def client(robots="User-agent: *\nAllow: /", post_response=None):
    c = PoliteHttpClient({"user_agent": "MunichRadar", "timeout": 20, "min_interval": 0}, {"https://calendar.example"})
    c.session = Mock()
    c.session.get.return_value = response(body=robots)
    c.session.post.return_value = post_response or response()
    return c


def test_public_search_checks_robots_and_sends_read_only_query():
    c = client()
    assert c.post("https://calendar.example/search", json={"query": ""}, headers={}) == "{}"
    c.session.get.assert_called_once_with("https://calendar.example/robots.txt", timeout=20, allow_redirects=False)
    c.session.post.assert_called_once_with("https://calendar.example/search", json={"query": ""}, headers={}, timeout=20, allow_redirects=False)


def test_search_cannot_bypass_robots():
    c = client("User-agent: *\nDisallow: /search")
    with pytest.raises(PermissionError):
        c.post("https://calendar.example/search", json={}, headers={})
    c.session.post.assert_not_called()


def test_explicit_legacy_charset_and_utf8_default():
    legacy = response()
    legacy._content = '§ 4 München'.encode('cp1252')
    legacy.headers['Content-Type'] = 'text/html;charset=windows-1252'
    legacy.encoding = requests.utils.get_encoding_from_headers(legacy.headers)
    c = client(post_response=legacy)
    assert c.post('https://calendar.example/search',json={},headers={}) == '§ 4 München'
    c = client(post_response=response(body='München'))
    assert c.post('https://calendar.example/search',json={},headers={}) == 'München'


def test_search_cannot_leak_headers_to_other_origin_or_redirect():
    c = client()
    with pytest.raises(ValueError):
        c.post("https://unconfigured.example/search", json={}, headers={"Authorization": "public-search-value"})
    c.session.post.assert_not_called()
    c = client(post_response=response(302, location="https://elsewhere.example/"))
    with pytest.raises(ValueError, match="redirects refused"):
        c.post("https://calendar.example/search", json={}, headers={"Authorization": "public-search-value"})
    assert c.session.post.call_count == 1
