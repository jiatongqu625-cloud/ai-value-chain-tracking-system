"""
pipeline.py — 主流程
每天运行一次：抓取新闻 → Claude 分析 → 存储 → git push

用法：
  python pipeline.py              # 正常运行（批量模式）
  python pipeline.py --single     # 单条逐个分析（调试用）
  python pipeline.py --dry-run    # 只抓取不分析不推送
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

# 确保能 import 同级模块
sys.path.insert(0, str(Path(__file__).parent))

from fetcher import fetch_all
from analyzer import analyze_one, analyze_batch
from store import load_seen_ids, save_seen_ids, save_one, save_daily, rebuild_latest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pipeline.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
MAX_ARTICLES_PER_RUN = int(os.getenv("MAX_ARTICLES_PER_RUN", "20"))


# ─── Git 推送 ─────────────────────────────────────────────

def git_push(message: str = ""):
    """自动 commit + push data/ 目录的变更"""
    from datetime import datetime, timezone
    if not message:
        message = f"data: daily update {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC"

    try:
        # 配置 git user（GitHub Actions 环境）
        subprocess.run(
            ["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"],
            cwd=REPO_ROOT, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "github-actions[bot]"],
            cwd=REPO_ROOT, check=True, capture_output=True,
        )

        # stage data/
        subprocess.run(
            ["git", "add", "data/"],
            cwd=REPO_ROOT, check=True, capture_output=True,
        )

        # 检查是否有变更
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=REPO_ROOT, capture_output=True,
        )
        if result.returncode == 0:
            log.info("No changes to commit.")
            return

        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=REPO_ROOT, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "push"],
            cwd=REPO_ROOT, check=True, capture_output=True,
        )
        log.info(f"Git push success: {message}")

    except subprocess.CalledProcessError as e:
        log.error(f"Git error: {e.stderr.decode() if e.stderr else e}")
        raise


# ─── 主流程 ───────────────────────────────────────────────

def run(use_batch: bool = True, dry_run: bool = False):
    log.info("═" * 60)
    log.info("Pipeline start")

    # 1. 加载已处理 ID
    seen_ids = load_seen_ids()
    log.info(f"Seen IDs: {len(seen_ids)}")

    # 2. 抓取新文章
    articles = fetch_all(seen_ids)
    articles = articles[:MAX_ARTICLES_PER_RUN]
    log.info(f"New articles to process: {len(articles)}")

    if not articles:
        log.info("Nothing new. Exiting.")
        return

    if dry_run:
        log.info("Dry run — skipping analysis and push")
        for a in articles:
            log.info(f"  [{a.source}] {a.title[:80]}")
        return

    # 3. 分析
    records = []
    if use_batch and len(articles) > 3:
        # 批量模式（更省钱，但需要等待 5-30 分钟）
        log.info("Using Batch API...")
        article_dicts = [asdict(a) for a in articles]
        batch_results = analyze_batch(article_dicts)

        id_to_article = {a.id: asdict(a) for a in articles}
        for br in batch_results:
            article = id_to_article.get(br["article_id"])
            if article:
                records.append(save_one(article, br["analysis"]))
    else:
        # 单条模式（实时，适合少量文章或调试）
        log.info("Using single-call mode...")
        for i, article in enumerate(articles):
            log.info(f"  [{i+1}/{len(articles)}] {article.title[:60]}")
            try:
                analysis = analyze_one(article.title, article.summary or "")
                records.append(save_one(asdict(article), analysis))
                time.sleep(0.5)   # 避免触发 rate limit
            except Exception as e:
                log.warning(f"  Failed to analyze '{article.title[:40]}': {e}")
                continue

    # 4. 更新 seen_ids
    new_ids = {a.id for a in articles}
    save_seen_ids(seen_ids | new_ids)

    # 5. 重建 latest.json
    rebuild_latest()

    log.info(f"Processed {len(records)} articles successfully")

    # 6. Git push
    git_push(f"data: add {len(records)} articles ({len(articles)} fetched)")
    log.info("Pipeline complete ✓")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--single",  action="store_true", help="逐条分析（不用 Batch API）")
    parser.add_argument("--dry-run", action="store_true", help="只抓取，不分析不推送")
    args = parser.parse_args()

    run(use_batch=not args.single, dry_run=args.dry_run)
