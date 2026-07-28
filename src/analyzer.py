"""调用阿里云百炼(OpenAI 兼容接口)逐项目分析生成中文介绍."""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

from openai import OpenAI

from .fetch_trending import TrendingRepo

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.7-plus"
MAX_RETRIES = 2
RETRY_DELAY = 5
ONE_LINER_MAX = 60

REPO_PROMPT = """\
你是资深开源技术分析师。请分析以下 GitHub Trending 项目, 用中文输出。

项目: {full_name}
Stars: {stars}
官方描述: {description}
README 节选:
{readme}

DeepWiki 解读参考:
{wiki}

输出要求(严格遵守):
- 第一行: 一句话简介, 不超过 40 字, 不要任何前缀、标点序号或加粗
- 第二行: 空行
- 之后: 详细介绍(Markdown), 依次包含四个小节: **解决什么问题**、**核心功能**、**技术亮点**、**适合谁用**, 共 200~400 字
"""


@dataclass
class Analysis:
    one_liner: str
    detail_md: str
    failed: bool = False


def _parse_analysis(text: str, repo: TrendingRepo) -> Analysis:
    lines = text.strip().splitlines()
    first = lines[0].strip()
    rest = "\n".join(lines[1:]).strip()
    if not rest or len(first) > ONE_LINER_MAX:
        # 格式不符预期: 整段作为详情, 一句话回退用榜单描述
        return Analysis(one_liner=repo.description or first[:40], detail_md=text.strip())
    return Analysis(one_liner=first, detail_md=rest)


class Analyzer:
    def __init__(self, client: OpenAI | None = None, model: str | None = None):
        self.client = client or OpenAI(
            base_url=os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL),
            api_key=os.environ["LLM_API_KEY"],
        )
        self.model = model or os.environ.get("LLM_MODEL", DEFAULT_MODEL)

    def _chat(self, prompt: str) -> str:
        last_err: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.6,
                    # qwen3.7-plus 默认开启思考模式, 日报场景关闭以支持非流式并节省 token
                    extra_body={"enable_thinking": False},
                )
                content = resp.choices[0].message.content
                if not content or not content.strip():
                    raise ValueError("LLM 返回空内容")
                return content.strip()
            except Exception as e:  # noqa: BLE001 - 重试边界需要捕获所有异常
                last_err = e
                if attempt < MAX_RETRIES:
                    delay = RETRY_DELAY * (2 ** attempt)
                    logger.warning("LLM 调用失败(第 %d 次), %ds 后重试: %s", attempt + 1, delay, e)
                    time.sleep(delay)
        raise last_err

    def analyze_repo(self, repo: TrendingRepo, readme: str | None,
                     wiki: str | None) -> Analysis:
        prompt = REPO_PROMPT.format(
            full_name=repo.full_name,
            stars=repo.stars,
            description=repo.description or "(无)",
            readme=readme or "(未获取到 README)",
            wiki=wiki or "(无)",
        )
        try:
            return _parse_analysis(self._chat(prompt), repo)
        except Exception:
            logger.error("项目 %s 分析失败", repo.full_name, exc_info=True)
            return Analysis(
                one_liner=repo.description or "(分析失败)",
                detail_md=f"> 注: 自动分析失败。官方描述: {repo.description or '无'}",
                failed=True,
            )
