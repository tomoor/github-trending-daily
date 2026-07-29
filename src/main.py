"""编排入口: generate 生成日报与卡片, notify 推送飞书."""
from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .context7 import fetch_context7_description
from .deepwiki import fetch_deepwiki_summary
from .digest import build_analysis
from .feishu import build_card, send_card
from .feishu_doc import create_daily_doc
from .fetch_trending import fetch_trending
from .report import render_report
from .state import from_item, load_state, save_state, to_item
from .zread import fetch_zread_description

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

    # 当天已推送清单: 首次运行为空(主推), 后续运行只处理增量(补推)
    state_path = REPORTS_DIR / f"{date_str}.json"
    state = load_state(state_path)
    items = state["items"]
    is_first_run = not items
    seen_ids = {it["id"] for it in items}
    new_repos = [r for r in repos if r.full_name not in seen_ids]
    logger.info("榜单 %d 个, 新上榜 %d 个", len(repos), len(new_repos))

    new_analyses = []
    for i, repo in enumerate(new_repos, 1):
        logger.info("[%d/%d] 解读 %s", i, len(new_repos), repo.full_name)
        wiki = fetch_deepwiki_summary(repo.owner, repo.name)
        fallback = None
        if wiki is None:
            fallback = (fetch_zread_description(repo.owner, repo.name)
                        or fetch_context7_description(repo.owner, repo.name))
        new_analyses.append(build_analysis(repo, wiki, fallback))

    items += [to_item(r, a) for r, a in zip(new_repos, new_analyses)]

    # 日报由清单全量重渲染, 全天累积所有上过榜的项目
    all_repos, all_analyses = [], []
    for item in items:
        repo, analysis = from_item(item)
        all_repos.append(repo)
        all_analyses.append(analysis)
    report_md = render_report(date_str, all_repos, all_analyses)
    report_path = REPORTS_DIR / f"{date_str}.md"
    REPORTS_DIR.mkdir(exist_ok=True)
    report_path.write_text(report_md, encoding="utf-8")
    logger.info("日报已写入 %s (共 %d 个项目)", report_path, len(items))

    # 有新内容且配置了自建应用: 全量日报导入为飞书云文档(每天保留一个)
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    if new_repos and app_id and app_secret:
        result = create_daily_doc(report_md, f"GitHub Trending 日报 {date_str}",
                                  app_id, app_secret,
                                  old_doc_token=state["doc_token"])
        if result:
            state["doc_token"], state["doc_url"] = result

    save_state(state_path, state)

    # 卡片只含本次新项目; 无新项目则清除卡片, notify 将静默跳过
    if not new_repos:
        CARD_PATH.unlink(missing_ok=True)
        logger.info("无新上榜项目, 本次不推送")
        return
    base_url = os.environ.get("REPORT_BASE_URL", "").rstrip("/")
    github_url = f"{base_url}/{date_str}.md" if base_url else None
    report_url = state["doc_url"] or github_url  # 优先飞书文档
    card = build_card(date_str, new_repos, new_analyses, report_url,
                      supplement=not is_first_run)
    BUILD_DIR.mkdir(exist_ok=True)
    CARD_PATH.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("卡片已写入 %s", CARD_PATH)


def notify() -> None:
    if not CARD_PATH.exists():
        logger.info("无待推送卡片, 跳过")
        return
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
