"""调用火山方舟 DeepSeek 逐项目分析并生成今日总览."""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

from openai import OpenAI

from .fetch_trending import TrendingRepo

logger = logging.getLogger(__name__)

ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-seed-1-6-250615"
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

输出要求(严格遵守):
- 第一行: 一句话简介, 不超过 40 字, 不要任何前缀、标点序号或加粗
- 第二行: 空行
- 之后: 详细介绍(Markdown), 依次包含四个小节: **解决什么问题**、**核心功能**、**技术亮点**、**适合谁用**, 共 200~400 字
"""

OVERVIEW_PROMPT = """\
你是技术日报主编。以下是今天 GitHub Trending 榜单全部项目及一句话简介:

{repo_lines}

请用中文写一段「今日看点」总览, 3~5 句话, 归纳今天榜单的整体趋势与最值得关注的 2~3 个项目。直接输出正文, 不要标题。
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
        self.client = client or OpenAI(base_url=ARK_BASE_URL, api_key=os.environ["ARK_API_KEY"])
        self.model = model or os.environ.get("ARK_MODEL", DEFAULT_MODEL)

    def _chat(self, prompt: str) -> str:
        last_err: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.6,
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

    def analyze_repo(self, repo: TrendingRepo, readme: str | None) -> Analysis:
        prompt = REPO_PROMPT.format(
            full_name=repo.full_name,
            stars=repo.stars,
            description=repo.description or "(无)",
            readme=readme or "(未获取到 README)",
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

    def summarize_day(self, repos: list[TrendingRepo], analyses: list[Analysis]) -> str:
        lines = [f"- {r.full_name} (✰ {r.stars:,}): {a.one_liner}"
                 for r, a in zip(repos, analyses)]
        try:
            return self._chat(OVERVIEW_PROMPT.format(repo_lines="\n".join(lines)))
        except Exception:
            logger.error("今日看点生成失败", exc_info=True)
            return ""
