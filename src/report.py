"""渲染 Markdown 日报."""
from __future__ import annotations

import re

from .digest import Analysis
from .fetch_trending import TrendingRepo


def _demote_headings(detail_md: str) -> str:
    """详情中偶发的 markdown 标题降为加粗, 避免与日报框架标题冲突/污染文档大纲."""
    return re.sub(r"(?m)^#{1,6}\s*(.+?)\s*#*\s*$", r"**\1**", detail_md)


def render_report(date_str: str,
                  repos: list[TrendingRepo], analyses: list[Analysis]) -> str:
    lines = [
        f"# GitHub Trending 日报 · {date_str}",
        "",
        "> 由 DeepWiki 自动解读生成",
        "",
    ]
    lines += [
        "## 项目速览",
        "",
        "| # | 项目 | Stars | 一句话简介 |",
        "|---|------|-------|-----------|",
    ]
    for i, (r, a) in enumerate(zip(repos, analyses), 1):
        one = a.one_liner.replace("|", "\\|")
        lines.append(f"| {i} | [{r.full_name}]({r.url}) | {r.stars:,} | {one} |")
    lines += ["", "## 项目详情", ""]
    for i, (r, a) in enumerate(zip(repos, analyses), 1):
        lines += [f"### {i}. [{r.full_name}]({r.url}) ✰ {r.stars:,}", "",
                  _demote_headings(a.detail_md), ""]
    return "\n".join(lines)
