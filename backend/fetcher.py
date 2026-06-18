"""
fetcher.py — 每日 AI 新闻抓取器
支持来源：arXiv RSS、TechCrunch、HackerNews、NewsAPI
"""

import os
import json
import hashlib
import logging
import time
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Optional
import xml.etree.ElementTree as ET

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")   # newsapi.org 免费额度 100req/day

@dataclass
class RawArticle:
    id: str                   # sha256(url)[:16]
    title: str
    summary: str
    url: str
    source: str
    published_at: str         # ISO8601
    fetched_at: str


# ─── 各数据源 ──────────────────────────────────────────────

def fetch_arxiv() -> list[RawArticle]:
    """抓取 arXiv cs.AI / cs.LG 最新论文"""
    articles = []
    feeds = [
        "https://rss.arxiv.org/rss/cs.AI",
        "https://rss.arxiv.org/rss/cs.LG",
    ]
    for url in feeds:
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            ns = {"dc": "http://purl.org/dc/elements/1.1/"}
            for item in root.findall(".//item")[:15]:
                title = item.findtext("title", "").strip()
                link  = item.findtext("link", "").strip()
                desc  = item.findtext("description", "").strip()[:400]
                pub   = item.findtext("pubDate", datetime.now(timezone.utc).isoformat())
                if not title or not link:
                    continue
                articles.append(RawArticle(
                    id=hashlib.sha256(link.encode()).hexdigest()[:16],
                    title=title, summary=desc, url=link,
                    source="arXiv", published_at=pub,
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                ))
        except Exception as e:
            log.warning(f"arXiv fetch error ({url}): {e}")
    log.info(f"arXiv: {len(articles)} articles")
    return articles


def fetch_hackernews() -> list[RawArticle]:
    """抓取 HackerNews AI 相关 Top Stories"""
    AI_KEYWORDS = {"ai", "llm", "openai", "anthropic", "deepseek", "nvidia",
                   "model", "gpt", "gemini", "claude", "mistral", "chip",
                   "inference", "training", "transformer", "agent", "rag"}
    articles = []
    try:
        top = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10
        ).json()[:60]

        for story_id in top:
            try:
                item = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                    timeout=8,
                ).json()
                if not item or item.get("type") != "story":
                    continue
                title = item.get("title", "")
                if not any(kw in title.lower() for kw in AI_KEYWORDS):
                    continue
                url = item.get("url", f"https://news.ycombinator.com/item?id={story_id}")
                articles.append(RawArticle(
                    id=hashlib.sha256(url.encode()).hexdigest()[:16],
                    title=title,
                    summary=f"HN score: {item.get('score',0)}, comments: {item.get('descendants',0)}",
                    url=url, source="HackerNews",
                    published_at=datetime.fromtimestamp(
                        item.get("time", 0), tz=timezone.utc
                    ).isoformat(),
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                ))
                time.sleep(0.05)
            except Exception:
                continue
    except Exception as e:
        log.warning(f"HackerNews fetch error: {e}")
    log.info(f"HackerNews: {len(articles)} articles")
    return articles


def fetch_newsapi() -> list[RawArticle]:
    """NewsAPI — AI 行业新闻（需要免费 API key）"""
    if not NEWS_API_KEY:
        log.info("NEWS_API_KEY not set, skipping NewsAPI")
        return []
    articles = []
    queries = ["artificial intelligence", "large language model", "OpenAI Anthropic Nvidia"]
    for q in queries:
        try:
            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params={"q": q, "language": "en", "sortBy": "publishedAt",
                        "pageSize": 10, "apiKey": NEWS_API_KEY},
                timeout=15,
            )
            for a in resp.json().get("articles", []):
                url = a.get("url", "")
                if not url:
                    continue
                articles.append(RawArticle(
                    id=hashlib.sha256(url.encode()).hexdigest()[:16],
                    title=a.get("title", "")[:200],
                    summary=(a.get("description") or "")[:400],
                    url=url, source=a.get("source", {}).get("name", "NewsAPI"),
                    published_at=a.get("publishedAt", ""),
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                ))
        except Exception as e:
            log.warning(f"NewsAPI error (q={q}): {e}")
    log.info(f"NewsAPI: {len(articles)} articles")
    return articles


# ─── 去重 ──────────────────────────────────────────────────

def deduplicate(articles: list[RawArticle], seen_ids: set[str]) -> list[RawArticle]:
    """按 id 去重，同时过滤已处理过的"""
    result, local_seen = [], set()
    for a in articles:
        if a.id not in seen_ids and a.id not in local_seen:
            result.append(a)
            local_seen.add(a.id)
    return result


# ─── 入口 ──────────────────────────────────────────────────

def fetch_all(seen_ids: set[str] | None = None) -> list[RawArticle]:
    seen_ids = seen_ids or set()
    raw = fetch_arxiv() + fetch_hackernews() + fetch_newsapi()
    deduped = deduplicate(raw, seen_ids)
    log.info(f"Total unique new articles: {len(deduped)}")
    return deduped


if __name__ == "__main__":
    articles = fetch_all()
    print(json.dumps([asdict(a) for a in articles[:3]], indent=2, ensure_ascii=False))
