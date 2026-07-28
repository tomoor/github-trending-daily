import json

import src.main as main
from src.analyzer import Analysis
from src.fetch_trending import TrendingRepo

REPO = TrendingRepo(owner="foo", name="bar", url="https://github.com/foo/bar",
                    stars=100, description="demo")


class FakeAnalyzer:
    def __init__(self, *args, **kwargs):
        self.model = "fake-model"
        self.seen = []

    def analyze_repo(self, repo, readme, wiki):
        self.seen.append((repo.full_name, readme, wiki))
        return Analysis(one_liner="一句话", detail_md="详情")


def _patch_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(main, "BUILD_DIR", tmp_path / "build")
    monkeypatch.setattr(main, "CARD_PATH", tmp_path / "build" / "card.json")


def test_generate_writes_report_and_card(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    analyzers = []
    monkeypatch.setattr(main, "fetch_trending", lambda: [REPO, REPO])
    monkeypatch.setattr(main, "fetch_readme", lambda owner, name: "readme")
    monkeypatch.setattr(main, "fetch_deepwiki_summary", lambda owner, name: "wiki 内容")
    monkeypatch.setattr(main, "Analyzer",
                        lambda *a, **kw: analyzers.append(FakeAnalyzer()) or analyzers[-1])
    monkeypatch.setenv("REPORT_BASE_URL", "https://example.com/reports")
    main.generate()
    assert analyzers[0].seen == [("foo/bar", "readme", "wiki 内容")] * 2
    date_str = main.today_str()
    report = (tmp_path / "reports" / f"{date_str}.md").read_text(encoding="utf-8")
    assert "foo/bar" in report and "今日看点" not in report
    card = json.loads((tmp_path / "build" / "card.json").read_text(encoding="utf-8"))
    assert card["header"]["title"]["content"].endswith(date_str)
    button = card["elements"][-1]["actions"][0]
    assert button["url"] == f"https://example.com/reports/{date_str}.md"


def test_generate_limit(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    readme_calls = []
    monkeypatch.setattr(main, "fetch_trending", lambda: [REPO, REPO, REPO])
    monkeypatch.setattr(main, "fetch_readme",
                        lambda owner, name: readme_calls.append(name) or None)
    monkeypatch.setattr(main, "fetch_deepwiki_summary", lambda owner, name: None)
    monkeypatch.setattr(main, "Analyzer", FakeAnalyzer)
    monkeypatch.delenv("REPORT_BASE_URL", raising=False)
    main.generate(limit=1)
    assert len(readme_calls) == 1


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
