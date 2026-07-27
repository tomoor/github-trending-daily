import requests

import src.github_readme as gr


class FakeResp:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


def test_fetch_readme_truncates(monkeypatch):
    monkeypatch.setattr(gr.requests, "get", lambda url, **kw: FakeResp(text="x" * 9000))
    result = gr.fetch_readme("o", "r", max_chars=5000)
    assert len(result) == 5000


def test_fetch_readme_none_on_404(monkeypatch):
    monkeypatch.setattr(gr.requests, "get", lambda url, **kw: FakeResp(status_code=404))
    assert gr.fetch_readme("o", "r") is None


def test_fetch_readme_none_on_network_error(monkeypatch):
    def boom(url, **kw):
        raise requests.ConnectionError("net down")

    monkeypatch.setattr(gr.requests, "get", boom)
    assert gr.fetch_readme("o", "r") is None


def test_fetch_readme_none_on_empty_body(monkeypatch):
    monkeypatch.setattr(gr.requests, "get", lambda url, **kw: FakeResp(text="   "))
    assert gr.fetch_readme("o", "r") is None


def test_fetch_readme_sends_token(monkeypatch):
    seen = {}

    def fake_get(url, headers=None, timeout=None):
        seen["url"] = url
        seen["headers"] = headers
        return FakeResp(text="hello")

    monkeypatch.setattr(gr.requests, "get", fake_get)
    monkeypatch.setenv("GITHUB_TOKEN", "t0k3n")
    assert gr.fetch_readme("o", "r") == "hello"
    assert seen["url"] == "https://api.github.com/repos/o/r/readme"
    assert seen["headers"]["Authorization"] == "Bearer t0k3n"
