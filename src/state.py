"""当天已推送项目清单的持久化(reports/YYYY-MM-DD.json, 随日报提交)."""
from __future__ import annotations

import json
from pathlib import Path

from .digest import Analysis
from .fetch_trending import TrendingRepo


def _empty_state() -> dict:
    # 每次返回全新对象, 避免共享可变 items 列表被调用方原地修改
    return {"doc_token": None, "doc_url": None, "items": []}


def load_state(path: Path) -> dict:
    """返回 {"doc_token", "doc_url", "items"}; 兼容旧版纯 list 格式."""
    if not path.exists():
        return _empty_state()
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {**_empty_state(), "items": data}
    return data


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


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
