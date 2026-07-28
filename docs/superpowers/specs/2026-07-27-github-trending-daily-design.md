# GitHub Trending 每日 AI 分析日报 — 设计文档

日期：2026-07-27
状态：已与用户确认

## 1. 背景与目标

每天早上（北京时间 8:00 左右）自动完成：

1. 获取 GitHub Trending 当日榜单（数据口径与 newsnow 的 github 源一致）
2. 用大模型（火山方舟 DeepSeek）逐项目深度分析并生成中文介绍
3. 生成 Markdown 日报，存档到本 GitHub 仓库 `reports/`
4. 通过飞书群自定义机器人 webhook 推送摘要卡片 + 日报链接

### 非目标

- 不写飞书云文档（用户仅有群 webhook，无自建应用；以 GitHub 仓库存档替代）
- 不做 Web 界面、数据库、历史趋势分析
- 不支持多群、多数据源（当前仅 GitHub Trending 一个源）

## 2. 关键决策（已确认）

| 决策点 | 结论 |
|--------|------|
| 运行环境 | GitHub Actions 定时：北京 7:10 主推 + 12:10/18:10 补推（2026-07-28 新增；trending 是 24h 滚动窗口，白天新上榜项目增量补推） |
| 增量机制 | 当天已推送清单存 `reports/YYYY-MM-DD.json`（随日报提交）；每次运行只解读清单外的新项目，主推=清单为空的首次运行；日报由清单全量重渲染（全天累积）；卡片只含本次新项目，无新项目静默跳过 |
| 大模型 | **不使用自有 LLM**（2026-07-28 用户决策）：DeepWiki `ask_question` 直出中文解读（按日报格式提问 + 清洗服务端尾巴），未索引时依次用 zread.ai og:description / Context7 search description（英文）兜底，全无则用榜单原始描述。已知代价：兜底内容为英文、格式依赖 DeepWiki 遵循度、免费服务无 SLA |
| 分析策略 | 逐项目获取解读；「今日看点」总览已按用户要求移除（2026-07-28） |
| 分析范围 | 榜单全部项目（通常 10~30 个） |
| 群消息详略 | 每项目一行（名称 + star + 一句话简介），完整分析看日报链接 |
| 存档 | 本仓库 `reports/YYYY-MM-DD.md`，由 workflow 提交 |
| 仓库 | `github-trending-daily`，Public（群成员点链接可直接查看） |
| 代码组织 | 轻度模块化：4 个职责单一模块 + main 编排，无框架 |

## 3. 总体数据流

```
GitHub Actions (UTC 23:10 触发, 支持 workflow_dispatch 手动触发)
  │
  ├─ ① fetch_trending  获取榜单
  │     首选: GET https://newsnow.busiyi.world/api/s?id=github-trending-today
  │           (必须带浏览器 User-Agent, 否则被 Cloudflare 拦截)
  │     降级: GET https://github.com/trending?spoken_language_code= 解析 HTML
  │           (newsnow 该源本身就是爬此页面, 两者数据等价, 已验证)
  │
  ├─ ② 逐项目获取解读(无 LLM)
  │     主力: DeepWiki POST https://mcp.deepwiki.com/mcp (JSON-RPC ask_question, 免费无鉴权)
  │       按日报格式提问, 返回中文解读; 清洗服务端尾巴(## Notes / Wiki pages / View this search)
  │     兜底1: zread.ai/{owner}/{repo} 页面 og:description (英文一句话)
  │     兜底2: context7.com/api/v1/search?query={name}, id/title 精确匹配 (英文一句话)
  │     全无: 榜单自带描述
  │
  ├─ ③ digest  纯组装(无网络)
  │     DeepWiki 命中: 第一行→一句话简介, 其余→详情
  │     仅兜底简介: 标注「未获得 DeepWiki 深度解读」, degraded=True
  │
  ├─ ④ report  渲染 reports/YYYY-MM-DD.md (日期取 Asia/Shanghai 时区)
  │     同时把飞书卡片 JSON 写到 build/card.json (不提交)
  │     workflow 步骤负责 git commit + push (脚本本身不做 git 操作)
  │
  └─ ⑤ feishu  读取 build/card.json, POST 到群 webhook
        (在 push 之后执行, 保证群里日报链接已可访问)
        卡片 = 项目列表(每行: [名称](url) ✰star — 一句话) + 日报链接
```

## 4. 项目结构

```
github-trending-daily/
├── .github/workflows/daily.yml   # 定时 + 手动触发; 安装依赖 → 运行 → 提交报告
├── src/
│   ├── __init__.py
│   ├── fetch_trending.py         # ① 榜单获取, 含 Cloudflare 降级逻辑
│   ├── deepwiki.py               # ② DeepWiki 中文解读(主力信息源)
│   ├── zread.py                  # ② zread og:description 兜底
│   ├── context7.py               # ② context7 search 兜底
│   ├── digest.py                 # ③ 解读/简介 → 日报条目(纯组装)
│   ├── state.py                  # ③ 当天已推送清单读写(增量补推的状态源)
│   ├── report.py                 # ④ Markdown 日报渲染
│   ├── feishu.py                 # ⑤ 卡片构造 + webhook 发送(含可选签名)
│   └── main.py                   # 编排; --dry-run / --limit N 便于本地调试
├── tests/                        # pytest 单测, mock 所有外部调用
├── reports/                      # 每日日报存档
├── requirements.txt              # requests, openai, beautifulsoup4, pytest
└── README.md                     # 部署与使用说明
```

## 5. 组件接口

### 5.1 fetch_trending.py

```python
@dataclass
class TrendingRepo:
    owner: str        # "nodejs"
    name: str         # "node"
    url: str          # "https://github.com/nodejs/node"
    stars: int        # 118544 (从 "✰ 118,544" 解析)
    description: str  # 榜单自带一句话描述, 可为空

def fetch_trending() -> list[TrendingRepo]
```

- newsnow 响应格式：`{"status": "success", "items": [{"url", "title", "id", "extra": {"info": "✰ 31,374", "hover": "描述"}}]}`
- newsnow 请求失败（非 200 / 非 JSON / status != success）时降级抓 GitHub Trending 页面，用 BeautifulSoup 解析（选择器与 newsnow 源码一致：`article` 下 `h2 a` 取名称、`[href$=stargazers]` 取 star、`p` 取描述）
- 两个来源都失败 → 抛异常，整个任务失败（Actions 标红，GitHub 邮件通知）

### 5.2 deepwiki.py（主力信息源）

```python
def fetch_deepwiki_summary(owner: str, name: str) -> str | None
```

- POST `https://mcp.deepwiki.com/mcp`（官方 MCP 端点，JSON-RPC `tools/call` → `ask_question`，免费无鉴权）
- 提问要求日报固定格式（第一行一句话简介 + 四小节详细介绍，全中文）
- 解析 SSE 响应取带 `result` 事件的 `content[0].text`，跳过 ping 注释与 notifications 事件；按 UTF-8 显式解码（响应头无 charset）
- 清洗服务端固定尾巴：`## Notes` / `Wiki pages you might want to explore` / `View this search on DeepWiki` 起截断
- 输出规范化：偶发 HTML 形态（`<p>/<strong>/<br>`）转 Markdown；清理引用角标残留的中文标点前空格
- 语言判定：中文占比（中文字符/(中文字符+英文字母)）< 0.3 视为英文回答，返回 None 走兜底（阈值容忍技术专有名词的英文字母）
- 未索引（文本以 `Error processing question` 开头）/ HTTP / 网络 / 解析失败均返回 None

### 5.2b zread.py / context7.py（兜底简介，英文）

```python
def fetch_zread_description(owner: str, name: str) -> str | None      # og:description
def fetch_context7_description(owner: str, name: str) -> str | None  # search API, id/title 精确匹配
```

- zread 无公开 API，取项目页 `og:description` meta；页面不存在/无 meta 返回 None
- context7 搜索按名称模糊命中，仅接受 `id == /owner/name` 或 `title == name` 的精确匹配，避免同名误命中
- 仅在 DeepWiki 未命中时才调用（省请求）

### 5.3 digest.py（纯组装，无网络）

```python
@dataclass
class Analysis:
    one_liner: str          # 一句话简介, ≤60 字
    detail_md: str          # 详情 Markdown
    degraded: bool = False  # 未获得 DeepWiki 深度解读, 仅有简介

def build_analysis(repo: TrendingRepo, wiki: str | None, fallback_desc: str | None) -> Analysis
```

- wiki 命中且格式正常（首行 ≤60 字且有正文）：首行→one_liner，其余→detail_md
- wiki 首行超长/无正文结构：one_liner 从中文解读首句提取（按句末标点切分+截断），整段作 detail_md；**不回退英文榜单描述**（2026-07-28 修复：此前回退导致卡片混入英文）
- 无 wiki：`fallback_desc or repo.description or "(无可用介绍)"` 作简介，detail_md 标注「未获得 DeepWiki 深度解读, 仅展示简介」，degraded=True

### 5.4 report.py

```python
def render_report(date_str: str, repos: list[TrendingRepo],
                  analyses: list[Analysis]) -> str
```

日报结构：

```markdown
# GitHub Trending 日报 · 2026-07-27

> 由 DeepWiki 自动解读生成

## 项目速览
| # | 项目 | Stars | 一句话简介 |
|---|------|-------|-----------|

## 项目详情
### 1. owner/name ✰ 31,374
（详细分析）
...
```

### 5.5 feishu.py

```python
def build_card(date_str: str, repos, analyses, report_url: str | None) -> dict
def send_card(webhook_url: str, card: dict, secret: str | None = None) -> None
```

- `msg_type: interactive` 卡片：蓝色 header「GitHub Trending 日报 · 日期」+ 项目列表（lark_md，每行 `[owner/name](url) ✰ 31,374 — 一句话`）+ 底部日报链接按钮
- 日报链接：`https://github.com/<owner>/github-trending-daily/blob/main/reports/YYYY-MM-DD.md`
- 可选签名：设置了 `FEISHU_WEBHOOK_SECRET` 时按飞书规范计算 HmacSHA256 签名（`timestamp\nsecret` 为 key 对空串签名，base64）
- 发送失败（HTTP 非 200 或响应 `code != 0`）重试 2 次后抛异常
- 卡片体积安全：30 项目 × ~100 字符/行 ≈ 4KB，远低于飞书 30KB 上限

### 5.6 main.py

两个子命令，对应 workflow 的两个阶段（先 push 报告、后发飞书，保证群里链接可用）：

```
python -m src.main generate [--limit N]   # ①②③④: 生成 reports/*.md 与 build/card.json
python -m src.main notify                 # ⑤: 读 build/card.json 发送飞书
```

- `generate` 只写本地文件、无外部副作用，本地调试直接跑它即可（`--limit N` 限制项目数以降低调试成本），不跑 `notify` 就不会打扰群
- `notify` 与生成解耦：workflow 在 push 报告之后才执行它

环境变量：

| 变量 | 必填 | 说明 |
|------|------|------|
| `FEISHU_WEBHOOK_URL` | notify 时必填 | 群机器人 webhook 地址（generate 阶段不需要） |
| `FEISHU_WEBHOOK_SECRET` | 否 | 机器人签名校验密钥 |
| `REPORT_BASE_URL` | 否 | 日报链接前缀；Actions 中由 workflow 传入 `https://github.com/${{ github.repository }}/blob/main/reports`，本地未设置时卡片省略链接按钮 |

（无 LLM 后不再需要任何模型相关密钥与配置）

### 5.7 daily.yml

- `on: schedule`（UTC 23:10/04:10/10:10 = 北京 7:10 主推 + 12:10/18:10 补推）+ `workflow_dispatch`
- `permissions: contents: write`
- 步骤：checkout → setup-python 3.12 → `pip install -r requirements.txt` → `python -m src.main generate` → 以 `github-actions[bot]` 身份 commit `reports/` 并 push（提交信息如 `report: 2026-07-27`，无编辑器署名）→ `python -m src.main notify`
- 先 push 后发飞书：群成员点开链接时日报必定已存在
- 报告文件已存在时覆盖重写（同日重跑幂等）

## 6. 错误处理汇总

| 故障 | 处理 |
|------|------|
| newsnow 被 Cloudflare 拦 | 降级直接抓 github.com/trending |
| 两个榜单来源都失败 | 任务失败，Actions 标红 + GitHub 邮件 |
| 单项目 DeepWiki 失败/未索引/返回英文主导内容 | 依次回退 zread → context7 → 榜单描述，日报标注「未获得深度解读」，不中断 |
| zread/context7 也失败 | 用榜单原始描述占位，不中断 |
| 飞书发送失败（重试后） | 任务失败标红（日报已提交，不丢数据） |

## 7. 测试策略

pytest，全部 mock 外部 HTTP / LLM：

- newsnow JSON 解析（含 star 数 `"✰ 31,374"` → 31374、空描述）
- GitHub Trending HTML 降级解析（用本地 fixture HTML）
- newsnow 失败 → 降级路径触发
- README 截断、404 回退
- LLM 输出解析（正常格式 / 异常格式兜底）与重试
- 日报渲染（关键结构断言）
- 卡片 JSON 结构、签名计算、发送重试
- main 编排：generate 产出两个文件且不触发发送、单项目失败不中断、notify 读取卡片发送

## 8. 部署步骤（用户操作）

1. GitHub 创建 Public 仓库 `github-trending-daily`，推送代码
2. 飞书群：设置 → 群机器人 → 添加「自定义机器人」，复制 webhook 地址（建议开启签名校验，记下密钥）
3. 仓库 Settings → Secrets and variables → Actions 添加：`ARK_API_KEY`、`FEISHU_WEBHOOK_URL`（可选 `FEISHU_WEBHOOK_SECRET`）
4. Actions 页手动触发 `workflow_dispatch` 验证全流程，检查群消息与 `reports/` 文件
5. 安全提醒：`~/workspace/code/dev/open_ai_test.py` 中硬编码的方舟 key 建议轮换

## 9. 成本估算

每天 1 次运行：约 25 个项目 × (输入 ~6K tokens + 输出 ~0.8K tokens) + 1 次总览 ≈ 17 万 tokens/天，DeepSeek 价位下约 0.2~0.5 元/天。GitHub Actions Public 仓库免费。
