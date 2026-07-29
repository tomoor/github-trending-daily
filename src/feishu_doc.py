"""通过飞书自建应用将日报 markdown 导入为云文档(docx)并开启链接分享.

流程: tenant_access_token → 上传 md 素材 → 创建导入任务 → 轮询结果
      → 开启「互联网获得链接可阅读」 → 删除当天旧文档(保持每天一个)
任何关键步骤失败返回 None, 调用方回退 GitHub 日报链接, 不中断推送。
"""
from __future__ import annotations

import json
import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

BASE = "https://open.feishu.cn/open-apis"
TIMEOUT = 30
POLL_INTERVAL = 2
POLL_MAX = 15  # 最长约 30 秒


def _api(method: str, url: str, **kwargs) -> dict | None:
    """调用飞书 API, 返回 code==0 的响应 JSON, 失败返回 None."""
    try:
        resp = requests.request(method, url, timeout=TIMEOUT, **kwargs)
        data = resp.json()
    except (requests.RequestException, ValueError):
        logger.warning("飞书 API 请求异常 %s", url, exc_info=True)
        return None
    if data.get("code") != 0:
        logger.warning("飞书 API 返回错误 %s: %s", url, data)
        return None
    return data


def _get_tenant_token(app_id: str, app_secret: str) -> str | None:
    data = _api("POST", f"{BASE}/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret})
    return data.get("tenant_access_token") if data else None


def _upload_md(token: str, title: str, md_content: str) -> str | None:
    content = md_content.encode("utf-8")
    data = _api(
        "POST", f"{BASE}/drive/v1/medias/upload_all",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "file_name": f"{title}.md",
            "parent_type": "ccm_import_open",
            "size": str(len(content)),
            "extra": json.dumps({"obj_type": "docx", "file_extension": "md"}),
        },
        files={"file": content},
    )
    return data["data"]["file_token"] if data else None


def _import_as_docx(token: str, file_token: str, title: str) -> tuple[str, str] | None:
    headers = {"Authorization": f"Bearer {token}"}
    data = _api("POST", f"{BASE}/drive/v1/import_tasks", headers=headers, json={
        "file_extension": "md",
        "file_token": file_token,
        "type": "docx",
        "file_name": title,
        # FEISHU_FOLDER_TOKEN: 挂载到用户共享文件夹(长效浏览入口), 未配置则应用空间根目录
        "point": {"mount_type": 1,
                  "mount_key": os.environ.get("FEISHU_FOLDER_TOKEN", "")},
    })
    if not data:
        return None
    ticket = data["data"]["ticket"]
    for _ in range(POLL_MAX):
        data = _api("GET", f"{BASE}/drive/v1/import_tasks/{ticket}", headers=headers)
        if not data:
            return None
        result = data["data"]["result"]
        status = result.get("job_status")
        if status == 0:
            return result["token"], result["url"]
        if status not in (1, 2):  # 1 初始化 2 处理中, 其余为失败
            logger.warning("飞书导入任务失败: %s", result)
            return None
        time.sleep(POLL_INTERVAL)
    logger.warning("飞书导入任务超时: ticket=%s", ticket)
    return None


def _enable_link_share(token: str, doc_token: str) -> None:
    """互联网获得链接可阅读(群含外部成员); 失败仅降级为组织内可见, 不影响主流程."""
    _api("PATCH", f"{BASE}/drive/v2/permissions/{doc_token}/public",
         headers={"Authorization": f"Bearer {token}"},
         params={"type": "docx"},
         json={"external_access_entity": "open", "link_share_entity": "anyone_readable"})


def update_daily_doc(md_content: str, doc_token: str,
                     app_id: str, app_secret: str) -> bool:
    """原地替换已有文档内容(URL 不变, 历史卡片链接始终有效).

    流程: markdown 转块 → 清空文档一级块 → 插入新块。失败返回 False,
    调用方保留旧文档(内容略旧但链接可用), 下次运行自动重试。
    """
    token = _get_tenant_token(app_id, app_secret)
    if not token:
        return False
    headers = {"Authorization": f"Bearer {token}"}

    data = _api("POST", f"{BASE}/docx/v1/documents/blocks/convert", headers=headers,
                json={"content_type": "markdown", "content": md_content})
    if not data:
        return False
    children_ids = data["data"]["first_level_block_ids"]
    blocks = data["data"]["blocks"]
    for block in blocks:  # merge_info 为只读字段, 提交前须去除
        if "table" in block:
            block["table"].get("property", {}).pop("merge_info", None)

    data = _api("GET", f"{BASE}/docx/v1/documents/{doc_token}/blocks",
                headers=headers, params={"page_size": 500})
    if not data:
        return False
    page = next((b for b in data["data"]["items"] if b["block_id"] == doc_token), None)
    old_count = len(page.get("children") or []) if page else 0

    if old_count:
        if not _api("DELETE",
                    f"{BASE}/docx/v1/documents/{doc_token}/blocks/{doc_token}"
                    "/children/batch_delete",
                    headers=headers,
                    json={"start_index": 0, "end_index": old_count}):
            return False
    if not _api("POST",
                f"{BASE}/docx/v1/documents/{doc_token}/blocks/{doc_token}/descendant",
                headers=headers,
                json={"children_id": children_ids, "index": 0, "descendants": blocks}):
        return False
    logger.info("飞书文档已原地更新: %s", doc_token)
    return True


def create_daily_doc(md_content: str, title: str,
                     app_id: str, app_secret: str) -> tuple[str, str] | None:
    """导入日报为飞书云文档, 返回 (doc_token, doc_url); 失败返回 None."""
    token = _get_tenant_token(app_id, app_secret)
    if not token:
        return None
    file_token = _upload_md(token, title, md_content)
    if not file_token:
        return None
    result = _import_as_docx(token, file_token, title)
    if not result:
        return None
    doc_token, doc_url = result
    _enable_link_share(token, doc_token)
    logger.info("飞书文档已生成: %s", doc_url)
    return doc_token, doc_url
