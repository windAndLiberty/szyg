from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta

import pytest

import szyg.workflow_service as workflow_module


class FakeSkills:
    def __init__(self):
        self.executed: list[str] = []
        self.capabilities = [
            {
                "skill_name": "account-health",
                "action_id": "accounts.health_check",
                "name": "检查渠道账号",
                "description": "检查账号",
                "risk_level": "low",
                "execution_mode": "builtin",
                "input_schema": {},
                "output_schema": {"online": "number"},
            },
            {
                "skill_name": "report-compose",
                "action_id": "report.compose",
                "name": "生成报告",
                "description": "生成报告",
                "risk_level": "low",
                "execution_mode": "builtin",
                "input_schema": {},
                "output_schema": {"title": "string"},
            },
            {
                "skill_name": "lead-summary",
                "action_id": "leads.summarize",
                "name": "整理线索",
                "description": "整理线索",
                "risk_level": "low",
                "execution_mode": "builtin",
                "input_schema": {},
                "output_schema": {"total": "number"},
            },
            {
                "skill_name": "publish-summary",
                "action_id": "publishing.summarize",
                "name": "汇总发布内容",
                "description": "汇总发布内容",
                "risk_level": "low",
                "execution_mode": "builtin",
                "input_schema": {},
                "output_schema": {"total": "number"},
            },
            {
                "skill_name": "knowledge-search",
                "action_id": "knowledge.search",
                "name": "检索企业资料",
                "description": "检索企业资料",
                "risk_level": "low",
                "execution_mode": "builtin",
                "input_schema": {},
                "output_schema": {"items": "array"},
            },
            {
                "skill_name": "external-send",
                "action_id": "outbound.send",
                "name": "发送外部消息",
                "description": "发送外部消息",
                "risk_level": "high",
                "execution_mode": "builtin",
                "input_schema": {},
                "output_schema": {"sent": "boolean"},
            },
            {
                "skill_name": "manual",
                "action_id": "human.complete_task",
                "name": "人工完成任务",
                "description": "人工完成任务",
                "risk_level": "medium",
                "execution_mode": "manual",
                "input_schema": {},
                "output_schema": {},
            },
        ]

    def list_capabilities(self):
        return deepcopy(self.capabilities)

    def get(self, action_id):
        return next((deepcopy(item) for item in self.capabilities if item["action_id"] == action_id), None)

    async def execute(self, action_id, params, context):
        self.executed.append(action_id)
        if action_id == "accounts.health_check":
            return {"total": 2, "online": 2, "needs_human": 0}
        if action_id == "report.compose":
            return {"title": params.get("title", "报告"), "summary": deepcopy(context["outputs"])}
        if action_id == "outbound.send":
            return {"sent": True, "message": "已发送"}
        return {"total": 0}


class FakeKernel:
    def __init__(self):
        self.runs = []
        self.steps = []
        self.audit = []
        self.runners = {}

    def register_task_runner(self, task_type, runner):
        self.runners[task_type] = runner

    def create_run(self, task_type, platform, executor_type, input_data, **kwargs):
        run = {
            "id": f"exec_{len(self.runs) + 1}", "task_type": task_type,
            "title": kwargs.get("title", ""), "status": "queued",
            "input": deepcopy(input_data), "result": {},
            "created_at": "2026-07-18T09:00:00+08:00", "started_at": "",
            "finished_at": "", "duration_ms": 0, "error_code": "", "error_message": "",
        }
        self.runs.append(run)
        return deepcopy(run)

    def start_run(self, run_id):
        return deepcopy(self._patch_run(run_id, status="queued", error_code="", error_message=""))

    def _patch_run(self, run_id, **updates):
        run = self.get_run(run_id)
        run.update(updates)
        return run

    def _ensure_active(self, run_id):
        run = self.get_run(run_id)
        if run["status"] in {"paused", "cancelled"}:
            raise RuntimeError("inactive")
        return run

    def start_step(self, run_id, step_id, name, executor_type, action):
        step = {"id": f"step_{len(self.steps) + 1}", "run_id": run_id, "step_id": step_id, "status": "running"}
        self.steps.append(step)
        self._patch_run(run_id, status="running", current_step_id=step_id)
        return step

    def finish_step(self, step, status, message, error_code=""):
        step.update(status=status, message=message, error_code=error_code)
        return deepcopy(step)

    def complete_run(self, run_id, status, result=None, error_code="", error_message=""):
        run = self.get_run(run_id)
        run.update(status=status, result=deepcopy(result or {}), error_code=error_code, error_message=error_message)
        if status in {"success", "failed", "cancelled", "needs_human"}:
            run["finished_at"] = "2026-07-18T09:00:02+08:00"
            run["duration_ms"] = 1000
        return deepcopy(run)

    def add_audit(self, run_id, step_id, action, status, message):
        self.audit.append({"run_id": run_id, "step_id": step_id, "action": action, "status": status, "message": message})

    def cancel_run(self, run_id, reason=""):
        return self.complete_run(run_id, "cancelled", error_code="cancelled", error_message=reason)

    def get_run(self, run_id):
        return next((run for run in self.runs if run["id"] == run_id), None)

    def list_runs(self, limit=100, task_type="", **_kwargs):
        rows = [run for run in self.runs if not task_type or run["task_type"] == task_type]
        return list(reversed(rows))[:limit]


@pytest.fixture
def service(tmp_path, monkeypatch):
    for name in ("INSTANCES_FILE", "SOPS_FILE", "DRAFTS_FILE", "DEFINITIONS_FILE", "LEARNING_EVENTS_FILE"):
        monkeypatch.setattr(workflow_module, name, tmp_path / f"{name.lower()}.json")
    kernel = FakeKernel()
    skills = FakeSkills()
    monkeypatch.setattr(workflow_module, "get_execution_kernel", lambda: kernel)
    monkeypatch.setattr(workflow_module, "get_workflow_skills", lambda: skills)
    return workflow_module.WorkflowService(), kernel, skills


def test_templates_are_job_oriented_and_content_publish_is_not_faked(service):
    workflow, _kernel, _skills = service
    templates = workflow.list_templates()
    assert {item["id"] for item in templates} == {
        "content_scheduled_publish", "account_health_check",
        "customer_followup_reminder", "lead_daily_digest",
    }
    assert workflow.get_template("content_scheduled_publish")["available"] is False
    assert all("model" not in item for item in templates)


def test_instance_lifecycle_and_schedule(service):
    workflow, _kernel, _skills = service
    created = workflow.create_instance({
        "template_id": "account_health_check", "name": "每天巡检",
        "schedule": {"type": "daily", "time": "09:00"},
    })
    assert created["status"] == "active"
    assert created["next_run_at"]
    paused = workflow.update_instance(created["id"], {"status": "paused"})
    assert paused["next_run_at"] == ""
    assert workflow.delete_instance(created["id"]) is True


def test_unavailable_template_cannot_be_enabled(service):
    workflow, _kernel, _skills = service
    with pytest.raises(ValueError, match="暂不可启用"):
        workflow.create_instance({"template_id": "content_scheduled_publish", "name": "自动发布"})


@pytest.mark.asyncio
async def test_run_is_registered_and_executes_through_kernel_runner(service):
    workflow, kernel, skills = service
    created = workflow.create_instance({
        "template_id": "account_health_check", "name": "账号巡检", "schedule": {"type": "manual"},
    })
    queued = await workflow.run_instance(created["id"])
    assert queued["status"] == "queued"
    assert kernel.runners["workflow"] == workflow.execute_run

    finished = await workflow.execute_run(queued["id"])
    assert finished["status"] == "success"
    assert skills.executed == ["accounts.health_check", "report.compose"]
    assert workflow.list_instances()[0]["last_run"]["id"] == queued["id"]


def test_draft_versions_validate_and_activate(service):
    workflow, _kernel, _skills = service
    draft = workflow.create_draft({"goal": "每天检查渠道账号"})
    assert draft["context"]["knowledge"] is True
    assert draft["context"]["accounts"] is False
    updated = workflow.update_draft(draft["id"], {
        "name": "每日账号巡检", "description": "检查登录状态", "outcome": "获得清单",
        "steps": [{
            "id": "check", "name": "检查账号", "description": "检查状态",
            "skill_name": "account-health", "action_id": "accounts.health_check", "params": {},
            "condition": None, "risk_level": "low", "confirmation_policy": "automatic",
        }],
    })
    assert updated["version"] == 2
    assert len(updated["versions"]) == 1
    assert workflow.validate_draft(draft["id"])["valid"] is True
    instance = workflow.activate_draft(draft["id"])
    assert instance["definition_id"]
    assert workflow.get_draft(draft["id"])["status"] == "active"
    edited_definition = workflow.update_sop(instance["definition_id"], {"description": "更新后的企业流程"})
    assert edited_definition["version"] == instance["definition_version"] + 1


def test_condition_must_reference_a_previous_step(service):
    workflow, _kernel, _skills = service
    draft = workflow.create_draft({"goal": "条件任务"})
    workflow.update_draft(draft["id"], {
        "name": "条件任务", "steps": [{
            "id": "report", "name": "生成报告", "action_id": "report.compose", "params": {},
            "condition": {"step_id": "future", "field": "total", "operator": "gt", "value": 0},
            "risk_level": "low",
        }],
    })
    result = workflow.validate_draft(draft["id"])
    assert result["valid"] is False
    assert any("前序步骤" in issue for issue in result["issues"])


@pytest.mark.asyncio
async def test_false_condition_is_skipped_not_failed(service):
    workflow, kernel, skills = service
    instance = workflow._create_instance_record({
        "name": "条件执行", "schedule": {"type": "manual"},
        "steps": [
            {"id": "check", "name": "检查", "action_id": "accounts.health_check", "params": {}, "risk_level": "low"},
            {"id": "report", "name": "报告", "action_id": "report.compose", "params": {}, "risk_level": "low",
             "condition": {"step_id": "check", "field": "online", "operator": "gt", "value": 10}},
        ],
    })
    queued = await workflow.run_instance(instance["id"])
    finished = await workflow.execute_run(queued["id"])
    assert finished["status"] == "success"
    assert [step["status"] for step in kernel.steps] == ["success", "skipped"]
    assert skills.executed == ["accounts.health_check"]


@pytest.mark.asyncio
async def test_high_risk_step_waits_for_confirmation_then_continues(service):
    workflow, kernel, _skills = service
    instance = workflow._create_instance_record({
        "name": "外部发送", "schedule": {"type": "manual"},
        "steps": [{"id": "send", "name": "发送消息", "action_id": "outbound.send", "params": {}, "risk_level": "high"}],
    })
    queued = await workflow.run_instance(instance["id"])
    waiting = await workflow.execute_run(queued["id"])
    assert waiting["status"] == "needs_human"
    assert waiting["result"]["pending_step"]["id"] == "send"

    resumed = workflow.confirm_run(queued["id"])
    assert resumed["status"] == "queued"
    finished = await workflow.execute_run(queued["id"])
    assert finished["status"] == "success"
    assert finished["result"]["step_outputs"]["send"]["sent"] is True
    assert any(item["action"] == "confirm" for item in kernel.audit)


def test_builtin_sop_can_be_cloned_without_changing_source(service):
    workflow, _kernel, _skills = service
    builtin = workflow.list_sops()[0]
    cloned = workflow.clone_sop(builtin["id"])
    assert cloned["source"] == "custom"
    assert cloned["id"] != builtin["id"]


def test_instance_keeps_definition_snapshot_until_explicit_upgrade(service):
    workflow, _kernel, _skills = service
    cloned = workflow.clone_sop("sop_account_health_check")
    instance = workflow.create_instance({"definition_id": cloned["id"], "name": "企业巡检"})
    original_steps = deepcopy(instance["steps"])

    updated = workflow.update_sop(cloned["id"], {
        "steps": [*cloned["steps"], {
            "id": "extra_report", "name": "补充报告", "description": "补充说明",
            "action_id": "report.compose", "params": {}, "risk_level": "low",
        }],
    })

    before_upgrade = workflow.list_instances()[0]
    assert before_upgrade["steps"] == original_steps
    assert before_upgrade["upgrade_available"] is True
    assert before_upgrade["definition_version"] == 1

    upgraded = workflow.upgrade_instance(instance["id"])
    assert upgraded["definition_version"] == updated["version"]
    assert len(upgraded["steps"]) == len(original_steps) + 1
    with pytest.raises(ValueError, match="仍被工作流方案使用"):
        workflow.delete_sop(cloned["id"])
    assert workflow.delete_instance(instance["id"]) is True
    assert workflow.delete_sop(cloned["id"]) is True


def test_supported_schedules_calculate_next_run(service):
    workflow, _kernel, _skills = service
    schedules = [
        {"type": "daily", "time": "09:00"},
        {"type": "weekly", "time": "09:00", "weekdays": [1, 5]},
        {"type": "interval", "interval_minutes": 15},
        {"type": "once", "at": (datetime.now().astimezone() + timedelta(hours=1)).isoformat()},
    ]
    for index, schedule in enumerate(schedules):
        created = workflow.create_instance({
            "template_id": "account_health_check", "name": f"计划{index}", "schedule": schedule,
        })
        assert created["next_run_at"]


@pytest.mark.asyncio
async def test_due_instance_is_claimed_only_once(service):
    workflow, kernel, _skills = service
    instance = workflow.create_instance({
        "template_id": "account_health_check", "name": "到期巡检",
        "schedule": {"type": "interval", "interval_minutes": 5},
    })
    instance["next_run_at"] = (datetime.now().astimezone() - timedelta(minutes=1)).isoformat()
    workflow._replace(workflow_module.INSTANCES_FILE, instance["id"], instance)

    await workflow.process_due()
    await workflow.process_due()

    assert len(kernel.runs) == 1
    assert kernel.runs[0]["input"]["trigger"] == "scheduled"
    assert workflow.get_instance(instance["id"])["next_run_at"]


def test_legacy_scheduler_data_is_archived_without_migration(tmp_path, monkeypatch, service):
    workflow, _kernel, _skills = service
    jobs = tmp_path / "scheduler_jobs.json"
    history = tmp_path / "scheduler_history.json"
    jobs.write_text('[{"id":"demo_1"}]', encoding="utf-8")
    history.write_text('[{"id":"history_1"}]', encoding="utf-8")
    archive_root = tmp_path / "archive"
    monkeypatch.setattr(workflow_module, "LEGACY_SCHEDULER_FILES", (jobs, history))
    monkeypatch.setattr(workflow_module, "LEGACY_SCHEDULER_ARCHIVE_DIR", archive_root)

    archived = workflow.archive_legacy_scheduler_data()

    assert archived
    assert not jobs.exists()
    assert not history.exists()
    archive_dir = workflow_module.Path(archived)
    assert (archive_dir / "scheduler_jobs.json").exists()
    assert (archive_dir / "scheduler_history.json").exists()
    assert workflow.list_instances() == []


def test_planner_shape_normalizes_numeric_ids_and_empty_conditions():
    normalized = workflow_module._normalize_planner_shape({
        "name": "账号巡检",
        "description": "检查账号并生成报告",
        "outcome": "获得内部报告",
        "steps": [
            {"id": 1, "name": "检查", "action_id": "accounts.health_check", "params": None, "condition": ""},
            {"id": 2, "name": "报告", "action_id": "report.compose", "params": {}, "condition": {"step_id": 1, "field": "online", "operator": "gt", "value": 0}},
        ],
    })

    validated = workflow_module.DraftPlanModel.model_validate(normalized)
    assert validated.steps[0].id == "1"
    assert validated.steps[0].condition is None
    assert validated.steps[0].params == {}
    assert validated.steps[1].condition is not None
    assert validated.steps[1].condition.step_id == "1"
