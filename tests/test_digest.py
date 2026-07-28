from src.digest import Analysis, build_analysis
from src.fetch_trending import TrendingRepo

REPO = TrendingRepo(owner="foo", name="bar", url="https://github.com/foo/bar",
                    stars=100, description="官方描述")
REPO_NO_DESC = TrendingRepo(owner="foo", name="bar", url="https://github.com/foo/bar",
                            stars=100, description="")


def test_wiki_normal_format():
    a = build_analysis(REPO, "一句话简介\n\n**解决什么问题**\n内容", None)
    assert a.one_liner == "一句话简介"
    assert a.detail_md.startswith("**解决什么问题**")
    assert not a.degraded


def test_wiki_bad_format_falls_back_one_liner():
    text = "x" * 100  # 首行超长且无详情段
    a = build_analysis(REPO, text, None)
    assert a.one_liner == "官方描述"
    assert a.detail_md == text
    assert not a.degraded


def test_no_wiki_uses_fallback_desc():
    a = build_analysis(REPO, None, "Fallback description from zread.")
    assert a.one_liner == "Fallback description from zread."
    assert "未获得 DeepWiki 深度解读" in a.detail_md
    assert "Fallback description from zread." in a.detail_md
    assert a.degraded


def test_no_wiki_no_fallback_uses_repo_description():
    a = build_analysis(REPO, None, None)
    assert a.one_liner == "官方描述"
    assert a.degraded


def test_nothing_available_uses_placeholder():
    a = build_analysis(REPO_NO_DESC, None, None)
    assert a.one_liner == "(无可用介绍)"
    assert a.degraded


def test_long_fallback_desc_truncated_for_one_liner():
    long_desc = "d" * 200
    a = build_analysis(REPO_NO_DESC, None, long_desc)
    assert len(a.one_liner) <= 60
    assert long_desc in a.detail_md


def test_analysis_dataclass_fields():
    a = Analysis(one_liner="x", detail_md="y")
    assert not a.degraded
