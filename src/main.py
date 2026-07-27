"""编排入口: generate 生成日报与卡片, notify 推送飞书."""
from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .analyzer import Analyzer
from .feishu import build_card, send_card
from .fetch_trending import fetch_trending
from .github_readme import fetch_readme
from .report import render_report

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports"
BUILD_DIR = ROOT / "build"
CARD_PATH = BUILD_DIR / "card.json"


def today_str() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")


def generate(limit: int | None = None) -> None:
    date_str = today_str()
    repos = fetch_trending()
    if limit:
        repos = repos[:limit]
    logger.info("待分析项目: %d 个", len(repos))

    analyzer = Analyzer()
    analyses = []
    for i, repo in enumerate(repos, 1):
        logger.info("[%d/%d] 分析 %s", i, len(repos), repo.full_name)
        readme = fetch_readme(repo.owner, repo.name)
        analyses.append(analyzer.analyze_repo(repo, readme))

    overview = analyzer.summarize_day(repos, analyses)

    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / f"{date_str}.md"
    report_path.write_text(
        render_report(date_str, overview, repos, analyses, analyzer.model),
        encoding="utf-8")
    logger.info("日报已写入 %s", report_path)

    base_url = os.environ.get("REPORT_BASE_URL", "").rstrip("/")
    report_url = f"{base_url}/{date_str}.md" if base_url else None
    card = build_card(date_str, overview, repos, analyses, report_url)
    BUILD_DIR.mkdir(exist_ok=True)
    CARD_PATH.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("卡片已写入 %s", CARD_PATH)


def notify() -> None:
    webhook_url = os.environ["FEISHU_WEBHOOK_URL"]
    card = json.loads(CARD_PATH.read_text(encoding="utf-8"))
    send_card(webhook_url, card, os.environ.get("FEISHU_WEBHOOK_SECRET") or None)


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="GitHub Trending 每日 AI 分析日报")
    sub = parser.add_subparsers(dest="command", required=True)
    p_gen = sub.add_parser("generate", help="抓取榜单并生成日报与飞书卡片")
    p_gen.add_argument("--limit", type=int, default=None, help="只分析前 N 个项目(调试用)")
    sub.add_parser("notify", help="读取卡片并推送到飞书群")
    args = parser.parse_args()
    if args.command == "generate":
        generate(limit=args.limit)
    else:
        notify()


if __name__ == "__main__":
    main()
