"""获取 GitHub Trending 榜单: 首选 newsnow API, 失败降级抓 GitHub Trending 页面."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

NEWSNOW_URL = "https://newsnow.busiyi.world/api/s?id=github-trending-today"
GITHUB_TRENDING_URL = "https://github.com/trending?spoken_language_code="
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
TIMEOUT = 30


@dataclass
class TrendingRepo:
    owner: str
    name: str
    url: str
    stars: int
    description: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


def parse_stars(text: str | None) -> int:
    """解析 star 数, 如 "✰ 31,374" → 31374, 解析失败返回 0."""
    m = re.search(r"[\d,]+", text or "")
    return int(m.group().replace(",", "")) if m else 0


def _parse_newsnow(data: dict) -> list[TrendingRepo]:
    repos = []
    for item in data.get("items", []):
        parts = (item.get("id") or "").strip("/").split("/")
        if len(parts) != 2:
            continue
        extra = item.get("extra") or {}
        repos.append(TrendingRepo(
            owner=parts[0],
            name=parts[1],
            url=item.get("url") or f"https://github.com/{parts[0]}/{parts[1]}",
            stars=parse_stars(extra.get("info", "")),
            description=(extra.get("hover") or "").strip(),
        ))
    return repos


def _parse_trending_html(html: str) -> list[TrendingRepo]:
    repos = []
    for article in BeautifulSoup(html, "html.parser").select("article.Box-row"):
        a = article.select_one("h2 a")
        href = (a.get("href") or "").strip() if a else ""
        parts = href.strip("/").split("/")
        if len(parts) != 2:
            continue
        star_el = article.select_one('a[href$="/stargazers"]')
        desc_el = article.select_one("p")
        repos.append(TrendingRepo(
            owner=parts[0],
            name=parts[1],
            url=f"https://github.com{href}",
            stars=parse_stars(star_el.get_text() if star_el else ""),
            description=desc_el.get_text(strip=True) if desc_el else "",
        ))
    return repos


def _fetch_from_newsnow() -> list[TrendingRepo]:
    resp = requests.get(
        NEWSNOW_URL,
        headers={"User-Agent": BROWSER_UA, "Accept": "application/json"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") not in ("success", "cache"):
        raise ValueError(f"newsnow 返回异常状态: {data.get('status')}")
    repos = _parse_newsnow(data)
    if not repos:
        raise ValueError("newsnow 返回空榜单")
    return repos


def _fetch_from_github() -> list[TrendingRepo]:
    resp = requests.get(GITHUB_TRENDING_URL, headers={"User-Agent": BROWSER_UA}, timeout=TIMEOUT)
    resp.raise_for_status()
    repos = _parse_trending_html(resp.text)
    if not repos:
        raise ValueError("GitHub Trending 页面解析为空")
    return repos


def fetch_trending() -> list[TrendingRepo]:
    try:
        repos = _fetch_from_newsnow()
        logger.info("newsnow 获取成功: %d 个项目", len(repos))
        return repos
    except Exception:
        logger.warning("newsnow 获取失败, 降级抓取 GitHub Trending", exc_info=True)
    repos = _fetch_from_github()
    logger.info("GitHub Trending 页面获取成功: %d 个项目", len(repos))
    return repos
