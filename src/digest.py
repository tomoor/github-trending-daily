"""将 DeepWiki 解读或兜底简介组装为日报条目(纯组装, 无网络调用)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .fetch_trending import TrendingRepo

ONE_LINER_MAX = 100


@dataclass
class Analysis:
    one_liner: str
    detail_md: str
    degraded: bool = False  # 未获得 DeepWiki 深度解读, 仅有简介


def _truncate(text: str) -> str:
    return text if len(text) <= ONE_LINER_MAX else text[:ONE_LINER_MAX - 1] + "…"


def _first_sentence(line: str) -> str:
    """取首句(按中文句末标点切分), 超长截断; 保证一句话始终来自中文解读本身."""
    sentence = re.split(r"(?<=[。！？])", line, maxsplit=1)[0].strip()
    return _truncate(sentence)


def build_analysis(repo: TrendingRepo, wiki: str | None,
                   fallback_desc: str | None) -> Analysis:
    if wiki:
        lines = wiki.strip().splitlines()
        first = lines[0].strip()
        rest = "\n".join(lines[1:]).strip()
        if rest and len(first) <= ONE_LINER_MAX:
            return Analysis(one_liner=first, detail_md=rest)
        # 首行超长或无正文结构: 一句话仍从中文解读首句提取, 整段作为详情
        return Analysis(one_liner=_first_sentence(first), detail_md=wiki.strip())

    desc = fallback_desc or repo.description or "(无可用介绍)"
    return Analysis(
        one_liner=_truncate(desc),
        detail_md=f"> 注: 未获得 DeepWiki 深度解读, 仅展示简介\n\n{desc}",
        degraded=True,
    )
