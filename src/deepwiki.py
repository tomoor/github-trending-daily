"""通过 DeepWiki MCP 端点获取仓库解读, 作为 README 之外的补充信息源.

免费无鉴权; 未索引/失败时返回 None, 调用方仅用 README 继续分析。
"""
from __future__ import annotations

import json
import logging
import re

import requests

logger = logging.getLogger(__name__)

DEEPWIKI_MCP_URL = "https://mcp.deepwiki.com/mcp"
TIMEOUT = 90
QUESTION = (
    "请严格按以下格式用中文介绍这个项目, 不要任何额外内容: "
    "第一行为不超过 40 字的一句话简介; 然后空一行; 之后是四个小节: "
    "**解决什么问题**、**核心功能**、**技术亮点**、**适合谁用**, 共 200~400 字。"
)
# DeepWiki 服务端固定附加的尾巴 marker, 从首个出现处截断
TAIL_MARKERS = ("## Notes", "Wiki pages you might want to explore",
                "View this search on DeepWiki")
# 中文占比(中文字符/(中文字符+英文字母))低于该阈值视为英文回答, 走兜底
MIN_CHINESE_RATIO = 0.3


def _chinese_ratio(text: str) -> float:
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    letters = len(re.findall(r"[a-zA-Z]", text))
    total = chinese + letters
    return chinese / total if total else 0.0


def _strip_tail(text: str) -> str:
    for marker in TAIL_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
    return text.strip()


def _normalize(text: str) -> str:
    """规范化 DeepWiki 输出: HTML 转 Markdown, 清理引用角标残留的标点前空格."""
    if "<p>" in text or "</p>" in text:
        text = re.sub(r"<strong>(.*?)</strong>", r"**\1**", text)
        text = re.sub(r"<br\s*/?>", "\n", text)
        text = re.sub(r"</p>\s*<p>", "\n\n", text)
        text = re.sub(r"</?[a-zA-Z][^>]*>", "", text)
    text = re.sub(r" +([。，、；：！？])", r"\1", text)
    return text.strip()


def _parse_sse_text(raw: str) -> str | None:
    """从 SSE 响应中提取带 result 的事件文本, 跳过 ping 注释与 notifications 事件."""
    for line in raw.splitlines():
        if not line.startswith("data: "):
            continue
        try:
            payload = json.loads(line[len("data: "):])
            return payload["result"]["content"][0]["text"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            continue
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
    cleaned = _normalize(_strip_tail(text))
    if not cleaned:
        return None
    ratio = _chinese_ratio(cleaned)
    if ratio < MIN_CHINESE_RATIO:
        logger.info("DeepWiki 解读为英文主导(中文占比 %.0f%%), 走兜底 %s/%s",
                    ratio * 100, owner, name)
        return None
    return cleaned
