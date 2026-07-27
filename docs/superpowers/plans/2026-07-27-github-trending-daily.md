# GitHub Trending 每日 AI 分析日报 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GitHub Actions 每天北京时间 ~7:10 抓取 GitHub Trending 榜单，DeepSeek 逐项目分析生成中文日报存入仓库 `reports/`，再向飞书群 webhook 推送摘要卡片。

**Architecture:** 轻度模块化 Python 项目（无框架）：`fetch_trending`（榜单+降级）→ `github_readme` → `analyzer`（LLM）→ `report`（Markdown）→ `feishu`（卡片）由 `main` 编排为 `generate` / `notify` 两个子命令；workflow 先 push 报告后发飞书。

**Tech Stack:** Python 3.12、requests、openai SDK（火山方舟兼容接口）、beautifulsoup4、pytest、GitHub Actions。

**Spec:** `docs/superpowers/specs/2026-07-27-github-trending-daily-design.md`

**约定:**
- 项目根目录 `/home/grm/workspace/code/github-trending-daily`，所有命令在根目录执行
- 统一用 `python -m pytest`（保证 `src` 可导入），激活 `.venv` 后执行
- 提交信息不带任何编辑器/AI 署名（用户全局规则）

---

### Task 0: 项目脚手架

**Files:**
- Create: `requirements.txt`, `pytest.ini`, `.gitignore`, `src/__init__.py`, `tests/fixtures/`（目录）

- [ ] **Step 1: 初始化 git 与目录结构**

```bash
cd /home/grm/workspace/code/github-trending-daily
git init -b main
mkdir -p src tests/fixtures reports .github/workflows
touch src/__init__.py
```

- [ ] **Step 2: 写 requirements.txt**

```
requests>=2.32,<3
openai>=1.40,<2
beautifulsoup4>=4.12,<5
pytest>=8.0,<9
```

- [ ] **Step 3: 写 pytest.ini**

```ini
[pytest]
testpaths = tests
```

- [ ] **Step 4: 写 .gitignore**

```
__pycache__/
*.pyc
.venv/
build/
.pytest_cache/
```

- [ ] **Step 5: 创建虚拟环境并安装依赖**

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Expected: 安装成功无报错

- [ ] **Step 6: pytest 冒烟**

Run: `.venv/bin/python -m pytest`
Expected: `no tests ran`（exit code 5，属正常）

- [ ] **Step 7: 首次提交（含设计文档与本计划）**

```bash
git add -A
git commit -m "chore: 项目脚手架与设计文档"
```

---

### Task 1: fetch_trending — 榜单获取（newsnow + GitHub 降级）

**Files:**
- Create: `src/fetch_trending.py`
- Test: `tests/test_fetch_trending.py`, `tests/conftest.py`, `tests/fixtures/trending.html`

- [ ] **Step 1: 写测试 fixture `tests/fixtures/trending.html`**（结构与真实 Trending 页一致的最小样本）

```html
<html><body><main><div data-hpc>
<article class="Box-row">
  <h2><a href="/foo/bar">foo / bar</a></h2>
  <p>a demo repo</p>
  <a href="/foo/bar/stargazers">31,374</a>
</article>
<article class="Box-row">
  <h2><a href="/a/b">a / b</a></h2>
  <a href="/a/b/stargazers">5</a>
</article>
</div></main></body></html>
```

- [ ] **Step 2: 写 `tests/conftest.py`**

```python
from pathlib import Path

import pytest


@pytest.fixture
def trending_html():
    return (Path(__file__).parent / "fixtures" / "trending.html").read_text(encoding="utf-8")
```

- [ ] **Step 3: 写失败测试 `tests/test_fetch_trending.py`**

```python
import pytest
import requests

import src.fetch_trending as ft

NEWSNOW_DATA = {
    "status": "success",
    "items": [
        {"url": "https://github.com/foo/bar", "title": "foo /  bar", "id": "/foo/bar",
         "extra": {"info": "✰ 31,374", "hover": "a demo repo"}},
        {"url": "https://github.com/a/b", "title": "a / b", "id": "/a/b",
         "extra": {"info": "✰ 5", "hover": ""}},
        {"url": "https://github.com/bad", "title": "bad", "id": "/bad", "extra": {}},
    ],
}


class FakeResp:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self._json is None:
            raise ValueError("not json")
        return self._json


def test_parse_stars():
    assert ft.parse_stars("✰ 31,374") == 31374
    assert ft.parse_stars("5") == 5
    assert ft.parse_stars("") == 0
    assert ft.parse_stars(None) == 0


def test_parse_newsnow_skips_invalid_id():
    repos = ft._parse_newsnow(NEWSNOW_DATA)
    assert len(repos) == 2
    assert repos[0].owner == "foo" and repos[0].name == "bar"
    assert repos[0].full_name == "foo/bar"
    assert repos[0].stars == 31374
    assert repos[0].description == "a demo repo"
    assert repos[1].description == ""


def test_parse_trending_html(trending_html):
    repos = ft._parse_trending_html(trending_html)
    assert len(repos) == 2
    assert repos[0].url == "https://github.com/foo/bar"
    assert repos[0].stars == 31374
    assert repos[0].description == "a demo repo"
    assert repos[1].description == ""


def test_fetch_trending_newsnow_ok(monkeypatch):
    monkeypatch.setattr(ft.requests, "get",
                        lambda url, **kw: FakeResp(json_data=NEWSNOW_DATA))
    assert len(ft.fetch_trending()) == 2


def test_fetch_trending_fallback_to_github(monkeypatch, trending_html):
    def fake_get(url, **kw):
        if "newsnow" in url:
            return FakeResp(status_code=403, text="blocked")
        return FakeResp(text=trending_html)

    monkeypatch.setattr(ft.requests, "get", fake_get)
    repos = ft.fetch_trending()
    assert len(repos) == 2
    assert repos[0].full_name == "foo/bar"


def test_fetch_trending_both_fail(monkeypatch):
    monkeypatch.setattr(ft.requests, "get", lambda url, **kw: FakeResp(status_code=500))
    with pytest.raises(Exception):
        ft.fetch_trending()
```

- [ ] **Step 4: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_fetch_trending.py -v`
Expected: FAIL/ERROR（`No module named 'src.fetch_trending'`）

- [ ] **Step 5: 实现 `src/fetch_trending.py`**

```python
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
```

- [ ] **Step 6: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_fetch_trending.py -v`
Expected: 6 passed

- [ ] **Step 7: 提交**

```bash
git add src/fetch_trending.py tests/
git commit -m "feat: 榜单获取(newsnow + GitHub Trending 降级)"
```

---

### Task 2: github_readme — README 抓取

**Files:**
- Create: `src/github_readme.py`
- Test: `tests/test_github_readme.py`

- [ ] **Step 1: 写失败测试 `tests/test_github_readme.py`**

```python
import requests

import src.github_readme as gr


class FakeResp:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


def test_fetch_readme_truncates(monkeypatch):
    monkeypatch.setattr(gr.requests, "get", lambda url, **kw: FakeResp(text="x" * 9000))
    result = gr.fetch_readme("o", "r", max_chars=5000)
    assert len(result) == 5000


def test_fetch_readme_none_on_404(monkeypatch):
    monkeypatch.setattr(gr.requests, "get", lambda url, **kw: FakeResp(status_code=404))
    assert gr.fetch_readme("o", "r") is None


def test_fetch_readme_none_on_network_error(monkeypatch):
    def boom(url, **kw):
        raise requests.ConnectionError("net down")

    monkeypatch.setattr(gr.requests, "get", boom)
    assert gr.fetch_readme("o", "r") is None


def test_fetch_readme_none_on_empty_body(monkeypatch):
    monkeypatch.setattr(gr.requests, "get", lambda url, **kw: FakeResp(text="   "))
    assert gr.fetch_readme("o", "r") is None


def test_fetch_readme_sends_token(monkeypatch):
    seen = {}

    def fake_get(url, headers=None, timeout=None):
        seen["url"] = url
        seen["headers"] = headers
        return FakeResp(text="hello")

    monkeypatch.setattr(gr.requests, "get", fake_get)
    monkeypatch.setenv("GITHUB_TOKEN", "t0k3n")
    assert gr.fetch_readme("o", "r") == "hello"
    assert seen["url"] == "https://api.github.com/repos/o/r/readme"
    assert seen["headers"]["Authorization"] == "Bearer t0k3n"
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_github_readme.py -v`
Expected: ERROR（模块不存在）

- [ ] **Step 3: 实现 `src/github_readme.py`**

```python
"""抓取 GitHub 仓库 README 并截断, 失败返回 None(调用方回退榜单描述)."""
from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

TIMEOUT = 30


def fetch_readme(owner: str, name: str, max_chars: int = 5000) -> str | None:
    headers = {"Accept": "application/vnd.github.raw+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{name}/readme",
            headers=headers,
            timeout=TIMEOUT,
        )
    except requests.RequestException:
        logger.warning("README 请求异常 %s/%s", owner, name, exc_info=True)
        return None
    if resp.status_code != 200:
        logger.warning("README 获取失败 %s/%s: HTTP %d", owner, name, resp.status_code)
        return None
    text = resp.text.strip()
    return text[:max_chars] if text else None
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_github_readme.py -v`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add src/github_readme.py tests/test_github_readme.py
git commit -m "feat: README 抓取与截断"
```

---

### Task 3: analyzer — DeepSeek 逐项分析与今日总览

**Files:**
- Create: `src/analyzer.py`
- Test: `tests/test_analyzer.py`

- [ ] **Step 1: 写失败测试 `tests/test_analyzer.py`**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_analyzer.py -v`
Expected: ERROR（模块不存在）

- [ ] **Step 3: 实现 `src/analyzer.py`**

```python
"""调用火山方舟 DeepSeek 逐项目分析并生成今日总览."""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

from openai import OpenAI

from .fetch_trending import TrendingRepo

logger = logging.getLogger(__name__)

ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "deepseek-v3-1-terminus"
MAX_RETRIES = 2
RETRY_DELAY = 5
ONE_LINER_MAX = 60

REPO_PROMPT = """\
你是资深开源技术分析师。请分析以下 GitHub Trending 项目, 用中文输出。

项目: {full_name}
Stars: {stars}
官方描述: {description}
README 节选:
{readme}

输出要求(严格遵守):
- 第一行: 一句话简介, 不超过 40 字, 不要任何前缀、标点序号或加粗
- 第二行: 空行
- 之后: 详细介绍(Markdown), 依次包含四个小节: **解决什么问题**、**核心功能**、**技术亮点**、**适合谁用**, 共 200~400 字
"""

OVERVIEW_PROMPT = """\
你是技术日报主编。以下是今天 GitHub Trending 榜单全部项目及一句话简介:

{repo_lines}

请用中文写一段「今日看点」总览, 3~5 句话, 归纳今天榜单的整体趋势与最值得关注的 2~3 个项目。直接输出正文, 不要标题。
"""


@dataclass
class Analysis:
    one_liner: str
    detail_md: str
    failed: bool = False


def _parse_analysis(text: str, repo: TrendingRepo) -> Analysis:
    lines = text.strip().splitlines()
    first = lines[0].strip()
    rest = "\n".join(lines[1:]).strip()
    if not rest or len(first) > ONE_LINER_MAX:
        # 格式不符预期: 整段作为详情, 一句话回退用榜单描述
        return Analysis(one_liner=repo.description or first[:40], detail_md=text.strip())
    return Analysis(one_liner=first, detail_md=rest)


class Analyzer:
    def __init__(self, client: OpenAI | None = None, model: str | None = None):
        self.client = client or OpenAI(base_url=ARK_BASE_URL, api_key=os.environ["ARK_API_KEY"])
        self.model = model or os.environ.get("ARK_MODEL", DEFAULT_MODEL)

    def _chat(self, prompt: str) -> str:
        last_err: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.6,
                )
                content = resp.choices[0].message.content
                if not content or not content.strip():
                    raise ValueError("LLM 返回空内容")
                return content.strip()
            except Exception as e:  # noqa: BLE001 - 重试边界需要捕获所有异常
                last_err = e
                if attempt < MAX_RETRIES:
                    delay = RETRY_DELAY * (2 ** attempt)
                    logger.warning("LLM 调用失败(第 %d 次), %ds 后重试: %s", attempt + 1, delay, e)
                    time.sleep(delay)
        raise last_err

    def analyze_repo(self, repo: TrendingRepo, readme: str | None) -> Analysis:
        prompt = REPO_PROMPT.format(
            full_name=repo.full_name,
            stars=repo.stars,
            description=repo.description or "(无)",
            readme=readme or "(未获取到 README)",
        )
        try:
            return _parse_analysis(self._chat(prompt), repo)
        except Exception:
            logger.error("项目 %s 分析失败", repo.full_name, exc_info=True)
            return Analysis(
                one_liner=repo.description or "(分析失败)",
                detail_md=f"> 注: 自动分析失败。官方描述: {repo.description or '无'}",
                failed=True,
            )

    def summarize_day(self, repos: list[TrendingRepo], analyses: list[Analysis]) -> str:
        lines = [f"- {r.full_name} (✰ {r.stars:,}): {a.one_liner}"
                 for r, a in zip(repos, analyses)]
        try:
            return self._chat(OVERVIEW_PROMPT.format(repo_lines="\n".join(lines)))
        except Exception:
            logger.error("今日看点生成失败", exc_info=True)
            return ""
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_analyzer.py -v`
Expected: 6 passed

- [ ] **Step 5: 提交**

```bash
git add src/analyzer.py tests/test_analyzer.py
git commit -m "feat: DeepSeek 逐项分析与今日总览(重试+占位兜底)"
```

---

### Task 4: report — Markdown 日报渲染

**Files:**
- Create: `src/report.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: 写失败测试 `tests/test_report.py`**

```python
from src.analyzer import Analysis
from src.fetch_trending import TrendingRepo
from src.report import render_report

REPO = TrendingRepo(owner="foo", name="bar", url="https://github.com/foo/bar",
                    stars=1234, description="demo")


def test_render_report_structure():
    md = render_report("2026-07-27", "总览内容", [REPO], [Analysis("一句话", "详细内容")])
    assert "# GitHub Trending 日报 · 2026-07-27" in md
    assert "## 今日看点" in md and "总览内容" in md
    assert "| 1 | [foo/bar](https://github.com/foo/bar) | 1,234 | 一句话 |" in md
    assert "### 1. [foo/bar](https://github.com/foo/bar) ✰ 1,234" in md
    assert "详细内容" in md


def test_render_report_without_overview():
    md = render_report("2026-07-27", "", [REPO], [Analysis("一句话", "详情")])
    assert "## 今日看点" not in md


def test_render_report_escapes_pipe_and_marks_failure():
    md = render_report("2026-07-27", "", [REPO], [Analysis("有|竖线", "详情", failed=True)])
    assert "有\\|竖线" in md
    assert "> 注: 本项目自动分析失败" in md
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_report.py -v`
Expected: ERROR（模块不存在）

- [ ] **Step 3: 实现 `src/report.py`**

```python
"""渲染 Markdown 日报."""
from __future__ import annotations

from .analyzer import Analysis
from .fetch_trending import TrendingRepo


def render_report(date_str: str, overview: str,
                  repos: list[TrendingRepo], analyses: list[Analysis]) -> str:
    lines = [
        f"# GitHub Trending 日报 · {date_str}",
        "",
        "> 由 DeepSeek 自动分析生成",
        "",
    ]
    if overview:
        lines += ["## 今日看点", "", overview, ""]
    lines += [
        "## 项目速览",
        "",
        "| # | 项目 | Stars | 一句话简介 |",
        "|---|------|-------|-----------|",
    ]
    for i, (r, a) in enumerate(zip(repos, analyses), 1):
        one = a.one_liner.replace("|", "\\|")
        lines.append(f"| {i} | [{r.full_name}]({r.url}) | {r.stars:,} | {one} |")
    lines += ["", "## 项目详情", ""]
    for i, (r, a) in enumerate(zip(repos, analyses), 1):
        lines += [f"### {i}. [{r.full_name}]({r.url}) ✰ {r.stars:,}", ""]
        if a.failed:
            lines += ["> 注: 本项目自动分析失败", ""]
        lines += [a.detail_md, ""]
    return "\n".join(lines)
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_report.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/report.py tests/test_report.py
git commit -m "feat: Markdown 日报渲染"
```

---

### Task 5: feishu — 卡片构造与 webhook 发送

**Files:**
- Create: `src/feishu.py`
- Test: `tests/test_feishu.py`

- [ ] **Step 1: 写失败测试 `tests/test_feishu.py`**

```python
import base64

import pytest

import src.feishu as fs
from src.analyzer import Analysis
from src.fetch_trending import TrendingRepo

REPO = TrendingRepo(owner="foo", name="bar", url="https://github.com/foo/bar",
                    stars=100, description="demo")
AN = Analysis(one_liner="一句话", detail_md="详情")


def test_gen_sign_deterministic():
    s1 = fs.gen_sign("secret", 1700000000)
    assert s1 == fs.gen_sign("secret", 1700000000)
    assert s1 != fs.gen_sign("other", 1700000000)
    assert len(base64.b64decode(s1)) == 32  # HmacSHA256 摘要 32 字节


def test_build_card_with_report_url():
    card = fs.build_card("2026-07-27", "总览", [REPO], [AN], "https://example.com/r.md")
    assert card["header"]["title"]["content"] == "GitHub Trending 日报 · 2026-07-27"
    md_texts = [e["content"] for e in card["elements"] if e.get("tag") == "markdown"]
    assert any("总览" in t for t in md_texts)
    assert any("[foo/bar](https://github.com/foo/bar)" in t and "一句话" in t for t in md_texts)
    actions = [e for e in card["elements"] if e.get("tag") == "action"]
    assert actions and actions[0]["actions"][0]["url"] == "https://example.com/r.md"


def test_build_card_without_report_url_or_overview():
    card = fs.build_card("2026-07-27", "", [REPO], [AN], None)
    assert all(e.get("tag") != "action" for e in card["elements"])
    md_texts = [e["content"] for e in card["elements"] if e.get("tag") == "markdown"]
    assert not any("今日看点" in t for t in md_texts)


class FakeResp:
    def __init__(self, code=0, status=200):
        self._code = code
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise fs.requests.HTTPError("http error")

    def json(self):
        return {"code": self._code}


def test_send_card_success_without_secret(monkeypatch):
    sent = {}

    def fake_post(url, json=None, timeout=None):
        sent["url"] = url
        sent["body"] = json
        return FakeResp()

    monkeypatch.setattr(fs.requests, "post", fake_post)
    fs.send_card("https://hook", {"a": 1})
    assert sent["body"]["msg_type"] == "interactive"
    assert sent["body"]["card"] == {"a": 1}
    assert "sign" not in sent["body"]


def test_send_card_with_secret_adds_sign(monkeypatch):
    sent = {}
    monkeypatch.setattr(
        fs.requests, "post",
        lambda url, json=None, timeout=None: sent.update(body=json) or FakeResp())
    fs.send_card("https://hook", {"a": 1}, secret="s")
    assert "sign" in sent["body"] and "timestamp" in sent["body"]


def test_send_card_retries_then_raises(monkeypatch):
    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None):
        calls["n"] += 1
        return FakeResp(code=19001)

    monkeypatch.setattr(fs.requests, "post", fake_post)
    monkeypatch.setattr(fs.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        fs.send_card("https://hook", {})
    assert calls["n"] == 3
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_feishu.py -v`
Expected: ERROR（模块不存在）

- [ ] **Step 3: 实现 `src/feishu.py`**

```python
"""飞书群自定义机器人: interactive 卡片构造与 webhook 发送(可选签名)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time

import requests

from .analyzer import Analysis
from .fetch_trending import TrendingRepo

logger = logging.getLogger(__name__)

TIMEOUT = 30
MAX_RETRIES = 2
RETRY_DELAY = 3


def gen_sign(secret: str, timestamp: int) -> str:
    """飞书签名: 以 "{timestamp}\\n{secret}" 为 key 对空串做 HmacSHA256 再 base64."""
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def build_card(date_str: str, overview: str,
               repos: list[TrendingRepo], analyses: list[Analysis],
               report_url: str | None) -> dict:
    repo_lines = "\n".join(
        f"{i}. [{r.full_name}]({r.url}) ✰ {r.stars:,} — {a.one_liner}"
        for i, (r, a) in enumerate(zip(repos, analyses), 1)
    )
    elements: list[dict] = []
    if overview:
        elements += [
            {"tag": "markdown", "content": f"**今日看点**\n{overview}"},
            {"tag": "hr"},
        ]
    elements.append({"tag": "markdown", "content": repo_lines})
    if report_url:
        elements += [
            {"tag": "hr"},
            {"tag": "action", "actions": [{
                "tag": "button",
                "text": {"tag": "plain_text", "content": "查看完整日报"},
                "type": "primary",
                "url": report_url,
            }]},
        ]
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": f"GitHub Trending 日报 · {date_str}"},
        },
        "elements": elements,
    }


def send_card(webhook_url: str, card: dict, secret: str | None = None) -> None:
    body: dict = {"msg_type": "interactive", "card": card}
    if secret:
        ts = int(time.time())
        body["timestamp"] = str(ts)
        body["sign"] = gen_sign(secret, ts)
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(webhook_url, json=body, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code", 0) != 0:
                raise RuntimeError(f"飞书返回错误: {data}")
            logger.info("飞书推送成功")
            return
        except Exception as e:  # noqa: BLE001 - 重试边界需要捕获所有异常
            last_err = e
            if attempt < MAX_RETRIES:
                logger.warning("飞书推送失败(第 %d 次), 重试: %s", attempt + 1, e)
                time.sleep(RETRY_DELAY)
    raise last_err
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_feishu.py -v`
Expected: 6 passed

- [ ] **Step 5: 提交**

```bash
git add src/feishu.py tests/test_feishu.py
git commit -m "feat: 飞书卡片构造与 webhook 发送(签名+重试)"
```

---

### Task 6: main — generate / notify 编排

**Files:**
- Create: `src/main.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: 写失败测试 `tests/test_main.py`**

```python
import json

import src.main as main
from src.analyzer import Analysis
from src.fetch_trending import TrendingRepo

REPO = TrendingRepo(owner="foo", name="bar", url="https://github.com/foo/bar",
                    stars=100, description="demo")


class FakeAnalyzer:
    def __init__(self, *args, **kwargs):
        pass

    def analyze_repo(self, repo, readme):
        return Analysis(one_liner="一句话", detail_md="详情")

    def summarize_day(self, repos, analyses):
        return "今日总览"


def _patch_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(main, "BUILD_DIR", tmp_path / "build")
    monkeypatch.setattr(main, "CARD_PATH", tmp_path / "build" / "card.json")


def test_generate_writes_report_and_card(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(main, "fetch_trending", lambda: [REPO, REPO])
    monkeypatch.setattr(main, "fetch_readme", lambda owner, name: "readme")
    monkeypatch.setattr(main, "Analyzer", FakeAnalyzer)
    monkeypatch.setenv("REPORT_BASE_URL", "https://example.com/reports")
    main.generate()
    date_str = main.today_str()
    report = (tmp_path / "reports" / f"{date_str}.md").read_text(encoding="utf-8")
    assert "foo/bar" in report and "今日总览" in report
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
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_main.py -v`
Expected: ERROR（模块不存在）

- [ ] **Step 3: 实现 `src/main.py`**

```python
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
        render_report(date_str, overview, repos, analyses), encoding="utf-8")
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
```

- [ ] **Step 4: 运行全量测试确认通过**

Run: `.venv/bin/python -m pytest -v`
Expected: 全部通过（约 23 个用例）

- [ ] **Step 5: 提交**

```bash
git add src/main.py tests/test_main.py
git commit -m "feat: generate/notify 编排入口"
```

---

### Task 7: workflow 与 README

**Files:**
- Create: `.github/workflows/daily.yml`, `README.md`

- [ ] **Step 1: 写 `.github/workflows/daily.yml`**

```yaml
name: Daily Trending Report

on:
  schedule:
    - cron: "10 23 * * *"  # UTC 23:10 = 北京时间次日 7:10
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: daily-report
  cancel-in-progress: false

jobs:
  report:
    runs-on: ubuntu-latest
    timeout-minutes: 45
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Generate report
        env:
          ARK_API_KEY: ${{ secrets.ARK_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          REPORT_BASE_URL: https://github.com/${{ github.repository }}/blob/main/reports
        run: python -m src.main generate

      - name: Commit report
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add reports/
          if git diff --cached --quiet; then
            echo "No changes to commit"
          else
            git commit -m "report: $(TZ=Asia/Shanghai date +%F)"
            git push
          fi

      - name: Notify Feishu
        env:
          FEISHU_WEBHOOK_URL: ${{ secrets.FEISHU_WEBHOOK_URL }}
          FEISHU_WEBHOOK_SECRET: ${{ secrets.FEISHU_WEBHOOK_SECRET }}
        run: python -m src.main notify
```

- [ ] **Step 2: 写 `README.md`**

````markdown
# github-trending-daily

每天早上自动分析 GitHub Trending 榜单并推送到飞书群。

## 工作方式

GitHub Actions 每天 UTC 23:10（北京时间 7:10）触发：

1. 获取 GitHub Trending 榜单（首选 [newsnow](https://newsnow.busiyi.world/) API，失败降级直接抓取 github.com/trending）
2. 逐项目抓取 README，调用火山方舟 DeepSeek 生成中文分析
3. 生成日报 `reports/YYYY-MM-DD.md` 并提交到本仓库
4. 向飞书群 webhook 推送摘要卡片（含日报链接）

## 部署

1. 飞书群: 设置 → 群机器人 → 添加「自定义机器人」，复制 webhook 地址（建议开启签名校验）
2. 仓库 Settings → Secrets and variables → Actions 添加:
   - `ARK_API_KEY`: 火山方舟 API Key
   - `FEISHU_WEBHOOK_URL`: 群机器人 webhook 地址
   - `FEISHU_WEBHOOK_SECRET`: （可选）签名密钥
3. Actions 页手动触发 `Daily Trending Report` 验证

## 本地调试

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export ARK_API_KEY=xxx
.venv/bin/python -m src.main generate --limit 3   # 只分析前 3 个项目, 产出 reports/ 与 build/card.json
export FEISHU_WEBHOOK_URL=xxx
.venv/bin/python -m src.main notify               # 真实推送到群, 谨慎执行
```

环境变量: `ARK_MODEL`（默认 `deepseek-v3-1-terminus`）、`REPORT_BASE_URL`（卡片日报链接前缀，缺省则卡片无链接按钮）、`GITHUB_TOKEN`（提高 README 抓取限流阈值）

## 测试

```bash
.venv/bin/python -m pytest
```
````

- [ ] **Step 3: 校验 workflow YAML 语法**

Run: `.venv/bin/python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/daily.yml').read_text()); print('yaml ok')"`
（若 venv 无 pyyaml 先 `.venv/bin/pip install pyyaml`）
Expected: `yaml ok`

- [ ] **Step 4: 提交**

```bash
git add .github/workflows/daily.yml README.md
git commit -m "feat: 每日定时 workflow 与使用说明"
```

---

### Task 8: 本地端到端验证（真实外部服务）

前置：向用户索要 `ARK_API_KEY`（或经用户同意复用现有 key）；此步骤消耗少量 token（约 3 个项目）。

- [ ] **Step 1: 真实运行 generate（限 3 个项目）**

```bash
export ARK_API_KEY=<用户提供>
.venv/bin/python -m src.main generate --limit 3
```

Expected: 日志显示榜单来源与逐项分析进度；生成 `reports/<今日>.md` 与 `build/card.json`

- [ ] **Step 2: 人工检查产物质量**

```bash
cat reports/$(TZ=Asia/Shanghai date +%F).md
cat build/card.json
```

检查: 日报含今日看点/速览表/逐项详情且为中文；card.json 结构完整、无日报链接按钮（本地未设 `REPORT_BASE_URL`，符合预期）

- [ ] **Step 3: （可选，经用户同意）配置 webhook 后真实推送一条**

```bash
export FEISHU_WEBHOOK_URL=<用户提供>
export FEISHU_WEBHOOK_SECRET=<若开启签名>
.venv/bin/python -m src.main notify
```

Expected: 日志 `飞书推送成功`，群里收到卡片

- [ ] **Step 4: 清理本次测试产物（不提交测试日报）**

```bash
git status   # 确认 reports/ 下今日文件为未跟踪状态
rm -f reports/$(TZ=Asia/Shanghai date +%F).md
```

---

### Task 9: 创建 GitHub 仓库并部署验证（需用户参与）

- [ ] **Step 1: 检查 gh CLI 登录态**

Run: `gh auth status`
若未登录: 请用户执行 `gh auth login` 或改为手动在网页创建仓库

- [ ] **Step 2: 创建 Public 仓库并推送**

```bash
gh repo create github-trending-daily --public --source . --push
```

Expected: 仓库创建成功, main 分支已推送

- [ ] **Step 3: 配置 Secrets（值由用户提供）**

```bash
gh secret set ARK_API_KEY
gh secret set FEISHU_WEBHOOK_URL
gh secret set FEISHU_WEBHOOK_SECRET   # 可选
```

- [ ] **Step 4: 手动触发 workflow 并观察**

```bash
gh workflow run "Daily Trending Report" && sleep 10 && gh run watch
```

Expected: 全部步骤绿色; 仓库出现 `reports/<今日>.md` 提交; 飞书群收到卡片且日报链接可打开

- [ ] **Step 5: 收尾确认**

- 确认 Actions 定时任务已启用（Actions 页可见 schedule）
- 提醒用户: `~/workspace/code/dev/open_ai_test.py` 中明文 key 建议轮换

---

## Self-Review 结果

1. **Spec 覆盖**: 双来源降级(Task 1)、README 抓取回退(Task 2)、逐项分析+重试+占位/总览失败兜底(Task 3)、日报结构(Task 4)、卡片/签名/重试/无链接省略按钮(Task 5)、generate/notify 两阶段与幂等覆盖写(Task 6)、workflow 先 push 后通知+同日幂等(Task 7)、部署步骤(Task 9)——全部对应。
2. **占位符扫描**: 无 TBD/TODO；所有代码/命令完整给出。
3. **类型一致性**: `TrendingRepo(owner,name,url,stars,description)`、`Analysis(one_liner,detail_md,failed)`、`Analyzer(client,model)`、`render_report(date_str,overview,repos,analyses)`、`build_card(...,report_url)`、`send_card(webhook_url,card,secret)` 在各任务间一致。
