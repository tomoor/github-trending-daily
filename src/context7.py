"""从 Context7 search API 取项目描述作为兜底简介(英文, 免费接口)."""
from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

TIMEOUT = 30
SEARCH_URL = "https://context7.com/api/v1/search"


def fetch_context7_description(owner: str, name: str) -> str | None:
    try:
        resp = requests.get(SEARCH_URL, params={"query": name}, timeout=TIMEOUT)
    except requests.RequestException:
        logger.warning("context7 请求异常 %s/%s", owner, name, exc_info=True)
        return None
    if resp.status_code != 200:
        logger.info("context7 搜索失败 %s/%s: HTTP %d", owner, name, resp.status_code)
        return None
    try:
        results = resp.json().get("results", [])
    except ValueError:
        return None
    repo_id = f"/{owner}/{name}".lower()
    for item in results:
        # 仅接受 id 精确匹配 /owner/name 或 title 精确匹配仓库名, 避免同名误命中
        if (item.get("id", "").lower() == repo_id
                or item.get("title", "").lower() == name.lower()):
            desc = (item.get("description") or "").strip()
            return desc or None
    return None
