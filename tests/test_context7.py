import requests

import src.context7 as c7

SEARCH_DATA = {
    "results": [
        {"id": "/superfly/docs", "title": "Fly.io", "description": "wrong project"},
        {"id": "/yorukot/superfile", "title": "superfile",
         "description": "superfile is a modern terminal file manager."},
    ]
}


class FakeResp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data

    def json(self):
        return self._json


def test_fetch_description_matches_repo_id(monkeypatch):
    monkeypatch.setattr(c7.requests, "get",
                        lambda url, **kw: FakeResp(json_data=SEARCH_DATA))
    result = c7.fetch_context7_description("yorukot", "superfile")
    assert result == "superfile is a modern terminal file manager."


def test_fetch_description_none_when_no_match(monkeypatch):
    monkeypatch.setattr(c7.requests, "get",
                        lambda url, **kw: FakeResp(json_data=SEARCH_DATA))
    assert c7.fetch_context7_description("other", "unknown-repo") is None


def test_fetch_description_none_on_http_error(monkeypatch):
    monkeypatch.setattr(c7.requests, "get", lambda url, **kw: FakeResp(status_code=429))
    assert c7.fetch_context7_description("o", "r") is None


def test_fetch_description_none_on_network_error(monkeypatch):
    def boom(url, **kw):
        raise requests.ConnectionError("net down")

    monkeypatch.setattr(c7.requests, "get", boom)
    assert c7.fetch_context7_description("o", "r") is None
