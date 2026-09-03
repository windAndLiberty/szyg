"""Task Board API — aggregate observable Execution Kernel tasks."""
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

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
    is_computer_use = run.get("task_type") == "computer_use"
    is_publish = str(run.get("task_type") or "").startswith("publish_")
    return {
        "id": run.get("id", ""),
        "name": run.get("title") or f"{run.get('platform', '')} {run.get('task_type', '')}".strip() or "ExecutionRun",
        "description": f"{run.get('executor_type', '')} · {run.get('task_type', '')}".strip(" ·"),
        "type": "tool" if is_computer_use else "publish" if is_publish else "workflow",
        "type_label": "网页代办" if is_computer_use else "内容发布" if is_publish else "自动化执行",
        "type_icon": "🖥️" if is_computer_use else "⚙️",
        "platform": "Windows" if is_computer_use else run.get("platform", ""),
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
    counts = {
        "all": 0,
        "running": 0,
        "needs_human": 0,
        "completed": 0,
        "failed": 0,
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

    raise HTTPException(404, "任务不存在")


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

    raise HTTPException(404, "任务不存在")


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

    raise HTTPException(404, "任务不存在")
