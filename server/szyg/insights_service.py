"""Global business insights assembled from real SZYG data sources.

The service keeps arithmetic deterministic. Knowledge retrieval and market
intelligence provide business context and evidence, while counts and rates are
computed from persisted business records.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from szyg.data_path import DATA_DIR


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> int:
    try:
        return max(0, int(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator * 100 / denominator, 1)


def _status(value: Any) -> str:
    return str(value or "").strip().lower()


def _title(row: dict[str, Any]) -> str:
    return str(row.get("title") or row.get("name") or row.get("filename") or "未命名内容").strip()


class InsightsService:
    def __init__(self, data_dir: Path | None = None, knowledge_service: Any | None = None):
        self.data_dir = Path(data_dir or DATA_DIR)
        self._knowledge_service = knowledge_service

    def _rows(self, filename: str) -> list[dict[str, Any]]:
        path = self.data_dir / filename
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        if isinstance(data, dict):
            items = data.get("items") or data.get("rows") or data.get("data")
            if isinstance(items, list):
                return [row for row in items if isinstance(row, dict)]
        return []

    def _updated_at(self, *filenames: str) -> str:
        values: list[datetime] = []
        for filename in filenames:
            path = self.data_dir / filename
            if path.exists():
                try:
                    values.append(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc))
                except OSError:
                    continue
        return _iso(max(values)) if values else ""

    def _knowledge(self) -> Any | None:
        if self._knowledge_service is not None:
            return self._knowledge_service
        try:
            from szyg.knowledge_service import get_knowledge_service

            self._knowledge_service = get_knowledge_service()
            return self._knowledge_service
        except Exception:
            return None

    def _knowledge_summary(self, query: str = "") -> tuple[dict[str, Any], list[dict[str, Any]]]:
        service = self._knowledge()
        if service is None:
            return {"total_docs": 0, "total_chunks": 0, "updated_at": ""}, []
        try:
            stats = dict(service.stats() or {})
        except Exception:
            stats = {"total_docs": 0, "total_chunks": 0, "updated_at": ""}
        if not stats.get("updated_at"):
            stats["updated_at"] = stats.get("last_update") or ""
        references: list[dict[str, Any]] = []
        if query.strip():
            try:
                results = service.search_sync(query, limit=4)
                references = [
                    {
                        "document_id": row.get("document_id") or "",
                        "source": row.get("filename") or row.get("source") or "企业资料",
                        "heading": row.get("heading") or "",
                        "locator": row.get("locator") or "",
                        "excerpt": str(row.get("content") or "")[:180],
                        "score": row.get("score"),
                    }
                    for row in results
                ]
            except Exception:
                references = []
        return stats, references

    def _latest_market_report(self) -> dict[str, Any] | None:
        reports = self._rows("intelligence_reports.json")
        reports.sort(
            key=lambda row: _parse_time(row.get("updated_at") or row.get("created_at"))
            or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return reports[0] if reports else None

    def _publish_rows(self) -> list[dict[str, Any]]:
        runs = [
            row
            for row in self._rows("execution_runs.json")
            if str(row.get("task_type") or "").startswith("publish_")
        ]
        if runs:
            return runs
        return self._rows("publish_log.json")

    def _internal_data(self, days: int) -> dict[str, Any]:
        days = max(1, min(days, 365))
        cutoff = _now() - timedelta(days=days)
        generations = self._rows("generation_history.json")
        materials = self._rows("materials.json")
        publish_rows = self._publish_rows()
        accounts = self._rows("channel_accounts.json")
        leads = self._rows("leads.json") or self._rows("lead_scores.json")
        conversions = self._rows("conversions.json")
        followups = self._rows("private_domain_followups.json")
        workflows = self._rows("workflow_instances.json")
        workflow_runs = [
            row for row in self._rows("execution_runs.json") if row.get("task_type") == "workflow"
        ]

        def recent(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            result = []
            for row in rows:
                timestamp = _parse_time(
                    row.get("updated_at")
                    or row.get("created_at")
                    or row.get("published_at")
                    or row.get("finished_at")
                )
                if timestamp and timestamp >= cutoff:
                    result.append(row)
            return result

        recent_generations = recent(generations)
        recent_publish = recent(publish_rows)
        recent_leads = recent(leads)
        recent_conversions = recent(conversions)
        recent_workflow_runs = recent(workflow_runs)

        publish_success_statuses = {"success", "published", "completed", "done"}
        publish_failed_statuses = {"failed", "error", "cancelled"}
        publish_success = sum(1 for row in recent_publish if _status(row.get("status")) in publish_success_statuses)
        publish_failed = sum(1 for row in recent_publish if _status(row.get("status")) in publish_failed_statuses)
        publish_finished = publish_success + publish_failed
        adopted = sum(1 for row in recent_generations if bool(row.get("adopted")))
        active_accounts = sum(
            1
            for row in accounts
            if row.get("enabled", True) and _status(row.get("status")) in {"online", "logged_in", "active", "ready"}
        )
        high_intent = sum(
            1
            for row in recent_leads
            if _status(row.get("grade") or row.get("level") or row.get("intent")) in {"s", "a", "high", "高", "高意向"}
        )
        workflow_success = sum(1 for row in recent_workflow_runs if _status(row.get("status")) == "success")
        workflow_finished = sum(
            1 for row in recent_workflow_runs if _status(row.get("status")) in {"success", "failed", "cancelled"}
        )
        needs_human = sum(
            1
            for row in self._rows("execution_runs.json")
            if _status(row.get("status")) in {"needs_human", "paused"}
        )

        return {
            "period_days": days,
            "generations": len(recent_generations),
            "adopted": adopted,
            "adoption_rate": _rate(adopted, len(recent_generations)),
            "materials": len(materials),
            "publish_total": len(recent_publish),
            "publish_success": publish_success,
            "publish_failed": publish_failed,
            "publish_success_rate": _rate(publish_success, publish_finished),
            "active_accounts": active_accounts,
            "leads": len(recent_leads),
            "high_intent_leads": high_intent,
            "conversions": len(recent_conversions),
            "lead_conversion_rate": _rate(len(recent_conversions), len(recent_leads)),
            "followups": len(recent(followups)),
            "active_workflows": sum(1 for row in workflows if _status(row.get("status")) == "active"),
            "workflow_runs": len(recent_workflow_runs),
            "workflow_success_rate": _rate(workflow_success, workflow_finished),
            "needs_human": needs_human,
            "recent_generations": recent_generations,
            "recent_publish": recent_publish,
            "recent_leads": recent_leads,
            "recent_conversions": recent_conversions,
        }

    def _trend(self, internal: dict[str, Any], days: int) -> list[dict[str, Any]]:
        span = 7 if days <= 7 else 14 if days <= 30 else 30
        now = _now()
        buckets: dict[str, dict[str, Any]] = {}
        for offset in range(span - 1, -1, -1):
            day = (now - timedelta(days=offset)).date()
            buckets[day.isoformat()] = {
                "date": day.strftime("%m-%d"),
                "generated": 0,
                "published": 0,
                "leads": 0,
                "conversions": 0,
            }

        def count(rows: list[dict[str, Any]], key: str) -> None:
            for row in rows:
                timestamp = _parse_time(
                    row.get("updated_at")
                    or row.get("created_at")
                    or row.get("published_at")
                    or row.get("finished_at")
                )
                if timestamp and timestamp.date().isoformat() in buckets:
                    buckets[timestamp.date().isoformat()][key] += 1

        count(internal["recent_generations"], "generated")
        count(internal["recent_publish"], "published")
        count(internal["recent_leads"], "leads")
        count(internal["recent_conversions"], "conversions")
        return list(buckets.values())

    def _data_health(
        self,
        internal: dict[str, Any],
        knowledge: dict[str, Any],
        market_report: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        market_scope = (market_report or {}).get("data_scope") or {}
        sources = market_scope.get("source_health") or []
        healthy_sources = sum(1 for row in sources if _status(row.get("status")) in {"success", "partial"})
        return [
            {
                "id": "knowledge",
                "label": "企业知识库",
                "status": "ready" if _number(knowledge.get("total_docs")) else "empty",
                "count": _number(knowledge.get("total_docs")),
                "detail": f"{_number(knowledge.get('total_chunks'))} 个知识片段",
                "updated_at": str(knowledge.get("updated_at") or ""),
            },
            {
                "id": "operations",
                "label": "内部经营数据",
                "status": "ready" if internal["generations"] or internal["publish_total"] or internal["leads"] else "empty",
                "count": internal["generations"] + internal["publish_total"] + internal["leads"],
                "detail": "内容、发布、线索与转化",
                "updated_at": self._updated_at(
                    "generation_history.json", "execution_runs.json", "leads.json", "conversions.json"
                ),
            },
            {
                "id": "market",
                "label": "市场情报",
                "status": "ready" if market_report else "empty",
                "count": _number(market_scope.get("relevant_samples")),
                "detail": f"{healthy_sources}/{len(sources)} 个外部来源可用" if sources else "暂无来源健康信息",
                "updated_at": str((market_report or {}).get("updated_at") or (market_report or {}).get("created_at") or ""),
            },
            {
                "id": "workflow",
                "label": "工作流执行",
                "status": "ready" if internal["workflow_runs"] else "empty",
                "count": internal["workflow_runs"],
                "detail": f"{internal['needs_human']} 项需要处理",
                "updated_at": self._updated_at("workflow_instances.json", "execution_runs.json"),
            },
        ]

    def _insights(self, internal: dict[str, Any], market_report: dict[str, Any] | None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for index, gap in enumerate(((market_report or {}).get("market_gap") or [])[:3]):
            if not isinstance(gap, dict):
                continue
            gap_value = _number(gap.get("gap"))
            if gap_value <= 0:
                continue
            topic = str(gap.get("topic") or "待验证主题")
            items.append({
                "id": f"market-gap-{index}",
                "type": "opportunity",
                "title": f"值得验证：{topic}",
                "finding": f"市场热度 {_number(gap.get('market_score'))}，企业内容覆盖 {_number(gap.get('enterprise_coverage'))}。",
                "why_it_matters": "外部需求强于当前内容覆盖，存在可验证的内容机会。",
                "action": str(gap.get("recommendation") or "围绕该主题设计一组小规模内容测试。"),
                "value_score": min(100, 55 + gap_value // 2),
                "confidence": str(((market_report or {}).get("data_scope") or {}).get("confidence") or "low"),
                "source_report_id": (market_report or {}).get("id") or "",
            })

        publish_rate = internal.get("publish_success_rate")
        if publish_rate is not None and internal["publish_total"]:
            healthy = publish_rate >= 90
            items.append({
                "id": "publish-health",
                "type": "strength" if healthy else "risk",
                "title": "多平台发布保持稳定" if healthy else "发布稳定性需要优先处理",
                "finding": f"最近 {internal['period_days']} 天完成 {internal['publish_total']} 次发布，成功率 {publish_rate}%。",
                "why_it_matters": "发布失败会直接中断内容到业务结果的数据链路。",
                "action": "继续观察失败分类。" if healthy else "先处理登录失效、页面变化和上传失败最多的平台。",
                "value_score": 70 if healthy else min(100, round(100 - publish_rate / 2)),
                "confidence": "high",
                "source_report_id": "",
            })

        conversion_rate = internal.get("lead_conversion_rate")
        if conversion_rate is not None and internal["leads"]:
            items.append({
                "id": "lead-conversion",
                "type": "opportunity" if conversion_rate < 20 else "strength",
                "title": "线索承接仍有提升空间" if conversion_rate < 20 else "线索转化表现积极",
                "finding": f"最近 {internal['period_days']} 天新增 {internal['leads']} 条线索，形成 {internal['conversions']} 条转化记录。",
                "why_it_matters": "获客价值最终取决于线索是否进入持续跟进和转化阶段。",
                "action": "优先检查高意向线索的跟进时效。" if conversion_rate < 20 else "复用高转化来源和回复策略。",
                "value_score": 78,
                "confidence": "high",
                "source_report_id": "",
            })

        adoption_rate = internal.get("adoption_rate")
        if adoption_rate is not None and internal["generations"] >= 3:
            items.append({
                "id": "content-adoption",
                "type": "opportunity" if adoption_rate < 40 else "strength",
                "title": "生成内容利用率偏低" if adoption_rate < 40 else "生成内容利用率良好",
                "finding": f"最近 {internal['period_days']} 天生成 {internal['generations']} 项内容，采纳率 {adoption_rate}%。",
                "why_it_matters": "采纳率反映生成结果是否真正进入后续发布流程。",
                "action": "复盘未采纳内容的提示词与质量问题。" if adoption_rate < 40 else "保留当前提示词和审核方法。",
                "value_score": 65,
                "confidence": "high",
                "source_report_id": "",
            })
        return sorted(items, key=lambda row: _number(row.get("value_score")), reverse=True)[:6]

    def overview(self, days: int = 30) -> dict[str, Any]:
        internal = self._internal_data(days)
        market_report = self._latest_market_report()
        market_gaps = [row for row in ((market_report or {}).get("market_gap") or []) if isinstance(row, dict)][:6]
        knowledge_query = " ".join(str(row.get("topic") or "") for row in market_gaps[:3]).strip()
        if not knowledge_query:
            knowledge_query = str((market_report or {}).get("query") or "")
        knowledge, knowledge_references = self._knowledge_summary(knowledge_query)
        return {
            "generated_at": _iso(),
            "period_days": internal["period_days"],
            "summary": {
                "published": internal["publish_success"],
                "publish_success_rate": internal["publish_success_rate"],
                "leads": internal["leads"],
                "conversions": internal["conversions"],
                "market_opportunities": sum(1 for row in market_gaps if _number(row.get("gap")) > 0),
                "needs_human": internal["needs_human"],
            },
            "trend": self._trend(internal, days),
            "insights": self._insights(internal, market_report),
            "market_gap": market_gaps,
            "actions": [row for row in ((market_report or {}).get("actions") or []) if isinstance(row, dict)][:5],
            "knowledge": {
                "stats": knowledge,
                "references": knowledge_references,
            },
            "market_report": {
                "id": (market_report or {}).get("id") or "",
                "title": (market_report or {}).get("title") or "",
                "query": (market_report or {}).get("query") or "",
                "created_at": (market_report or {}).get("created_at") or "",
                "confidence": ((market_report or {}).get("data_scope") or {}).get("confidence") or "",
                "evidence": [row for row in ((market_report or {}).get("evidence") or []) if isinstance(row, dict)][:5],
            },
            "data_health": self._data_health(internal, knowledge, market_report),
        }

    def content(self, days: int = 30) -> dict[str, Any]:
        internal = self._internal_data(days)
        market_report = self._latest_market_report()
        generations = internal["recent_generations"]
        publish_rows = internal["recent_publish"]
        type_counts = Counter(str(row.get("type") or "unknown") for row in generations)
        platform_counts = Counter(str(row.get("platform") or "unknown") for row in publish_rows)
        status_counts = Counter(_status(row.get("status")) or "unknown" for row in publish_rows)
        recent_items = sorted(
            generations,
            key=lambda row: _parse_time(row.get("updated_at") or row.get("created_at"))
            or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[:12]
        return {
            "generated_at": _iso(),
            "period_days": internal["period_days"],
            "summary": {
                "generated": internal["generations"],
                "adopted": internal["adopted"],
                "adoption_rate": internal["adoption_rate"],
                "published": internal["publish_total"],
                "publish_success": internal["publish_success"],
                "publish_success_rate": internal["publish_success_rate"],
            },
            "funnel": [
                {"stage": "generated", "label": "生成内容", "count": internal["generations"]},
                {"stage": "adopted", "label": "采纳素材", "count": internal["adopted"]},
                {"stage": "published", "label": "提交发布", "count": internal["publish_total"]},
                {"stage": "success", "label": "发布成功", "count": internal["publish_success"]},
            ],
            "content_types": [{"name": key, "value": value} for key, value in type_counts.most_common()],
            "platforms": [{"name": key, "value": value} for key, value in platform_counts.most_common()],
            "publish_statuses": [{"name": key, "value": value} for key, value in status_counts.most_common()],
            "recent_items": [
                {
                    "id": row.get("id") or "",
                    "title": _title(row),
                    "type": row.get("type") or "unknown",
                    "adopted": bool(row.get("adopted")),
                    "created_at": row.get("updated_at") or row.get("created_at") or "",
                }
                for row in recent_items
            ],
            "market_opportunities": [
                row for row in ((market_report or {}).get("market_gap") or []) if isinstance(row, dict)
            ][:5],
            "limitations": [
                "平台作品表现尚未形成统一的定时快照；当前内容洞察聚焦生产、采纳与发布转化。"
            ],
        }


_service: InsightsService | None = None


def get_insights_service() -> InsightsService:
    global _service
    if _service is None:
        _service = InsightsService()
    return _service
