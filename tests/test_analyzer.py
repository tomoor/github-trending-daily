from types import SimpleNamespace

import pytest

import src.analyzer as az
from src.analyzer import Analysis, Analyzer, _parse_analysis
from src.fetch_trending import TrendingRepo

REPO = TrendingRepo(owner="foo", name="bar", url="https://github.com/foo/bar",
                    stars=100, description="官方描述")


def make_client(results):
    """results: 每次调用依次弹出, str 为成功返回, Exception 为抛出."""
    class Completions:
        def create(self, **kwargs):
            r = results.pop(0)
            if isinstance(r, Exception):
                raise r
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=r))])

    return SimpleNamespace(chat=SimpleNamespace(completions=Completions()))


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(az.time, "sleep", lambda s: None)


def test_analyzer_default_model(monkeypatch):
    monkeypatch.delenv("ARK_MODEL", raising=False)
    assert Analyzer(client=make_client([])).model == "doubao-seed-2-0-pro-260215"


def test_analyzer_model_env_override(monkeypatch):
    monkeypatch.setenv("ARK_MODEL", "custom-model")
    assert Analyzer(client=make_client([])).model == "custom-model"


def test_parse_analysis_normal():
    a = _parse_analysis("一句话简介\n\n**解决什么问题**\n内容", REPO)
    assert a.one_liner == "一句话简介"
    assert a.detail_md.startswith("**解决什么问题**")
    assert not a.failed


def test_parse_analysis_fallback_when_format_bad():
    text = "x" * 100  # 首行超长且无详情段
    a = _parse_analysis(text, REPO)
    assert a.one_liner == "官方描述"
    assert a.detail_md == text


def test_analyze_repo_retries_then_success():
    client = make_client([RuntimeError("boom"), "一句话\n\n详情"])
    a = Analyzer(client=client, model="m").analyze_repo(REPO, "readme")
    assert a.one_liner == "一句话"
    assert not a.failed


def test_analyze_repo_placeholder_after_all_retries():
    client = make_client([RuntimeError("1"), RuntimeError("2"), RuntimeError("3")])
    a = Analyzer(client=client, model="m").analyze_repo(REPO, None)
    assert a.failed
    assert a.one_liner == "官方描述"


def test_summarize_day_ok():
    client = make_client(["今日总览内容"])
    s = Analyzer(client=client, model="m").summarize_day([REPO], [Analysis("x", "y")])
    assert s == "今日总览内容"


def test_summarize_day_failure_returns_empty():
    client = make_client([RuntimeError("1"), RuntimeError("2"), RuntimeError("3")])
    s = Analyzer(client=client, model="m").summarize_day([REPO], [Analysis("x", "y")])
    assert s == ""
