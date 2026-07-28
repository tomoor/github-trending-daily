from src.digest import Analysis
from src.fetch_trending import TrendingRepo
from src.report import render_report

REPO = TrendingRepo(owner="foo", name="bar", url="https://github.com/foo/bar",
                    stars=1234, description="demo")


def test_render_report_structure():
    md = render_report("2026-07-27", [REPO], [Analysis("一句话", "详细内容")])
    assert "# GitHub Trending 日报 · 2026-07-27" in md
    assert "> 由 DeepWiki 自动解读生成" in md
    assert "今日看点" not in md
    assert "| 1 | [foo/bar](https://github.com/foo/bar) | 1,234 | 一句话 |" in md
    assert "### 1. [foo/bar](https://github.com/foo/bar) ✰ 1,234" in md
    assert "详细内容" in md


def test_render_report_escapes_pipe_and_keeps_degraded_note():
    degraded = Analysis("有|竖线", "> 注: 未获得 DeepWiki 深度解读, 仅展示简介\n\ndesc",
                        degraded=True)
    md = render_report("2026-07-27", [REPO], [degraded])
    assert "有\\|竖线" in md
    assert "未获得 DeepWiki 深度解读" in md
