"""飞书群自定义机器人: interactive 卡片构造与 webhook 发送(可选签名)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time

import requests

from .analyzer import Analysis
from .fetch_trending import TrendingRepo

logger = logging.getLogger(__name__)

TIMEOUT = 30
MAX_RETRIES = 2
RETRY_DELAY = 3


def gen_sign(secret: str, timestamp: int) -> str:
    """飞书签名: 以 "{timestamp}\\n{secret}" 为 key 对空串做 HmacSHA256 再 base64."""
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def build_card(date_str: str,
               repos: list[TrendingRepo], analyses: list[Analysis],
               report_url: str | None) -> dict:
    repo_lines = "\n".join(
        f"{i}. [{r.full_name}]({r.url}) ✰ {r.stars:,} — {a.one_liner}"
        for i, (r, a) in enumerate(zip(repos, analyses), 1)
    )
    elements: list[dict] = [{"tag": "markdown", "content": repo_lines}]
    if report_url:
        elements += [
            {"tag": "hr"},
            {"tag": "action", "actions": [{
                "tag": "button",
                "text": {"tag": "plain_text", "content": "查看完整日报"},
                "type": "primary",
                "url": report_url,
            }]},
        ]
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": f"GitHub Trending 日报 · {date_str}"},
        },
        "elements": elements,
    }


def send_card(webhook_url: str, card: dict, secret: str | None = None) -> None:
    body: dict = {"msg_type": "interactive", "card": card}
    if secret:
        ts = int(time.time())
        body["timestamp"] = str(ts)
        body["sign"] = gen_sign(secret, ts)
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(webhook_url, json=body, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code", 0) != 0:
                raise RuntimeError(f"飞书返回错误: {data}")
            logger.info("飞书推送成功")
            return
        except Exception as e:  # noqa: BLE001 - 重试边界需要捕获所有异常
            last_err = e
            if attempt < MAX_RETRIES:
                logger.warning("飞书推送失败(第 %d 次), 重试: %s", attempt + 1, e)
                time.sleep(RETRY_DELAY)
    raise last_err
