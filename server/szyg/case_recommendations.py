"""Knowledge-led ranking for the super employee's featured videos."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any


AI_NEWS_KEYWORD = "人工智能 最新资讯"

_GENERIC_TERMS = {
    "一个", "一种", "一些", "以及", "可以", "进行", "相关", "内容", "产品", "用户",
    "视频", "最新", "资讯", "介绍", "分享", "如何", "这个", "什么", "我们", "他们",
}


def knowledge_case_context(max_documents: int = 6, max_chars: int = 4800) -> tuple[str, str]:
    """Return a compact knowledge context and its basis.

    The knowledge service remains the source of truth. Missing or unreadable
    documents deliberately fall back to a general AI-news topic.
    """
    try:
        from szyg.knowledge_service import get_knowledge_service

        service = get_knowledge_service()
        documents = service.list_documents(status="ready")[:max_documents]
        parts: list[str] = []
        for row in documents:
            detail = service.get_document(str(row.get("id", "")), include_markdown=True) or row
            filename = str(detail.get("filename") or "企业资料")
            collection = str(detail.get("collection") or "企业资料")
            markdown = re.sub(r"\s+", " ", str(detail.get("markdown") or "")).strip()
            excerpt = markdown[:900]
            parts.append(f"[{collection}] {filename}\n{excerpt}" if excerpt else f"[{collection}] {filename}")
            if sum(len(part) for part in parts) >= max_chars:
                break
        context = "\n".join(parts)[:max_chars].strip()
        if context:
            return context, "knowledge"
    except Exception:
        pass
    return "人工智能、AI 产品、AI 行业动态、应用进展与商业趋势", "ai_news"


def knowledge_fallback_keyword(context: str) -> str:
    """Build a useful search phrase when remote keyword extraction is unavailable."""
    lines = [line.strip() for line in str(context or "").splitlines() if line.strip()]
    for line in lines:
        candidate = re.sub(r"^\[[^]]+\]\s*", "", line)
        candidate = re.sub(r"\.(pdf|docx?|xlsx?|pptx?|md|txt)$", "", candidate, flags=re.I)
        candidate = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff.+-]", "", candidate)
        if len(candidate) >= 4 and candidate not in {"企业资料", "知识库"}:
            return candidate[:16]
    return AI_NEWS_KEYWORD


def _number(value: Any) -> float:
    if isinstance(value, (int, float)):
        return max(float(value), 0.0)
    text = str(value or "").strip().lower().replace(",", "")
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return 0.0
    number = float(match.group())
    if "万" in text or text.endswith("w"):
        number *= 10_000
    elif "亿" in text:
        number *= 100_000_000
    return number


def normalized_count(value: Any) -> int:
    return int(_number(value))


def _terms(text: str) -> list[str]:
    normalized = re.sub(r"\s+", "", str(text or "").lower())
    terms = re.findall(r"[a-z][a-z0-9.+-]{1,}|[\u4e00-\u9fff]{2,}", normalized)
    expanded: list[str] = []
    for term in terms:
        if re.fullmatch(r"[\u4e00-\u9fff]+", term):
            for size in (2, 3, 4):
                expanded.extend(term[index:index + size] for index in range(max(len(term) - size + 1, 0)))
        else:
            expanded.append(term)
    return [term for term in expanded if term not in _GENERIC_TERMS]


def _query_weights(keyword: str, context: str) -> dict[str, float]:
    weights: Counter[str] = Counter()
    for term in _terms(context):
        weights[term] += 1.0
    for term in _terms(keyword):
        weights[term] += 5.0
    return dict(weights.most_common(80))


def relevance_score(item: dict[str, Any], keyword: str, context: str) -> float:
    """Score semantic surface relevance; popularity only breaks close ties."""
    weights = _query_weights(keyword, context)
    candidate_text = f"{item.get('title', '')} {item.get('description', '')}"
    candidate_terms = set(_terms(candidate_text))
    matched = sum(weight for term, weight in weights.items() if term in candidate_terms)
    denominator = sum(sorted(weights.values(), reverse=True)[:35]) or 1.0
    semantic = matched / denominator

    compact_keyword = re.sub(r"\s+", "", keyword.lower())
    compact_candidate = re.sub(r"\s+", "", candidate_text.lower())
    exact_bonus = 0.35 if compact_keyword and compact_keyword in compact_candidate else 0.0
    engagement = _number(item.get("likes")) + _number(item.get("plays")) * 0.08
    popularity_tiebreaker = min(math.log1p(engagement) / 120.0, 0.12)
    return semantic + exact_bonus + popularity_tiebreaker


def select_diverse_videos(
    videos: list[dict[str, Any]],
    keyword: str,
    context: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Choose relevant videos while gently preferring distinct sources/authors."""
    unique: dict[str, dict[str, Any]] = {}
    for item in videos:
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        if not url or not title:
            continue
        key = url.split("?")[0].rstrip("/")
        candidate = dict(item)
        candidate["_score"] = relevance_score(candidate, keyword, context)
        current = unique.get(key)
        if current is None or candidate["_score"] > current["_score"]:
            unique[key] = candidate

    remaining = sorted(unique.values(), key=lambda row: row["_score"], reverse=True)
    selected: list[dict[str, Any]] = []
    sources: set[str] = set()
    authors: set[str] = set()

    while remaining and len(selected) < max(1, min(limit, 3)):
        best_score = remaining[0]["_score"]
        relevance_floor = best_score * 0.72
        viable = [row for row in remaining if row["_score"] >= relevance_floor]

        def diversified_score(row: dict[str, Any]) -> float:
            source = str(row.get("platform") or "")
            author = str(row.get("author") or "").strip().lower()
            return (
                row["_score"]
                + (0.10 if source and source not in sources else 0.0)
                + (0.06 if author and author not in authors else 0.0)
            )

        chosen = max(viable, key=diversified_score)
        remaining.remove(chosen)
        sources.add(str(chosen.get("platform") or ""))
        author = str(chosen.get("author") or "").strip().lower()
        if author:
            authors.add(author)
        chosen.pop("_score", None)
        selected.append(chosen)

    return selected
