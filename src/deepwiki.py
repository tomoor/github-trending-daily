"""通过 DeepWiki MCP 端点获取仓库解读, 作为 README 之外的补充信息源.

免费无鉴权; 未索引/失败时返回 None, 调用方仅用 README 继续分析。
"""
from __future__ import annotations

import json
import logging

import requests

logger = logging.getLogger(__name__)

DEEPWIKI_MCP_URL = "https://mcp.deepwiki.com/mcp"
TIMEOUT = 90
QUESTION = "请用中文介绍这个项目: 它解决什么问题、核心功能、技术架构与亮点、适合谁用。300 字以内。"


def _parse_sse_text(raw: str) -> str | None:
    """从 SSE 响应中提取第一个 message 的 result.content[0].text."""
    for line in raw.splitlines():
        if not line.startswith("data: "):
            continue
        try:
            payload = json.loads(line[len("data: "):])
            return payload["result"]["content"][0]["text"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            return None
    return None


def fetch_deepwiki_summary(owner: str, name: str) -> str | None:
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "ask_question",
            "arguments": {"repoName": f"{owner}/{name}", "question": QUESTION},
        },
    }
    try:
        resp = requests.post(
            DEEPWIKI_MCP_URL,
            headers={"Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream"},
            json=body,
            timeout=TIMEOUT,
        )
    except requests.RequestException:
        logger.warning("DeepWiki 请求异常 %s/%s", owner, name, exc_info=True)
        return None
    if resp.status_code != 200:
        logger.warning("DeepWiki 获取失败 %s/%s: HTTP %d", owner, name, resp.status_code)
        return None
    # 响应头 text/event-stream 未声明 charset, requests 会误用 ISO-8859-1,
    # 必须按 UTF-8 显式解码, 否则中文乱码导致 JSON 解析失败
    raw = resp.content.decode("utf-8", errors="replace")
    text = _parse_sse_text(raw)
    if not text or text.startswith("Error processing question"):
        logger.info("DeepWiki 无可用解读 %s/%s: %s", owner, name,
                    (text or f"解析失败, 响应前 120 字符: {raw[:120]!r}"))
        return None
    return text.strip()
