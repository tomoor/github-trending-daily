"""当天已推送项目清单的持久化(reports/YYYY-MM-DD.json, 随日报提交)."""
from __future__ import annotations

import json
from pathlib import Path

from .digest import Analysis
from .fetch_trending import TrendingRepo


def load_state(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def to_item(repo: TrendingRepo, analysis: Analysis) -> dict:
    return {
        "id": repo.full_name,
        "owner": repo.owner,
        "name": repo.name,
        "url": repo.url,
        "stars": repo.stars,
        "description": repo.description,
        "one_liner": analysis.one_liner,
        "detail_md": analysis.detail_md,
        "degraded": analysis.degraded,
    }


def from_item(item: dict) -> tuple[TrendingRepo, Analysis]:
    repo = TrendingRepo(owner=item["owner"], name=item["name"], url=item["url"],
                        stars=item["stars"], description=item["description"])
    analysis = Analysis(one_liner=item["one_liner"], detail_md=item["detail_md"],
                        degraded=item["degraded"])
    return repo, analysis
