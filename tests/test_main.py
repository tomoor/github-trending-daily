import json

import src.main as main
from src.fetch_trending import TrendingRepo

REPO = TrendingRepo(owner="foo", name="bar", url="https://github.com/foo/bar",
                    stars=100, description="demo")
REPO2 = TrendingRepo(owner="baz", name="qux", url="https://github.com/baz/qux",
                     stars=50, description="demo2")

SEEN_ITEM = {
    "id": "foo/bar", "owner": "foo", "name": "bar",
    "url": "https://github.com/foo/bar", "stars": 100, "description": "demo",
    "one_liner": "旧简介", "detail_md": "旧详情", "degraded": False,
}


def _patch_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(main, "BUILD_DIR", tmp_path / "build")
    monkeypatch.setattr(main, "CARD_PATH", tmp_path / "build" / "card.json")


def _write_state(tmp_path, items):
    (tmp_path / "reports").mkdir(exist_ok=True)
    path = tmp_path / "reports" / f"{main.today_str()}.json"
    path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")


def test_generate_first_run_all_new(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    fallback_calls = []
    monkeypatch.setattr(main, "fetch_trending", lambda: [REPO, REPO2])
    monkeypatch.setattr(main, "fetch_deepwiki_summary",
                        lambda owner, name: "一句话简介\n\n**解决什么问题**\n内容")
    monkeypatch.setattr(main, "fetch_zread_description",
                        lambda owner, name: fallback_calls.append("zread"))
    monkeypatch.setattr(main, "fetch_context7_description",
                        lambda owner, name: fallback_calls.append("c7"))
    monkeypatch.setenv("REPORT_BASE_URL", "https://example.com/reports")
    main.generate()
    assert fallback_calls == []  # DeepWiki 命中时不应调用兜底源
    date_str = main.today_str()
    report = (tmp_path / "reports" / f"{date_str}.md").read_text(encoding="utf-8")
    assert "一句话简介" in report and "**解决什么问题**" in report
    state = json.loads(
        (tmp_path / "reports" / f"{date_str}.json").read_text(encoding="utf-8"))
    assert [it["id"] for it in state] == ["foo/bar", "baz/qux"]
    card = json.loads((tmp_path / "build" / "card.json").read_text(encoding="utf-8"))
    assert card["header"]["title"]["content"] == f"GitHub Trending 日报 · {date_str}"
    button = card["elements"][-1]["actions"][0]
    assert button["url"] == f"https://example.com/reports/{date_str}.md"


def test_generate_supplement_handles_only_new_repos(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    wiki_calls = []
    monkeypatch.setattr(main, "fetch_trending", lambda: [REPO, REPO2])
    monkeypatch.setattr(
        main, "fetch_deepwiki_summary",
        lambda owner, name: wiki_calls.append(f"{owner}/{name}") or "新简介\n\n新详情")
    monkeypatch.setattr(main, "fetch_zread_description", lambda owner, name: None)
    monkeypatch.setattr(main, "fetch_context7_description", lambda owner, name: None)
    monkeypatch.delenv("REPORT_BASE_URL", raising=False)
    _write_state(tmp_path, [SEEN_ITEM])
    main.generate()
    assert wiki_calls == ["baz/qux"]  # 只解读新项目
    date_str = main.today_str()
    report = (tmp_path / "reports" / f"{date_str}.md").read_text(encoding="utf-8")
    assert "旧简介" in report and "新简介" in report  # 日报全天累积
    card = json.loads((tmp_path / "build" / "card.json").read_text(encoding="utf-8"))
    assert card["header"]["title"]["content"] == f"GitHub Trending 新上榜 1 项 · {date_str}"
    assert "baz/qux" in card["elements"][0]["content"]
    assert "foo/bar" not in card["elements"][0]["content"]  # 卡片只含新项目


def test_generate_no_new_repos_removes_card(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(main, "fetch_trending", lambda: [REPO])
    monkeypatch.setattr(main, "fetch_deepwiki_summary",
                        lambda owner, name: 1 / 0)  # 不应被调用
    monkeypatch.setattr(main, "fetch_zread_description", lambda owner, name: None)
    monkeypatch.setattr(main, "fetch_context7_description", lambda owner, name: None)
    monkeypatch.delenv("REPORT_BASE_URL", raising=False)
    _write_state(tmp_path, [SEEN_ITEM])
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "card.json").write_text("{}", encoding="utf-8")  # 上次残留
    main.generate()
    assert not (tmp_path / "build" / "card.json").exists()  # 无新项目不留卡片


def test_generate_falls_back_zread_then_context7(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(main, "fetch_trending", lambda: [REPO])
    monkeypatch.setattr(main, "fetch_deepwiki_summary", lambda owner, name: None)
    monkeypatch.setattr(main, "fetch_zread_description", lambda owner, name: None)
    monkeypatch.setattr(main, "fetch_context7_description",
                        lambda owner, name: "c7 description")
    monkeypatch.delenv("REPORT_BASE_URL", raising=False)
    main.generate()
    report = (tmp_path / "reports" / f"{main.today_str()}.md").read_text(encoding="utf-8")
    assert "c7 description" in report
    assert "未获得 DeepWiki 深度解读" in report


def test_generate_limit(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    wiki_calls = []
    monkeypatch.setattr(main, "fetch_trending", lambda: [REPO, REPO2])
    monkeypatch.setattr(main, "fetch_deepwiki_summary",
                        lambda owner, name: wiki_calls.append(name) or "一句话\n\n详情")
    monkeypatch.setattr(main, "fetch_zread_description", lambda owner, name: None)
    monkeypatch.setattr(main, "fetch_context7_description", lambda owner, name: None)
    monkeypatch.delenv("REPORT_BASE_URL", raising=False)
    main.generate(limit=1)
    assert len(wiki_calls) == 1


def test_notify_reads_card_and_sends(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "build").mkdir(parents=True)
    (tmp_path / "build" / "card.json").write_text('{"elements": []}', encoding="utf-8")
    sent = {}
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://hook")
    monkeypatch.setenv("FEISHU_WEBHOOK_SECRET", "sec")
    monkeypatch.setattr(
        main, "send_card",
        lambda url, card, secret=None: sent.update(url=url, card=card, secret=secret))
    main.notify()
    assert sent["url"] == "https://hook"
    assert sent["card"] == {"elements": []}
    assert sent["secret"] == "sec"


def test_notify_skips_when_no_card(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://hook")
    monkeypatch.setattr(main, "send_card",
                        lambda url, card, secret=None: 1 / 0)  # 不应被调用
    main.notify()  # 无卡片时静默跳过, 不抛异常
