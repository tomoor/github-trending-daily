from src.analyzer import Analysis
from src.fetch_trending import TrendingRepo
from src.report import render_report

REPO = TrendingRepo(owner="foo", name="bar", url="https://github.com/foo/bar",
                    stars=1234, description="demo")


def test_render_report_structure():
    md = render_report("2026-07-27", "总览内容", [REPO], [Analysis("一句话", "详细内容")])
    assert "# GitHub Trending 日报 · 2026-07-27" in md
    assert "## 今日看点" in md and "总览内容" in md
    assert "| 1 | [foo/bar](https://github.com/foo/bar) | 1,234 | 一句话 |" in md
    assert "### 1. [foo/bar](https://github.com/foo/bar) ✰ 1,234" in md
    assert "详细内容" in md


def test_render_report_without_overview():
    md = render_report("2026-07-27", "", [REPO], [Analysis("一句话", "详情")])
    assert "## 今日看点" not in md


def test_render_report_escapes_pipe_and_marks_failure():
    md = render_report("2026-07-27", "", [REPO], [Analysis("有|竖线", "详情", failed=True)])
    assert "有\\|竖线" in md
    assert "> 注: 本项目自动分析失败" in md
