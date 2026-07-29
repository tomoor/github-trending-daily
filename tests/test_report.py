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


def test_render_report_demotes_headings_in_detail():
    # DeepWiki 偶发用 markdown 标题而非加粗小节, 渲染时统一降为加粗,
    # 避免与日报框架标题平级、在飞书文档大纲中产生噪音
    detail = "## 解决什么问题\n内容一\n\n### 核心功能\n内容二\n#### 技术亮点 ##\n内容三"
    md = render_report("2026-07-29", [REPO], [Analysis("一句话", detail)])
    assert "## 解决什么问题" not in md
    assert "**解决什么问题**" in md
    assert "**核心功能**" in md
    assert "**技术亮点**" in md  # 尾部悬挂 # 也被清理
    # 日报框架自身标题不受影响
    assert "## 项目详情" in md
    assert "### 1. [foo/bar]" in md


def test_render_report_escapes_pipe_and_keeps_degraded_note():
    degraded = Analysis("有|竖线", "> 注: 未获得 DeepWiki 深度解读, 仅展示简介\n\ndesc",
                        degraded=True)
    md = render_report("2026-07-27", [REPO], [degraded])
    assert "有\\|竖线" in md
    assert "未获得 DeepWiki 深度解读" in md
