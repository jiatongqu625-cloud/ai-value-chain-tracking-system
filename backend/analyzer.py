"""
analyzer.py — 用 Claude API 分析新闻对 AI 产业链的影响
支持单条分析 + Batch 批量分析（节省 50% 成本）
"""

import os
import json
import time
import logging
from dataclasses import dataclass, asdict
from typing import Optional

import anthropic

log = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

SYSTEM_PROMPT = """你是一个 AI 产业链分析专家。用户输入一条 AI 行业新闻，你需要分析该新闻对产业链五个层级的影响并输出严格 JSON。

产业链五层定义：
- compute（基础算力层）：GPU/NPU 芯片设计、芯片制造（EDA/封装）、高性能计算集群、存储与互联（HBM/NVLink）
- data（数据与能源层）：数据采集清洗、人工/合成标注、向量数据库、电力与数据中心冷却
- model（模型基础设施层）：基础大模型预训练、后训练对齐（RLHF/DPO）、MLOps 平台、推理服务 API、模型分发 Hub
- tools（工具中间件层）：RAG 知识库、AI Agent 框架、Prompt 工程与评估、开发工具 Copilot/SDK、安全对齐工具链
- app（应用层）：企业效率自动化、消费者 AI 助手、医疗/法律/教育垂直行业、具身智能与机器人

严格输出以下 JSON，不要任何解释文字：
{
  "news_title": "15字以内标题",
  "category": "芯片|模型|开源|融资|监管|应用|研究|其他",
  "heat": "极热|热|新兴|变局",
  "heat_bg": "#FAECE7（极热）|#FAEEDA（热）|#E1F5EE（新兴）|#FBEAF0（变局）",
  "heat_c":  "#993C1D（极热）|#854F0B（热）|#085041（新兴）|#72243E（变局）",
  "layers": {
    "compute": {
      "impact_level": "high|mid|low|none",
      "badge": "6字以内标签",
      "summary": "影响机制，2-3句",
      "upside": "正面方向（无则null）",
      "downside": "负面方向（无则null）",
      "companies": [
        {
          "name": "公司名",
          "role": "在此层的角色",
          "type": "positive|negative|neutral",
          "impact_label": "6字以内",
          "reason": "影响机制一句话",
          "specific": "具体数字/事件/预期，尽量量化",
          "impact_depth": 1
        }
      ]
    },
    "data":  { "同上结构" },
    "model": { "同上结构" },
    "tools": { "同上结构" },
    "app":   { "同上结构" }
  }
}

规则：
1. impact_level=none 时 companies=[], summary 可简短
2. 只列真正受影响的公司，不要凑数
3. specific 必须包含数字或可验证事实
4. impact_depth: 1=间接  2=显著  3=核心"""


# ─── 单条分析 ──────────────────────────────────────────────

def analyze_one(article_title: str, article_summary: str,
                client: Optional[anthropic.Anthropic] = None) -> dict:
    """分析单条新闻，返回结构化 dict"""
    if client is None:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"请分析以下新闻对 AI 产业链的影响：\n\n标题：{article_title}\n\n摘要：{article_summary}"

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    # 提取 JSON（防止模型偶尔加 markdown 代码块）
    if "```" in raw:
        raw = raw.split("```")[1].lstrip("json").strip()
    return json.loads(raw)


# ─── 批量分析（Batch API，省 50% 费用）─────────────────────

def analyze_batch(articles: list[dict]) -> list[dict]:
    """
    用 Anthropic Message Batches API 批量分析
    articles: [{"id": ..., "title": ..., "summary": ...}, ...]
    返回: [{"article_id": ..., "analysis": {...}}, ...]
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    requests_list = []
    for a in articles:
        prompt = f"标题：{a['title']}\n\n摘要：{a.get('summary', '')[:400]}"
        requests_list.append({
            "custom_id": a["id"],
            "params": {
                "model": "claude-sonnet-4-6",
                "max_tokens": 2000,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": f"请分析以下新闻对 AI 产业链的影响：\n\n{prompt}"}],
            },
        })

    log.info(f"Submitting batch of {len(requests_list)} articles...")
    batch = client.beta.messages.batches.create(requests=requests_list)
    batch_id = batch.id
    log.info(f"Batch created: {batch_id}")

    # 轮询等待完成（批量通常 5-30 分钟）
    while True:
        status = client.beta.messages.batches.retrieve(batch_id)
        log.info(f"Batch status: {status.processing_status} | "
                 f"succeeded={status.request_counts.succeeded} "
                 f"errored={status.request_counts.errored} "
                 f"processing={status.request_counts.processing}")
        if status.processing_status == "ended":
            break
        time.sleep(30)

    # 收集结果
    results = []
    for result in client.beta.messages.batches.results(batch_id):
        if result.result.type == "succeeded":
            raw = result.result.message.content[0].text.strip()
            if "```" in raw:
                raw = raw.split("```")[1].lstrip("json").strip()
            try:
                analysis = json.loads(raw)
                results.append({"article_id": result.custom_id, "analysis": analysis})
            except json.JSONDecodeError as e:
                log.warning(f"JSON parse error for {result.custom_id}: {e}")
        else:
            log.warning(f"Batch item failed: {result.custom_id} — {result.result.type}")

    log.info(f"Batch complete: {len(results)}/{len(articles)} succeeded")
    return results


# ─── 入口 ──────────────────────────────────────────────────

if __name__ == "__main__":
    # 测试单条
    sample = {
        "title": "Nvidia Blackwell GB200 NVL72 开始大规模出货",
        "summary": "Nvidia 新一代 Blackwell 架构旗舰 GB200 NVL72 已开始大规模出货，"
                   "单机柜算力达 1.4 EFLOP，训练成本较 H100 下降约 40%。"
                   "微软、谷歌、CoreWeave 等云厂商已开始部署。",
    }
    result = analyze_one(sample["title"], sample["summary"])
    print(json.dumps(result, indent=2, ensure_ascii=False))
