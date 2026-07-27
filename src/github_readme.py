"""抓取 GitHub 仓库 README 并截断, 失败返回 None(调用方回退榜单描述)."""
from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

TIMEOUT = 30


def fetch_readme(owner: str, name: str, max_chars: int = 5000) -> str | None:
    headers = {"Accept": "application/vnd.github.raw+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{name}/readme",
            headers=headers,
            timeout=TIMEOUT,
        )
    except requests.RequestException:
        logger.warning("README 请求异常 %s/%s", owner, name, exc_info=True)
        return None
    if resp.status_code != 200:
        logger.warning("README 获取失败 %s/%s: HTTP %d", owner, name, resp.status_code)
        return None
    text = resp.text.strip()
    return text[:max_chars] if text else None
