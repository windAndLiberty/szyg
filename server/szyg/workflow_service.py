"""AI-assisted, Hermes-skill-backed workflow service."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from szyg.atomic_file import atomic_read, atomic_write
from szyg.data_path import DATA_DIR
from szyg.execution_kernel import get_execution_kernel
from szyg.workflow_skills import RISK_ORDER, get_workflow_skills


INSTANCES_FILE = DATA_DIR / "workflow_instances.json"
SOPS_FILE = DATA_DIR / "workflow_sops.json"
DRAFTS_FILE = DATA_DIR / "workflow_drafts.json"
DEFINITIONS_FILE = DATA_DIR / "workflow_definitions.json"
LEARNING_EVENTS_FILE = DATA_DIR / "workflow_learning_events.json"
LEGACY_SCHEDULER_FILES = (
    DATA_DIR / "scheduler_jobs.json",
    DATA_DIR / "scheduler_history.json",
)
LEGACY_SCHEDULER_ARCHIVE_DIR = DATA_DIR / "archive" / "legacy_scheduler"

logger = logging.getLogger(__name__)
CONDITION_OPERATORS = {"equals", "not_equals", "contains", "gt", "lt", "empty", "not_empty"}


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _step(
    step_id: str,
    name: str,
    description: str,
    action_id: str,
    *,
    params: dict[str, Any] | None = None,
    risk_level: str = "low",
    requires_confirmation: bool = False,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "name": name,
        "description": description,
        "skill_name": "",
        "action_id": action_id,
        "params": params or {},
        "condition": None,
        "risk_level": risk_level,
        "confirmation_policy": "every_run" if requires_confirmation else "automatic",
        "requires_confirmation": requires_confirmation,
        "on_failure": "needs_human" if requires_confirmation else "stop",
    }


WORKFLOW_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "content_scheduled_publish", "name": "内容定时发布", "category": "content_operations",
        "category_label": "内容运营", "description": "按设定时间将已确认的素材交给内容发布模块执行。",
        "outcome": "获得可追踪的多渠道发布记录", "icon": "send", "risk_level": "high",
        "estimated_minutes": 5, "available": False, "config_schema": {"requires": ["publish_task_ids"]},
        "steps": [_step("publish", "执行内容发布", "发布前等待你确认", "publishing.publish", risk_level="high", requires_confirmation=True)],
    },
    {
        "id": "account_health_check", "name": "渠道账号巡检", "category": "channel_operations",
        "category_label": "渠道运营", "description": "检查已连接渠道的登录状态、账号异常和需要处理事项。",
        "outcome": "生成账号健康清单和待处理事项", "icon": "shield", "risk_level": "low",
        "estimated_minutes": 1, "available": True, "config_schema": {},
        "steps": [
            _step("check_accounts", "检查账号状态", "识别在线、需登录和异常账号", "accounts.health_check"),
            _step("build_report", "整理巡检结果", "形成健康清单和处理建议", "report.compose", params={"title": "渠道账号巡检"}),
        ],
    },
    {
        "id": "customer_followup_reminder", "name": "客户跟进提醒", "category": "customer_operations",
        "category_label": "客户运营", "description": "整理待跟进和高意向客户，形成当天行动清单。",
        "outcome": "获得按优先级排列的客户跟进清单", "icon": "users", "risk_level": "low",
        "estimated_minutes": 1, "available": True, "config_schema": {},
        "steps": [
            _step("summarize_leads", "整理客户线索", "识别高意向和待跟进客户", "leads.summarize"),
            _step("build_report", "生成行动清单", "形成今天的客户跟进清单", "report.compose", params={"title": "今日客户跟进"}),
        ],
    },
    {
        "id": "lead_daily_digest", "name": "线索整理日报", "category": "data_operations",
        "category_label": "数据整理", "description": "汇总新增线索、意向等级和来源渠道，减少人工整理。",
        "outcome": "获得结构化线索日报", "icon": "report", "risk_level": "low",
        "estimated_minutes": 1, "available": True, "config_schema": {},
        "steps": [
            _step("summarize_leads", "汇总线索", "统计渠道、状态和意向等级", "leads.summarize"),
            _step("build_report", "生成日报", "输出线索概览和下一步建议", "report.compose", params={"title": "线索整理日报"}),
        ],
    },
    {
        "id": "geo_weekly_audit", "name": "每周检查AI是否推荐我的企业", "category": "geo_operations",
        "category_label": "GEO品牌增长", "description": "按照已确认的客户问题，检查已配置AI平台是否提及、推荐和引用企业。",
        "outcome": "获得可追踪的AI品牌可见度变化和优化建议", "icon": "globe", "risk_level": "low",
        "estimated_minutes": 5, "available": True, "config_schema": {},
        "steps": [
            _step("run_geo_audit", "检查AI推荐表现", "向已配置平台发起真实检测并保存回答与引用", "geo.audit"),
            _step("build_report", "整理GEO结果", "形成品牌提及、推荐和引用摘要", "report.compose", params={"title": "每周GEO品牌检查"}),
        ],
    },
]


class ConditionModel(BaseModel):
    step_id: str = ""
    field: str = ""
    operator: str
    value: Any = None


class DraftStepModel(BaseModel):
    id: str = ""
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)
    action_id: str = Field(min_length=1, max_length=120)
    params: dict[str, Any] = Field(default_factory=dict)
    condition: ConditionModel | None = None


class DraftPlanModel(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)
    outcome: str = Field(default="", max_length=300)
    steps: list[DraftStepModel] = Field(min_length=1, max_length=20)


def _extract_json(raw: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
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
        except json.JSONDecodeError:
            continue
    return None


def _normalize_planner_shape(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize harmless JSON representation differences before validation."""
    normalized = deepcopy(data)
    steps = normalized.get("steps")
    if not isinstance(steps, list):
        return normalized
    for index, raw in enumerate(steps):
        if not isinstance(raw, dict):
            continue
        raw["id"] = str(raw.get("id") or f"step_{index + 1}")
        if not isinstance(raw.get("params"), dict):
            raw["params"] = {}
        condition = raw.get("condition")
        if condition in (None, "", False):
            raw["condition"] = None
        elif isinstance(condition, dict):
            condition["step_id"] = str(condition.get("step_id") or "")
    return normalized


class WorkflowService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._scheduler_task: asyncio.Task | None = None
        self._stopping = False
        self.skills = get_workflow_skills()
        get_execution_kernel().register_task_runner("workflow", self.execute_run)

    @staticmethod
    def _read(path: Path) -> list[dict[str, Any]]:
        rows = atomic_read(path)
        return rows if isinstance(rows, list) else []

    def _replace(self, path: Path, item_id: str, item: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            rows = self._read(path)
            for index, row in enumerate(rows):
                if row.get("id") == item_id:
                    rows[index] = item
                    atomic_write(path, rows)
                    return item
            rows.append(item)
            atomic_write(path, rows)
            return item

    def list_capabilities(self) -> list[dict[str, Any]]:
        return self.skills.list_capabilities()

    def archive_legacy_scheduler_data(self) -> str:
        """Move legacy scheduler state out of the active data set exactly once."""
        sources = [path for path in LEGACY_SCHEDULER_FILES if path.exists()]
        if not sources:
            return ""
        with self._lock:
            stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
            archive_dir = LEGACY_SCHEDULER_ARCHIVE_DIR / stamp
            suffix = 1
            while archive_dir.exists():
                archive_dir = LEGACY_SCHEDULER_ARCHIVE_DIR / f"{stamp}_{suffix}"
                suffix += 1
            archive_dir.mkdir(parents=True, exist_ok=False)
            moved: list[str] = []
            for source in sources:
                target = archive_dir / source.name
                source.replace(target)
                moved.append(source.name)
            atomic_write(archive_dir / "manifest.json", {
                "archived_at": _now(),
                "reason": "legacy_scheduler_retired",
                "migrated": False,
                "files": moved,
            })
            logger.info("Archived legacy scheduler data to %s", archive_dir)
            return str(archive_dir)

    def list_templates(self) -> list[dict[str, Any]]:
        return deepcopy(WORKFLOW_TEMPLATES)

    def get_template(self, template_id: str) -> dict[str, Any] | None:
        return next((deepcopy(item) for item in WORKFLOW_TEMPLATES if item["id"] == template_id), None)

    def get_definition(self, definition_id: str) -> dict[str, Any] | None:
        """Resolve a reusable standard process from builtin or enterprise definitions."""
        if not definition_id:
            return None
        if definition_id.startswith("sop_"):
            return next((deepcopy(item) for item in self.list_sops() if item.get("id") == definition_id), None)
        for path in (SOPS_FILE, DEFINITIONS_FILE):
            item = next((row for row in self._read(path) if row.get("id") == definition_id), None)
            if item:
                return deepcopy(item)
        return None

    def create_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        goal = str(payload.get("goal") or "").strip()
        if not goal:
            raise ValueError("请先描述希望系统完成的工作")
        now = _now()
        item = {
            "id": _id("wfd"), "goal": goal, "name": "", "description": "", "outcome": "",
            "status": "draft", "context": self._normalize_context(payload.get("context") or {}),
            "schedule": self._normalize_schedule(payload.get("schedule") or {"type": "manual"}),
            "notification": str(payload.get("notification") or "in_app"), "steps": [],
            "validation": {"valid": False, "issues": ["方案尚未设计"]}, "version": 1, "versions": [],
            "created_at": now, "updated_at": now,
        }
        with self._lock:
            rows = self._read(DRAFTS_FILE)
            rows.append(item)
            atomic_write(DRAFTS_FILE, rows)
        return item

    def get_draft(self, draft_id: str) -> dict[str, Any] | None:
        return next((item for item in self._read(DRAFTS_FILE) if item.get("id") == draft_id), None)

    def update_draft(self, draft_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        item = self.get_draft(draft_id)
        if not item:
            raise KeyError("draft_not_found")
        if item.get("status") == "active":
            raise ValueError("已启用方案不能继续修改")
        snapshot = {key: deepcopy(item.get(key)) for key in ("name", "description", "outcome", "steps", "schedule")}
        for key in ("name", "description", "outcome", "steps", "notification"):
            if key in updates and updates[key] is not None:
                item[key] = deepcopy(updates[key])
        if updates.get("context") is not None:
            item["context"] = self._normalize_context(updates["context"])
        if updates.get("schedule") is not None:
            item["schedule"] = self._normalize_schedule(updates["schedule"])
        item["versions"] = [*item.get("versions", []), {"version": item.get("version", 1), "saved_at": _now(), **snapshot}][-20:]
        item["version"] = int(item.get("version") or 1) + 1
        item["updated_at"] = _now()
        item["validation"] = {"valid": False, "issues": ["方案修改后需要重新检查"]}
        return self._replace(DRAFTS_FILE, draft_id, item)

    async def design_draft(self, draft_id: str) -> dict[str, Any]:
        item = self.get_draft(draft_id)
        if not item:
            raise KeyError("draft_not_found")
        business_context = await self._collect_design_context(item)
        plan = await self._plan_with_model(item, business_context)
        normalized = self._normalize_plan(plan, goal=item["goal"])
        return self.update_draft(draft_id, normalized)

    async def revise_draft(self, draft_id: str, instruction: str) -> dict[str, Any]:
        item = self.get_draft(draft_id)
        if not item:
            raise KeyError("draft_not_found")
        if not item.get("steps"):
            raise ValueError("请先生成方案")
        plan = await self._plan_with_model(item, {"current_plan": {
            "name": item.get("name"), "description": item.get("description"),
            "outcome": item.get("outcome"), "steps": item.get("steps"),
        }, "revision": instruction}, revision=True)
        return self.update_draft(draft_id, self._normalize_plan(plan, goal=item["goal"]))

    async def _plan_with_model(self, draft: dict[str, Any], context: dict[str, Any], revision: bool = False) -> dict[str, Any]:
        from szyg.config.loader import load_config
        from szyg.integrations.volcengine_client import VolcEngineClient

        cfg = (load_config().get("workflow", {}) or {}).get("ai", {}) or {}
        model = str(cfg.get("planner_model") or "doubao-seed-2-0-lite-260428")
        effort = str(cfg.get("reasoning_effort") or "minimal")
        capabilities = [{key: item.get(key) for key in ("action_id", "name", "description", "risk_level", "input_schema")} for item in self.list_capabilities()]
        system = """你是企业工作流方案设计师。把用户目标整理成可执行的顺序步骤，只输出JSON。
JSON字段：name、description、outcome、steps。steps每项包含id、name、description、action_id、params、condition。
id和condition.step_id必须是字符串；没有条件时condition必须为null，不要使用空字符串。
只能优先使用给出的action_id。条件仅允许引用前序步骤，operator只能是equals、not_equals、contains、gt、lt、empty、not_empty。
不创建循环、并行或任意代码。若缺少能力，action_id写missing.<简短英文标识>，并把人工可执行说明写入description。
不要输出模型、工具、Skill、API等技术词。"""
        payload = {
            "mode": "revise" if revision else "design", "goal": draft.get("goal"),
            "schedule": draft.get("schedule"), "context_selection": draft.get("context"),
            "business_context": context, "available_actions": capabilities,
        }
        client = VolcEngineClient(timeout=90)
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                response = await client.responses_text(
                    [{"role": "user", "content": [{"type": "input_text", "text": f"{system}\n\n输入：\n{json.dumps(payload, ensure_ascii=False)}"}]}],
                    model=model, max_output_tokens=5000, reasoning_effort=effort,
                )
                data = _extract_json(str((response.get("message") or {}).get("content") or ""))
                if not data:
                    raise ValueError("AI 未返回有效方案")
                normalized = _normalize_planner_shape(data)
                return DraftPlanModel.model_validate(normalized).model_dump()
            except Exception as exc:
                last_error = exc
                payload["validation_feedback"] = str(exc)[:1000]
        raise ValueError(f"AI 方案设计暂时不可用：{last_error}")

    async def _collect_design_context(self, draft: dict[str, Any]) -> dict[str, Any]:
        selected = draft.get("context") or {}
        result: dict[str, Any] = {}
        if selected.get("knowledge", True):
            try:
                from szyg.mcp_servers.knowledge_mcp import kb_search

                result["knowledge"] = kb_search(draft["goal"], 5)
            except Exception:
                result["knowledge"] = []
        if selected.get("accounts"):
            from szyg.channel_accounts import list_accounts

            result["accounts"] = [{"platform": row.get("platform"), "status": row.get("status"), "name": row.get("nickname") or row.get("label")} for row in list_accounts(include_defaults=False)]
        if selected.get("leads"):
            result["leads"] = await self.skills.execute("leads.summarize", {}, {"goal": draft["goal"]})
        if selected.get("materials"):
            result["materials"] = [{"name": row.get("name"), "type": row.get("type")} for row in self._read(DATA_DIR / "materials.json")[:100]]
        if selected.get("publish_records"):
            result["publish_records"] = await self.skills.execute("publishing.summarize", {"limit": 30}, {"goal": draft["goal"]})
        return result

    def _normalize_plan(self, plan: dict[str, Any], goal: str) -> dict[str, Any]:
        capabilities = {item["action_id"]: item for item in self.list_capabilities()}
        steps: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, raw in enumerate(plan.get("steps") or []):
            action_id = str(raw.get("action_id") or "")
            if action_id not in capabilities:
                learned = None
                if action_id.startswith("missing."):
                    try:
                        learned = self.skills.learn_manual_capability(str(raw.get("name") or "新任务"), str(raw.get("description") or goal), action_id)
                        self._learning_event(action_id, learned.get("action_id", ""), "installed", "")
                    except Exception as exc:
                        self._learning_event(action_id, "human.complete_task", "failed", str(exc))
                action_id = str((learned or {}).get("action_id") or "human.complete_task")
            capability = capabilities.get(action_id) or self.skills.get(action_id) or self.skills.get("human.complete_task") or {}
            step_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(raw.get("id") or f"step_{index + 1}"))[:60]
            if not step_id or step_id in seen:
                step_id = f"step_{index + 1}"
            seen.add(step_id)
            condition = raw.get("condition")
            if isinstance(condition, dict) and condition.get("operator") not in CONDITION_OPERATORS:
                condition = None
            params = deepcopy(raw.get("params") or {})
            if capability.get("execution_mode") == "manual":
                params.setdefault("instruction", str(raw.get("description") or goal))
            risk = str(capability.get("risk_level") or "medium")
            steps.append({
                "id": step_id, "name": str(raw.get("name") or capability.get("name") or "执行任务")[:80],
                "description": str(raw.get("description") or capability.get("description") or "")[:300],
                "skill_name": capability.get("skill_name", ""), "action_id": action_id, "params": params,
                "condition": condition, "risk_level": risk,
                "confirmation_policy": "every_run" if risk == "high" else "automatic",
                "requires_confirmation": risk == "high", "on_failure": "needs_human" if risk == "high" else "stop",
            })
        if not steps:
            raise ValueError("方案至少需要一个步骤")
        return {
            "name": str(plan.get("name") or "我的工作流方案")[:80],
            "description": str(plan.get("description") or goal)[:300],
            "outcome": str(plan.get("outcome") or "按计划完成目标并记录结果")[:300],
            "steps": steps,
        }

    def validate_draft(self, draft_id: str) -> dict[str, Any]:
        item = self.get_draft(draft_id)
        if not item:
            raise KeyError("draft_not_found")
        capabilities = {row["action_id"]: row for row in self.list_capabilities()}
        issues: list[str] = []
        warnings: list[str] = []
        seen: set[str] = set()
        for index, step in enumerate(item.get("steps") or []):
            step_id = str(step.get("id") or "")
            if not step_id or step_id in seen:
                issues.append(f"第 {index + 1} 步缺少唯一标识")
            seen.add(step_id)
            capability = capabilities.get(str(step.get("action_id") or ""))
            if not capability:
                issues.append(f"“{step.get('name') or step_id}”当前不可执行")
                continue
            declared = str(step.get("risk_level") or "low")
            if RISK_ORDER.get(declared, 0) < RISK_ORDER.get(capability["risk_level"], 2):
                step["risk_level"] = capability["risk_level"]
                warnings.append(f"“{step.get('name')}”风险等级已按系统规则调整")
            condition = step.get("condition")
            if condition:
                if condition.get("operator") not in CONDITION_OPERATORS:
                    issues.append(f"“{step.get('name')}”使用了不支持的判断条件")
                if condition.get("step_id") not in seen - {step_id}:
                    issues.append(f"“{step.get('name')}”只能引用前序步骤")
        if not item.get("steps"):
            issues.append("方案至少需要一个步骤")
        item["steps"] = item.get("steps") or []
        item["validation"] = {"valid": not issues, "issues": issues, "warnings": warnings, "checked_at": _now()}
        item["updated_at"] = _now()
        self._replace(DRAFTS_FILE, draft_id, item)
        return item["validation"]

    def activate_draft(self, draft_id: str) -> dict[str, Any]:
        validation = self.validate_draft(draft_id)
        if not validation["valid"]:
            raise ValueError("方案检查未通过，请先修正问题")
        draft = self.get_draft(draft_id)
        if not draft:
            raise KeyError("draft_not_found")
        now = _now()
        definition = {
            "id": _id("wfdn"), "draft_id": draft_id, "name": draft["name"],
            "description": draft.get("description", ""), "outcome": draft.get("outcome", ""),
            "goal": draft["goal"], "steps": deepcopy(draft["steps"]), "version": draft.get("version", 1),
            "source": "custom", "category": "custom", "category_label": "我的流程",
            "enabled": True, "created_at": now, "updated_at": now, "versions": [],
        }
        with self._lock:
            definitions = self._read(DEFINITIONS_FILE)
            definitions.append(definition)
            atomic_write(DEFINITIONS_FILE, definitions)
        instance = self._create_instance_record({
            "template_id": "custom_ai", "template_name": "自定义工作流", "definition_id": definition["id"],
            "definition_version": definition["version"],
            "name": draft["name"], "description": draft.get("description", ""), "schedule": draft["schedule"],
            "config": {"goal": draft["goal"], "context": draft.get("context", {}), "notification": draft.get("notification")},
            "human_policy": "risk_based", "steps": definition["steps"],
        })
        draft["status"] = "active"
        draft["definition_id"] = definition["id"]
        draft["instance_id"] = instance["id"]
        draft["updated_at"] = _now()
        self._replace(DRAFTS_FILE, draft_id, draft)
        return instance

    def _learning_event(self, requested: str, installed: str, status: str, error: str) -> None:
        event = {"id": _id("learn"), "requested_action": requested, "installed_action": installed, "status": status, "error": error[:500], "created_at": _now()}
        with self._lock:
            rows = self._read(LEARNING_EVENTS_FILE)
            rows.append(event)
            atomic_write(LEARNING_EVENTS_FILE, rows[-1000:])

    def list_instances(self) -> list[dict[str, Any]]:
        rows = self._read(INSTANCES_FILE)
        runs = self.list_runs(limit=500)
        latest: dict[str, dict[str, Any]] = {}
        for run in runs:
            if run.get("instance_id") and run["instance_id"] not in latest:
                latest[run["instance_id"]] = run
        result = []
        for row in sorted(rows, key=lambda item: item.get("created_at", ""), reverse=True):
            item = dict(row)
            item["last_run"] = latest.get(item["id"])
            definition = self.get_definition(str(item.get("definition_id") or ""))
            latest_version = int((definition or {}).get("version") or item.get("definition_version") or 1)
            item["latest_definition_version"] = latest_version
            item["upgrade_available"] = bool(definition) and latest_version > int(item.get("definition_version") or 1)
            result.append(item)
        return result

    def get_instance(self, instance_id: str) -> dict[str, Any] | None:
        return next((item for item in self._read(INSTANCES_FILE) if item.get("id") == instance_id), None)

    def _create_instance_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        schedule = self._normalize_schedule(payload.get("schedule") or {"type": "manual"})
        now = _now()
        item = {
            "id": _id("wf"), "template_id": payload.get("template_id", "custom_ai"),
            "template_name": payload.get("template_name", "自定义工作流"), "definition_id": payload.get("definition_id", ""),
            "name": str(payload.get("name") or "工作流方案").strip(), "description": str(payload.get("description") or "").strip(),
            "status": "active", "schedule": schedule, "config": payload.get("config") or {},
            "human_policy": payload.get("human_policy") or "risk_based", "steps": deepcopy(payload.get("steps") or []),
            "definition_version": int(payload.get("definition_version") or 1),
            "definition_snapshot": {
                "definition_id": payload.get("definition_id", ""),
                "version": int(payload.get("definition_version") or 1),
                "steps": deepcopy(payload.get("steps") or []),
                "saved_at": now,
            },
            "created_at": now, "updated_at": now, "last_run_at": "", "next_run_at": self._next_run(schedule),
        }
        with self._lock:
            rows = self._read(INSTANCES_FILE)
            rows.append(item)
            atomic_write(INSTANCES_FILE, rows)
        return item

    def create_instance(self, payload: dict[str, Any]) -> dict[str, Any]:
        definition_id = str(payload.get("definition_id") or "")
        if definition_id:
            definition = self.get_definition(definition_id)
            if not definition:
                raise KeyError("definition_not_found")
            if definition.get("enabled") is False:
                raise ValueError("该标准流程已停用")
            template_id = str(definition.get("template_id") or payload.get("template_id") or "custom")
            builtin = self.get_template(template_id)
            if builtin and not builtin.get("available"):
                raise ValueError("该方案正在接入现有业务能力，暂不可启用")
            return self._create_instance_record({
                **payload,
                "template_id": template_id,
                "template_name": definition.get("name") or "企业标准流程",
                "definition_id": definition_id,
                "definition_version": int(definition.get("version") or 1),
                "steps": definition.get("steps") or [],
            })

        template = self.get_template(str(payload.get("template_id", "")))
        if not template:
            raise KeyError("template_not_found")
        if not template.get("available"):
            raise ValueError("该方案正在接入现有业务能力，暂不可启用")
        return self._create_instance_record({
            **payload,
            "definition_id": f"sop_{template['id']}",
            "definition_version": 1,
            "template_name": template["name"],
            "steps": template["steps"],
        })

    def upgrade_instance(self, instance_id: str) -> dict[str, Any]:
        instance = self.get_instance(instance_id)
        if not instance:
            raise KeyError("instance_not_found")
        definition = self.get_definition(str(instance.get("definition_id") or ""))
        if not definition:
            raise ValueError("当前方案没有可更新的标准流程")
        current = int(instance.get("definition_version") or 1)
        latest = int(definition.get("version") or 1)
        if latest <= current:
            return instance
        with self._lock:
            rows = self._read(INSTANCES_FILE)
            for index, item in enumerate(rows):
                if item.get("id") != instance_id:
                    continue
                item["definition_version"] = latest
                item["steps"] = deepcopy(definition.get("steps") or [])
                item["definition_snapshot"] = {
                    "definition_id": definition.get("id", ""),
                    "version": latest,
                    "steps": deepcopy(definition.get("steps") or []),
                    "saved_at": _now(),
                }
                item["updated_at"] = _now()
                rows[index] = item
                atomic_write(INSTANCES_FILE, rows)
                return item
        raise KeyError("instance_not_found")

    def update_instance(self, instance_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        allowed = {"name", "description", "status", "schedule", "config", "human_policy"}
        with self._lock:
            rows = self._read(INSTANCES_FILE)
            for index, item in enumerate(rows):
                if item.get("id") != instance_id:
                    continue
                clean = {key: value for key, value in updates.items() if key in allowed and value is not None}
                if "status" in clean and clean["status"] not in {"draft", "active", "paused", "disabled"}:
                    raise ValueError("无效的方案状态")
                if "schedule" in clean:
                    clean["schedule"] = self._normalize_schedule(clean["schedule"])
                item.update(clean)
                item["updated_at"] = _now()
                item["next_run_at"] = self._next_run(item.get("schedule") or {"type": "manual"}) if item.get("status") == "active" else ""
                rows[index] = item
                atomic_write(INSTANCES_FILE, rows)
                return item
        raise KeyError("instance_not_found")

    def delete_instance(self, instance_id: str) -> bool:
        with self._lock:
            rows = self._read(INSTANCES_FILE)
            kept = [item for item in rows if item.get("id") != instance_id]
            if len(kept) == len(rows):
                return False
            atomic_write(INSTANCES_FILE, kept)
            return True

    async def run_instance(self, instance_id: str, trigger: str = "manual") -> dict[str, Any]:
        instance = self.get_instance(instance_id)
        if not instance:
            raise KeyError("instance_not_found")
        active = next((item for item in self.list_runs(limit=500)
                       if item.get("instance_id") == instance_id and item.get("status") in {"queued", "running", "needs_human"}), None)
        if active:
            raise ValueError("该工作流方案已有任务正在运行或等待处理")
        kernel = get_execution_kernel()
        run = kernel.create_run(
            "workflow", "", "hermes", {
                "instance_id": instance_id, "instance_name": instance["name"],
                "template_id": instance.get("template_id", ""), "definition_id": instance.get("definition_id", ""),
                "definition_version": instance.get("definition_version", 1), "trigger": trigger,
                "goal": (instance.get("config") or {}).get("goal", instance.get("description", "")),
                "confirmed_step_ids": [],
            }, title=instance["name"], source_task_id=f"workflow:{instance_id}", auto_start=False,
        )
        kernel.start_run(run["id"])
        return self._map_run(kernel.get_run(run["id"]) or run)

    async def execute_run(self, run_id: str) -> dict[str, Any]:
        kernel = get_execution_kernel()
        run = kernel.get_run(run_id)
        if not run:
            raise KeyError(run_id)
        payload = run.get("input") or {}
        instance = self.get_instance(str(payload.get("instance_id") or ""))
        if not instance:
            return kernel.complete_run(run_id, "failed", error_code="workflow_missing", error_message="工作流方案已不存在")
        persisted = run.get("result") or {}
        outputs = dict(persisted.get("step_outputs") or {})
        completed_ids = list(persisted.get("completed_step_ids") or [])
        confirmed = set(payload.get("confirmed_step_ids") or [])
        context = {"goal": payload.get("goal", ""), "outputs": outputs}
        try:
            for step_info in instance.get("steps") or []:
                step_id = step_info["id"]
                if step_id in completed_ids:
                    continue
                kernel._ensure_active(run_id)
                if not self._condition_matches(step_info.get("condition"), outputs):
                    step = kernel.start_step(run_id, step_id, step_info["name"], "hermes", step_info.get("action_id", step_id))
                    kernel.finish_step(step, "skipped", "条件不成立，本步骤已跳过")
                    completed_ids.append(step_id)
                    kernel.complete_run(run_id, "running", {"step_outputs": outputs, "completed_step_ids": completed_ids})
                    continue
                capability = self.skills.get(step_info.get("action_id", "")) or {}
                requires_confirmation = step_info.get("risk_level") == "high" or capability.get("risk_level") == "high"
                is_manual = capability.get("execution_mode") == "manual"
                if (requires_confirmation or is_manual) and step_id not in confirmed:
                    step = kernel.start_step(run_id, step_id, step_info["name"], "hermes", step_info.get("action_id", step_id))
                    message = "执行前需要你确认" if requires_confirmation else str((step_info.get("params") or {}).get("instruction") or step_info.get("description") or "请人工完成此步骤")
                    kernel.finish_step(step, "needs_human", message, error_code="workflow_confirmation_required" if requires_confirmation else "manual_step_required")
                    return kernel.complete_run(run_id, "needs_human", {
                        "step_outputs": outputs, "completed_step_ids": completed_ids,
                        "pending_step": {"id": step_id, "name": step_info["name"], "message": message},
                    }, "workflow_confirmation_required" if requires_confirmation else "manual_step_required", message)
                step = kernel.start_step(run_id, step_id, step_info["name"], "hermes", step_info.get("action_id", step_id))
                if is_manual:
                    result = {"confirmed": True, "message": "人工步骤已确认完成"}
                else:
                    result = await self.skills.execute(step_info["action_id"], step_info.get("params") or {}, context)
                outputs[step_id] = result
                context["outputs"] = outputs
                completed_ids.append(step_id)
                kernel.finish_step(step, "success", str(result.get("message") or step_info.get("description") or "步骤执行完成"))
                kernel.complete_run(run_id, "running", {"step_outputs": outputs, "completed_step_ids": completed_ids})
            completed = kernel.complete_run(run_id, "success", {"step_outputs": outputs, "completed_step_ids": completed_ids, "message": "工作流方案执行完成"})
            self._mark_instance_run(instance["id"], completed, str(payload.get("trigger") or "manual"))
            return completed
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            completed = kernel.complete_run(run_id, "failed", {"step_outputs": outputs, "completed_step_ids": completed_ids}, "workflow_failed", str(exc))
            self._mark_instance_run(instance["id"], completed, str(payload.get("trigger") or "manual"))
            return completed

    def confirm_run(self, run_id: str) -> dict[str, Any]:
        kernel = get_execution_kernel()
        run = kernel.get_run(run_id)
        if not run or run.get("task_type") != "workflow":
            raise KeyError("run_not_found")
        pending = (run.get("result") or {}).get("pending_step") or {}
        step_id = str(pending.get("id") or "")
        if run.get("status") != "needs_human" or not step_id:
            raise ValueError("当前任务没有等待确认的步骤")
        payload = dict(run.get("input") or {})
        payload["confirmed_step_ids"] = list(dict.fromkeys([*(payload.get("confirmed_step_ids") or []), step_id]))
        kernel._patch_run(run_id, input=payload, status="queued", error_code="", error_message="", finished_at="")
        kernel.add_audit(run_id, "", "confirm", "queued", f"用户已确认步骤：{pending.get('name') or step_id}")
        return self._map_run(kernel.start_run(run_id))

    @staticmethod
    def _condition_matches(condition: dict[str, Any] | None, outputs: dict[str, Any]) -> bool:
        if not condition:
            return True
        value: Any = outputs.get(str(condition.get("step_id") or ""), {})
        for part in str(condition.get("field") or "").split("."):
            if not part:
                continue
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(part)
        expected = condition.get("value")
        operator = condition.get("operator")
        if operator == "equals": return value == expected
        if operator == "not_equals": return value != expected
        if operator == "contains": return expected in value if isinstance(value, (str, list, dict)) else False
        if operator == "gt":
            try: return float(value) > float(expected)
            except (TypeError, ValueError): return False
        if operator == "lt":
            try: return float(value) < float(expected)
            except (TypeError, ValueError): return False
        if operator == "empty": return value in (None, "", [], {})
        if operator == "not_empty": return value not in (None, "", [], {})
        return False

    def _mark_instance_run(self, instance_id: str, run: dict[str, Any], trigger: str = "manual") -> None:
        with self._lock:
            rows = self._read(INSTANCES_FILE)
            for index, item in enumerate(rows):
                if item.get("id") == instance_id:
                    item["last_run_at"] = run.get("finished_at") or _now()
                    item["updated_at"] = _now()
                    if trigger == "scheduled" and item.get("status") == "active":
                        item["next_run_at"] = self._next_run(item.get("schedule") or {"type": "manual"}, after_run=True)
                    rows[index] = item
                    atomic_write(INSTANCES_FILE, rows)
                    return

    def list_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        return [self._map_run(item) for item in get_execution_kernel().list_runs(limit=limit, task_type="workflow")]

    @staticmethod
    def _map_run(run: dict[str, Any]) -> dict[str, Any]:
        payload = run.get("input") or {}
        return {
            "id": run.get("id", ""), "instance_id": payload.get("instance_id", ""),
            "instance_name": payload.get("instance_name") or run.get("title") or "工作流任务",
            "template_id": payload.get("template_id", ""), "status": run.get("status", "queued"),
            "definition_id": payload.get("definition_id", ""), "definition_version": payload.get("definition_version", 1),
            "current_step_id": run.get("current_step_id", ""), "result": run.get("result") or {},
            "error_code": run.get("error_code", ""), "error_message": run.get("error_message", ""),
            "created_at": run.get("created_at", ""), "started_at": run.get("started_at", ""),
            "finished_at": run.get("finished_at", ""), "duration_ms": run.get("duration_ms", 0),
        }

    def overview(self) -> dict[str, Any]:
        instances = self._read(INSTANCES_FILE)
        runs = self.list_runs(limit=500)
        today = datetime.now().astimezone().date().isoformat()
        return {
            "templates": sum(1 for item in WORKFLOW_TEMPLATES if item.get("available")),
            "active_instances": sum(1 for item in instances if item.get("status") == "active"),
            "running": sum(1 for item in runs if item.get("status") in {"queued", "running"}),
            "needs_human": sum(1 for item in runs if item.get("status") == "needs_human"),
            "success_today": sum(1 for item in runs if item.get("status") == "success" and str(item.get("finished_at", "")).startswith(today)),
        }

    def list_sops(self) -> list[dict[str, Any]]:
        custom = self._read(SOPS_FILE)
        runs = self.list_runs(limit=1000)
        builtin = []
        for template in WORKFLOW_TEMPLATES:
            template_runs = [item for item in runs if item.get("template_id") == template["id"]]
            successes = sum(1 for item in template_runs if item.get("status") == "success")
            builtin.append({
                "id": f"sop_{template['id']}", "name": f"{template['name']}标准流程",
                "description": template["description"], "category": template["category"],
                "category_label": template["category_label"], "source": "builtin", "enabled": True,
                "available": bool(template.get("available")),
                "template_id": template["id"], "outcome": template.get("outcome", ""), "version": 1,
                "steps": deepcopy(template["steps"]), "execution_count": len(template_runs),
                "success_rate": round(successes / len(template_runs) * 100, 1) if template_runs else 0,
                "recent_runs": template_runs[:5],
            })
        definitions = []
        custom_ids = {item.get("id") for item in custom}
        for item in self._read(DEFINITIONS_FILE):
            if item.get("id") in custom_ids:
                continue
            definitions.append({**item, "source": "custom", "enabled": item.get("enabled", True),
                                "category": item.get("category", "custom"),
                                "category_label": item.get("category_label", "我的流程"),
                                "execution_count": 0, "success_rate": 0, "recent_runs": []})
        return builtin + sorted([*custom, *definitions], key=lambda item: item.get("created_at", ""), reverse=True)

    def clone_sop(self, sop_id: str) -> dict[str, Any]:
        source = next((item for item in self.list_sops() if item.get("id") == sop_id), None)
        if not source:
            raise KeyError("sop_not_found")
        now = _now()
        item = {**{key: value for key, value in source.items() if key not in {"id", "source", "execution_count", "success_rate"}},
                "id": _id("sop"), "name": f"{source['name']}（副本）", "source": "custom",
                "version": 1, "versions": [], "created_at": now, "updated_at": now,
                "execution_count": 0, "success_rate": 0}
        with self._lock:
            rows = self._read(SOPS_FILE); rows.append(item); atomic_write(SOPS_FILE, rows)
        return item

    def update_sop(self, sop_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            for path in (SOPS_FILE, DEFINITIONS_FILE):
                rows = self._read(path)
                for index, item in enumerate(rows):
                    if item.get("id") != sop_id:
                        continue
                    snapshot = {"version": int(item.get("version") or 1), "saved_at": _now(),
                                "name": item.get("name", ""), "description": item.get("description", ""),
                                "steps": deepcopy(item.get("steps") or [])}
                    for key in {"name", "description", "enabled", "steps"}:
                        if key in updates and updates[key] is not None:
                            item[key] = updates[key]
                    item["versions"] = [*item.get("versions", []), snapshot][-20:]
                    item["version"] = int(item.get("version") or 1) + 1
                    item["updated_at"] = _now()
                    rows[index] = item
                    atomic_write(path, rows)
                    return item
        raise KeyError("sop_not_found")

    def delete_sop(self, sop_id: str) -> bool:
        if any(item.get("definition_id") == sop_id for item in self._read(INSTANCES_FILE)):
            raise ValueError("该标准流程仍被工作流方案使用，请先移除相关方案")
        with self._lock:
            for path in (SOPS_FILE, DEFINITIONS_FILE):
                rows = self._read(path)
                kept = [item for item in rows if item.get("id") != sop_id]
                if len(kept) == len(rows):
                    continue
                atomic_write(path, kept)
                return True
        return False

    @staticmethod
    def _normalize_context(context: dict[str, Any]) -> dict[str, bool]:
        return {"knowledge": bool(context.get("knowledge", True)), "accounts": bool(context.get("accounts", False)),
                "leads": bool(context.get("leads", False)), "materials": bool(context.get("materials", False)),
                "publish_records": bool(context.get("publish_records", False))}

    @staticmethod
    def _normalize_schedule(schedule: dict[str, Any]) -> dict[str, Any]:
        schedule_type = str(schedule.get("type") or "manual")
        if schedule_type not in {"manual", "daily", "weekly", "interval", "once"}: raise ValueError("无效的运行频率")
        result: dict[str, Any] = {"type": schedule_type}
        if schedule_type in {"daily", "weekly"}: result["time"] = str(schedule.get("time") or "09:00")
        if schedule_type == "weekly": result["weekdays"] = schedule.get("weekdays") or [1]
        if schedule_type == "interval": result["interval_minutes"] = max(5, int(schedule.get("interval_minutes") or 60))
        if schedule_type == "once": result["at"] = str(schedule.get("at") or "")
        return result

    @staticmethod
    def _next_run(schedule: dict[str, Any], after_run: bool = False) -> str:
        now = datetime.now().astimezone(); schedule_type = schedule.get("type", "manual")
        if schedule_type == "manual": return ""
        if schedule_type == "interval": return (now + timedelta(minutes=max(5, int(schedule.get("interval_minutes") or 60)))).isoformat()
        if schedule_type == "once": return "" if after_run else str(schedule.get("at") or "")
        hour, minute = (str(schedule.get("time") or "09:00").split(":") + ["0"])[:2]
        candidate = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
        if schedule_type == "daily":
            if candidate <= now: candidate += timedelta(days=1)
            return candidate.isoformat()
        weekdays = {int(value) for value in schedule.get("weekdays") or [1]}
        for offset in range(8):
            day = candidate + timedelta(days=offset)
            if day.isoweekday() in weekdays and day > now: return day.isoformat()
        return (candidate + timedelta(days=7)).isoformat()

    async def process_due(self) -> None:
        now = datetime.now().astimezone()
        due_ids: list[str] = []
        with self._lock:
            rows = self._read(INSTANCES_FILE)
            changed = False
            for index, item in enumerate(rows):
                if item.get("status") != "active" or not item.get("next_run_at"):
                    continue
                try:
                    if datetime.fromisoformat(item["next_run_at"]) > now:
                        continue
                except ValueError:
                    continue
                due_ids.append(item["id"])
                item["next_run_at"] = self._next_run(item.get("schedule") or {"type": "manual"}, after_run=True)
                item["updated_at"] = _now()
                rows[index] = item
                changed = True
            if changed:
                atomic_write(INSTANCES_FILE, rows)
        for instance_id in due_ids:
            try:
                await self.run_instance(instance_id, trigger="scheduled")
            except ValueError:
                continue

    def start_scheduler(self) -> None:
        if self._scheduler_task and not self._scheduler_task.done(): return
        self._stopping = False; self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def stop_scheduler(self) -> None:
        self._stopping = True
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            try: await self._scheduler_task
            except asyncio.CancelledError: pass

    async def _scheduler_loop(self) -> None:
        while not self._stopping:
            try: await self.process_due()
            except Exception: logger.exception("Workflow scheduler iteration failed")
            await asyncio.sleep(30)


_SERVICE: WorkflowService | None = None


def get_workflow_service() -> WorkflowService:
    global _SERVICE
    if _SERVICE is None: _SERVICE = WorkflowService()
    return _SERVICE
