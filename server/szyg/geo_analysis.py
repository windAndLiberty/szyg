"""Evidence-first analysis helpers for GEO observations."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


RECOMMENDATION_WORDS = ("推荐", "建议选择", "值得考虑", "优先考虑", "首选", "recommend", "best choice", "consider")


def normalize_url(url: str) -> tuple[str, str]:
    raw = str(url or "").strip().rstrip(".,;，。；")
    if not raw:
        return "", ""
    try:
        parts = urlsplit(raw)
        domain = parts.netloc.lower().removeprefix("www.")
        query = urlencode([(key, value) for key, value in parse_qsl(parts.query) if not key.lower().startswith(("utm_", "spm", "source"))])
        normalized = urlunsplit((parts.scheme.lower() or "https", parts.netloc.lower(), parts.path.rstrip("/") or "/", query, ""))
        return normalized, domain
    except ValueError:
        return raw, ""


def normalize_citations(items: list[Any], website: str = "") -> list[dict[str, Any]]:
    _, owned_domain = normalize_url(website)
    result, seen = [], set()
    for raw in items:
        item = raw if isinstance(raw, dict) else {"url": raw}
        normalized, domain = normalize_url(str(item.get("url") or ""))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append({
            "url": str(item.get("url") or normalized),
            "normalized_url": normalized,
            "domain": domain,
            "title": str(item.get("title") or ""),
            "snippet": str(item.get("snippet") or ""),
            "cited_text": str(item.get("cited_text") or ""),
            "is_owned_domain": bool(owned_domain and (domain == owned_domain or domain.endswith(f".{owned_domain}"))),
        })
    return result


def _evidence_window(answer: str, needle: str, radius: int = 90) -> str:
    index = answer.lower().find(needle.lower())
    if index < 0:
        return ""
    start, end = max(0, index - radius), min(len(answer), index + len(needle) + radius)
    return answer[start:end].strip()


def deterministic_analysis(profile: dict[str, Any], answer: str, citations: list[dict[str, Any]]) -> dict[str, Any]:
    brand = str(profile.get("product_name") or "").strip()
    aliases = [value for value in [brand, *list(profile.get("brand_aliases") or [])] if str(value).strip()]
    lowered = answer.lower()
    mentioned_alias = next((str(alias) for alias in aliases if str(alias).lower() in lowered), "")
    evidence = _evidence_window(answer, mentioned_alias) if mentioned_alias else ""
    evidence_lower = evidence.lower()
    recommended = bool(mentioned_alias and any(word in evidence_lower for word in RECOMMENDATION_WORDS))
    position = 0
    if mentioned_alias:
        prefix = answer[: lowered.find(mentioned_alias.lower())]
        numbered = re.findall(r"(?:^|\n)\s*(\d+)[\.、)]", prefix)
        position = int(numbered[-1]) if numbered else 0
    competitors = []
    for raw_name in profile.get("competitors") or []:
        name = str(raw_name).strip()
        if not name or name.lower() not in lowered:
            continue
        comp_evidence = _evidence_window(answer, name)
        competitors.append({
            "name": name,
            "position": 0,
            "recommended": any(word in comp_evidence.lower() for word in RECOMMENDATION_WORDS),
            "evidence": comp_evidence,
        })
    return {
        "mentioned": bool(mentioned_alias),
        "recommended": recommended,
        "recommendation_strength": "explicit" if recommended else ("mentioned" if mentioned_alias else "none"),
        "recommendation_evidence": evidence if recommended else "",
        "position": position,
        "sentiment": "positive" if recommended else ("neutral" if mentioned_alias else "not_mentioned"),
        "competitor_mentions": competitors,
        "factual_issues": [],
        "citations": citations,
        "analysis_status": "deterministic",
    }


def _parse_json_object(value: str) -> dict[str, Any]:
    clean = str(value or "").strip()
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", clean, flags=re.I | re.S)
    start, end = clean.find("{"), clean.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        parsed = json.loads(clean[start:end + 1])
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


async def analyze_answer(
    profile: dict[str, Any],
    answer: str,
    citations: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    *,
    allow_remote: bool = True,
) -> dict[str, Any]:
    base = deterministic_analysis(profile, answer, citations)
    if not answer.strip() or not allow_remote:
        return base
    fact_lines = [f"- {item.get('subject')} / {item.get('predicate')}: {item.get('value')}" for item in facts[:80]]
    prompt = f"""你是品牌可见度证据分析器。只分析给出的回答，禁止补充外部信息。
品牌：{profile.get('product_name') or ''}
品牌别名：{json.dumps(profile.get('brand_aliases') or [], ensure_ascii=False)}
竞品：{json.dumps(profile.get('competitors') or [], ensure_ascii=False)}
企业已确认事实：
{chr(10).join(fact_lines) if fact_lines else '暂无已确认事实，因此 factual_issues 必须为空'}

AI回答：
{answer[:12000]}

只返回JSON对象：
{{"mentioned":true,"recommended":false,"recommendation_strength":"none|mentioned|implicit|explicit|first_choice","recommendation_evidence":"回答中的原文片段","position":0,"sentiment":"positive|neutral|negative|mixed|not_mentioned","competitor_mentions":[{{"name":"","position":0,"recommended":false,"evidence":"原文片段"}}],"factual_issues":[{{"claim":"回答中的说法","canonical_fact":"已确认事实","issue_type":"conflict|outdated|unsupported","severity":"low|medium|high","evidence":"原文片段"}}]}}
所有evidence必须逐字存在于AI回答中；没有证据时不得判断推荐或事实错误。"""
    try:
        from szyg.integrations.volcengine_client import VolcEngineClient

        client = VolcEngineClient(timeout=90)
        try:
            result = await client.chat([{"role": "user", "content": prompt}], temperature=0, max_tokens=1600)
        finally:
            close = getattr(client, "close", None)
            if close:
                maybe_awaitable = close()
                if hasattr(maybe_awaitable, "__await__"):
                    await maybe_awaitable
        parsed = _parse_json_object(str((result.get("message") or {}).get("content") or ""))
    except Exception:
        return base
    if not parsed:
        return base

    rec_evidence = str(parsed.get("recommendation_evidence") or "").strip()
    recommended = bool(parsed.get("recommended") and rec_evidence and rec_evidence in answer)
    competitors = []
    allowed_competitors = {str(name).lower(): str(name) for name in profile.get("competitors") or []}
    for item in parsed.get("competitor_mentions") or []:
        if not isinstance(item, dict):
            continue
        key, evidence = str(item.get("name") or "").lower(), str(item.get("evidence") or "")
        if key in allowed_competitors and evidence and evidence in answer:
            competitors.append({
                "name": allowed_competitors[key], "position": max(0, int(item.get("position") or 0)),
                "recommended": bool(item.get("recommended")), "evidence": evidence,
            })
    issues = []
    known_facts = [f"{item.get('subject')} / {item.get('predicate')}: {item.get('value')}" for item in facts]
    for item in parsed.get("factual_issues") or []:
        if not isinstance(item, dict):
            continue
        evidence, canonical = str(item.get("evidence") or ""), str(item.get("canonical_fact") or "")
        if facts and evidence and evidence in answer and any(canonical in fact or fact in canonical for fact in known_facts):
            issues.append({
                "claim": str(item.get("claim") or evidence), "canonical_fact": canonical,
                "issue_type": str(item.get("issue_type") or "conflict"),
                "severity": str(item.get("severity") or "medium"), "evidence": evidence,
            })
    return {
        **base,
        "mentioned": bool(parsed.get("mentioned")) or base["mentioned"],
        "recommended": recommended,
        "recommendation_strength": str(parsed.get("recommendation_strength") or ("explicit" if recommended else "none")),
        "recommendation_evidence": rec_evidence if recommended else "",
        "position": max(0, int(parsed.get("position") or 0)),
        "sentiment": str(parsed.get("sentiment") or base["sentiment"]),
        "competitor_mentions": competitors or base["competitor_mentions"],
        "factual_issues": issues,
        "analysis_status": "completed",
    }


def build_recommendations(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid = [
        item for item in observations
        if item.get("status") == "completed"
        and item.get("fidelity") == "consumer_surface"
        and item.get("capture_method") == "sidebar_browser"
    ]
    groups: list[tuple[str, str, str, list[dict[str, Any]]]] = [
        ("not_understood", "补齐AI对企业的基础认知", "这些客户问题中AI没有识别到企业，优先统一官网定位、产品名称和品牌别名。", [item for item in valid if not item.get("mentioned")]),
        ("not_recommended", "说明为什么客户应该选择你", "AI已经知道企业，但没有把它作为选择建议，需要补充适用场景、差异和客户证据。", [item for item in valid if item.get("mentioned") and not item.get("recommended")]),
        ("competitor_ahead", "补充与竞品的客观选型依据", "回答推荐或提到了竞品，却没有推荐本品牌，需要补充可核验的对比与案例。", [item for item in valid if item.get("competitor_mentions") and not item.get("recommended")]),
        ("owned_site_gap", "让企业官网成为AI可引用的来源", "AI提到了企业但没有引用官网，需要为关键产品事实提供清晰、可访问的落地页面。", [item for item in valid if item.get("mentioned") and not any(c.get("is_owned_domain") for c in item.get("citations") or [])]),
        ("citation_gap", "补充带来源的权威内容", "这些回答没有给出可验证引用，需要增加数据出处、客户案例和明确的事实来源。", [item for item in valid if not item.get("citations")]),
        ("factual_error", "纠正AI对企业的错误信息", "AI回答与已确认企业事实不一致，应优先修正官网、知识库和可能的错误来源。", [item for item in valid if item.get("factual_issues")]),
    ]
    result = []
    for category, title, description, rows in groups:
        if not rows:
            continue
        evidence_ids = list(dict.fromkeys(str(row["id"]) for row in rows))
        question_ids = list(dict.fromkeys(str(row["question_id"]) for row in rows))
        providers = list(dict.fromkeys(str(row["provider_id"]) for row in rows))
        importance = max(int(row.get("importance") or 2) for row in rows)
        priority = "high" if category == "factual_error" or importance >= 3 or len(evidence_ids) >= 3 else "medium"
        result.append({
            "category": category, "title": title, "description": description, "priority": priority,
            "rationale": f"影响 {len(question_ids)} 个客户问题、{len(providers)} 个AI平台，共有 {len(evidence_ids)} 条回答证据。",
            "evidence_ids": evidence_ids, "question_ids": question_ids, "provider_ids": providers,
            "evidence_count": len(evidence_ids),
        })
    return result
