# github-trending-daily

每天早上自动分析 GitHub Trending 榜单并推送到飞书群。

## 工作方式

GitHub Actions 每天 UTC 23:10（北京时间 7:10）触发：

1. 获取 GitHub Trending 榜单（首选 [newsnow](https://newsnow.busiyi.world/) API，失败降级直接抓取 github.com/trending）
2. 逐项目抓取 README，调用火山方舟大模型生成中文分析
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

环境变量: `ARK_MODEL`（默认 `doubao-seed-2-0-pro-260215`）、`REPORT_BASE_URL`（卡片日报链接前缀，缺省则卡片无链接按钮）、`GITHUB_TOKEN`（提高 README 抓取限流阈值）

## 测试

```bash
.venv/bin/python -m pytest
```
