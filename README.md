# github-trending-daily

每天早上自动分析 GitHub Trending 榜单并推送到飞书群。

## 工作方式

GitHub Actions 每天北京时间 7:10（主推）、12:10 / 18:10（补推）触发：

1. 获取 GitHub Trending 榜单（首选 [newsnow](https://newsnow.busiyi.world/) API，失败降级直接抓取 github.com/trending）
2. 与当天已推送清单（`reports/YYYY-MM-DD.json`）比对，只处理**新上榜项目**（主推 = 清单为空的首次运行）
3. 逐项目获取 [DeepWiki](https://deepwiki.com/) 中文解读（免费无需 key）；未索引时依次用 [zread.ai](https://zread.ai/) / [Context7](https://context7.com/) 的英文简介兜底
4. 全量重渲染日报 `reports/YYYY-MM-DD.md`（全天累积）并提交到本仓库
5. 向飞书群 webhook 推送卡片：主推为蓝色日报卡片，补推为橙色「新上榜 N 项」卡片，只含新项目；无新项目则静默不推送

不调用任何自有大模型，无 LLM API 成本。

## 部署

1. 飞书群: 设置 → 群机器人 → 添加「自定义机器人」，复制 webhook 地址（建议开启签名校验）
2. 仓库 Settings → Secrets and variables → Actions 添加:
   - `FEISHU_WEBHOOK_URL`: 群机器人 webhook 地址
   - `FEISHU_WEBHOOK_SECRET`: （可选）签名密钥
3. Actions 页手动触发 `Daily Trending Report` 验证

## 本地调试

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m src.main generate --limit 3   # 只处理前 3 个项目, 产出 reports/ 与 build/card.json
export FEISHU_WEBHOOK_URL=xxx
.venv/bin/python -m src.main notify               # 真实推送到群, 谨慎执行
```

环境变量: `REPORT_BASE_URL`（卡片日报链接前缀，缺省则卡片无链接按钮）

## 测试

```bash
.venv/bin/python -m pytest
```
