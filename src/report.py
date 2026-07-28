"""渲染 Markdown 日报."""
from __future__ import annotations

from .analyzer import Analysis
from .fetch_trending import TrendingRepo


def render_report(date_str: str,
                  repos: list[TrendingRepo], analyses: list[Analysis],
                  model: str) -> str:
    lines = [
        f"# GitHub Trending 日报 · {date_str}",
        "",
        f"> 由 {model} 自动分析生成",
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
        lines += [f"### {i}. [{r.full_name}]({r.url}) ✰ {r.stars:,}", ""]
        if a.failed:
            lines += ["> 注: 本项目自动分析失败", ""]
        lines += [a.detail_md, ""]
    return "\n".join(lines)
