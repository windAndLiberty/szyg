"""Hermes-backed capability catalog for user-designed workflows.

Workflow capabilities are described by metadata in Hermes ``SKILL.md`` files.
This module does not maintain a second executable skill registry: it discovers
the installed Hermes skills and dispatches their declared workflow actions to
existing SZYG services.
"""

from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

CORE_SKILLS: list[dict[str, Any]] = [
    {
        "name": "szyg-account-health",
        "action_id": "accounts.health_check",
        "label": "检查渠道账号",
        "description": "读取渠道账号状态并整理需要处理的账号。",
        "risk_level": "low",
        "business_objects": ["accounts"],
        "input_schema": {},
        "output_schema": {"total": "number", "online": "number", "needs_human": "number"},
        "execution_mode": "builtin",
    },
    {
        "name": "szyg-knowledge-search",
        "action_id": "knowledge.search",
        "label": "检索企业资料",
        "description": "从企业知识库检索与任务目标相关的资料。",
        "risk_level": "low",
        "business_objects": ["knowledge"],
        "input_schema": {"query": "string", "limit": "number"},
        "output_schema": {"items": "array", "total": "number"},
        "execution_mode": "builtin",
    },
    {
        "name": "szyg-lead-summary",
        "action_id": "leads.summarize",
        "label": "整理客户线索",
        "description": "汇总线索来源、意向等级和待跟进客户。",
        "risk_level": "low",
        "business_objects": ["leads", "customers"],
        "input_schema": {"minimum_score": "number"},
        "output_schema": {"total": "number", "pending": "number", "high_intent": "number"},
        "execution_mode": "builtin",
    },
    {
        "name": "szyg-published-content-summary",
        "action_id": "publishing.summarize",
        "label": "汇总发布内容",
        "description": "读取已成功发布的内容并形成简洁摘要。",
        "risk_level": "low",
        "business_objects": ["publish_records", "content"],
        "input_schema": {"limit": "number"},
        "output_schema": {"items": "array", "total": "number"},
        "execution_mode": "builtin",
    },
    {
        "name": "szyg-report-compose",
        "action_id": "report.compose",
        "label": "生成工作报告",
        "description": "把前序步骤结果整理为可阅读的工作报告。",
        "risk_level": "low",
        "business_objects": ["report"],
        "input_schema": {"title": "string"},
        "output_schema": {"title": "string", "summary": "object"},
        "execution_mode": "builtin",
    },
    {
        "name": "szyg-private-domain-review",
        "action_id": "private_domain.review_queue",
        "label": "梳理私域待跟进客户",
        "description": "读取私域营销队列，整理高意向客户和建议跟进动作。",
        "risk_level": "low",
        "business_objects": ["leads", "customers", "private_domain"],
        "input_schema": {"limit": "number"},
        "output_schema": {"items": "array", "total": "number"},
        "execution_mode": "builtin",
    },
    {
        "name": "szyg-intelligence-query",
        "action_id": "intelligence.query",
        "label": "发现市场情报",
        "description": "结合企业资料、知识库和发布记录发现有营销价值的外部情报。",
        "risk_level": "low",
        "business_objects": ["intelligence", "knowledge", "publish_records"],
        "input_schema": {"query": "string", "use_enterprise_context": "boolean", "include_publish_records": "boolean"},
        "output_schema": {"report": "object"},
        "execution_mode": "builtin",
    },
    {
        "name": "szyg-global-insights",
        "action_id": "insights.review",
        "label": "生成全局数据洞察",
        "description": "综合内部经营记录、知识库和市场情报生成可执行洞察。",
        "risk_level": "low",
        "business_objects": ["insights", "knowledge", "intelligence"],
        "input_schema": {"days": "number"},
        "output_schema": {"overview": "object"},
        "execution_mode": "builtin",
    },
    {
        "name": "szyg-material-inventory",
        "action_id": "materials.inventory",
        "label": "盘点可用素材",
        "description": "读取素材管理中的图片、视频、音频和文案并按类型汇总。",
        "risk_level": "low",
        "business_objects": ["materials"],
        "input_schema": {"type": "string", "platform": "string"},
        "output_schema": {"items": "array", "total": "number", "by_type": "object"},
        "execution_mode": "builtin",
    },
    {
        "name": "szyg-publishing-accounts",
        "action_id": "publishing.accounts_review",
        "label": "检查发布账号与配置档案",
        "description": "读取真实渠道账号状态和常用发布配置档案。",
        "risk_level": "low",
        "business_objects": ["accounts", "publishing_profiles"],
        "input_schema": {"platform": "string"},
        "output_schema": {"accounts": "array", "profiles": "array"},
        "execution_mode": "builtin",
    },
    {
        "name": "szyg-execution-review",
        "action_id": "executions.review",
        "label": "复盘任务执行情况",
        "description": "汇总真实执行任务的状态、失败原因和需要人工处理的问题。",
        "risk_level": "low",
        "business_objects": ["executions", "audit"],
        "input_schema": {"limit": "number", "status": "string", "task_type": "string"},
        "output_schema": {"runs": "array", "summary": "object"},
        "execution_mode": "builtin",
    },
    {
        "name": "szyg-manual-action",
        "action_id": "human.complete_task",
        "label": "人工完成任务",
        "description": "当系统尚未掌握某项能力时，创建清晰的人工待办。",
        "risk_level": "medium",
        "business_objects": ["manual_task"],
        "input_schema": {"instruction": "string"},
        "output_schema": {"instruction": "string"},
        "execution_mode": "manual",
    },
]


RISK_ORDER = {"low": 1, "medium": 2, "high": 3}


def _skill_markdown(item: dict[str, Any]) -> str:
    metadata = {
        "name": item["name"],
        "description": item["description"],
        "metadata": {
            "szyg_workflow": {
                key: deepcopy(item[key])
                for key in (
                    "action_id", "label", "risk_level", "business_objects",
                    "input_schema", "output_schema", "execution_mode",
                )
            }
        },
    }
    return (
        "---\n"
        + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
        + "---\n\n"
        + f"# {item['label']}\n\n{item['description']}\n\n"
        + "仅在工作流明确选择本能力时使用。严格遵守输入契约、风险等级和人工确认要求。\n"
    )


def _parse_skill(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    match = re.match(r"^---\s*\n([\s\S]*?)\n---\s*\n", text)
    if not match:
        return None
    try:
        frontmatter = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return None
    workflow = ((frontmatter.get("metadata") or {}).get("szyg_workflow") or {})
    if not isinstance(workflow, dict) or not workflow.get("action_id"):
        return None
    risk = str(workflow.get("risk_level") or "medium").lower()
    if risk not in RISK_ORDER:
        risk = "medium"
    return {
        "skill_name": str(frontmatter.get("name") or path.parent.name),
        "action_id": str(workflow["action_id"]),
        "name": str(workflow.get("label") or frontmatter.get("name") or path.parent.name),
        "description": str(frontmatter.get("description") or ""),
        "risk_level": risk,
        "permissions": list(workflow.get("permissions") or []),
        "business_objects": list(workflow.get("business_objects") or []),
        "input_schema": workflow.get("input_schema") or {},
        "output_schema": workflow.get("output_schema") or {},
        "execution_mode": str(workflow.get("execution_mode") or "manual"),
        "auto_execute": risk in {"low", "medium"},
        "source_path": str(path),
    }


class HermesWorkflowSkills:
    def __init__(self) -> None:
        self.ensure_core_skills()

    @staticmethod
    def _skills_dir() -> Path:
        try:
            from hermes_constants import get_hermes_home

            return get_hermes_home() / "skills"
        except Exception:
            return Path.home() / ".hermes" / "skills"

    def ensure_core_skills(self) -> None:
        """Install bundled workflow skills into Hermes' single skill store."""
        root = self._skills_dir() / "szyg-workflow"
        root.mkdir(parents=True, exist_ok=True)
        for item in CORE_SKILLS:
            skill_dir = root / item["name"]
            skill_file = skill_dir / "SKILL.md"
            expected = _skill_markdown(item)
            if skill_file.exists() and _parse_skill(skill_file):
                continue
            skill_dir.mkdir(parents=True, exist_ok=True)
            tmp = skill_file.with_suffix(".md.tmp")
            tmp.write_text(expected, encoding="utf-8")
            tmp.replace(skill_file)

    def list_capabilities(self) -> list[dict[str, Any]]:
        self.ensure_core_skills()
        result: dict[str, dict[str, Any]] = {}
        try:
            from agent.skill_utils import get_all_skills_dirs

            roots = get_all_skills_dirs()
        except Exception:
            roots = [self._skills_dir()]
        for root in roots:
            if not root.exists():
                continue
            for skill_file in root.rglob("SKILL.md"):
                item = _parse_skill(skill_file)
                if item and item["action_id"] not in result:
                    result[item["action_id"]] = item
        return sorted(result.values(), key=lambda item: (RISK_ORDER[item["risk_level"]], item["name"]))

    def get(self, action_id: str) -> dict[str, Any] | None:
        return next((item for item in self.list_capabilities() if item["action_id"] == action_id), None)

    def learn_manual_capability(self, name: str, description: str, requested_action: str) -> dict[str, Any]:
        """Persist a safe Hermes skill for a missing capability.

        The learned procedure is intentionally manual until Hermes can bind it
        to a verified tool. This keeps the workflow usable without pretending
        an unverified external action succeeded.
        """
        slug = re.sub(r"[^a-z0-9]+", "-", requested_action.lower()).strip("-")[:42] or "new-capability"
        skill_name = f"szyg-learned-{slug}"
        item = {
            "name": skill_name,
            "action_id": f"learned.{slug}",
            "label": name[:80] or "新学习的任务",
            "description": description[:500] or "根据用户目标学习的工作方法。",
            "risk_level": "medium",
            "business_objects": ["manual_task"],
            "input_schema": {"instruction": "string"},
            "output_schema": {"instruction": "string"},
            "execution_mode": "manual",
        }
        path = self._skills_dir() / "szyg-workflow" / skill_name
        if path.exists():
            parsed = _parse_skill(path / "SKILL.md")
            return parsed or self.get(item["action_id"]) or {}

        try:
            from agent.curator_backup import snapshot_skills

            snapshot_skills(reason=f"workflow-auto-learn:{skill_name}")
        except Exception:
            pass

        content = _skill_markdown(item)
        try:
            from tools.skill_manager_tool import skill_manage

            created = skill_manage(action="create", name=skill_name, category="szyg-workflow", content=content)
            if not created.get("success"):
                raise ValueError(str(created.get("error") or "Skill creation failed"))
            from tools.skills_guard import scan_skill, should_allow_install

            scan = scan_skill(path, source="agent-created")
            allowed, reason = should_allow_install(scan)
            if allowed is not True:
                skill_manage(action="delete", name=skill_name, absorbed_into="")
                raise ValueError(f"Skill security scan blocked: {reason}")
        except Exception:
            if path.exists():
                import shutil

                shutil.rmtree(path, ignore_errors=True)
            raise
        return self.get(item["action_id"]) or {}

    async def execute(self, action_id: str, params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        capability = self.get(action_id)
        if not capability:
            raise KeyError(f"Unknown workflow capability: {action_id}")
        mode = capability.get("execution_mode")
        if mode == "manual":
            return {
                "_status": "needs_human",
                "instruction": str(params.get("instruction") or capability["description"]),
                "capability": capability["name"],
            }
        if action_id == "accounts.health_check":
            from szyg.channel_accounts import list_accounts

            accounts = list_accounts(include_defaults=False)
            online_states = {"online", "active", "logged_in", "connected"}
            problematic = [item for item in accounts if str(item.get("status", "")).lower() not in online_states]
            return {
                "total": len(accounts),
                "online": len(accounts) - len(problematic),
                "needs_human": len(problematic),
                "attention_accounts": [item.get("nickname") or item.get("label") or item.get("platform") for item in problematic[:20]],
            }
        if action_id == "knowledge.search":
            from szyg.mcp_servers.knowledge_mcp import kb_search

            items = kb_search(str(params.get("query") or context.get("goal") or ""), int(params.get("limit") or 5))
            return {"items": items, "total": len(items)}
        if action_id == "leads.summarize":
            from szyg.listen_engine import get_listen_engine

            leads = await get_listen_engine().list_leads(limit=500)
            minimum = int(params.get("minimum_score") or 70)
            grades = Counter(str(item.get("grade") or "未评级") for item in leads)
            platforms = Counter(str(item.get("platform") or "未知") for item in leads)
            pending = [item for item in leads if str(item.get("status", "new")).lower() not in {"followed", "converted", "invalid", "done"}]
            high = [item for item in pending if str(item.get("grade", "")).lower() in {"a", "s", "高", "high"} or int(item.get("lead_score") or item.get("intent_score") or 0) >= minimum]
            return {
                "total": len(leads), "pending": len(pending), "high_intent": len(high),
                "by_grade": dict(grades), "by_platform": dict(platforms),
                "priority_leads": [item.get("author_name") or item.get("user_name") or item.get("lead_id") for item in high[:20]],
            }
        if action_id == "publishing.summarize":
            from szyg.intelligence_pipeline import load_published_context

            items = load_published_context(limit=max(1, min(int(params.get("limit") or 20), 100)))
            return {"items": items, "total": len(items)}
        if action_id == "report.compose":
            return {
                "title": str(params.get("title") or "自动化工作报告"),
                "summary": deepcopy(context.get("outputs") or {}),
            }
        if action_id == "private_domain.review_queue":
            from szyg.api.private_domain_routes import private_domain_queue

            return await private_domain_queue(limit=max(1, min(int(params.get("limit") or 50), 200)))
        if action_id == "intelligence.query":
            from szyg.intelligence_pipeline import run_intelligence_query

            query = str(params.get("query") or context.get("goal") or "").strip()
            if not query:
                raise ValueError("市场情报任务缺少查询目标")
            report = await run_intelligence_query(
                query,
                use_enterprise_context=bool(params.get("use_enterprise_context", True)),
                include_publish_records=bool(params.get("include_publish_records", True)),
            )
            return {"report": report}
        if action_id == "insights.review":
            from szyg.insights_service import get_insights_service

            days = max(1, min(int(params.get("days") or 30), 365))
            return {"overview": get_insights_service().overview(days=days)}
        if action_id == "materials.inventory":
            from szyg.api.publisher_routes import list_materials

            result = await list_materials(
                mtype=str(params.get("type") or ""),
                platform=str(params.get("platform") or ""),
            )
            items = list(result.get("items") or [])
            return {
                "items": items,
                "total": len(items),
                "by_type": dict(Counter(str(item.get("type") or "other") for item in items)),
            }
        if action_id == "publishing.accounts_review":
            from szyg.channel_accounts import list_accounts, list_profiles

            accounts = list_accounts(platform=str(params.get("platform") or ""), include_defaults=True)
            return {"accounts": accounts, "profiles": list_profiles()}
        if action_id == "executions.review":
            from szyg.execution_kernel import get_execution_kernel

            runs = get_execution_kernel().list_runs(
                limit=max(1, min(int(params.get("limit") or 50), 200)),
                status=str(params.get("status") or ""),
                task_type=str(params.get("task_type") or ""),
            )
            return {
                "runs": runs,
                "summary": dict(Counter(str(item.get("status") or "unknown") for item in runs)),
            }
        raise ValueError(f"Capability has no verified executor: {action_id}")


_CATALOG: HermesWorkflowSkills | None = None


def get_workflow_skills() -> HermesWorkflowSkills:
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = HermesWorkflowSkills()
    return _CATALOG
