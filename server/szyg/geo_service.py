"""GEO brand growth service backed by the visible desktop browser and SQLite evidence."""

from __future__ import annotations

import asyncio
import json
import logging
import ipaddress
import socket
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

from szyg.competitor_intelligence import latest_report, list_business_profiles, upsert_business_profile
from szyg.data_path import DATA_DIR
from szyg.geo_analysis import analyze_answer, build_recommendations, normalize_citations
from szyg.geo_repository import GeoRepository
from szyg.tenant import get_tenant_data_file

logger = logging.getLogger(__name__)

AUDITS_FILE = DATA_DIR / "geo_audits.json"
OBSERVATIONS_FILE = DATA_DIR / "geo_observations.json"
RECOMMENDATIONS_FILE = DATA_DIR / "geo_recommendations.json"
GEO_DB_FILE: Path | None = None

KNOWN_PROVIDERS = {
    "deepseek": {"label": "DeepSeek", "mode": "consumer_surface"},
    "doubao": {"label": "豆包", "mode": "consumer_surface"},
    "openai": {"label": "ChatGPT", "mode": "consumer_surface"},
    "perplexity": {"label": "Perplexity", "mode": "consumer_surface"},
    "gemini": {"label": "Google Gemini", "mode": "consumer_surface"},
}
PROVIDER_ALIASES = {"chatgpt": "openai", "google_ai": "gemini"}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _safe_error(exc: Exception) -> str:
    message = str(exc).lower()
    if "停止本次浏览器检测" in str(exc) or "user_cancelled" in message:
        return "你已停止本次浏览器检测"
    if "登录" in str(exc) or "401" in message:
        return "登录状态已失效，请重新登录"
    if "额度" in str(exc) or "credit" in message or "429" in message:
        return "本次检测额度不足或请求较多，请稍后重试"
    if "未配置" in str(exc) or "not configured" in message or "403" in message:
        return "该AI平台尚未接入可用的联网检测服务"
    if "timeout" in message or "超时" in str(exc):
        return "该AI平台本次响应超时"
    if "桌面版" in str(exc):
        return "请使用领鹿开发桌面版进行实际界面检测"
    if "检测现场" in str(exc):
        return str(exc)
    if "提问框" in str(exc) or "登录" in str(exc) or "验证码" in str(exc):
        return str(exc)
    return "该AI平台本次没有返回可用结果"


class GeoService:
    def __init__(self, repository: GeoRepository | None = None) -> None:
        path = GEO_DB_FILE or get_tenant_data_file("geo.db")
        self.repository = repository or GeoRepository(path)
        self._running: set[str] = set()
        self._running_lock = asyncio.Lock()
        self.repository.migrate_legacy(
            audits_path=AUDITS_FILE,
            observations_path=OBSERVATIONS_FILE,
            recommendations_path=RECOMMENDATIONS_FILE,
            questions=list(self._profile_raw().get("target_questions") or []),
        )

    @staticmethod
    def _profile_raw() -> dict[str, Any]:
        profiles = list_business_profiles()
        return dict(profiles[0]) if profiles else {"id": "default"}

    def get_profile(self) -> dict[str, Any]:
        profile = self._profile_raw()
        details = self.repository.list_questions()
        return {
            **profile,
            "id": profile.get("id") or "default",
            "product_name": str(profile.get("product_name") or ""),
            "website": str(profile.get("website") or ""),
            "brand_aliases": list(profile.get("brand_aliases") or []),
            "products": list(profile.get("products") or []),
            "competitors": list(profile.get("competitors") or []),
            "languages": list(profile.get("languages") or ["zh-CN"]),
            "target_questions": [item["text"] for item in details],
            "geo_providers": [PROVIDER_ALIASES.get(str(item), str(item)) for item in profile.get("geo_providers") or []],
        }

    def update_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.get_profile()
        merged = {**current, **payload, "id": current.get("id") or "default"}
        if not str(merged.get("product_name") or "").strip():
            raise ValueError("请填写企业或品牌名称")
        merged["geo_providers"] = list(dict.fromkeys(PROVIDER_ALIASES.get(str(item), str(item)) for item in merged.get("geo_providers") or []))
        upsert_business_profile(merged)
        profile_fact_ids = {"profile_brand", "profile_website", "profile_products", "profile_region"}
        facts = [item for item in self.repository.list_facts() if item.get("id") not in profile_fact_ids]
        source_url = str(merged.get("website") or "")
        generated = [
            {"id": "profile_brand", "subject": str(merged["product_name"]), "predicate": "品牌名称", "value": str(merged["product_name"]), "source_url": source_url},
        ]
        if source_url:
            generated.append({"id": "profile_website", "subject": str(merged["product_name"]), "predicate": "官方网站", "value": source_url, "source_url": source_url})
        if merged.get("products"):
            generated.append({"id": "profile_products", "subject": str(merged["product_name"]), "predicate": "主要产品", "value": "、".join(map(str, merged["products"])), "source_url": source_url})
        if str(merged.get("region") or "").strip():
            generated.append({"id": "profile_region", "subject": str(merged["product_name"]), "predicate": "服务地区", "value": str(merged["region"]), "source_url": source_url})
        self.repository.replace_facts(facts + generated)
        return self.get_profile()

    def get_questions(self) -> list[str]:
        return [item["text"] for item in self.repository.list_questions()]

    def list_question_details(self) -> list[dict[str, Any]]:
        return self.repository.list_questions()

    def update_questions(self, questions: list[Any]) -> list[str]:
        items = [dict(raw) if isinstance(raw, dict) else {"text": str(raw), "source": "manual"} for raw in questions]
        saved = self.repository.replace_questions(items)
        upsert_business_profile({**self.get_profile(), "target_questions": [item["text"] for item in saved]})
        return [item["text"] for item in saved]

    async def suggest_questions(self, limit: int = 12) -> list[dict[str, Any]]:
        profile = self.get_profile()
        product = profile.get("product_name") or "本企业"
        product_label = (profile.get("products") or [product])[0]
        audience = profile.get("audience") or "目标客户"
        competitor = (profile.get("competitors") or ["同类产品"])[0]
        report = latest_report()
        analysis = report.get("analysis") or {}
        signals = list(analysis.get("demand_signals") or [])
        voices = list(analysis.get("customer_voice") or [])
        templates: list[tuple[str, str, str, int, str]] = [
            (f"适合{audience}的{product_label}有哪些？", "寻找解决方案", "discovery", 3, "ai_suggestion"),
            (f"{audience}如何选择{product_label}？", "寻找解决方案", "discovery", 3, "ai_suggestion"),
            (f"{product_label}能解决哪些实际经营问题？", "寻找解决方案", "problem_solution", 2, "ai_suggestion"),
            (f"{product}和{competitor}有什么区别？", "比较和选型", "comparison", 3, "ai_suggestion"),
            (f"选择{product_label}时最应该比较哪些能力？", "比较和选型", "comparison", 2, "ai_suggestion"),
            (f"{product}适合什么规模的企业？", "比较和选型", "comparison", 2, "ai_suggestion"),
            (f"{product_label}一般如何收费？", "价格与服务", "price_service", 3, "ai_suggestion"),
            (f"使用{product}需要准备哪些资料和账号？", "价格与服务", "price_service", 2, "ai_suggestion"),
            (f"{product}是否提供实施和售后服务？", "价格与服务", "price_service", 2, "ai_suggestion"),
            (f"{product}是否安全可靠？", "信任与风险", "trust_risk", 3, "ai_suggestion"),
            (f"{product}有哪些真实客户案例？", "信任与风险", "trust_risk", 3, "ai_suggestion"),
            (f"{product}是什么，主要提供什么服务？", "品牌直接查询", "brand_direct", 2, "ai_suggestion"),
        ]
        for item in signals[:4]:
            text = str(item.get("text") or "").strip()
            if text:
                templates.append((f"{text.rstrip('？?')}应该如何解决？", "寻找解决方案", "problem_solution", 2, "marketing_intelligence"))
        for item in voices[:3]:
            text = str(item.get("summary") or item.get("theme") or "").strip()
            if text:
                templates.append((f"针对{text}，有哪些可靠方案？", "寻找解决方案", "problem_solution", 2, "marketing_intelligence"))

        existing, result, seen = set(self.get_questions()), [], set()
        for text, topic, intent, importance, source in templates:
            clean = text[:300]
            if clean in seen:
                continue
            seen.add(clean)
            result.append({
                "id": f"suggested_{uuid.uuid4().hex[:10]}", "text": clean, "topic": topic, "intent": intent,
                "importance": importance, "source": "existing" if clean in existing else source,
                "selected": len(result) < min(12, limit),
            })
            if len(result) >= max(1, min(limit, 30)):
                break
        return result

    def get_facts(self) -> list[dict[str, Any]]:
        return self.repository.list_facts()

    def update_facts(self, facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self.repository.replace_facts(facts)

    def _cached_provider_status(self) -> dict[str, dict[str, Any]]:
        try:
            rows = json.loads(self.repository.get_meta("provider_status") or "[]")
        except json.JSONDecodeError:
            rows = []
        return {str(item.get("id") or ""): dict(item) for item in rows if isinstance(item, dict)}

    async def refresh_provider_status(self) -> list[dict[str, Any]]:
        try:
            from szyg.geo_browser import get_geo_sidebar_browser

            rows = await get_geo_sidebar_browser().provider_status()
        except Exception as exc:
            logger.info("GEO sidebar browser status unavailable: %s", exc)
            rows = list(self._cached_provider_status().values())
        status = {str(item.get("id")): dict(item) for item in rows}
        normalized = []
        for provider_id, defaults in KNOWN_PROVIDERS.items():
            item = {"id": provider_id, **defaults, **status.get(provider_id, {})}
            item["availability"] = item.get("availability") or ("available" if item.get("configured") else "not_configured")
            normalized.append(item)
        self.repository.set_meta("provider_status", json.dumps(normalized, ensure_ascii=False))
        return normalized

    def describe_providers(self) -> list[dict[str, Any]]:
        cache = self._cached_provider_status()
        result = []
        for provider_id, defaults in KNOWN_PROVIDERS.items():
            item = {"id": provider_id, **defaults, **cache.get(provider_id, {})}
            item.setdefault("configured", False)
            item.setdefault("availability", "available" if item["configured"] else "desktop_required")
            result.append(item)
        return result

    def create_audit(self, provider_ids: list[str] | None = None, questions: list[str] | None = None, *, question_ids: list[str] | None = None, sample_count: int | None = None, mode: str = "diagnostic") -> dict[str, Any]:
        profile = self.get_profile()
        if not str(profile.get("product_name") or "").strip():
            raise ValueError("请先完成企业资料")
        if questions:
            selected_questions = [self.repository.ensure_question(text, source="manual") for text in questions[:30] if str(text).strip()]
        elif question_ids:
            selected_questions = [item for item in (self.repository.get_question(qid) for qid in question_ids[:30]) if item and item.get("active")]
        else:
            selected_questions = self.repository.list_questions()[:30]
        if not selected_questions:
            raise ValueError("请先确认客户会向AI提出的问题")
        requested = [PROVIDER_ALIASES.get(str(pid), str(pid)) for pid in (provider_ids or profile.get("geo_providers") or [])]
        if not requested:
            available = [item["id"] for item in self.describe_providers() if item.get("configured") and item.get("mode") == "consumer_surface"]
            requested = (["deepseek"] if "deepseek" in available else available[:1])
        requested = list(dict.fromkeys(pid for pid in requested if pid in KNOWN_PROVIDERS))
        if not requested:
            raise ValueError("请使用领鹿开发桌面版进行实际界面检测")
        default_samples = 3 if mode == "verification" else 1
        samples = max(1, min(int(sample_count or default_samples), 5))
        audit = {
            "id": f"geo_{uuid.uuid4().hex[:12]}", "status": "queued", "mode": mode,
            "provider_ids": requested, "question_ids": [item["id"] for item in selected_questions], "sample_count": samples,
            "total": len(requested) * len(selected_questions) * samples, "completed": 0, "failed": 0,
            "created_at": _now(), "started_at": "", "finished_at": "", "error": "",
        }
        return self._enrich_audit(self.repository.insert_audit(audit))

    def _enrich_audit(self, audit: dict[str, Any]) -> dict[str, Any]:
        return {**audit, "questions": [item["text"] for item in (self.repository.get_question(qid) for qid in audit.get("question_ids") or []) if item]}

    async def _query_provider(self, provider_id: str, question: str, audit_id: str, question_id: str, sample_index: int) -> dict[str, Any]:
        # GEO intentionally reuses the visible browser owned by SuperAgent.  This
        # preserves the user's consumer-product login session and keeps both the
        # question and answer on the desktop instead of routing them via Dolphin.
        from szyg.geo_browser import get_geo_sidebar_browser

        return await get_geo_sidebar_browser().query(provider_id, question)

    async def run_audit(self, audit_id: str) -> dict[str, Any]:
        async with self._running_lock:
            if audit_id in self._running:
                return self._enrich_audit(self.repository.get_audit(audit_id) or {})
            self._running.add(audit_id)
        try:
            audit = self.repository.get_audit(audit_id)
            if not audit:
                raise KeyError(audit_id)
            if audit["status"] not in {"queued", "running"}:
                return self._enrich_audit(audit)
            statuses = {item["id"]: item for item in await self.refresh_provider_status()}
            available = [
                pid for pid in audit["provider_ids"]
                if statuses.get(pid, {}).get("configured")
                and statuses.get(pid, {}).get("mode") == "consumer_surface"
            ]
            if not available:
                return self._enrich_audit(self.repository.update_audit(
                    audit_id,
                    status="failed",
                    finished_at=_now(),
                    error="侧边栏浏览器当前不可用，请使用领鹿开发桌面版启动检测",
                ))
            if audit.get("mode") == "scheduled":
                from szyg.geo_browser import get_geo_sidebar_browser

                if not await get_geo_sidebar_browser().visible():
                    return self._enrich_audit(self.repository.update_audit(
                        audit_id,
                        status="queued",
                        error="本周检测已准备好，打开GEO品牌体检后会在右侧实际AI界面中执行",
                    ))
            self.repository.update_audit(audit_id, status="running", started_at=audit.get("started_at") or _now(), error="")
            # There is one visible browser surface and one shared login session.
            # Serial execution also makes each question and result understandable
            # to the user while the side panel is open.
            global_semaphore = asyncio.Semaphore(1)
            provider_semaphores = {pid: asyncio.Semaphore(1) for pid in available}
            facts, profile = self.get_facts(), self.get_profile()
            cancelled = False
            abort_error = ""

            async def execute(provider_id: str, question: dict[str, Any], sample_index: int) -> None:
                nonlocal cancelled, abort_error
                if self.repository.observation_exists(audit_id, provider_id, question["id"], sample_index):
                    return
                started = time.perf_counter()
                item: dict[str, Any] = {
                    "id": f"obs_{uuid.uuid4().hex[:12]}", "audit_id": audit_id, "question_id": question["id"],
                    "provider_id": provider_id, "provider_label": KNOWN_PROVIDERS[provider_id]["label"], "provider_model": "",
                    "fidelity": "consumer_surface", "capture_method": "sidebar_browser", "sample_index": sample_index,
                    "answer": "", "citations": [], "search_queries": [], "status": "failed", "analysis_status": "pending",
                    "mentioned": False, "recommended": False, "competitor_mentions": [], "factual_issues": [], "error": "", "observed_at": _now(), "request_id": "",
                }
                try:
                    async with global_semaphore, provider_semaphores[provider_id]:
                        result = await self._query_provider(provider_id, question["text"], audit_id, question["id"], sample_index)
                    citations = normalize_citations(result.get("citations") or [], profile.get("website") or "")
                    # The deterministic pass deliberately avoids the remote LLM
                    # analyzer; GEO browser checks must not consume Dolphin tokens.
                    analysis = await analyze_answer(
                        profile,
                        str(result.get("answer") or ""),
                        citations,
                        facts,
                        allow_remote=False,
                    )
                    item.update({
                        "answer": result.get("answer") or "",
                        "citations": citations,
                        "search_queries": result.get("search_queries") or [],
                        "provider_model": result.get("provider_model") or "消费端实际界面",
                        "fidelity": result.get("fidelity") or "consumer_surface",
                        "capture_method": result.get("capture_method") or "sidebar_browser",
                        "request_id": result.get("request_id") or "",
                        "status": "completed",
                        **analysis,
                    })
                except Exception as exc:
                    item["error"] = _safe_error(exc)
                    if item["error"] == "你已停止本次浏览器检测" or "检测现场" in item["error"]:
                        cancelled = True
                        abort_error = item["error"]
                    logger.warning("GEO provider failed audit=%s provider=%s question=%s: %s", audit_id, provider_id, question["id"], exc)
                item["latency_ms"] = int((time.perf_counter() - started) * 1000)
                self.repository.insert_observation(item)
                rows = self.repository.list_observations(audit_id=audit_id, limit=5000)
                self.repository.update_audit(audit_id, completed=sum(row["status"] == "completed" for row in rows), failed=sum(row["status"] == "failed" for row in rows))

            for provider_id in audit["provider_ids"]:
                if cancelled or (self.repository.get_audit(audit_id) or {}).get("status") != "running":
                    cancelled = True
                    break
                if provider_id not in available:
                    for qid in audit["question_ids"]:
                        for sample_index in range(1, int(audit["sample_count"]) + 1):
                            if not self.repository.observation_exists(audit_id, provider_id, qid, sample_index):
                                self.repository.insert_observation({"id": f"obs_{uuid.uuid4().hex[:12]}", "audit_id": audit_id, "question_id": qid, "provider_id": provider_id, "provider_label": KNOWN_PROVIDERS.get(provider_id, {}).get("label", provider_id), "fidelity": "consumer_surface", "capture_method": "sidebar_browser", "sample_index": sample_index, "status": "failed", "analysis_status": "not_run", "error": "该AI平台暂时无法通过侧边栏浏览器检测"})
                    continue
                for qid in audit["question_ids"]:
                    if cancelled:
                        break
                    question = self.repository.get_question(qid)
                    if question:
                        for sample_index in range(1, int(audit["sample_count"]) + 1):
                            if cancelled or (self.repository.get_audit(audit_id) or {}).get("status") != "running":
                                cancelled = True
                                break
                            await execute(provider_id, question, sample_index)
            rows = self.repository.list_observations(audit_id=audit_id, limit=5000)
            completed = sum(row["status"] == "completed" for row in rows)
            failed_count = sum(row["status"] == "failed" for row in rows)
            if cancelled:
                latest_error = str((self.repository.get_audit(audit_id) or {}).get("error") or "")
                final = self.repository.update_audit(
                    audit_id,
                    status="failed",
                    completed=completed,
                    failed=failed_count,
                    finished_at=_now(),
                    error=abort_error or latest_error or "你已停止本次浏览器检测",
                )
                return self._enrich_audit(final)
            status = "partial" if completed and failed_count else ("completed" if completed else "failed")
            final = self.repository.update_audit(audit_id, status=status, completed=completed, failed=failed_count, finished_at=_now(), error="" if completed else "本次检测没有获得可用结果")
            self.repository.replace_recommendations(audit_id, build_recommendations(rows))
            for recommendation in self.repository.list_recommendations(limit=1000):
                if recommendation.get("verification_audit_id") == audit_id:
                    before = (recommendation.get("verification_result") or {}).get("before") or {}
                    after = self._verification_metrics(rows)
                    self.repository.update_recommendation(recommendation["id"], status="verified", verification_result={
                        "status": status, "completed": completed, "failed": failed_count,
                        "finished_at": final.get("finished_at"), "before": before, "after": after,
                        "changes": {
                            key: round(float(after.get(key) or 0) - float(before.get(key) or 0), 1)
                            for key in ("mention_rate", "recommendation_rate", "owned_citation_rate", "accuracy_rate")
                        },
                    })
            return self._enrich_audit(final)
        finally:
            async with self._running_lock:
                self._running.discard(audit_id)

    def get_audit(self, audit_id: str) -> dict[str, Any]:
        item = self.repository.get_audit(audit_id)
        if not item:
            raise KeyError(audit_id)
        return self._enrich_audit(item)

    def cancel_audit(self, audit_id: str) -> dict[str, Any]:
        audit = self.repository.get_audit(audit_id)
        if not audit:
            raise KeyError(audit_id)
        if audit.get("status") in {"completed", "partial", "failed"}:
            return self._enrich_audit(audit)
        return self._enrich_audit(self.repository.update_audit(
            audit_id,
            status="failed",
            finished_at=_now(),
            error="你已停止本次浏览器检测",
        ))

    def list_observations(self, *, audit_id: str = "", provider_id: str = "", question_id: str = "", limit: int = 200) -> list[dict[str, Any]]:
        return self.repository.list_observations(audit_id=audit_id, provider_id=PROVIDER_ALIASES.get(provider_id, provider_id), question_id=question_id, limit=limit)

    def list_recommendations(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.repository.list_recommendations(limit=limit)

    def get_recommendation(self, recommendation_id: str) -> dict[str, Any]:
        item = self.repository.get_recommendation(recommendation_id)
        if not item:
            raise KeyError(recommendation_id)
        item["evidence"] = [entry for entry in (self.repository.get_observation(obs_id) for obs_id in item.get("evidence_ids") or []) if entry]
        return item

    def update_recommendation(self, recommendation_id: str, status: str) -> dict[str, Any]:
        if status not in {"open", "in_progress", "done", "dismissed"}:
            raise ValueError("不支持的建议状态")
        return self.repository.update_recommendation(recommendation_id, status=status)

    @staticmethod
    def _verification_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
        valid = [
            row for row in rows
            if row.get("status") == "completed"
            and row.get("fidelity") == "consumer_surface"
            and row.get("capture_method") == "sidebar_browser"
        ]
        total = len(valid)
        related = [row for row in valid if row.get("mentioned")]
        fact_checked = [row for row in related if row.get("analysis_status") == "completed"]

        def rate(count: int, denominator: int = total) -> float:
            return round(count * 100 / denominator, 1) if denominator else 0.0

        return {
            "valid_samples": total,
            "mention_rate": rate(sum(bool(row.get("mentioned")) for row in valid)),
            "recommendation_rate": rate(sum(bool(row.get("recommended")) for row in valid)),
            "owned_citation_rate": rate(sum(any(citation.get("is_owned_domain") for citation in row.get("citations") or []) for row in valid)),
            "accuracy_rate": rate(sum(not row.get("factual_issues") for row in fact_checked), len(fact_checked)) if fact_checked else 0.0,
        }

    def verify_recommendation(self, recommendation_id: str) -> dict[str, Any]:
        item = self.get_recommendation(recommendation_id)
        audit = self.create_audit(provider_ids=item.get("provider_ids") or None, question_ids=item.get("question_ids") or None, sample_count=3, mode="verification")
        question_ids, provider_ids = set(item.get("question_ids") or []), set(item.get("provider_ids") or [])
        baseline_rows = [
            row for row in self.repository.list_observations(audit_id=str(item.get("audit_id") or ""), limit=5000)
            if row.get("question_id") in question_ids and row.get("provider_id") in provider_ids
        ]
        self.repository.update_recommendation(
            recommendation_id, status="verifying", verification_audit_id=audit["id"],
            verification_result={"status": "queued", "before": self._verification_metrics(baseline_rows)},
        )
        return audit

    def create_spot_check(self, question_ids: list[str] | None = None) -> dict[str, Any]:
        questions = question_ids or [item["id"] for item in self.repository.list_questions()[:5]]
        audit = self.create_audit(provider_ids=["deepseek"], question_ids=questions[:5], sample_count=1, mode="spot_check")
        return {
            "audit": audit,
            "questions": [
                {"id": qid, "text": (self.repository.get_question(qid) or {}).get("text", "")}
                for qid in audit["question_ids"]
            ],
            "launch": {
                "ok": True,
                "message": "将由超级员工侧边栏浏览器自动询问并采集回答",
            },
        }

    async def capture_spot_check(self, audit_id: str, question_id: str, answer: str, citations: list[Any]) -> dict[str, Any]:
        audit = self.get_audit(audit_id)
        if audit.get("mode") != "spot_check" or question_id not in audit.get("question_ids", []):
            raise ValueError("抽检任务与客户问题不匹配")
        if not answer.strip():
            raise ValueError("请粘贴DeepSeek实际回答")
        existing = next((
            row for row in self.repository.list_observations(audit_id=audit_id, provider_id="deepseek", question_id=question_id, limit=5)
            if int(row.get("sample_index") or 1) == 1
        ), None)
        if existing:
            return existing
        profile = self.get_profile()
        normalized = normalize_citations(citations, profile.get("website") or "")
        analysis = await analyze_answer(profile, answer, normalized, self.get_facts(), allow_remote=False)
        observation = self.repository.insert_observation({"id": f"obs_{uuid.uuid4().hex[:12]}", "audit_id": audit_id, "question_id": question_id, "provider_id": "deepseek", "provider_label": "DeepSeek", "provider_model": "消费端搜索", "fidelity": "consumer_surface", "capture_method": "legacy_manual", "sample_index": 1, "answer": answer, "citations": normalized, "status": "completed", "observed_at": _now(), **analysis})
        rows = self.repository.list_observations(audit_id=audit_id, limit=10)
        completed = len([row for row in rows if row["status"] == "completed"])
        status = "completed" if completed >= audit["total"] else "needs_human"
        self.repository.update_audit(audit_id, status=status, completed=completed, finished_at=_now() if status == "completed" else "")
        if status == "completed":
            self.repository.replace_recommendations(audit_id, build_recommendations(rows))
        return observation

    def list_sources(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.repository.source_summary(limit)

    async def review_site(self) -> dict[str, Any]:
        website = str(self.get_profile().get("website") or "").strip()
        parsed = urlsplit(website)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("请先填写有效的企业官网")
        try:
            addresses = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, 443 if parsed.scheme == "https" else 80)
            if any(ipaddress.ip_address(item[4][0]).is_private or ipaddress.ip_address(item[4][0]).is_loopback or ipaddress.ip_address(item[4][0]).is_reserved for item in addresses):
                raise ValueError("企业官网必须是可公开访问的地址")
        except socket.gaierror as exc:
            raise ValueError("企业官网域名暂时无法访问") from exc
        import httpx
        checks: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=True, max_redirects=3, headers={"User-Agent": "SZYG-GEO-SiteReview/1.0"}) as client:
            try:
                home = await client.get(website)
                home.raise_for_status()
                html = home.text[:2_000_000]
                checks.extend([
                    {"id": "reachable", "label": "官网可以公开访问", "passed": True, "detail": f"HTTP {home.status_code}"},
                    {"id": "title", "label": "页面有清晰标题", "passed": "<title" in html.lower(), "detail": "建议标题中明确品牌和主营业务"},
                    {"id": "structured_data", "label": "页面包含结构化数据", "passed": "application/ld+json" in html.lower(), "detail": "可补充Organization、Product或FAQ结构化数据"},
                ])
            except Exception:
                return {"website": website, "status": "failed", "checks": [{"id": "reachable", "label": "官网可以公开访问", "passed": False, "detail": "当前无法从公开网络访问官网"}], "reviewed_at": _now()}
            for key, path, label in (("robots", "/robots.txt", "提供robots.txt"), ("sitemap", "/sitemap.xml", "提供网站地图")):
                try:
                    response = await client.get(urljoin(website, path))
                    passed = response.status_code == 200 and bool(response.text.strip())
                except Exception:
                    passed = False
                checks.append({"id": key, "label": label, "passed": passed, "detail": "让搜索与AI抓取系统更容易发现公开页面"})
        return {"website": website, "status": "completed", "checks": checks, "passed": sum(bool(item["passed"]) for item in checks), "total": len(checks), "reviewed_at": _now()}

    def overview(self, days: int = 30) -> dict[str, Any]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 365)))
        rows, all_recent = [], []
        for item in self.repository.list_observations(limit=5000):
            try:
                when = datetime.fromisoformat(str(item.get("observed_at") or "").replace("Z", "+00:00")).astimezone(timezone.utc)
            except ValueError:
                continue
            if when >= cutoff:
                all_recent.append(item)
                if (
                    item.get("status") == "completed"
                    and item.get("fidelity") == "consumer_surface"
                    and item.get("capture_method") == "sidebar_browser"
                ):
                    rows.append(item)
        total = len(rows)
        mentioned = sum(bool(row.get("mentioned")) for row in rows)
        recommended = sum(bool(row.get("recommended")) for row in rows)
        owned_cited = sum(any(c.get("is_owned_domain") for c in row.get("citations") or []) for row in rows)
        first_choice = sum(bool(row.get("recommended")) and int(row.get("position") or 0) == 1 for row in rows)
        brand_related = [row for row in rows if row.get("mentioned")]
        fact_checked = [row for row in brand_related if row.get("analysis_status") == "completed"]
        accurate = sum(not row.get("factual_issues") for row in fact_checked)
        competitor_mentions = sum(len(row.get("competitor_mentions") or []) for row in rows)
        denominator = mentioned + competitor_mentions
        providers = sorted({row["provider_id"] for row in rows})
        failed = [
            row for row in all_recent
            if row.get("status") == "failed"
            and row.get("fidelity") == "consumer_surface"
            and row.get("capture_method") == "sidebar_browser"
        ]
        failed_providers = sorted({str(row.get("provider_id") or "") for row in failed if row.get("provider_id")})
        official_sample_count = sum(
            row.get("status") == "completed" and row.get("fidelity") == "official_search_api"
            for row in all_recent
        )
        consumer_sample_count = len(rows)
        confidence, confidence_label = (("stable", "较稳定") if total >= 20 and len(providers) >= 2 else (("reference", "可参考") if total >= 8 else ("insufficient", "样本不足")))
        audits = self.repository.list_audits(limit=1)
        return {
            "period_days": days, "total_observations": len(all_recent), "valid_sample_count": total,
            "mention_rate": round(mentioned / total * 100, 1) if total else 0,
            "recommendation_rate": round(recommended / total * 100, 1) if total else 0,
            "owned_citation_rate": round(owned_cited / total * 100, 1) if total else 0,
            "first_choice_rate": round(first_choice / total * 100, 1) if total else 0,
            "brand_share_of_voice": round(mentioned / denominator * 100, 1) if denominator else 0,
            "accuracy_rate": round(accurate / len(fact_checked) * 100, 1) if fact_checked else 0,
            "fact_checked_sample_count": len(fact_checked),
            "citation_count": sum(len(row.get("citations") or []) for row in rows),
            "factual_issue_count": sum(len(row.get("factual_issues") or []) for row in rows),
            "competitor_gap_count": sum(bool(row.get("competitor_mentions")) and not bool(row.get("recommended")) for row in rows),
            "provider_coverage": len(providers), "successful_provider_count": len(providers),
            "failed_provider_count": len(failed_providers), "failed_sample_count": len(failed),
            "official_sample_count": official_sample_count, "consumer_sample_count": consumer_sample_count,
            "confidence": confidence, "confidence_label": confidence_label,
            "providers": self.describe_providers(), "latest_audit": self._enrich_audit(audits[0]) if audits else None, "recommendations": self.list_recommendations(10),
        }


_SERVICE: GeoService | None = None

def get_geo_service() -> GeoService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = GeoService()
    return _SERVICE

def get_profile() -> dict[str, Any]: return get_geo_service().get_profile()
def update_profile(payload: dict[str, Any]) -> dict[str, Any]: return get_geo_service().update_profile(payload)
def get_questions() -> list[str]: return get_geo_service().get_questions()
def update_questions(questions: list[Any]) -> list[str]: return get_geo_service().update_questions(questions)
def create_audit(provider_ids: list[str] | None = None, questions: list[str] | None = None, **kwargs: Any) -> dict[str, Any]: return get_geo_service().create_audit(provider_ids, questions, **kwargs)
async def run_audit(audit_id: str) -> dict[str, Any]: return await get_geo_service().run_audit(audit_id)
def get_audit(audit_id: str) -> dict[str, Any]: return get_geo_service().get_audit(audit_id)
def list_observations(**kwargs: Any) -> list[dict[str, Any]]: return get_geo_service().list_observations(**kwargs)
def list_recommendations(limit: int = 100) -> list[dict[str, Any]]: return get_geo_service().list_recommendations(limit)
def overview(days: int = 30) -> dict[str, Any]: return get_geo_service().overview(days)
def describe_providers() -> list[dict[str, Any]]: return get_geo_service().describe_providers()

async def geo_audit_worker_loop() -> None:
    service = get_geo_service()
    service.repository.recover_audits()
    await service.refresh_provider_status()
    while True:
        try:
            queued = service.repository.list_queued_audits(limit=2)
            if not queued:
                await asyncio.sleep(2)
                continue
            for audit in queued:
                await service.run_audit(audit["id"])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("GEO audit worker iteration failed: %s", exc)
            await asyncio.sleep(3)
