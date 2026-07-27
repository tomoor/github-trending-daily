import pytest
import requests

import src.fetch_trending as ft

NEWSNOW_DATA = {
    "status": "success",
    "items": [
        {"url": "https://github.com/foo/bar", "title": "foo /  bar", "id": "/foo/bar",
         "extra": {"info": "✰ 31,374", "hover": "a demo repo"}},
        {"url": "https://github.com/a/b", "title": "a / b", "id": "/a/b",
         "extra": {"info": "✰ 5", "hover": ""}},
        {"url": "https://github.com/bad", "title": "bad", "id": "/bad", "extra": {}},
    ],
}


class FakeResp:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self._json is None:
            raise ValueError("not json")
        return self._json


def test_parse_stars():
    assert ft.parse_stars("✰ 31,374") == 31374
    assert ft.parse_stars("5") == 5
    assert ft.parse_stars("") == 0
    assert ft.parse_stars(None) == 0


def test_parse_newsnow_skips_invalid_id():
    repos = ft._parse_newsnow(NEWSNOW_DATA)
    assert len(repos) == 2
    assert repos[0].owner == "foo" and repos[0].name == "bar"
    assert repos[0].full_name == "foo/bar"
    assert repos[0].stars == 31374
    assert repos[0].description == "a demo repo"
    assert repos[1].description == ""


def test_parse_trending_html(trending_html):
    repos = ft._parse_trending_html(trending_html)
    assert len(repos) == 2
    assert repos[0].url == "https://github.com/foo/bar"
    assert repos[0].stars == 31374
    assert repos[0].description == "a demo repo"
    assert repos[1].description == ""


def test_fetch_trending_newsnow_ok(monkeypatch):
    monkeypatch.setattr(ft.requests, "get",
                        lambda url, **kw: FakeResp(json_data=NEWSNOW_DATA))
    assert len(ft.fetch_trending()) == 2


def test_fetch_trending_fallback_to_github(monkeypatch, trending_html):
    def fake_get(url, **kw):
        if "newsnow" in url:
            return FakeResp(status_code=403, text="blocked")
        return FakeResp(text=trending_html)

    monkeypatch.setattr(ft.requests, "get", fake_get)
    repos = ft.fetch_trending()
    assert len(repos) == 2
    assert repos[0].full_name == "foo/bar"


def test_fetch_trending_both_fail(monkeypatch):
    monkeypatch.setattr(ft.requests, "get", lambda url, **kw: FakeResp(status_code=500))
    with pytest.raises(Exception):
        ft.fetch_trending()
