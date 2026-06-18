# AI 产业链追踪

每天自动抓取全球 AI 行业热点，用 Claude API 分析对产业链各层和具体公司的影响，结果推送到 GitHub，前端静态页面实时展示。

## 效果

- **左侧**：AI 产业链五层（算力→数据→模型→工具→应用），高亮受影响的层
- **中间**：当日热点 Feed，按类别过滤
- **右侧**：点击热点，查看对每一层的具体影响 + 受影响公司详情（正/负/中性，影响深度）

## 目录结构

```
ai-chain-tracker/
├── .github/
│   └── workflows/
│       └── daily_update.yml   # GitHub Actions 定时任务
├── backend/
│   ├── fetcher.py             # 新闻抓取（arXiv / HN / NewsAPI）
│   ├── analyzer.py            # Claude API 分析
│   ├── store.py               # JSON 文件存储
│   ├── pipeline.py            # 主流程（抓取→分析→存储→git push）
│   └── requirements.txt
├── frontend/
│   └── index.html             # 纯静态前端（读 data/latest.json）
├── data/                      # 自动生成，由 GitHub Actions 维护
│   ├── latest.json            # 前端直接读取
│   ├── seen_ids.json          # 去重记录
│   └── daily/
│       └── YYYY-MM-DD.json    # 每日归档
└── setup.sh                   # 一键初始化脚本
```

## 快速开始

### 1. 创建 GitHub 仓库

在 GitHub 新建空仓库（**不要**勾选 README），然后：

```bash
cd ai-chain-tracker
bash setup.sh https://github.com/YOUR_USERNAME/YOUR_REPO.git
```

### 2. 配置 Secrets

进入仓库 **Settings → Secrets and variables → Actions**，添加：

| Secret 名 | 值 | 说明 |
|---|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | 必填，[获取地址](https://console.anthropic.com) |
| `NEWS_API_KEY` | `...` | 可选，[newsapi.org](https://newsapi.org) 免费 100 次/天 |

### 3. 手动触发第一次运行

进入仓库 **Actions → Daily AI Chain Update → Run workflow**。

运行完成后，`data/` 目录会自动出现并提交回仓库。

### 4. 开启 GitHub Pages（前端）

**Settings → Pages → Source: Deploy from a branch → Branch: main / (root)**

访问 `https://YOUR_USERNAME.github.io/YOUR_REPO/frontend/` 即可。

---

## 本地开发

```bash
cd backend
pip install -r requirements.txt

export ANTHROPIC_API_KEY="sk-ant-..."

# 测试抓取
python fetcher.py

# 测试单条分析
python analyzer.py

# 完整流程（单条模式，不用批量 API）
python pipeline.py --single

# 只抓取不分析（验证网络）
python pipeline.py --dry-run
```

## 费用估算

| 模式 | 每次成本 | 说明 |
|---|---|---|
| Batch API（默认）| ~$0.05–0.15 | 处理 15 条文章，节省 50% |
| 单条模式 | ~$0.10–0.30 | 实时返回，调试用 |
| 月费用 | ~$1.5–4.5 | 每天运行一次 |

## 定时任务

默认每天 UTC 08:00（北京时间 16:00）运行。修改 `.github/workflows/daily_update.yml` 中的 cron 表达式可以调整时间。

## 数据格式

`data/latest.json` 示例：

```json
{
  "updated_at": "2025-01-15T08:30:00Z",
  "count": 15,
  "items": [
    {
      "article_id": "abc123",
      "date": "2025-01-15",
      "article": {
        "title": "Nvidia Blackwell GB200 开始出货",
        "url": "https://...",
        "source": "HackerNews"
      },
      "analysis": {
        "news_title": "Blackwell GB200 大规模出货",
        "category": "芯片",
        "heat": "极热",
        "layers": {
          "compute": {
            "impact_level": "high",
            "summary": "...",
            "companies": [...]
          }
        }
      }
    }
  ]
}
```
