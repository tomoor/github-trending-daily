import json

import requests

import src.deepwiki as dw

def _sse(text):
    payload = {"jsonrpc": "2.0", "id": 1,
               "result": {"content": [{"type": "text", "text": text}], "isError": False}}
    return f"event: message\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


class FakeResp:
    """模拟 requests 对无 charset 的 text/event-stream 的行为:
    content 为 UTF-8 字节, text 按 ISO-8859-1 解码(中文会乱码)。"""

    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.content = text.encode("utf-8")
        self.text = self.content.decode("iso-8859-1")


def test_fetch_summary_ok(monkeypatch):
    sent = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        sent["url"] = url
        sent["body"] = json
        return FakeResp(text=_sse("这个项目是一个终端文件管理器。"))

    monkeypatch.setattr(dw.requests, "post", fake_post)
    result = dw.fetch_deepwiki_summary("yorukot", "superfile")
    assert result == "这个项目是一个终端文件管理器。"
    assert sent["url"] == "https://mcp.deepwiki.com/mcp"
    assert sent["body"]["params"]["arguments"]["repoName"] == "yorukot/superfile"


def test_fetch_summary_none_when_not_indexed(monkeypatch):
    monkeypatch.setattr(
        dw.requests, "post",
        lambda url, **kw: FakeResp(text=_sse(
            "Error processing question: Repository not found. Visit https://deepwiki.com")))
    assert dw.fetch_deepwiki_summary("o", "r") is None


def test_fetch_summary_none_on_http_error(monkeypatch):
    monkeypatch.setattr(dw.requests, "post", lambda url, **kw: FakeResp(status_code=500))
    assert dw.fetch_deepwiki_summary("o", "r") is None


def test_fetch_summary_none_on_network_error(monkeypatch):
    def boom(url, **kw):
        raise requests.ConnectionError("net down")

    monkeypatch.setattr(dw.requests, "post", boom)
    assert dw.fetch_deepwiki_summary("o", "r") is None


def test_fetch_summary_none_on_malformed_response(monkeypatch):
    monkeypatch.setattr(dw.requests, "post",
                        lambda url, **kw: FakeResp(text="event: message\ndata: not-json\n\n"))
    assert dw.fetch_deepwiki_summary("o", "r") is None


def test_fetch_summary_skips_pings_and_notifications(monkeypatch):
    notification = json.dumps({"method": "notifications/message",
                               "params": {"level": "info", "data": "working"}})
    raw = (": ping - 2026-07-28 10:17:30\r\n\r\n"
           f"event: message\r\ndata: {notification}\r\n\r\n"
           + _sse("最终解读内容").replace("\n", "\r\n"))
    monkeypatch.setattr(dw.requests, "post", lambda url, **kw: FakeResp(text=raw))
    assert dw.fetch_deepwiki_summary("o", "r") == "最终解读内容"
