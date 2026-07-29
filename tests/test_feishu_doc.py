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
        raise AssertionError(f"unexpected url: {url}")
    return fake_request


def test_create_daily_doc_success(monkeypatch):
    calls = []
    monkeypatch.setattr(fd.requests, "request", _happy_router(calls))
    result = fd.create_daily_doc("# md 内容", "日报 2026-07-28", "cli_id", "secret")
    assert result == ("doxcnNEW", "https://x.feishu.cn/docx/doxcnNEW")
    urls = [u for _, u, _ in calls]
    assert any("tenant_access_token" in u for u in urls)
    assert any("medias/upload_all" in u for u in urls)
    assert any("permissions/doxcnNEW/public" in u for u in urls)  # 开链接分享
    share_call = next(c for c in calls if "permissions" in c[1])
    assert share_call[2]["json"]["link_share_entity"] == "anyone_readable"


def test_create_daily_doc_mounts_to_folder_env(monkeypatch):
    calls = []
    monkeypatch.setattr(fd.requests, "request", _happy_router(calls))
    monkeypatch.setenv("FEISHU_FOLDER_TOKEN", "FldTest123")
    fd.create_daily_doc("# md", "t", "cli_id", "secret")
    import_call = next(c for c in calls if c[1].endswith("/import_tasks"))
    assert import_call[2]["json"]["point"]["mount_key"] == "FldTest123"


def test_create_daily_doc_default_mount_root(monkeypatch):
    calls = []
    monkeypatch.setattr(fd.requests, "request", _happy_router(calls))
    monkeypatch.delenv("FEISHU_FOLDER_TOKEN", raising=False)
    fd.create_daily_doc("# md", "t", "cli_id", "secret")
    import_call = next(c for c in calls if c[1].endswith("/import_tasks"))
    assert import_call[2]["json"]["point"]["mount_key"] == ""


def test_create_daily_doc_no_delete_calls(monkeypatch):
    # 原地更新策略下 create 只负责创建, 不再删除任何文档
    calls = []
    monkeypatch.setattr(fd.requests, "request", _happy_router(calls))
    result = fd.create_daily_doc("# md", "t", "cli_id", "secret")
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


def _update_router(calls, convert_code=0):
    """update_daily_doc 成功链路路由; blocks 里含带 merge_info 的表格块."""
    def fake_request(method, url, **kw):
        calls.append((method, url, kw))
        if "tenant_access_token" in url:
            return FakeResp({"code": 0, "tenant_access_token": "t"})
        if url.endswith("/blocks/convert"):
            return FakeResp({"code": convert_code, "data": {
                "first_level_block_ids": ["b1", "b2"],
                "blocks": [
                    {"block_id": "b1", "block_type": 2, "text": {}},
                    {"block_id": "b2", "block_type": 31,
                     "table": {"property": {"row_size": 2, "column_size": 2,
                                            "merge_info": [{}]}}},
                ]}})
        if url.endswith("/blocks") and method == "GET":
            return FakeResp({"code": 0, "data": {"items": [
                {"block_id": "docTOKEN", "block_type": 1,
                 "children": ["old1", "old2", "old3"]}], "has_more": False}})
        if "children/batch_delete" in url:
            return FakeResp({"code": 0})
        if url.endswith("/descendant"):
            return FakeResp({"code": 0})
        raise AssertionError(f"unexpected url: {url}")
    return fake_request


def test_update_daily_doc_success(monkeypatch):
    calls = []
    monkeypatch.setattr(fd.requests, "request", _update_router(calls))
    assert fd.update_daily_doc("# 新内容", "docTOKEN", "cli_id", "s") is True
    delete_call = next(c for c in calls if "batch_delete" in c[1])
    assert delete_call[2]["json"] == {"start_index": 0, "end_index": 3}  # 清空旧的 3 个一级块
    desc_call = next(c for c in calls if c[1].endswith("/descendant"))
    body = desc_call[2]["json"]
    assert body["children_id"] == ["b1", "b2"]
    table_block = next(b for b in body["descendants"] if "table" in b)
    assert "merge_info" not in table_block["table"]["property"]  # 只读字段须去除


def test_update_daily_doc_false_on_convert_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(fd.requests, "request", _update_router(calls, convert_code=99))
    assert fd.update_daily_doc("# md", "docTOKEN", "cli_id", "s") is False
    assert not any("batch_delete" in u for _, u, _ in calls)  # 转换失败不动原文档


def test_create_daily_doc_survives_share_failure(monkeypatch):
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
        return FakeResp({"code": 1061004, "msg": "forbidden"})  # 分享失败
    monkeypatch.setattr(fd.requests, "request", fake_request)
    # 文档已创建成功, 分享失败仅降级不影响返回
    assert fd.create_daily_doc("# md", "t", "cli_id", "s") == ("doxcnNEW", "https://u")
