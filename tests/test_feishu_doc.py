import pytest

import src.feishu_doc as fd


class FakeResp:
    def __init__(self, json_data=None, status_code=200):
        self._json = json_data or {}
        self.status_code = status_code

    def json(self):
        return self._json


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(fd.time, "sleep", lambda s: None)


def _happy_router(calls):
    """按 URL 路由的成功响应, 并记录调用."""
    def fake_request(method, url, **kw):
        calls.append((method, url, kw))
        if "tenant_access_token" in url:
            return FakeResp({"code": 0, "tenant_access_token": "t-token"})
        if "medias/upload_all" in url:
            return FakeResp({"code": 0, "data": {"file_token": "file123"}})
        if url.endswith("/import_tasks"):
            return FakeResp({"code": 0, "data": {"ticket": "ticket123"}})
        if "import_tasks/ticket123" in url:
            return FakeResp({"code": 0, "data": {"result": {
                "job_status": 0, "token": "doxcnNEW",
                "url": "https://x.feishu.cn/docx/doxcnNEW"}}})
        if "permissions/doxcnNEW/public" in url:
            return FakeResp({"code": 0})
        if "files/doxcnOLD" in url:
            return FakeResp({"code": 0})
        raise AssertionError(f"unexpected url: {url}")
    return fake_request


def test_create_daily_doc_success(monkeypatch):
    calls = []
    monkeypatch.setattr(fd.requests, "request", _happy_router(calls))
    result = fd.create_daily_doc("# md 内容", "日报 2026-07-28",
                                 "cli_id", "secret", old_doc_token="doxcnOLD")
    assert result == ("doxcnNEW", "https://x.feishu.cn/docx/doxcnNEW")
    urls = [u for _, u, _ in calls]
    assert any("tenant_access_token" in u for u in urls)
    assert any("medias/upload_all" in u for u in urls)
    assert any("permissions/doxcnNEW/public" in u for u in urls)  # 开链接分享
    assert any("files/doxcnOLD" in u for u in urls)               # 删除旧文档
    share_call = next(c for c in calls if "permissions" in c[1])
    assert share_call[2]["json"]["link_share_entity"] == "anyone_readable"


def test_create_daily_doc_no_old_token_skips_delete(monkeypatch):
    calls = []
    monkeypatch.setattr(fd.requests, "request", _happy_router(calls))
    result = fd.create_daily_doc("# md", "t", "cli_id", "secret", old_doc_token=None)
    assert result is not None
    assert not any("files/" in u for _, u, _ in calls)


def test_create_daily_doc_none_when_token_fails(monkeypatch):
    monkeypatch.setattr(
        fd.requests, "request",
        lambda method, url, **kw: FakeResp({"code": 99991663, "msg": "app not found"}))
    assert fd.create_daily_doc("# md", "t", "cli_id", "bad") is None


def test_create_daily_doc_none_when_import_job_fails(monkeypatch):
    def fake_request(method, url, **kw):
        if "tenant_access_token" in url:
            return FakeResp({"code": 0, "tenant_access_token": "t"})
        if "medias/upload_all" in url:
            return FakeResp({"code": 0, "data": {"file_token": "f"}})
        if url.endswith("/import_tasks"):
            return FakeResp({"code": 0, "data": {"ticket": "tk"}})
        return FakeResp({"code": 0, "data": {"result": {"job_status": 102,
                                                        "job_error_msg": "failed"}}})
    monkeypatch.setattr(fd.requests, "request", fake_request)
    assert fd.create_daily_doc("# md", "t", "cli_id", "s") is None


def test_create_daily_doc_survives_share_and_delete_failure(monkeypatch):
    def fake_request(method, url, **kw):
        if "tenant_access_token" in url:
            return FakeResp({"code": 0, "tenant_access_token": "t"})
        if "medias/upload_all" in url:
            return FakeResp({"code": 0, "data": {"file_token": "f"}})
        if url.endswith("/import_tasks"):
            return FakeResp({"code": 0, "data": {"ticket": "tk"}})
        if "import_tasks/tk" in url:
            return FakeResp({"code": 0, "data": {"result": {
                "job_status": 0, "token": "doxcnNEW", "url": "https://u"}}})
        return FakeResp({"code": 1061004, "msg": "forbidden"})  # 分享/删除失败
    monkeypatch.setattr(fd.requests, "request", fake_request)
    # 文档已创建成功, 分享/删除失败仅降级不影响返回
    assert fd.create_daily_doc("# md", "t", "cli_id", "s", "doxcnOLD") == (
        "doxcnNEW", "https://u")
