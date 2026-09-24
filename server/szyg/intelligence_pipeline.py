"""Question-driven marketing intelligence pipeline."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import threading
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from szyg.atomic_file import atomic_read, atomic_write
from szyg.data_path import DATA_DIR


REPORT_FILE = DATA_DIR / "intelligence_reports.json"
RUNS_FILE = DATA_DIR / "execution_runs.json"
ARCHIVED_RUNS_FILE = DATA_DIR / "execution_runs_archive.json"
_REPORT_LOCK = threading.Lock()
logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _config() -> dict[str, Any]:
    try:
        from szyg.config.loader import load_config

        return load_config().get("intelligence", {}) or {}
    except Exception:
        return {}


def _enabled_platforms() -> list[str]:
    configured = _config().get("collectors") or {}
    supported = ("douyin", "xhs", "kuaishou", "bilibili", "weibo")
    return [
        platform for platform in supported
        if configured.get(platform, "enabled") not in {False, "disabled", "off"}
    ]


def _read_rows(path: Path) -> list[dict[str, Any]]:
    rows = atomic_read(path)
    return rows if isinstance(rows, list) else []


def _clean_text(value: Any, limit: int = 2000) -> str:
    text = str(value or "")
    text = re.sub(r"(?:[A-Za-z]:\\|/)[^\s]+", " ", text)
    text = re.sub(r"\b(?:exec|batch|task|step)_[A-Za-z0-9_-]+\b", " ", text)
    text = re.sub(r"(?:SZYG\s*AI生成|AI生成内容)", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def load_published_context(limit: int | None = None) -> list[dict[str, Any]]:
    max_records = int(limit or _config().get("max_publish_records") or 100)
    rows = _read_rows(RUNS_FILE) + _read_rows(ARCHIVED_RUNS_FILE)
    published: list[dict[str, Any]] = []
    seen: set[str] = set()
    for run in sorted(rows, key=lambda item: str(item.get("finished_at") or item.get("created_at") or ""), reverse=True):
        if run.get("status") != "success" or not str(run.get("task_type") or "").startswith("publish_"):
            continue
        payload = run.get("input") if isinstance(run.get("input"), dict) else {}
        title = _clean_text(payload.get("title"), 200)
        body = _clean_text(payload.get("note") or payload.get("desc") or payload.get("description") or payload.get("content"), 1500)
        tags = [_clean_text(item, 60) for item in (payload.get("tags") or []) if _clean_text(item, 60)]
        if not title and not body:
            continue
        fingerprint = re.sub(r"\W+", "", f"{title}{body}").lower()[:500]
        if not fingerprint or fingerprint in seen:
            continue
        seen.add(fingerprint)
        published.append({
            "platform": str(run.get("platform") or payload.get("platform") or ""),
            "title": title,
            "content": body,
            "tags": tags[:10],
            "media_type": "video" if run.get("task_type") == "publish_video" else "graphic",
            "published_at": str(run.get("finished_at") or run.get("created_at") or ""),
        })
        if len(published) >= max(1, min(max_records, 300)):
            break
    return published


def _extract_json(raw: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    candidates = [text]
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except Exception:
            continue
    return None


async def _model_json(
    system: str,
    payload: dict[str, Any],
    max_output_tokens: int = 6000,
    timeout_seconds: int | None = None,
) -> dict[str, Any] | None:
    from szyg.integrations.volcengine_client import VolcEngineClient

    model = str(_config().get("analysis_model") or "doubao-seed-2-0-lite-260428")
    client = VolcEngineClient(timeout=120)
    try:
        result = await asyncio.wait_for(
            client.responses_text(
                [{
                    "role": "user",
                    "content": [{
                        "type": "input_text",
                        "text": f"{system}\n\n输入数据：\n{json.dumps(payload, ensure_ascii=False)}",
                    }],
                }],
                model=model,
                max_output_tokens=max_output_tokens,
                reasoning_effort="minimal",
            ),
            timeout=max(10, int(timeout_seconds or _config().get("model_timeout_seconds") or 45)),
        )
        return _extract_json(str((result.get("message") or {}).get("content") or ""))
    except Exception as exc:
        logger.warning("Intelligence model call failed for %s: %s", model, exc)
        return None


def _fallback_plan(query: str, profile: dict[str, Any]) -> dict[str, Any]:
    product = str(profile.get("product_name") or profile.get("industry") or "").strip()
    seed_keywords = [str(item).strip() for item in profile.get("seed_keywords") or [] if str(item).strip()]
    domain_phrases = re.findall(r"(?:AI\s*)?[\u4e00-\u9fff]{2,8}(?:陪练|学习|启蒙|产品|课程|工具)", query, flags=re.IGNORECASE)
    keywords = domain_phrases[:2] + seed_keywords[:2]
    if product:
        keywords.insert(0, product)
    keywords = list(dict.fromkeys(item for item in keywords if len(item) >= 3))
    if not keywords:
        keywords = [query.strip()[:30]]
    explicit_excludes: list[str] = []
    exclude_match = re.search(r"排除(.+?)(?:[。！？]|$)", query)
    if exclude_match:
        explicit_excludes.extend(
            item.strip()
            for item in re.split(r"[、,，和及与]", exclude_match.group(1))
            if len(item.strip()) >= 2
        )
    business_text = f"{product} {query}".lower()
    if "英语" in business_text and any(term in business_text for term in ("ai", "学习", "陪练", "启蒙")):
        explicit_excludes.extend(["教师婚恋", "英语老师结婚", "教师招聘", "教师资格考试", "高考英语"])
    return {
        "intent": "market_research",
        "focus": query.strip(),
        "search_keywords": list(dict.fromkeys(item for item in keywords if item))[:5],
        "exclude_topics": list(dict.fromkeys(explicit_excludes))[:12],
        "platforms": profile.get("platforms") or _enabled_platforms(),
        "time_range": "近30天",
    }


async def plan_intelligence_query(query: str, profile: dict[str, Any], knowledge_context: list[dict[str, Any]]) -> dict[str, Any]:
    system = """你是企业营销情报研究员。请把用户诉求转成精确的公开信息检索计划。
只输出JSON，不要解释。字段：intent、focus、search_keywords、exclude_topics、platforms、time_range。
search_keywords给出3-5个适合社交平台和资讯检索的短语，不要直接复制冗长问题。
exclude_topics必须列出容易因词面重合产生的无关主题。例如产品是AI英语学习时，应排除教师婚恋、教师招聘、教师资格考试等。
platforms只能从douyin、xhs、kuaishou、bilibili、weibo中选择。"""
    data = await _model_json(system, {
        "query": query,
        "business": {
            "product_name": profile.get("product_name"),
            "industry": profile.get("industry"),
            "audience": profile.get("audience"),
            "selling_points": profile.get("selling_points") or [],
            "seed_keywords": profile.get("seed_keywords") or [],
        },
        "knowledge": [item.get("content") for item in knowledge_context[:5]],
    }, max_output_tokens=1800, timeout_seconds=20)
    fallback = _fallback_plan(query, profile)
    if not data:
        return fallback
    keywords = [_clean_text(item, 60) for item in data.get("search_keywords", []) if _clean_text(item, 60)]
    requested_platforms = [item for item in data.get("platforms", []) if item in {"douyin", "xhs", "kuaishou", "bilibili", "weibo"}]
    platforms = _enabled_platforms() if _config().get("query_all_enabled_platforms", True) else requested_platforms
    return {
        "intent": str(data.get("intent") or fallback["intent"]),
        "focus": _clean_text(data.get("focus") or query, 200),
        "search_keywords": keywords[:5] or fallback["search_keywords"],
        "exclude_topics": [_clean_text(item, 50) for item in data.get("exclude_topics", []) if _clean_text(item, 50)][:12],
        "platforms": platforms or requested_platforms or fallback["platforms"],
        "time_range": _clean_text(data.get("time_range") or "近30天", 30),
    }


def _sample_payload(content_items: list[dict[str, Any]], market_news: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in content_items:
        rows.append({
            "id": str(item.get("id") or ""),
            "kind": "platform_content",
            "title": _clean_text(item.get("title"), 240),
            "text": _clean_text(item.get("description"), 500),
            "platform": item.get("platform_label") or item.get("platform"),
            "keyword": item.get("keyword"),
            "plays": int(item.get("plays") or 0),
            "likes": int(item.get("likes") or 0),
            "comments": int(item.get("comments_count") or 0),
            "favorites": int(item.get("favorites") or 0),
            "comment_signals": (item.get("comment_insights") or {}).get("summary") or "",
            "source_url": item.get("source_url") or "",
            "published_at": item.get("published_at") or "",
        })
    for item in market_news:
        rows.append({
            "id": str(item.get("id") or ""),
            "kind": "market_news",
            "title": _clean_text(item.get("title"), 240),
            "text": _clean_text(item.get("summary"), 500),
            "platform": item.get("source_name") or "公开资讯",
            "keyword": " / ".join(item.get("matched_keywords") or []),
            "plays": 0,
            "likes": 0,
            "comments": 0,
            "favorites": 0,
            "comment_signals": "",
            "source_url": item.get("source_url") or "",
            "published_at": item.get("published_at") or item.get("collected_at") or "",
        })
    rows.sort(key=lambda item: (item["likes"] + item["comments"] * 3 + item["favorites"] * 2, bool(item["source_url"])), reverse=True)
    return rows[: max(10, min(limit, 120))]


async def _collect_platform_content(profile: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    from szyg.competitor_intelligence import _video_to_item
    from szyg.intelligence_collectors import get_intelligence_collector_registry

    config = _config()
    timeout = max(5, int(config.get("platform_search_timeout_seconds") or 18))
    keyword_limit = max(1, min(int(config.get("max_query_keywords") or 2), 3))
    keywords = [str(item).strip() for item in plan.get("search_keywords") or [] if str(item).strip()][:keyword_limit]
    platforms = [str(item) for item in plan.get("platforms") or [] if str(item) in {"douyin", "xhs", "kuaishou", "bilibili", "weibo"}]
    registry = get_intelligence_collector_registry()
    batches = await registry.collect_many(
        platforms,
        keywords,
        limit=4,
        timeout_seconds=timeout,
    )
    content_items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    source_health: list[dict[str, Any]] = []
    seen: set[str] = set()
    for batch in batches:
        errors.extend(batch.errors)
        source_health.append(asdict(batch.health))
        for record in batch.records:
            item = _video_to_item(record["video"], record["keyword"])
            key = str(item.get("source_url") or item.get("id") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            content_items.append(item)
    content_items.sort(
        key=lambda item: (
            int(item.get("quality_score") or 0),
            int(item.get("likes") or 0) + int(item.get("comments_count") or 0) * 3,
        ),
        reverse=True,
    )
    return {"content_items": content_items[:80], "errors": errors, "source_health": source_health}


async def _collect_market_context(profile: dict[str, Any]) -> dict[str, Any]:
    from szyg.competitor_intelligence import collect_market_news, list_market_news

    active_auto_sources = {
        f"auto_{str(keyword).strip()}"
        for keyword in profile.get("seed_keywords") or []
        if str(keyword).strip()
    }

    def _belongs_to_current_research(item: dict[str, Any]) -> bool:
        source_id = str(item.get("source_id") or "")
        return not source_id.startswith("auto_") or source_id in active_auto_sources

    try:
        result = await asyncio.wait_for(
            collect_market_news(
                str(profile.get("id") or "default"),
                include_auto_search=True,
                profile_override=profile,
            ),
            timeout=max(15, int(_config().get("collection_timeout_seconds") or 65)),
        )
        fresh = result.get("items") or []
        cached = [
            item for item in list_market_news(limit=80)
            if _belongs_to_current_research(item)
        ]
        combined: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in fresh + cached:
            key = str(item.get("source_url") or item.get("id") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            combined.append(item)
        source_results = result.get("sources") if isinstance(result.get("sources"), list) else []
        failed_sources = [item for item in source_results if item.get("status") == "failed"]
        fresh_count = len(fresh)
        if fresh_count and failed_sources:
            status = "partial"
            message = f"已读取 {fresh_count} 条公开资讯，部分来源暂不可用"
        elif fresh_count:
            status = "success"
            message = f"已读取 {fresh_count} 条公开资讯"
        elif failed_sources and combined:
            status = "partial"
            message = "本轮部分来源不可用，已使用近期公开资讯"
        elif failed_sources:
            status = "failed"
            message = "公开资讯来源暂不可用"
        elif combined:
            status = "partial"
            message = f"本轮未发现新的公开资讯，已使用 {len(combined)} 条关注来源近期资讯"
        else:
            status = "no_data"
            message = "本轮未发现匹配的公开资讯"
        return {
            **result,
            "items": combined[:80],
            "total": len(combined),
            "source_health": {
                "source": "public_web",
                "label": "公开资讯",
                "source_type": "public_web",
                "method": "public_feed",
                "status": status,
                "item_count": fresh_count,
                "cached_item_count": max(0, len(combined) - fresh_count),
                "attempted_queries": len(source_results),
                "successful_queries": len(source_results) - len(failed_sources),
                "duration_ms": 0,
                "error_code": "source_unavailable" if status == "failed" else "",
                "message": message,
            },
        }
    except Exception as exc:
        cached = [
            item for item in list_market_news(limit=80)
            if _belongs_to_current_research(item)
        ]
        return {
            "items": cached,
            "total": len(cached),
            "sources": [],
            "source_health": {
                "source": "public_web",
                "label": "公开资讯",
                "source_type": "public_web",
                "method": "public_feed",
                "status": "partial" if cached else "failed",
                "item_count": 0,
                "attempted_queries": 0,
                "successful_queries": 0,
                "duration_ms": 0,
                "error_code": "source_unavailable",
                "message": "本轮读取失败，已使用近期公开资讯" if cached else "公开资讯来源暂不可用",
                "detail": str(exc)[:200],
            },
        }


def _fallback_semantic(query: str, plan: dict[str, Any], samples: list[dict[str, Any]]) -> dict[str, Any]:
    semantic_text = f"{query} {' '.join(plan.get('search_keywords') or [])}".lower()
    known_terms = [
        "ai口语陪练", "ai英语陪练", "英语口语陪练", "口语陪练", "英语陪练",
        "ai英语学习", "英语学习工具", "英语启蒙", "ai英语老师",
    ]
    query_terms = [term for term in known_terms if term in semantic_text]
    query_terms.extend(
        str(term).lower()
        for term in plan.get("search_keywords", [])
        if 3 <= len(str(term).strip()) <= 12
    )
    query_terms = list(dict.fromkeys(query_terms))
    excluded = [term.lower() for term in plan.get("exclude_topics", []) if len(term) >= 2]
    relevant: list[dict[str, Any]] = []
    for item in samples:
        text = f"{item.get('title', '')} {item.get('text', '')}".lower()
        if any(term in text for term in excluded):
            continue
        hits = [term for term in query_terms if term in text]
        if hits:
            relevant.append({
                "id": item["id"],
                "relevant": True,
                "relation_type": "market_signal" if item["kind"] == "market_news" else "content_opportunity",
                "marketing_value": min(90, 45 + len(hits) * 15),
                "topic": hits[0] if hits else query[:20],
                "reason": "内容与本次情报诉求存在直接关键词和业务语境关联",
                "customer_need": "",
                "sentiment": "neutral",
            })
    return {"items": relevant}


async def semantic_filter(query: str, plan: dict[str, Any], samples: list[dict[str, Any]], profile: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    system = """你是企业营销情报的语义筛选器。你的首要任务是排除词面相似但业务无关的内容。
例如研究AI英语学习产品时，“和英语老师结婚”“教师招聘”“教师资格考试”均不相关。
判断标准：是否服务相同用户、解决相同问题、属于可替代产品、反映真实客户需求、体现同行策略或会影响营销决策。
只输出JSON：{"items":[{"id":"原ID","relevant":true,"relation_type":"customer_need|content_opportunity|competitor_move|market_change","marketing_value":0-100,"topic":"简短主题","reason":"为何与业务有关","customer_need":"可为空","sentiment":"positive|negative|question|neutral"}]}。
不相关项也要返回，relevant=false。不得创建输入中不存在的ID。"""
    valid_ids = {item["id"] for item in samples}
    business = {
        "product_name": profile.get("product_name"),
        "industry": profile.get("industry"),
        "audience": profile.get("audience"),
        "selling_points": profile.get("selling_points") or [],
    }
    batches = [samples[index:index + 8] for index in range(0, len(samples), 8)]
    results = await asyncio.gather(*(
        _model_json(system, {
            "query": query,
            "focus": plan.get("focus"),
            "exclude_topics": plan.get("exclude_topics") or [],
            "business": business,
            "samples": batch,
        }, max_output_tokens=1800, timeout_seconds=35)
        for batch in batches
    )) if batches else []
    model_items = [
        item
        for data in results
        if data and isinstance(data.get("items"), list)
        for item in data["items"]
    ]
    if not model_items:
        return _fallback_semantic(query, plan, samples), False
    valid_items = []
    for item in model_items:
        if not isinstance(item, dict) or str(item.get("id") or "") not in valid_ids:
            continue
        valid_items.append({
            "id": str(item.get("id")),
            "relevant": bool(item.get("relevant")),
            "relation_type": str(item.get("relation_type") or "market_signal"),
            "marketing_value": max(0, min(100, int(item.get("marketing_value") or 0))),
            "topic": _clean_text(item.get("topic"), 40),
            "reason": _clean_text(item.get("reason"), 240),
            "customer_need": _clean_text(item.get("customer_need"), 240),
            "sentiment": str(item.get("sentiment") or "neutral"),
        })
    returned_ids = {item["id"] for item in valid_items}
    missing_samples = [item for item in samples if item["id"] not in returned_ids]
    if missing_samples:
        valid_items.extend(_fallback_semantic(query, plan, missing_samples).get("items") or [])
    return {"items": valid_items}, True


def _engagement(item: dict[str, Any]) -> int:
    return int(item.get("likes") or 0) + int(item.get("comments") or 0) * 3 + int(item.get("favorites") or 0) * 2


def _normalize_topic(value: Any) -> str:
    topic = _clean_text(value, 80)
    topic_rules = [
        (("伪ai", "避坑", "质疑", "踩坑"), "选购避坑"),
        (("测评", "实测", "推荐", "神器", "安利", "app排行"), "真实测评"),
        (("少儿", "儿童", "宝妈", "启蒙", "低龄"), "少儿英语启蒙"),
        (("学习机", "硬件", "词典笔", "听力机"), "AI英语学习机"),
        (("游戏化", "趣味性", "趣味学习"), "游戏化学习"),
        (("高互动", "工具推荐", "资源推荐"), "学习工具推荐"),
        (("ai教育", "ai英文教育", "教育类学习产品", "教育模型"), "AI教育内容"),
        (("专属外教", "ai外教", "口语陪练", "ai陪练"), "AI口语陪练"),
        (("哑巴英语", "不敢开口", "开口难", "开口练习"), "开口练习"),
        (("发音", "纠音", "口音"), "智能纠音"),
        (("个性化", "自适应", "因材施教"), "个性化学习"),
        (("ai老师", "学习工具"), "AI英语学习"),
        (("学习效果", "有效", "提分", "进步"), "学习效果"),
        (("价格", "成本", "收费", "付费"), "学习成本"),
        (("真人外教",), "真人外教"),
        (("家长", "管控", "监督"), "家长管控"),
        (("竞品", "推出", "上线", "发布"), "竞品动态"),
    ]
    lowered = topic.lower()
    for keywords, label in topic_rules:
        if any(keyword in lowered for keyword in keywords):
            return label
    if "ai" in lowered and "英语" in lowered:
        return "AI英语学习"
    compact = re.sub(r"[，。！？、,:：;；\s]+", "", topic)
    return compact[:10] or "其他"


def _aggregate_topics(samples: list[dict[str, Any]], decisions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in samples:
        decision = decisions.get(item["id"])
        if not decision or not decision.get("relevant"):
            continue
        topic = _normalize_topic(decision.get("topic") or item.get("keyword") or "其他")
        row = grouped.setdefault(topic, {"topic": topic, "count": 0, "engagement": 0, "value_total": 0})
        row["count"] += 1
        row["engagement"] += _engagement(item)
        row["value_total"] += int(decision.get("marketing_value") or 0)
    result = []
    for row in grouped.values():
        count = max(1, row["count"])
        result.append({
            "topic": row["topic"],
            "count": row["count"],
            "engagement": row["engagement"],
            "score": round(row["value_total"] / count),
        })
    result.sort(key=lambda row: (row["score"], row["engagement"], row["count"]), reverse=True)
    return result[:10]


def _platform_distribution(samples: list[dict[str, Any]], decisions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for item in samples:
        decision = decisions.get(item["id"])
        if decision and decision.get("relevant"):
            counts[str(item.get("platform") or "其他来源")] += 1
    return [{"name": name, "value": value} for name, value in counts.most_common(8)]


def _word_cloud(topics: list[dict[str, Any]], decisions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    weights: Counter[str] = Counter()
    for topic in topics:
        weights[topic["topic"]] += max(1, int(topic.get("score") or 0)) + int(topic.get("count") or 0) * 8
    need_terms = [
        "开口练习", "学习效果", "智能纠音", "个性化", "场景练习", "学习反馈",
        "学习成本", "课程价格", "适龄性", "坚持学习", "零基础", "真人外教", "自主学习",
    ]
    for item in decisions.values():
        need = str(item.get("customer_need") or "")
        for term in need_terms:
            if term in need:
                weights[term] += 18
    if not weights:
        return []
    maximum = max(weights.values())
    return [
        {"text": text, "weight": max(1, round(value / maximum * 100))}
        for text, value in weights.most_common(24)
    ]


def _enterprise_coverage(topic: str, published: list[dict[str, Any]]) -> int:
    if not published:
        return 0
    terms = re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{2,}", topic.lower())
    hits = 0
    for row in published:
        text = f"{row.get('title', '')} {row.get('content', '')} {' '.join(row.get('tags') or [])}".lower()
        if any(term in text for term in terms):
            hits += 1
    return min(100, round(hits / max(1, min(len(published), 10)) * 100))


async def _narrative_report(
    query: str,
    plan: dict[str, Any],
    topics: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    published: list[dict[str, Any]],
    sample_count: int,
) -> tuple[dict[str, Any], bool]:
    system = """你是中小企业的营销情报分析师。依据已经完成语义过滤的真实统计，提炼最重要的判断和行动。
只输出JSON，字段：executive_summary（2-3条，每条含title、finding、why_it_matters、confidence）、actions（2-3条，含title、description、priority）、topic_recommendations（对象，key为输入主题，value为一句建议）。
不得编造输入中没有的样本量、增长率、平台数据、品牌动作或用户原话。证据不足时明确写“样本不足”。"""
    compact_decisions = [
        {
            "relation_type": item.get("relation_type"),
            "marketing_value": item.get("marketing_value"),
            "topic": _normalize_topic(item.get("topic") or ""),
            "reason": _clean_text(item.get("reason"), 140),
            "customer_need": _clean_text(item.get("customer_need"), 140),
            "sentiment": item.get("sentiment"),
        }
        for item in decisions[:20]
    ]
    compact_published = [
        {
            "platform": item.get("platform"),
            "title": _clean_text(item.get("title"), 100),
            "content": _clean_text(item.get("content"), 260),
        }
        for item in published[:10]
    ]
    data = await _model_json(system, {
        "query": query,
        "plan": plan,
        "sample_count": sample_count,
        "topics": topics,
        "semantic_findings": compact_decisions,
        "enterprise_content": compact_published,
    }, max_output_tokens=1200, timeout_seconds=max(45, int(_config().get("model_timeout_seconds") or 45)))
    top = topics[0] if topics else None
    summary = []
    if top:
        summary.append({
            "title": f"优先关注“{top['topic']}”",
            "finding": f"该主题在当前有效样本中出现 {top['count']} 次，营销价值评分 {top['score']}。",
            "why_it_matters": "可作为下一轮内容和用户需求验证方向。",
            "confidence": "medium" if sample_count >= 10 else "low",
        })
    else:
        summary.append({
            "title": "当前证据不足",
            "finding": "本轮没有获得足够的业务相关样本。",
            "why_it_matters": "建议补充产品、目标客户或更明确的情报诉求后再次分析。",
            "confidence": "low",
        })
    need_counter: Counter[str] = Counter()
    need_sentiments: dict[str, str] = {}
    for item in decisions:
        need = _clean_text(item.get("customer_need"), 120)
        if not need:
            continue
        need_counter[need] += 1
        need_sentiments[need] = str(item.get("sentiment") or "neutral")
    customer_voice = [
        {
            "theme": _normalize_topic(need),
            "type": need_sentiments.get(need, "neutral"),
            "summary": need,
            "count": count,
        }
        for need, count in need_counter.most_common(6)
    ]
    content_patterns = [
        {
            "pattern": f"围绕“{topic['topic']}”解释真实使用场景",
            "finding": f"该主题在 {topic['count']} 条有效信号中出现，营销价值评分 {topic['score']}。",
            "recommendation": "先用一条图文或短视频验证点击、停留和咨询反馈，再决定是否扩大投入。",
        }
        for topic in topics[:4]
    ]
    industry_moves = [
        {
            "title": _normalize_topic(item.get("topic") or "同行动态"),
            "summary": _clean_text(item.get("reason"), 180),
            "impact": "建议关注其产品表达和用户反馈，不直接照搬内容。",
        }
        for item in decisions
        if item.get("relation_type") in {"competitor_move", "market_change"}
    ][:4]
    actions = [
        {
            "title": f"验证“{topic['topic']}”内容方向",
            "description": "结合企业现有卖点制作一个小样本内容，发布后观察互动和咨询信号。",
            "priority": index + 1,
        }
        for index, topic in enumerate(topics[:3])
    ]
    report = {
        "executive_summary": summary,
        "customer_voice": customer_voice,
        "content_patterns": content_patterns,
        "industry_moves": industry_moves,
        "actions": actions,
        "topic_recommendations": {},
    }
    if data:
        for key in ("executive_summary", "actions"):
            if isinstance(data.get(key), list) and data[key]:
                report[key] = data[key]
        if isinstance(data.get("topic_recommendations"), dict):
            report["topic_recommendations"] = data["topic_recommendations"]
        return report, True
    return report, False


def _sanitize_list(value: Any, limit: int) -> list[dict[str, Any]]:
    return [item for item in (value if isinstance(value, list) else []) if isinstance(item, dict)][:limit]


def _sanitize_summary(value: Any, confidence: str) -> list[dict[str, Any]]:
    rows = _sanitize_list(value, 5)
    for row in rows:
        level = str(row.get("confidence") or "").lower()
        row["confidence"] = level if level in {"high", "medium", "low"} else confidence
    return rows


async def run_intelligence_query(
    query: str,
    use_enterprise_context: bool = True,
    include_publish_records: bool = True,
) -> dict[str, Any]:
    from szyg.competitor_intelligence import (
        _load_knowledge_context,
        list_business_profiles,
    )

    question = _clean_text(query, 500)
    if len(question) < 4:
        raise ValueError("请更具体地描述你想了解的市场问题")

    profiles = list_business_profiles()
    existing = dict(profiles[0]) if profiles else {"id": "default"}
    knowledge_context = _load_knowledge_context(existing, limit=8) if use_enterprise_context else []
    published = load_published_context() if use_enterprise_context and include_publish_records else []
    plan = await plan_intelligence_query(question, existing, knowledge_context)

    merged_seeds = list(dict.fromkeys((plan.get("search_keywords") or []) + list(existing.get("seed_keywords") or [])))
    profile_payload = {
        **existing,
        "id": existing.get("id") or "default",
        "product_name": existing.get("product_name") or question[:40],
        "seed_keywords": merged_seeds[:8],
        "platforms": plan.get("platforms") or existing.get("platforms"),
        "use_knowledge_base": bool(use_enterprise_context),
        "max_keywords": min(5, len(plan.get("search_keywords") or []) or 4),
        "per_keyword_limit": 6,
    }
    discovery, market_result = await asyncio.gather(
        _collect_platform_content(profile_payload, plan),
        _collect_market_context(profile_payload),
    )

    max_samples = int(_config().get("max_external_samples") or 60)
    samples = _sample_payload(discovery.get("content_items") or [], market_result.get("items") or [], max_samples)
    semantic, semantic_model_used = await semantic_filter(question, plan, samples, profile_payload)
    decisions = {str(item.get("id") or ""): item for item in semantic.get("items", []) if isinstance(item, dict)}
    relevant_samples = [item for item in samples if decisions.get(item["id"], {}).get("relevant")]
    relevant_samples.sort(key=lambda item: (int(decisions[item["id"]].get("marketing_value") or 0), _engagement(item)), reverse=True)

    topics = _aggregate_topics(relevant_samples, decisions)
    narrative, narrative_model_used = await _narrative_report(
        question,
        plan,
        topics,
        [decisions[item["id"]] for item in relevant_samples],
        published,
        len(relevant_samples),
    )
    recommendations = narrative.get("topic_recommendations") if isinstance(narrative.get("topic_recommendations"), dict) else {}
    market_gap = []
    for topic in topics[:8]:
        coverage = _enterprise_coverage(topic["topic"], published)
        market_gap.append({
            "topic": topic["topic"],
            "market_score": topic["score"],
            "enterprise_coverage": coverage,
            "gap": max(0, int(topic["score"]) - coverage),
            "recommendation": _clean_text(recommendations.get(topic["topic"]) or ("建议优先验证" if coverage < topic["score"] else "继续保持并优化"), 160),
        })
    market_gap.sort(key=lambda item: item["gap"], reverse=True)

    evidence_limit = int(_config().get("evidence_limit") or 5)
    evidence = []
    for item in relevant_samples[: max(1, min(evidence_limit, 8))]:
        decision = decisions[item["id"]]
        evidence.append({
            "id": item["id"],
            "title": item.get("title") or "公开内容样本",
            "summary": item.get("text") or "",
            "source": item.get("platform") or "公开来源",
            "source_url": item.get("source_url") or "",
            "relation_type": decision.get("relation_type"),
            "marketing_value": decision.get("marketing_value"),
            "reason": decision.get("reason"),
            "metrics": {
                "plays": item.get("plays") or 0,
                "likes": item.get("likes") or 0,
                "comments": item.get("comments") or 0,
                "favorites": item.get("favorites") or 0,
            },
        })

    confidence = "high" if len(relevant_samples) >= 30 else "medium" if len(relevant_samples) >= 10 else "low"
    source_health = [
        *[item for item in discovery.get("source_health") or [] if isinstance(item, dict)],
        *([market_result["source_health"]] if isinstance(market_result.get("source_health"), dict) else []),
    ]
    report = {
        "id": f"report_{uuid.uuid4().hex[:10]}",
        "query": question,
        "title": question[:60],
        "status": "success",
        "plan": plan,
        "executive_summary": _sanitize_summary(narrative.get("executive_summary"), confidence),
        "word_cloud": _word_cloud(topics, decisions),
        "topic_trends": topics,
        "platform_distribution": _platform_distribution(relevant_samples, decisions),
        "customer_voice": _sanitize_list(narrative.get("customer_voice"), 6),
        "content_patterns": _sanitize_list(narrative.get("content_patterns"), 6),
        "industry_moves": _sanitize_list(narrative.get("industry_moves"), 5),
        "market_gap": market_gap,
        "actions": _sanitize_list(narrative.get("actions"), 5),
        "evidence": evidence,
        "data_scope": {
            "raw_samples": len(samples),
            "relevant_samples": len(relevant_samples),
            "filtered_samples": max(0, len(samples) - len(relevant_samples)),
            "platforms": [item["name"] for item in _platform_distribution(relevant_samples, decisions)],
            "knowledge_sources": sorted({str(item.get("source") or "知识库") for item in knowledge_context}),
            "published_records": len(published),
            "use_enterprise_context": bool(use_enterprise_context),
            "confidence": confidence,
            "semantic_model_used": semantic_model_used,
            "narrative_model_used": narrative_model_used,
            "source_health": source_health,
        },
        "created_at": _now(),
        "updated_at": _now(),
    }
    with _REPORT_LOCK:
        rows = _read_rows(REPORT_FILE)
        rows.insert(0, report)
        atomic_write(REPORT_FILE, rows[:100])
    return report


def list_intelligence_reports(limit: int = 20) -> list[dict[str, Any]]:
    return _read_rows(REPORT_FILE)[: max(1, min(limit, 100))]


def get_intelligence_report(report_id: str) -> dict[str, Any]:
    for report in _read_rows(REPORT_FILE):
        if report.get("id") == report_id:
            return report
    raise KeyError(report_id)
