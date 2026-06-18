"""
store.py — 数据存储层
用 JSON 文件存储（无需数据库，直接 commit 到 GitHub 即可被前端读取）

目录结构：
  data/
    seen_ids.json          — 已处理文章 ID 集合（去重用）
    daily/
      2025-01-15.json      — 当天分析结果
    latest.json            — 最新 N 条（前端直接读这个）
"""

import json
import os
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).parent.parent / "data"))
DAILY_DIR = DATA_DIR / "daily"
SEEN_IDS_FILE = DATA_DIR / "seen_ids.json"
LATEST_FILE = DATA_DIR / "latest.json"
LATEST_KEEP = 30   # latest.json 保留最近 N 条


def _ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DAILY_DIR.mkdir(parents=True, exist_ok=True)


# ─── seen_ids（去重） ──────────────────────────────────────

def load_seen_ids() -> set[str]:
    _ensure_dirs()
    if SEEN_IDS_FILE.exists():
        return set(json.loads(SEEN_IDS_FILE.read_text()))
    return set()


def save_seen_ids(ids: set[str]):
    _ensure_dirs()
    SEEN_IDS_FILE.write_text(json.dumps(sorted(ids), ensure_ascii=False, indent=2))


# ─── 每日文件 ─────────────────────────────────────────────

def today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_daily(date_str: str | None = None) -> list[dict]:
    _ensure_dirs()
    date_str = date_str or today_str()
    path = DAILY_DIR / f"{date_str}.json"
    if path.exists():
        return json.loads(path.read_text())
    return []


def save_daily(records: list[dict], date_str: str | None = None):
    _ensure_dirs()
    date_str = date_str or today_str()
    path = DAILY_DIR / f"{date_str}.json"
    existing = load_daily(date_str)
    # 合并，按 article_id 去重
    merged = {r["article_id"]: r for r in existing}
    for r in records:
        merged[r["article_id"]] = r
    final = sorted(merged.values(),
                   key=lambda x: x.get("fetched_at", ""), reverse=True)
    path.write_text(json.dumps(final, indent=2, ensure_ascii=False))
    log.info(f"Saved {len(final)} records to {path}")
    return final


# ─── latest.json（前端消费） ──────────────────────────────

def rebuild_latest(days: int = 7):
    """
    从最近 days 天的 daily 文件重建 latest.json
    每条记录结构：
    {
      "article_id": "...",
      "date": "2025-01-15",
      "fetched_at": "...",
      "article": { "title", "summary", "url", "source" },
      "analysis": { news_title, category, heat, layers... }
    }
    """
    _ensure_dirs()
    all_records = []
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        all_records.extend(load_daily(d))

    # 按时间降序，取最新 LATEST_KEEP 条
    all_records.sort(key=lambda x: x.get("fetched_at", ""), reverse=True)
    latest = all_records[:LATEST_KEEP]

    LATEST_FILE.write_text(json.dumps({
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(latest),
        "items": latest,
    }, indent=2, ensure_ascii=False))
    log.info(f"Rebuilt latest.json: {len(latest)} items")
    return latest


# ─── 单条写入 ─────────────────────────────────────────────

def save_one(article: dict, analysis: dict) -> dict:
    """保存单条分析结果"""
    record = {
        "article_id": article["id"],
        "date": today_str(),
        "fetched_at": article.get("fetched_at", ""),
        "article": {
            "title": article["title"],
            "summary": article.get("summary", ""),
            "url": article.get("url", ""),
            "source": article.get("source", ""),
            "published_at": article.get("published_at", ""),
        },
        "analysis": analysis,
    }
    save_daily([record])
    return record


if __name__ == "__main__":
    # 测试
    rebuild_latest()
    print("latest.json rebuilt")
    latest = json.loads(LATEST_FILE.read_text())
    print(f"Items: {latest['count']}, updated: {latest['updated_at']}")
