"""Execution Kernel v1 for observable automation runs.

The kernel wraps existing executors such as social-auto-upload without
rewriting their internals. It records run state, step timelines, audit
events, and observations so automation can pause safely when uncertain.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from szyg.atomic_file import atomic_read, atomic_write
from szyg.data_path import DATA_DIR

RUNS_FILE = DATA_DIR / "execution_runs.json"
STEPS_FILE = DATA_DIR / "execution_steps.json"
AUDIT_FILE = DATA_DIR / "execution_audit_events.json"
OBSERVATIONS_FILE = DATA_DIR / "execution_observations.json"
ASSERTIONS_FILE = DATA_DIR / "execution_assertions.json"

TERMINAL_STATUSES = {"success", "failed", "cancelled"}
HUMAN_REQUIRED_CODES = {
    "login_expired",
    "captcha_required",
    "account_risk",
    "unknown_popup",
    "platform_changed",
}


def _now() -> str:
    return datetime.now().isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{str(uuid.uuid4())[:8]}"


def _read(path: Path) -> list[dict]:
    return atomic_read(path)


def _write(path: Path, rows: list[dict]) -> None:
    atomic_write(path, rows)


def _clean_dict(value: dict | None, max_text: int = 4000) -> dict:
    cleaned = dict(value or {})
    for key, item in list(cleaned.items()):
        if isinstance(item, str) and len(item) > max_text:
            cleaned[f"{key}_tail"] = item[-max_text:]
            cleaned.pop(key, None)
    return cleaned


def classify_error(message: str) -> str:
    text = (message or "").lower()
    if "file not found" in text or "no such file" in text or "素材" in text and "不存在" in text:
        return "material_missing"
    if "captcha" in text or "验证码" in text or "验证" in text:
        return "captcha_required"
    if "login" in text or "登录" in text or "cookie" in text:
        return "login_expired"
    if "risk" in text or "风控" in text or "账号异常" in text:
        return "account_risk"
    if "timeout" in text or "timed out" in text or "超时" in text:
        return "publish_timeout"
    if "upload" in text or "上传" in text:
        return "upload_failed"
    if "selector" in text or "locator" in text or "button" in text or "页面" in text:
        return "platform_changed"
    if "popup" in text or "弹窗" in text:
        return "unknown_popup"
    return "unknown_error"


class Executor(Protocol):
    executor_type: str

    async def prepare(self, context: dict) -> dict: ...
    async def execute(self, context: dict) -> dict: ...
    async def detect(self, context: dict) -> dict: ...
    async def handoff(self, context: dict) -> dict: ...
    async def resume(self, context: dict) -> dict: ...
    async def cleanup(self, context: dict) -> dict: ...


class BaseExecutor:
    executor_type = "base"

    async def prepare(self, context: dict) -> dict:
        return {"success": True, "status": "success", "message": "prepared"}

    async def execute(self, context: dict) -> dict:
        return {"success": True, "status": "success", "message": "executed"}

    async def detect(self, context: dict) -> dict:
        return {"success": True, "status": "success", "message": "detected"}

    async def handoff(self, context: dict) -> dict:
        return {
            "success": False,
            "status": "needs_user_action",
            "message": "manual handoff required",
            "handoff": {"type": self.executor_type, "reason": "", "instruction": ""},
        }

    async def resume(self, context: dict) -> dict:
        return {"success": True, "status": "running", "message": "resumed"}

    async def cleanup(self, context: dict) -> dict:
        return {"success": True, "status": "success", "message": "cleaned up"}


class BrowserExecutor(BaseExecutor):
    executor_type = "browser"


class DesktopExecutor(BaseExecutor):
    executor_type = "desktop"


class MobileExecutor(BaseExecutor):
    executor_type = "mobile"


class ApiExecutor(BaseExecutor):
    executor_type = "api"


class ExecutionKernel:
    """Small persistent execution kernel for v1 automation observability."""

    def __init__(self) -> None:
        self._running: dict[str, asyncio.Task] = {}
        self._lock = threading.RLock()

    def _ensure_active(self, run_id: str) -> dict:
        run = self.get_run(run_id)
        if not run:
            raise KeyError(run_id)
        if run.get("status") in {"cancelled", "paused"}:
            raise asyncio.CancelledError(run.get("error_message") or f"Execution {run_id} is {run.get('status')}")
        return run

    def list_runs(self, limit: int = 100, status: str = "", platform: str = "") -> list[dict]:
        runs = _read(RUNS_FILE)
        if status:
            runs = [run for run in runs if run.get("status") == status]
        if platform:
            runs = [run for run in runs if run.get("platform") == platform]
        runs.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return runs[:limit]

    def get_run(self, run_id: str) -> dict | None:
        for run in _read(RUNS_FILE):
            if run.get("id") == run_id:
                return run
        return None

    def list_steps(self, run_id: str) -> list[dict]:
        rows = [item for item in _read(STEPS_FILE) if item.get("run_id") == run_id]
        rows.sort(key=lambda item: item.get("created_at", ""))
        return rows

    def list_audit(self, run_id: str) -> list[dict]:
        rows = [item for item in _read(AUDIT_FILE) if item.get("run_id") == run_id]
        rows.sort(key=lambda item: item.get("created_at", ""))
        return rows

    def list_observations(self, run_id: str) -> list[dict]:
        rows = [item for item in _read(OBSERVATIONS_FILE) if item.get("run_id") == run_id]
        rows.sort(key=lambda item: item.get("created_at", ""))
        return rows

    def _upsert_run(self, run: dict) -> dict:
        with self._lock:
            runs = _read(RUNS_FILE)
            for index, item in enumerate(runs):
                if item.get("id") == run["id"]:
                    runs[index] = run
                    _write(RUNS_FILE, runs)
                    return run
            runs.append(run)
            _write(RUNS_FILE, runs)
            return run

    def _patch_run(self, run_id: str, **updates: Any) -> dict:
        with self._lock:
            runs = _read(RUNS_FILE)
            for index, run in enumerate(runs):
                if run.get("id") == run_id:
                    run.update(updates)
                    run["updated_at"] = _now()
                    runs[index] = run
                    _write(RUNS_FILE, runs)
                    return run
        raise KeyError(run_id)

    def create_run(
        self,
        task_type: str,
        platform: str,
        executor_type: str,
        input_data: dict,
        *,
        title: str = "",
        source_task_id: str = "",
        auto_start: bool = False,
    ) -> dict:
        run = {
            "id": _id("exec"),
            "task_type": task_type,
            "title": title or input_data.get("title", ""),
            "platform": platform,
            "executor_type": executor_type,
            "status": "queued",
            "current_step_id": "",
            "input": input_data,
            "result": {},
            "error_code": "",
            "error_message": "",
            "source_task_id": source_task_id,
            "created_at": _now(),
            "updated_at": _now(),
            "started_at": "",
            "finished_at": "",
            "duration_ms": 0,
        }
        self._upsert_run(run)
        if auto_start:
            self._running[run["id"]] = asyncio.create_task(self.run_sau_publish(run["id"]))
        return run

    def start_step(self, run_id: str, step_id: str, name: str, executor_type: str, action: str = "") -> dict:
        step = {
            "id": _id("step"),
            "run_id": run_id,
            "step_id": step_id,
            "name": name,
            "executor_type": executor_type,
            "status": "running",
            "action": action or step_id,
            "created_at": _now(),
            "started_at": _now(),
            "finished_at": "",
            "duration_ms": 0,
            "attempt": 1,
            "error_code": "",
            "error_message": "",
        }
        with self._lock:
            steps = _read(STEPS_FILE)
            steps.append(step)
            _write(STEPS_FILE, steps)
        run = self.get_run(run_id)
        if run and not run.get("started_at"):
            self._patch_run(run_id, status="running", started_at=step["started_at"], current_step_id=step_id)
        else:
            self._patch_run(run_id, status="running", current_step_id=step_id)
        self.add_audit(run_id, step["id"], action or step_id, "running", f"{name} started")
        return step

    def finish_step(
        self,
        step: dict,
        status: str,
        message: str = "",
        *,
        error_code: str = "",
        artifact_path: str = "",
    ) -> dict:
        finished = _now()
        with self._lock:
            steps = _read(STEPS_FILE)
            for index, item in enumerate(steps):
                if item.get("id") == step["id"]:
                    item["status"] = status
                    item["finished_at"] = finished
                    item["duration_ms"] = _duration_ms(item.get("started_at", ""), finished)
                    item["error_code"] = error_code
                    item["error_message"] = message if status in {"failed", "needs_human"} else ""
                    steps[index] = item
                    _write(STEPS_FILE, steps)
                    self.add_audit(
                        item["run_id"],
                        item["id"],
                        item.get("action", item.get("step_id", "")),
                        status,
                        message or f"{item.get('name', '')} {status}",
                        error_code=error_code,
                        artifact_path=artifact_path,
                        duration_ms=item["duration_ms"],
                    )
                    return item
        raise KeyError(step["id"])

    def add_audit(
        self,
        run_id: str,
        step_id: str,
        action: str,
        status: str,
        message: str,
        *,
        error_code: str = "",
        artifact_path: str = "",
        duration_ms: int = 0,
    ) -> dict:
        event = {
            "id": _id("audit"),
            "run_id": run_id,
            "step_id": step_id,
            "action": action,
            "status": status,
            "message": message,
            "error_code": error_code,
            "artifact_path": artifact_path,
            "duration_ms": duration_ms,
            "created_at": _now(),
        }
        with self._lock:
            rows = _read(AUDIT_FILE)
            rows.append(event)
            _write(AUDIT_FILE, rows)
        return event

    def add_observation(
        self,
        run_id: str,
        step_id: str,
        observation_type: str,
        summary: str,
        artifact_path: str = "",
    ) -> dict:
        item = {
            "id": _id("obs"),
            "run_id": run_id,
            "step_id": step_id,
            "type": observation_type,
            "summary": summary,
            "artifact_path": artifact_path,
            "created_at": _now(),
        }
        with self._lock:
            rows = _read(OBSERVATIONS_FILE)
            rows.append(item)
            _write(OBSERVATIONS_FILE, rows)
        return item

    def add_assertion(self, run_id: str, step_id: str, name: str, passed: bool, message: str) -> dict:
        item = {
            "id": _id("assert"),
            "run_id": run_id,
            "step_id": step_id,
            "name": name,
            "passed": passed,
            "message": message,
            "created_at": _now(),
        }
        with self._lock:
            rows = _read(ASSERTIONS_FILE)
            rows.append(item)
            _write(ASSERTIONS_FILE, rows)
        return item

    def complete_run(self, run_id: str, status: str, result: dict | None = None, error_code: str = "", error_message: str = "") -> dict:
        run = self.get_run(run_id)
        if not run:
            raise KeyError(run_id)
        finished = _now()
        duration = _duration_ms(run.get("started_at", "") or run.get("created_at", ""), finished)
        return self._patch_run(
            run_id,
            status=status,
            result=_clean_dict(result),
            error_code=error_code,
            error_message=error_message,
            finished_at=finished if status in TERMINAL_STATUSES else run.get("finished_at", ""),
            duration_ms=duration,
        )

    def pause_run(self, run_id: str, reason: str = "paused by operator") -> dict:
        self.add_audit(run_id, "", "pause", "paused", reason)
        task = self._running.pop(run_id, None)
        if task and not task.done():
            task.cancel()
        return self._patch_run(run_id, status="paused", error_message=reason)

    def cancel_run(self, run_id: str, reason: str = "cancelled by operator") -> dict:
        self.add_audit(run_id, "", "cancel", "cancelled", reason)
        task = self._running.pop(run_id, None)
        if task and not task.done():
            task.cancel()
        return self.complete_run(run_id, "cancelled", error_code="cancelled", error_message=reason)

    def resume_run(self, run_id: str) -> dict:
        run = self.get_run(run_id)
        if not run:
            raise KeyError(run_id)
        if run.get("task_type") in {"publish_video", "publish_note"} and run.get("source_task_id", "").startswith("sau:"):
            updated = self._patch_run(run_id, status="queued", error_code="", error_message="", finished_at="")
            self.add_audit(run_id, "", "resume", "queued", "Execution resumed")
            self._running[run_id] = asyncio.create_task(self.run_sau_publish(run_id))
            return updated
        self.add_audit(run_id, "", "resume", "running", "Execution marked as running")
        return self._patch_run(run_id, status="running", error_code="", error_message="")

    def retry_run(self, run_id: str) -> dict:
        run = self.get_run(run_id)
        if not run:
            raise KeyError(run_id)
        if run.get("status") not in {"failed", "paused", "needs_human"}:
            raise ValueError("Only failed, paused, or needs_human executions can be retried")
        self.add_audit(run_id, "", "retry", "queued", "Execution retry queued")
        updated = self._patch_run(run_id, status="queued", error_code="", error_message="", finished_at="", result={})
        if run.get("task_type") in {"publish_video", "publish_note"} and run.get("source_task_id", "").startswith("sau:"):
            self._running[run_id] = asyncio.create_task(self.run_sau_publish(run_id))
        return updated

    def create_sau_upload_video_run(self, payload: dict, source_task_id: str = "") -> dict:
        return self.create_run(
            "publish_video",
            payload.get("platform", ""),
            "browser",
            payload,
            title=payload.get("title", ""),
            source_task_id=source_task_id or "sau:",
            auto_start=True,
        )

    def create_sau_upload_note_run(self, payload: dict, source_task_id: str = "") -> dict:
        return self.create_run(
            "publish_note",
            payload.get("platform", ""),
            "browser",
            payload,
            title=payload.get("title", ""),
            source_task_id=source_task_id or "sau:",
            auto_start=True,
        )

    async def run_sau_publish(self, run_id: str) -> None:
        started = datetime.now()
        try:
            run = self.get_run(run_id)
            if not run:
                return
            payload = dict(run.get("input") or {})
            self._ensure_active(run_id)
            self._patch_run(run_id, status="running", started_at=run.get("started_at") or started.isoformat())

            self._ensure_active(run_id)
            task_type = run.get("task_type", "publish_video")
            material = self.start_step(run_id, "validate_material", "Validate material", "browser", "validate_material")
            missing_materials = _missing_materials(payload, task_type)
            if missing_materials:
                message = "File not found: " + ", ".join(missing_materials)
                self.add_observation(run_id, material["id"], "text", message)
                self.finish_step(material, "failed", message, error_code="material_missing")
                self.complete_run(run_id, "failed", error_code="material_missing", error_message=message)
                return
            self.add_observation(run_id, material["id"], "text", "Material validated")
            self.finish_step(material, "success", "Material validated")

            self._ensure_active(run_id)
            preflight = self.start_step(run_id, "platform_preflight", "Check platform login", "browser", "check_login")
            from szyg.integrations.social_auto_upload_adapter import get_sau_adapter

            adapter = get_sau_adapter()
            login_status = await adapter.check_login(payload.get("platform", "douyin"))
            self._ensure_active(run_id)
            self.add_observation(run_id, preflight["id"], "text", login_status.get("message", "login checked"))
            if login_status.get("logged_in") is False:
                message = login_status.get("message") or "Login expired"
                self.finish_step(preflight, "needs_human", message, error_code="login_expired")
                self.complete_run(run_id, "needs_human", login_status, "login_expired", message)
                return
            self.finish_step(preflight, "success", "Platform login available")

            self._ensure_active(run_id)
            upload_action = "upload_note" if task_type == "publish_note" else "upload_video"
            upload = self.start_step(run_id, "execute_upload", "Execute social-auto-upload", "browser", upload_action)
            if payload.get("schedule"):
                payload["schedule"] = datetime.strptime(payload["schedule"], "%Y-%m-%d %H:%M")
            if task_type == "publish_note":
                result = await adapter.upload_note(**payload)
            else:
                result = await adapter.upload_video(**payload)
            self._ensure_active(run_id)
            status = "success" if result.get("success") else "failed"
            message = result.get("message", "")
            error_code = "" if status == "success" else classify_error(message)
            artifact = _debug_screenshot_path(started)
            if artifact:
                self.add_observation(run_id, upload["id"], "screenshot", "Executor debug screenshot", artifact)
            final_step_status = "needs_human" if error_code in HUMAN_REQUIRED_CODES else status
            self.finish_step(upload, final_step_status, message or f"Upload {status}", error_code=error_code, artifact_path=artifact)

            self._ensure_active(run_id)
            detect = self.start_step(run_id, "detect_result", "Detect publish result", "browser", "detect_result")
            self.add_assertion(run_id, detect["id"], "sau_success", bool(result.get("success")), message or "social-auto-upload finished")
            self.finish_step(detect, "success" if result.get("success") else final_step_status, message or "Result recorded", error_code=error_code)

            if result.get("success"):
                self.complete_run(run_id, "success", result)
            elif error_code in HUMAN_REQUIRED_CODES:
                self.complete_run(run_id, "needs_human", result, error_code, message)
            else:
                self.complete_run(run_id, "failed", result, error_code, message)
        except asyncio.CancelledError as exc:
            run = self.get_run(run_id)
            if run and run.get("status") not in {"cancelled", "paused"}:
                self._patch_run(run_id, status="cancelled", error_code="cancelled", error_message=str(exc) or "Execution cancelled")
            self.add_audit(run_id, "", "cancelled", run.get("status", "cancelled") if run else "cancelled", str(exc) or "Execution cancelled")
        except Exception as exc:
            message = str(exc)
            error_code = classify_error(message)
            status = "needs_human" if error_code in HUMAN_REQUIRED_CODES else "failed"
            self.add_audit(run_id, "", "exception", status, message, error_code=error_code)
            self.complete_run(run_id, status, error_code=error_code, error_message=message)
        finally:
            self._running.pop(run_id, None)

    def sau_compatible_tasks(self, limit: int = 50) -> list[dict]:
        tasks = []
        for run in self.list_runs(limit=limit):
            if run.get("task_type") not in {"publish_video", "publish_note"}:
                continue
            tasks.append(self.sau_compatible_task(run))
        return tasks[:limit]

    def sau_compatible_task(self, run_or_id: dict | str) -> dict:
        run = self.get_run(run_or_id) if isinstance(run_or_id, str) else run_or_id
        if not run:
            raise KeyError(run_or_id)
        status = {
            "success": "success",
            "failed": "failed",
            "needs_human": "failed",
            "paused": "queued",
            "cancelled": "failed",
        }.get(run.get("status"), run.get("status", "queued"))
        return {
            "id": run["id"],
            "execution_id": run["id"],
            "kind": "upload_note" if run.get("task_type") == "publish_note" else "upload_video",
            "platform": run.get("platform", ""),
            "title": run.get("title", ""),
            "status": status,
            "progress": run.get("current_step_id") or run.get("status", ""),
            "created_at": run.get("created_at", ""),
            "updated_at": run.get("updated_at", ""),
            "started_at": run.get("started_at", ""),
            "finished_at": run.get("finished_at", ""),
            "duration_ms": run.get("duration_ms", 0),
            "payload": run.get("input", {}),
            "result": run.get("result", {}),
            "error": run.get("error_message", ""),
            "error_code": run.get("error_code", ""),
            "debug_screenshot": _latest_artifact(self.list_audit(run["id"])),
        }


def _duration_ms(start: str, end: str) -> int:
    try:
        if not start or not end:
            return 0
        return int((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() * 1000)
    except Exception:
        return 0


def _latest_artifact(events: list[dict]) -> str:
    for event in reversed(events):
        artifact = event.get("artifact_path")
        if artifact:
            return artifact
    return ""


def _missing_materials(payload: dict, task_type: str) -> list[str]:
    if task_type == "publish_note":
        image_paths = payload.get("image_paths") or []
        if not image_paths:
            return ["image_paths is empty"]
        return [str(path) for path in image_paths if not Path(str(path)).exists()]
    file_path = payload.get("file_path") or payload.get("video_path") or ""
    if not file_path:
        return ["file_path is empty"]
    return [] if Path(str(file_path)).exists() else [str(file_path)]


def _debug_screenshot_path(started: datetime) -> str:
    path = DATA_DIR.parent / "external" / "social-auto-upload-main" / "logs" / "douyin_debug" / "publish_retry.png"
    if not path.exists():
        return ""
    modified = datetime.fromtimestamp(path.stat().st_mtime)
    return str(path) if modified >= started else ""


_kernel: ExecutionKernel | None = None


def get_execution_kernel() -> ExecutionKernel:
    global _kernel
    if _kernel is None:
        _kernel = ExecutionKernel()
    return _kernel
