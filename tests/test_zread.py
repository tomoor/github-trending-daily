import requests

import src.zread as zr

HTML = ('<html><head><meta property="og:description" '
        'content="Superfile is a modern terminal file manager."/></head>'
        "<body></body></html>")


class FakeResp:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


def test_fetch_description_ok(monkeypatch):
    seen = {}

    def fake_get(url, headers=None, timeout=None):
        seen["url"] = url
        return FakeResp(text=HTML)

    monkeypatch.setattr(zr.requests, "get", fake_get)
    result = zr.fetch_zread_description("yorukot", "superfile")
    assert result == "Superfile is a modern terminal file manager."
    assert seen["url"] == "https://zread.ai/yorukot/superfile"


def test_fetch_description_none_without_meta(monkeypatch):
    monkeypatch.setattr(zr.requests, "get",
                        lambda url, **kw: FakeResp(text="<html><body>no meta</body></html>"))
    assert zr.fetch_zread_description("o", "r") is None


def test_fetch_description_none_on_http_error(monkeypatch):
    monkeypatch.setattr(zr.requests, "get", lambda url, **kw: FakeResp(status_code=404))
    assert zr.fetch_zread_description("o", "r") is None


def test_fetch_description_none_on_network_error(monkeypatch):
    def boom(url, **kw):
        raise requests.ConnectionError("net down")

    monkeypatch.setattr(zr.requests, "get", boom)
    assert zr.fetch_zread_description("o", "r") is None
