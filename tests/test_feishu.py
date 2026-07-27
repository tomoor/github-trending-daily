import base64

import pytest

import src.feishu as fs
from src.analyzer import Analysis
from src.fetch_trending import TrendingRepo

REPO = TrendingRepo(owner="foo", name="bar", url="https://github.com/foo/bar",
                    stars=100, description="demo")
AN = Analysis(one_liner="一句话", detail_md="详情")


def test_gen_sign_deterministic():
    s1 = fs.gen_sign("secret", 1700000000)
    assert s1 == fs.gen_sign("secret", 1700000000)
    assert s1 != fs.gen_sign("other", 1700000000)
    assert len(base64.b64decode(s1)) == 32  # HmacSHA256 摘要 32 字节


def test_build_card_with_report_url():
    card = fs.build_card("2026-07-27", "总览", [REPO], [AN], "https://example.com/r.md")
    assert card["header"]["title"]["content"] == "GitHub Trending 日报 · 2026-07-27"
    md_texts = [e["content"] for e in card["elements"] if e.get("tag") == "markdown"]
    assert any("总览" in t for t in md_texts)
    assert any("[foo/bar](https://github.com/foo/bar)" in t and "一句话" in t for t in md_texts)
    actions = [e for e in card["elements"] if e.get("tag") == "action"]
    assert actions and actions[0]["actions"][0]["url"] == "https://example.com/r.md"


def test_build_card_without_report_url_or_overview():
    card = fs.build_card("2026-07-27", "", [REPO], [AN], None)
    assert all(e.get("tag") != "action" for e in card["elements"])
    md_texts = [e["content"] for e in card["elements"] if e.get("tag") == "markdown"]
    assert not any("今日看点" in t for t in md_texts)


class FakeResp:
    def __init__(self, code=0, status=200):
        self._code = code
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise fs.requests.HTTPError("http error")

    def json(self):
        return {"code": self._code}


def test_send_card_success_without_secret(monkeypatch):
    sent = {}

    def fake_post(url, json=None, timeout=None):
        sent["url"] = url
        sent["body"] = json
        return FakeResp()

    monkeypatch.setattr(fs.requests, "post", fake_post)
    fs.send_card("https://hook", {"a": 1})
    assert sent["body"]["msg_type"] == "interactive"
    assert sent["body"]["card"] == {"a": 1}
    assert "sign" not in sent["body"]


def test_send_card_with_secret_adds_sign(monkeypatch):
    sent = {}
    monkeypatch.setattr(
        fs.requests, "post",
        lambda url, json=None, timeout=None: sent.update(body=json) or FakeResp())
    fs.send_card("https://hook", {"a": 1}, secret="s")
    assert "sign" in sent["body"] and "timestamp" in sent["body"]


def test_send_card_retries_then_raises(monkeypatch):
    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None):
        calls["n"] += 1
        return FakeResp(code=19001)

    monkeypatch.setattr(fs.requests, "post", fake_post)
    monkeypatch.setattr(fs.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        fs.send_card("https://hook", {})
    assert calls["n"] == 3
