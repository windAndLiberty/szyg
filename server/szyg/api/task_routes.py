"""Task Board API — 任务看板后端
面向老板视角，展示 AI 员工任务执行状态（进行中/已完成/失败）。
对接 scheduler_engine.py，提供任务列表、详情、重试、取消接口。
"""
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from typing import Optional

from szyg.scheduler_engine import (
    get_scheduler, ScheduleJob, JobExecution,
    JobStatus, JobAction,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# ── Action → Task Type mapping ──────────────────────────────────
ACTION_TYPE_MAP: dict[str, dict[str, str]] = {
    "publish_content":       {"type": "publish", "label": "发布内容", "icon": "📹"},
    "generate_content":      {"type": "generate", "label": "AI生成", "icon": "🤖"},
    "run_workflow":          {"type": "workflow", "label": "工作流", "icon": "🔄"},
    "send_notification":     {"type": "notify", "label": "发送通知", "icon": "📢"},
    "execute_tool":          {"type": "tool", "label": "执行工具", "icon": "🔧"},
    "platform_login_check":  {"type": "check", "label": "登录检查", "icon": "🔐"},
    "platform_health_check": {"type": "health", "label": "健康检查", "icon": "💚"},
    "custom":                {"type": "custom", "label": "自定义", "icon": "⚙️"},
}

# Action-specific progress labels for running tasks
ACTION_PROGRESS_LABELS: dict[str, str] = {
    "publish_content":       "正在发布中...",
    "generate_content":      "AI 生成中...",
    "run_workflow":          "工作流执行中...",
    "send_notification":     "发送中...",
    "execute_tool":          "工具执行中...",
    "platform_login_check":  "检查中...",
    "platform_health_check": "巡检中...",
    "custom":                "执行中...",
}


def _job_status_to_board(job: ScheduleJob) -> str:
    """Map internal JobStatus to task board status."""
    status = job.status.value if hasattr(job.status, 'value') else job.status
    if status in ("active", "paused", "disabled"):
        return "pending"
    if status == "running":
        return "running"
    if status == "completed":
        return "completed"
    if status == "failed":
        return "failed"
    return "pending"


def _format_task(job: ScheduleJob, execution: Optional[JobExecution] = None) -> dict:
    """Transform a ScheduleJob into the task board response format."""
    action_key = job.action.value if hasattr(job.action, 'value') else str(job.action)
    type_info = ACTION_TYPE_MAP.get(action_key, ACTION_TYPE_MAP["custom"])
    board_status = _job_status_to_board(job)

    # Extract platform from action_config
    platform = job.action_config.get("platform", "") or job.action_config.get("tool", "") or "多平台"

    task: dict = {
        "id": job.id,
        "name": job.name,
        "description": job.description,
        "type": type_info["type"],
        "type_label": type_info["label"],
        "type_icon": type_info["icon"],
        "platform": platform,
        "status": board_status,
        "priority": job.priority,
        "tags": job.tags,
        "created_at": job.created_at,
        "started_at": job.last_run_at or job.created_at,
        "progress": "",
        "result": "",
        "error": "",
        "finished_at": "",
    }

    if execution:
        task["progress"] = execution.result or ACTION_PROGRESS_LABELS.get(action_key, "执行中...")
        task["finished_at"] = execution.finished_at
        if execution.status == "success":
            task["result"] = execution.result
        elif execution.status == "failed":
            task["error"] = execution.error
        elif execution.status == "running":
            task["progress"] = execution.result or ACTION_PROGRESS_LABELS.get(action_key, "执行中...")

    return task


def _get_latest_execution(job_id: str) -> Optional[JobExecution]:
    """Get the most recent execution for a job from history."""
    history = get_scheduler().get_history(job_id=job_id, limit=1)
    return history[0] if history else None


# ── Routes ──────────────────────────────────────────────────────


def _format_sau_task(task: dict) -> dict:
    status = task.get("status", "queued")
    board_status = {
        "queued": "running",
        "running": "running",
        "success": "completed",
        "failed": "failed",
    }.get(status, "running")
    return {
        "id": f"sau_{task.get('id', '')}",
        "name": task.get("title") or "social-auto-upload publish",
        "description": f"{task.get('platform', '')} {task.get('kind', '')}".strip(),
        "type": "publish",
        "type_label": "发布内容",
        "type_icon": "video",
        "platform": task.get("platform", ""),
        "status": board_status,
        "priority": 8,
        "tags": ["social-auto-upload"],
        "created_at": task.get("created_at", ""),
        "started_at": task.get("started_at") or task.get("created_at", ""),
        "progress": task.get("progress", ""),
        "result": task.get("result", {}).get("message", "") if status == "success" else "",
        "error": task.get("error", "") if status == "failed" else "",
        "finished_at": task.get("finished_at", ""),
    }


def _get_sau_task(task_id: str) -> dict | None:
    raw_id = task_id.removeprefix("sau_")
    try:
        from szyg.integrations.sau_task_manager import get_sau_task_manager
        return get_sau_task_manager().get_task(raw_id)
    except Exception:
        return None


def _execution_board_status(status: str) -> str:
    if status == "needs_human":
        return "needs_human"
    if status in ("queued", "running", "paused"):
        return "running"
    if status == "success":
        return "completed"
    if status in ("failed", "cancelled"):
        return "failed"
    return "running"


def _format_execution_task(run: dict) -> dict:
    status = run.get("status", "queued")
    board_status = _execution_board_status(status)
    error = run.get("error_message", "")
    if run.get("error_code"):
        error = f"{run.get('error_code')}: {error}".strip(": ")
    return {
        "id": run.get("id", ""),
        "name": run.get("title") or f"{run.get('platform', '')} {run.get('task_type', '')}".strip() or "ExecutionRun",
        "description": f"{run.get('executor_type', '')} · {run.get('task_type', '')}".strip(" ·"),
        "type": "publish" if run.get("task_type") == "publish_video" else "workflow",
        "type_label": "自动化执行",
        "type_icon": "⚙️",
        "platform": run.get("platform", ""),
        "status": board_status,
        "priority": 9,
        "tags": ["execution-kernel", run.get("executor_type", "")],
        "created_at": run.get("created_at", ""),
        "started_at": run.get("started_at") or run.get("created_at", ""),
        "progress": "需人工处理" if status == "needs_human" else run.get("current_step_id") or status,
        "result": run.get("result", {}).get("message", "") if status == "success" else "",
        "error": error if board_status == "failed" or status == "needs_human" else "",
        "finished_at": run.get("finished_at", ""),
    }


def _get_execution_task(task_id: str) -> dict | None:
    if not task_id.startswith("exec_"):
        return None
    try:
        from szyg.execution_kernel import get_execution_kernel
        return get_execution_kernel().get_run(task_id)
    except Exception:
        return None


@router.get("")
async def list_tasks(
    status: str = Query("all", description="Filter: all | running | needs_human | completed | failed"),
    search: str = Query("", description="Search in task name/description"),
    limit: int = Query(100, ge=1, le=500),
):
    """List tasks for the task board with status filter.

    Status mapping:
      - all       → no filter
      - running   → running + active + paused (进行中)
      - needs_human → needs_human (需人工)
      - completed   → completed (已完成)
      - failed      → failed (失败)
    """
    scheduler = get_scheduler()
    history = scheduler.get_history(limit=500)

    if status == "all":
        jobs = scheduler.list_jobs(status="", search=search, limit=limit)
    elif status == "running":
        # 进行中: running + active + paused
        all_jobs = scheduler.list_jobs(status="", search=search, limit=limit)
        jobs = [j for j in all_jobs if j.status.value in ("running", "active", "paused")]
    elif status == "completed":
        jobs = scheduler.list_jobs(status="completed", search=search, limit=limit)
    elif status == "failed":
        jobs = scheduler.list_jobs(status="failed", search=search, limit=limit)
    else:
        jobs = scheduler.list_jobs(status="", search=search, limit=limit)

    # Build history lookup: job_id → latest execution
    exec_map: dict[str, JobExecution] = {}
    for h in history:
        if h.job_id not in exec_map:
            exec_map[h.job_id] = h

    tasks = []
    try:
        from szyg.execution_kernel import get_execution_kernel
        execution_runs = get_execution_kernel().list_runs(limit=limit)
        if search:
            q = search.lower()
            execution_runs = [
                item for item in execution_runs
                if q in item.get("title", "").lower()
                or q in item.get("task_type", "").lower()
                or q in item.get("platform", "").lower()
            ]
        if status != "all":
            execution_runs = [
                item for item in execution_runs
                if _execution_board_status(item.get("status", "")) == status
            ]
        tasks.extend(_format_execution_task(item) for item in execution_runs)
    except Exception:
        pass

    tasks.extend(_format_task(j, exec_map.get(j.id)) for j in jobs)
    try:
        from szyg.integrations.sau_task_manager import get_sau_task_manager
        sau_tasks = [_format_sau_task(item) for item in get_sau_task_manager().list_tasks(limit=limit)]
        if search:
            q = search.lower()
            sau_tasks = [
                item for item in sau_tasks
                if q in item.get("name", "").lower() or q in item.get("description", "").lower()
            ]
        if status != "all":
            sau_tasks = [item for item in sau_tasks if item.get("status") == status]
        tasks.extend(sau_tasks)
    except Exception:
        pass

    # Sort: priority desc, then created_at desc
    tasks.sort(key=lambda t: (t["priority"], t["created_at"]), reverse=True)
    tasks = tasks[:limit]

    # Compute counts for each status bucket
    all_jobs = scheduler.list_jobs(status="", limit=500)
    counts = {
        "all": len(all_jobs),
        "running": sum(1 for j in all_jobs if j.status.value in ("running", "active", "paused")),
        "needs_human": 0,
        "completed": sum(1 for j in all_jobs if j.status.value == "completed"),
        "failed": sum(1 for j in all_jobs if j.status.value == "failed"),
    }
    try:
        from szyg.execution_kernel import get_execution_kernel
        for run in get_execution_kernel().list_runs(limit=500):
            counts["all"] += 1
            board_status = _execution_board_status(run.get("status", ""))
            if board_status in counts:
                counts[board_status] += 1
    except Exception:
        pass
    try:
        from szyg.integrations.sau_task_manager import get_sau_task_manager
        for item in get_sau_task_manager().list_tasks(limit=500):
            formatted = _format_sau_task(item)
            counts["all"] += 1
            if formatted["status"] in counts:
                counts[formatted["status"]] += 1
    except Exception:
        pass

    return {"tasks": tasks, "counts": counts}


@router.get("/{task_id}")
async def get_task_detail(task_id: str):
    """Get task detail including job info, execution history, and logs."""
    execution_run = _get_execution_task(task_id)
    if execution_run:
        from szyg.execution_kernel import get_execution_kernel
        kernel = get_execution_kernel()
        task = _format_execution_task(execution_run)
        steps = kernel.list_steps(task_id)
        audit = kernel.list_audit(task_id)
        observations = kernel.list_observations(task_id)
        task["executions"] = [{
            "id": step.get("id", ""),
            "job_id": task_id,
            "job_name": task["name"],
            "status": step.get("status", ""),
            "started_at": step.get("started_at", ""),
            "finished_at": step.get("finished_at", ""),
            "duration_ms": step.get("duration_ms", 0),
            "retry_count": max(0, int(step.get("attempt", 1)) - 1),
            "result": step.get("name", ""),
            "error": step.get("error_message", ""),
            "step_id": step.get("step_id", ""),
            "error_code": step.get("error_code", ""),
        } for step in steps]
        task["logs"] = [{
            "id": item.get("id", ""),
            "type": "audit",
            "message": item.get("message", ""),
            "timestamp": item.get("created_at", ""),
            "status": "error" if item.get("status") in ("failed", "needs_human") else "success" if item.get("status") == "success" else "info",
            "duration_ms": item.get("duration_ms", 0),
            "action": item.get("action", ""),
            "error_code": item.get("error_code", ""),
            "artifact_path": item.get("artifact_path", ""),
        } for item in audit]
        task["action"] = execution_run.get("task_type", "")
        task["action_config"] = execution_run.get("input", {})
        task["trigger_type"] = "execution"
        task["trigger_config"] = {"executor_type": execution_run.get("executor_type", "")}
        task["execution_run"] = execution_run
        task["steps"] = steps
        task["audit"] = audit
        task["observations"] = observations
        task["debug_screenshot"] = next((event.get("artifact_path") for event in reversed(audit) if event.get("artifact_path")), "")
        return task

    sau_task = _get_sau_task(task_id)
    if sau_task:
        task = _format_sau_task(sau_task)
        task["executions"] = [{
            "id": sau_task.get("id", ""),
            "job_id": task["id"],
            "job_name": task["name"],
            "status": sau_task.get("status", ""),
            "started_at": sau_task.get("started_at", ""),
            "finished_at": sau_task.get("finished_at", ""),
            "duration_ms": sau_task.get("duration_ms", 0),
            "retry_count": 0,
            "result": sau_task.get("result", {}).get("message", ""),
            "error": sau_task.get("error", ""),
        }]
        task["logs"] = [{
            "id": sau_task.get("id", ""),
            "type": "log",
            "message": sau_task.get("error") or sau_task.get("progress", ""),
            "timestamp": sau_task.get("updated_at", ""),
            "status": "error" if sau_task.get("status") == "failed" else "success" if sau_task.get("status") == "success" else "info",
            "duration_ms": sau_task.get("duration_ms", 0),
        }]
        task["action"] = "publish_content"
        task["action_config"] = sau_task.get("payload", {})
        task["trigger_type"] = "manual"
        task["trigger_config"] = {}
        task["debug_screenshot"] = sau_task.get("debug_screenshot", "")
        return task

    scheduler = get_scheduler()
    job = scheduler.get_job(task_id)
    if not job:
        raise HTTPException(404, "任务不存在")

    # Build history with logs
    executions = scheduler.get_history(job_id=task_id, limit=50)

    # Build subtask-like log entries from executions
    logs: list[dict] = []
    for ex in executions:
        log_entry: dict = {
            "id": ex.id,
            "type": "log",
            "message": ex.result or ex.error or f"执行状态: {ex.status}",
            "timestamp": ex.started_at,
            "status": "success" if ex.status == "success" else ("error" if ex.status == "failed" else "info"),
            "duration_ms": ex.duration_ms,
        }
        logs.append(log_entry)

    latest = executions[0] if executions else None
    task = _format_task(job, latest)

    # Add extra detail fields
    task["executions"] = [e.model_dump() for e in executions[:20]]
    task["logs"] = logs[:50]
    task["action"] = job.action.value if hasattr(job.action, 'value') else str(job.action)
    task["action_config"] = job.action_config
    task["trigger_type"] = job.trigger_type.value if hasattr(job.trigger_type, 'value') else str(job.trigger_type)
    task["trigger_config"] = job.trigger_config

    return task


@router.post("/{task_id}/retry")
async def retry_task(task_id: str):
    """Retry a failed task — reset status and re-execute."""
    if task_id.startswith("exec_"):
        from szyg.execution_kernel import get_execution_kernel
        try:
            run = get_execution_kernel().retry_run(task_id)
            return {"ok": True, "task_id": task_id, "execution_id": run.get("id", "")}
        except KeyError:
            raise HTTPException(404, "任务不存在")
        except ValueError as e:
            raise HTTPException(400, str(e))

    scheduler = get_scheduler()
    job = scheduler.get_job(task_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    if job.status.value not in ("failed", "paused"):
        raise HTTPException(400, "只能重试失败或暂停的任务")

    try:
        execution = scheduler.retry_job(task_id)
        return {"ok": True, "task_id": task_id, "execution_id": execution.id if execution else ""}
    except Exception as e:
        raise HTTPException(500, f"重试失败: {str(e)}")


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running/pending task."""
    if task_id.startswith("exec_"):
        from szyg.execution_kernel import get_execution_kernel
        try:
            get_execution_kernel().cancel_run(task_id)
            return {"ok": True, "task_id": task_id}
        except KeyError:
            raise HTTPException(404, "任务不存在")

    scheduler = get_scheduler()
    job = scheduler.get_job(task_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    if job.status.value not in ("running", "active", "paused"):
        raise HTTPException(400, "只能取消进行中的任务")

    scheduler.cancel_job(task_id)
    return {"ok": True, "task_id": task_id}
