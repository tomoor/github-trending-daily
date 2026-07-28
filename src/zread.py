"""从 zread.ai 项目页提取 og:description 作为兜底简介(英文, 无公开 API)."""
from __future__ import annotations

import logging

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TIMEOUT = 30
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def fetch_zread_description(owner: str, name: str) -> str | None:
    try:
        resp = requests.get(
            f"https://zread.ai/{owner}/{name}",
            headers={"User-Agent": BROWSER_UA},
            timeout=TIMEOUT,
        )
    except requests.RequestException:
        logger.warning("zread 请求异常 %s/%s", owner, name, exc_info=True)
        return None
    if resp.status_code != 200:
        logger.info("zread 无页面 %s/%s: HTTP %d", owner, name, resp.status_code)
        return None
    meta = BeautifulSoup(resp.text, "html.parser").find(
        "meta", attrs={"property": "og:description"})
    content = (meta.get("content") or "").strip() if meta else ""
    return content or None
