"""将 DeepWiki 解读或兜底简介组装为日报条目(纯组装, 无网络调用)."""
from __future__ import annotations

from dataclasses import dataclass

from .fetch_trending import TrendingRepo

ONE_LINER_MAX = 60


@dataclass
class Analysis:
    one_liner: str
    detail_md: str
    degraded: bool = False  # 未获得 DeepWiki 深度解读, 仅有简介


def build_analysis(repo: TrendingRepo, wiki: str | None,
                   fallback_desc: str | None) -> Analysis:
    if wiki:
        lines = wiki.strip().splitlines()
        first = lines[0].strip()
        rest = "\n".join(lines[1:]).strip()
        if rest and len(first) <= ONE_LINER_MAX:
            return Analysis(one_liner=first, detail_md=rest)
        # 格式不符预期: 整段作为详情, 一句话回退用兜底/榜单描述
        one_liner = fallback_desc or repo.description or first[:40]
        return Analysis(one_liner=one_liner[:ONE_LINER_MAX], detail_md=wiki.strip())

    desc = fallback_desc or repo.description or "(无可用介绍)"
    one_liner = desc if len(desc) <= ONE_LINER_MAX else desc[:ONE_LINER_MAX - 1] + "…"
    return Analysis(
        one_liner=one_liner,
        detail_md=f"> 注: 未获得 DeepWiki 深度解读, 仅展示简介\n\n{desc}",
        degraded=True,
    )
