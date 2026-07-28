import json

import src.main as main
from src.fetch_trending import TrendingRepo

REPO = TrendingRepo(owner="foo", name="bar", url="https://github.com/foo/bar",
                    stars=100, description="demo")


def _patch_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(main, "BUILD_DIR", tmp_path / "build")
    monkeypatch.setattr(main, "CARD_PATH", tmp_path / "build" / "card.json")


def test_generate_with_wiki_skips_fallbacks(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    fallback_calls = []
    monkeypatch.setattr(main, "fetch_trending", lambda: [REPO, REPO])
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
    card = json.loads((tmp_path / "build" / "card.json").read_text(encoding="utf-8"))
    button = card["elements"][-1]["actions"][0]
    assert button["url"] == f"https://example.com/reports/{date_str}.md"


def test_generate_falls_back_zread_then_context7(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(main, "fetch_trending", lambda: [REPO])
    monkeypatch.setattr(main, "fetch_deepwiki_summary", lambda owner, name: None)
    monkeypatch.setattr(main, "fetch_zread_description", lambda owner, name: None)
    monkeypatch.setattr(main, "fetch_context7_description",
                        lambda owner, name: "c7 description")
    monkeypatch.delenv("REPORT_BASE_URL", raising=False)
    main.generate()
    date_str = main.today_str()
    report = (tmp_path / "reports" / f"{date_str}.md").read_text(encoding="utf-8")
    assert "c7 description" in report
    assert "未获得 DeepWiki 深度解读" in report


def test_generate_limit(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    wiki_calls = []
    monkeypatch.setattr(main, "fetch_trending", lambda: [REPO, REPO, REPO])
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
