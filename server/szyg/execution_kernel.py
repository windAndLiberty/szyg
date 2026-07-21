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
from typing import Any, Awaitable, Callable, Protocol

from szyg.atomic_file import atomic_read, atomic_write
from szyg.data_path import DATA_DIR

RUNS_FILE = DATA_DIR / "execution_runs.json"
STEPS_FILE = DATA_DIR / "execution_steps.json"
AUDIT_FILE = DATA_DIR / "execution_audit_events.json"
OBSERVATIONS_FILE = DATA_DIR / "execution_observations.json"
ASSERTIONS_FILE = DATA_DIR / "execution_assertions.json"
ARCHIVED_RUNS_FILE = DATA_DIR / "execution_runs_archive.json"
ARCHIVED_STEPS_FILE = DATA_DIR / "execution_steps_archive.json"
ARCHIVED_AUDIT_FILE = DATA_DIR / "execution_audit_events_archive.json"
ARCHIVED_OBSERVATIONS_FILE = DATA_DIR / "execution_observations_archive.json"
ARCHIVED_ASSERTIONS_FILE = DATA_DIR / "execution_assertions_archive.json"

TERMINAL_STATUSES = {"success", "failed", "cancelled"}
PUBLISH_TASK_TYPES = {"publish_video", "publish_note"}
PUBLISH_ACTIVE_RECORD_LIMIT = 300
PUBLISH_ARCHIVE_RECORD_LIMIT = 2000
HUMAN_REQUIRED_CODES = {
    "login_expired",
    "captcha_required",
    "account_risk",
    "unknown_popup",
    "platform_changed",
    "sensitive_action",
    "low_confidence",
    "verification_uncertain",
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


def _record_time_key(item: dict) -> str:
    return item.get("finished_at") or item.get("updated_at") or item.get("created_at") or ""


def _match_keyword(run: dict, keyword: str) -> bool:
    if not keyword:
        return True
    text_parts = [
        run.get("id", ""),
        run.get("title", ""),
        run.get("platform", ""),
        run.get("account_label", ""),
        run.get("batch_id", ""),
        run.get("status", ""),
        run.get("error_code", ""),
        run.get("error_message", ""),
    ]
    input_data = run.get("input") if isinstance(run.get("input"), dict) else {}
    result = run.get("result") if isinstance(run.get("result"), dict) else {}
    text_parts.extend([
        str(input_data.get("title") or ""),
        str(input_data.get("desc") or input_data.get("note") or ""),
        " ".join(str(item) for item in input_data.get("tags") or [] if item),
        str(result.get("message") or ""),
        str(result.get("post_url") or ""),
    ])
    haystack = "\n".join(text_parts).lower()
    return keyword.lower() in haystack


def _sort_runs(runs: list[dict], sort_by: str, sort_dir: str) -> list[dict]:
    sort_key = sort_by if sort_by in {"created_at", "updated_at", "finished_at", "duration_ms", "platform", "status", "title"} else "created_at"
    reverse = sort_dir != "asc"

    def key(item: dict) -> Any:
        if sort_key == "duration_ms":
            return int(item.get("duration_ms") or 0)
        return str(item.get(sort_key) or "")

    return sorted(runs, key=key, reverse=reverse)


def classify_error(message: str) -> str:
    text = (message or "").lower()
    if "标题不能超过" in text or "title" in text and "too long" in text:
        return "invalid_publish_content"
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
        self._task_runners: dict[str, Callable[[str], Awaitable[dict]]] = {}
        self._lock = threading.RLock()
        self._sau_global_semaphore = asyncio.Semaphore(2)
        self._sau_platform_locks: dict[str, asyncio.Lock] = {}
        self._recover_stale_active_runs()

    def register_task_runner(self, task_type: str, runner: Callable[[str], Awaitable[dict]]) -> None:
        """Register a resumable task runner without hard-coding it in the kernel."""
        self._task_runners[task_type] = runner

    def start_run(self, run_id: str) -> dict:
        run = self.get_run(run_id)
        if not run:
            raise KeyError(run_id)
        runner = self._task_runners.get(str(run.get("task_type") or ""))
        if runner is None:
            raise ValueError(f"No runner registered for task type: {run.get('task_type')}")
        current = self._running.get(run_id)
        if current and not current.done():
            return run
        updated = self._patch_run(run_id, status="queued", error_code="", error_message="", finished_at="")
        self._running[run_id] = asyncio.create_task(self._run_registered(run_id, runner))
        return updated

    async def _run_registered(self, run_id: str, runner: Callable[[str], Awaitable[dict]]) -> dict:
        try:
            return await runner(run_id)
        finally:
            current = self._running.get(run_id)
            if current is asyncio.current_task():
                self._running.pop(run_id, None)

    def _recover_stale_active_runs(self) -> None:
        runs = _read(RUNS_FILE)
        changed = False
        now = datetime.now().isoformat()
        for run in runs:
            if run.get("status") not in {"queued", "running"}:
                continue
            if run.get("id") in self._running:
                continue
            run["status"] = "needs_human"
            run["error_code"] = run.get("error_code") or "execution_interrupted"
            run["error_message"] = run.get("error_message") or "后端重启或执行进程中断，请人工确认平台页面状态后重试"
            run["updated_at"] = now
            changed = True
        if changed:
            _write(RUNS_FILE, runs)

    def _archive_related_rows(self, source_file: Path, archive_file: Path, run_ids: set[str]) -> None:
        rows = _read(source_file)
        if not rows:
            return
        keep_rows = [row for row in rows if row.get("run_id") not in run_ids]
        archive_rows = [row for row in rows if row.get("run_id") in run_ids]
        if not archive_rows:
            return
        existing = _read(archive_file)
        by_id = {str(row.get("id") or f"{row.get('run_id')}:{index}"): row for index, row in enumerate(existing)}
        for index, row in enumerate(archive_rows):
            by_id[str(row.get("id") or f"{row.get('run_id')}:{index}")] = row
        archived = list(by_id.values())
        archived.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        _write(source_file, keep_rows)
        _write(archive_file, archived[: PUBLISH_ARCHIVE_RECORD_LIMIT * 8])

    def archive_old_publish_runs(self) -> dict:
        """Move old terminal publish runs out of the active execution list."""
        with self._lock:
            runs = _read(RUNS_FILE)
            terminal_publish = [
                run for run in runs
                if run.get("task_type") in PUBLISH_TASK_TYPES and run.get("status") in TERMINAL_STATUSES
            ]
            terminal_publish.sort(key=_record_time_key, reverse=True)
            if len(terminal_publish) <= PUBLISH_ACTIVE_RECORD_LIMIT:
                return self.archive_stats()

            archive_ids = {run.get("id") for run in terminal_publish[PUBLISH_ACTIVE_RECORD_LIMIT:] if run.get("id")}
            if not archive_ids:
                return self.archive_stats()

            archived_at = _now()
            active_runs = []
            archived_runs = []
            for run in runs:
                if run.get("id") in archive_ids:
                    archived = dict(run)
                    archived["archived_at"] = archived_at
                    archived["archive_reason"] = f"publish_record_limit_{PUBLISH_ACTIVE_RECORD_LIMIT}"
                    archived_runs.append(archived)
                else:
                    active_runs.append(run)

            existing_archive = _read(ARCHIVED_RUNS_FILE)
            by_id = {item.get("id"): item for item in existing_archive if item.get("id")}
            for run in archived_runs:
                by_id[run["id"]] = run
            archive_rows = list(by_id.values())
            archive_rows.sort(key=lambda item: item.get("archived_at") or _record_time_key(item), reverse=True)
            archive_rows = archive_rows[:PUBLISH_ARCHIVE_RECORD_LIMIT]

            _write(RUNS_FILE, active_runs)
            _write(ARCHIVED_RUNS_FILE, archive_rows)
            self._archive_related_rows(STEPS_FILE, ARCHIVED_STEPS_FILE, archive_ids)
            self._archive_related_rows(AUDIT_FILE, ARCHIVED_AUDIT_FILE, archive_ids)
            self._archive_related_rows(OBSERVATIONS_FILE, ARCHIVED_OBSERVATIONS_FILE, archive_ids)
            self._archive_related_rows(ASSERTIONS_FILE, ARCHIVED_ASSERTIONS_FILE, archive_ids)
            return self.archive_stats()

    def archive_stats(self) -> dict:
        active_publish = [
            run for run in _read(RUNS_FILE)
            if run.get("task_type") in PUBLISH_TASK_TYPES
        ]
        archived_publish = [
            run for run in _read(ARCHIVED_RUNS_FILE)
            if run.get("task_type") in PUBLISH_TASK_TYPES
        ]
        return {
            "active_publish_records": len(active_publish),
            "archived_publish_records": len(archived_publish),
            "active_limit": PUBLISH_ACTIVE_RECORD_LIMIT,
            "archive_limit": PUBLISH_ARCHIVE_RECORD_LIMIT,
        }

    def _ensure_active(self, run_id: str) -> dict:
        run = self.get_run(run_id)
        if not run:
            raise KeyError(run_id)
        if run.get("status") in {"cancelled", "paused"}:
            raise asyncio.CancelledError(run.get("error_message") or f"Execution {run_id} is {run.get('status')}")
        return run

    def list_runs(
        self,
        limit: int = 100,
        status: str = "",
        platform: str = "",
        task_type: str = "",
        keyword: str = "",
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        include_archived: bool = False,
    ) -> list[dict]:
        self.archive_old_publish_runs()
        runs = _read(RUNS_FILE)
        if include_archived:
            archived = []
            for run in _read(ARCHIVED_RUNS_FILE):
                item = dict(run)
                item["archived"] = True
                archived.append(item)
            runs = [*runs, *archived]
        if status:
            runs = [run for run in runs if run.get("status") == status]
        if platform:
            runs = [run for run in runs if run.get("platform") == platform]
        if task_type:
            allowed = {item.strip() for item in task_type.split(",") if item.strip()}
            runs = [run for run in runs if run.get("task_type") in allowed]
        if keyword:
            runs = [run for run in runs if _match_keyword(run, keyword)]
        runs = _sort_runs(runs, sort_by, sort_dir)
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
            "account_id": input_data.get("account_id", ""),
            "account_label": input_data.get("account_label", ""),
            "profile_id": input_data.get("profile_id", ""),
            "batch_id": input_data.get("batch_id", ""),
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

    def _sau_platform_lock(self, platform: str) -> asyncio.Lock:
        platform = platform or "default"
        lock = self._sau_platform_locks.get(platform)
        if not lock:
            lock = asyncio.Lock()
            self._sau_platform_locks[platform] = lock
        return lock

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
        if run.get("task_type") == "computer_use":
            updated = self._patch_run(run_id, status="queued", error_code="", error_message="", finished_at="")
            self.add_audit(run_id, "", "resume", "queued", "Computer-use execution resumed")
            self._running[run_id] = asyncio.create_task(self.run_computer_use(run_id))
            return updated
        if run.get("task_type") == "marketing_comment":
            updated = self._patch_run(run_id, status="queued", error_code="", error_message="", finished_at="")
            self.add_audit(run_id, "", "resume", "queued", "Marketing comment execution resumed")
            self._running[run_id] = asyncio.create_task(self.run_marketing_comment(run_id))
            return updated
        if run.get("task_type") in self._task_runners:
            self.add_audit(run_id, "", "resume", "queued", "Execution resumed")
            return self.start_run(run_id)
        self.add_audit(run_id, "", "resume", "running", "Execution marked as running")
        return self._patch_run(run_id, status="running", error_code="", error_message="")

    def retry_run(self, run_id: str) -> dict:
        run = self.get_run(run_id)
        if not run:
            raise KeyError(run_id)
        if run.get("status") not in {"failed", "paused", "needs_human"}:
            raise ValueError("Only failed, paused, or needs_human executions can be retried")
        self.add_audit(run_id, "", "retry", "queued", "Execution retry queued")
        # Registered resumable runners persist their completed-step checkpoint in
        # ``result``. Keep it on retry so successful external actions are not
        # executed twice; legacy runners retain their previous reset behavior.
        retry_result = (run.get("result") or {}) if run.get("task_type") in self._task_runners else {}
        updated = self._patch_run(
            run_id,
            status="queued",
            error_code="",
            error_message="",
            finished_at="",
            result=retry_result,
        )
        if run.get("task_type") in {"publish_video", "publish_note"} and run.get("source_task_id", "").startswith("sau:"):
            self._running[run_id] = asyncio.create_task(self.run_sau_publish(run_id))
        elif run.get("task_type") == "computer_use":
            self._running[run_id] = asyncio.create_task(self.run_computer_use(run_id))
        elif run.get("task_type") == "marketing_comment":
            self._running[run_id] = asyncio.create_task(self.run_marketing_comment(run_id))
        elif run.get("task_type") in self._task_runners:
            self._running[run_id] = asyncio.create_task(
                self._run_registered(run_id, self._task_runners[run.get("task_type")])
            )
        return updated

    async def run_marketing_comment(self, run_id: str) -> dict:
        run = self.get_run(run_id)
        if not run:
            raise KeyError(run_id)
        self._patch_run(run_id, status="running", started_at=run.get("started_at") or _now())
        payload = run.get("input", {}) or {}
        platform = payload.get("platform", run.get("platform", ""))
        step = self.start_step(run_id, "send_comment", "Send marketing comment", "browser", "send_comment")
        try:
            from szyg.comment_engine import batch_send

            results = await batch_send(
                platform,
                [{
                    "video_id": payload.get("video_id", ""),
                    "video_title": payload.get("video_title", ""),
                    "video_url": payload.get("video_url", ""),
                    "text": payload.get("text", ""),
                    "comment_text": payload.get("text", ""),
                    "queue_item_id": payload.get("queue_item_id", ""),
                    "human_confirmed": bool(payload.get("human_confirmed")),
                }],
                payload.get("strategy", "balanced"),
                payload.get("deai", True),
                create_execution=False,
            )
            result = results[0] if results else {"status": "failed", "error": "empty marketing comment result"}
            status = result.get("status", "failed")
            if status == "sent":
                self.finish_step(step, "success", "Marketing comment sent")
                return self.complete_run(run_id, "success", result)
            if status == "needs_human":
                message = str(result.get("error") or result.get("reason") or "Marketing comment needs human")
                self.finish_step(step, "needs_human", message, error_code="needs_human")
                return self.complete_run(run_id, "needs_human", result, "needs_human", message)
            message = str(result.get("error") or result.get("reason") or f"Marketing comment status: {status}")
            self.finish_step(step, "failed", message, error_code=str(result.get("decision") or status))
            return self.complete_run(run_id, "failed", result, str(result.get("decision") or status), message)
        except asyncio.CancelledError:
            self.finish_step(step, "cancelled", "Marketing comment cancelled", error_code="cancelled")
            raise
        except Exception as exc:
            message = str(exc)
            self.finish_step(step, "failed", message, error_code="marketing_comment_failed")
            return self.complete_run(run_id, "failed", error_code="marketing_comment_failed", error_message=message)

    def create_marketing_comment_run(self, payload: dict, source_task_id: str = "") -> dict:
        """Create and start an observable, confirmed marketing-comment run."""
        run = self.create_run(
            "marketing_comment",
            payload.get("platform", ""),
            "browser",
            payload,
            title=payload.get("video_title", "") or "营销评论",
            source_task_id=source_task_id or "acquisition:confirmed",
            auto_start=False,
        )
        self._running[run["id"]] = asyncio.create_task(self.run_marketing_comment(run["id"]))
        return run

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

    def create_computer_use_run(self, payload: dict, source_task_id: str = "") -> dict:
        normalized = _normalize_computer_use_payload(payload)
        run = self.create_run(
            "computer_use",
            normalized.get("target_app", "windows"),
            "desktop",
            normalized,
            title=normalized.get("instruction", "电脑使用任务"),
            source_task_id=source_task_id or "computer-use:",
            auto_start=False,
        )
        self._running[run["id"]] = asyncio.create_task(self.run_computer_use(run["id"]))
        return run

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
            login_status = await adapter.check_login(
                payload.get("platform", "douyin"),
                account_id=payload.get("account_id") or None,
                account_file=payload.get("account_file") or None,
                account_name=payload.get("account_name") or None,
            )
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
            timeout_seconds = 900
            timeout_getter = getattr(adapter, "_publish_timeout_seconds", None)
            if callable(timeout_getter):
                timeout_seconds = int(timeout_getter() or timeout_seconds)
            try:
                async with self._sau_global_semaphore:
                    async with self._sau_platform_lock(payload.get("platform", "")):
                        if task_type == "publish_note":
                            upload_payload = {
                                key: payload.get(key)
                                for key in [
                                    "platform",
                                    "image_paths",
                                    "title",
                                    "note",
                                    "tags",
                                    "schedule",
                                    "account_file",
                                    "account_id",
                                    "account_name",
                                    "headless",
                                ]
                                if key in payload
                            }
                            upload_coro = adapter.upload_note(**upload_payload)
                        else:
                            upload_payload = {
                                key: payload.get(key)
                                for key in [
                                    "platform",
                                    "file_path",
                                    "title",
                                    "desc",
                                    "tags",
                                    "thumbnail_path",
                                    "schedule",
                                    "account_file",
                                    "account_id",
                                    "account_name",
                                    "headless",
                                ]
                                if key in payload
                            }
                            upload_coro = adapter.upload_video(**upload_payload)
                        result = await asyncio.wait_for(upload_coro, timeout=timeout_seconds)
            except asyncio.TimeoutError:
                result = {
                    "success": False,
                    "platform": payload.get("platform", ""),
                    "message": f"social-auto-upload timed out after {timeout_seconds}s",
                    "error_code": "publish_timeout",
                }
            self._ensure_active(run_id)
            status = "success" if result.get("success") else "failed"
            message = result.get("message", "")
            error_code = "" if status == "success" else result.get("error_code") or classify_error(message)
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
                if payload.get("account_id"):
                    try:
                        from szyg.channel_accounts import patch_account

                        patch_account(payload.get("account_id"), last_publish_at=_now())
                    except Exception:
                        pass
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

    async def run_computer_use(self, run_id: str) -> None:
        started = datetime.now()
        try:
            run = self.get_run(run_id)
            if not run:
                return
            payload = _normalize_computer_use_payload(dict(run.get("input") or {}))
            self._ensure_active(run_id)
            self._patch_run(run_id, status="running", started_at=run.get("started_at") or started.isoformat())

            validate = self.start_step(run_id, "validate_request", "Validate computer-use request", "desktop", "validate_request")
            instruction = payload.get("instruction", "").strip()
            if not instruction:
                message = "电脑使用任务缺少目标说明"
                self.add_observation(run_id, validate["id"], "text", message)
                self.finish_step(validate, "failed", message, error_code="invalid_request")
                self.complete_run(run_id, "failed", error_code="invalid_request", error_message=message)
                return
            sensitive = _detect_sensitive_computer_action(payload)
            self.add_observation(run_id, validate["id"], "text", f"目标：{instruction}")
            self.finish_step(validate, "success", "任务目标已确认")

            self._ensure_active(run_id)
            preflight = self.start_step(run_id, "preflight_providers", "Check computer-use providers", "desktop", "preflight_providers")
            from szyg.integrations.computer_use_adapter import get_computer_use_adapter

            adapter = get_computer_use_adapter()
            health = await adapter.health()
            self._ensure_active(run_id)
            self.add_observation(run_id, preflight["id"], "text", health.get("message", "本机执行组件状态已检查"))
            if health.get("platform") != "nt":
                message = "电脑使用 v1 仅支持 Windows"
                self.finish_step(preflight, "failed", message, error_code="unsupported_platform")
                self.complete_run(run_id, "failed", health, "unsupported_platform", message)
                return
            self.finish_step(preflight, "success", health.get("message", "本机执行组件状态已检查"))

            self._ensure_active(run_id)
            observe = self.start_step(run_id, "observe_initial", "Observe browser, desktop, and vision state", "desktop", "observe_initial")
            observation = await adapter.observe()
            self._ensure_active(run_id)
            screenshot_path = ((observation.get("screenshot") or {}).get("path") or "")
            self.add_observation(run_id, observe["id"], "desktop", observation.get("summary", "已观察当前桌面"), screenshot_path)
            self.finish_step(observe, "success", observation.get("summary", "已观察当前桌面"), artifact_path=screenshot_path)

            self._ensure_active(run_id)
            plan_step = self.start_step(run_id, "plan_actions", "Plan controlled computer-use actions", "desktop", "plan_actions")
            plan = await adapter.plan_actions(payload, observation) if hasattr(adapter, "plan_actions") else {
                "success": True,
                "actions": [],
                "message": "使用兼容执行路径",
            }
            self._ensure_active(run_id)
            self.add_observation(run_id, plan_step["id"], "text", plan.get("message", "动作计划已生成"))
            self.finish_step(plan_step, "success" if plan.get("success", True) else "failed", plan.get("message", "动作计划已生成"))

            self._ensure_active(run_id)
            execute = self.start_step(run_id, "execute_actions", "Execute controlled computer-use actions", "desktop", "execute_actions")
            if payload.get("mode") == "observe_only":
                action_result = {"success": True, "message": "观察任务已完成", "observation": observation}
                self.finish_step(execute, "success", "观察任务无需执行动作")
            elif sensitive:
                message = "该任务包含外发、删除、付款、登录或账号敏感动作，已转入人工确认"
                self.add_observation(run_id, execute["id"], "text", message, screenshot_path)
                self.finish_step(execute, "needs_human", message, error_code="sensitive_action", artifact_path=screenshot_path)
                self.complete_run(run_id, "needs_human", {"observation": observation}, "sensitive_action", message)
                return
            elif payload.get("mode") == "execute" and not _has_required_computer_provider(health, payload, plan):
                message = "所需本机执行组件未就绪，不能进入自动执行模式"
                self.finish_step(execute, "failed", message, error_code="desktop_backend_unavailable")
                self.complete_run(run_id, "failed", {"health": health, "observation": observation}, "desktop_backend_unavailable", message)
                return
            else:
                if hasattr(adapter, "execute_computer_actions"):
                    action_result = await adapter.execute_computer_actions(payload, plan)
                else:
                    action_result = await _execute_safe_computer_actions(adapter, payload)
                final_step_status = "success" if action_result.get("success") else "needs_human" if action_result.get("error_code") in HUMAN_REQUIRED_CODES else "failed"
                self.add_observation(run_id, execute["id"], "text", action_result.get("message", "动作已执行"), screenshot_path)
                self.finish_step(
                    execute,
                    final_step_status,
                    action_result.get("message", "动作已执行"),
                    error_code=action_result.get("error_code", ""),
                    artifact_path=screenshot_path,
                )
                if final_step_status != "success":
                    self.complete_run(
                        run_id,
                        final_step_status,
                        {"health": health, "observation": observation, "action": action_result},
                        action_result.get("error_code", ""),
                        action_result.get("message", "电脑使用任务未完成"),
                    )
                    return

            self._ensure_active(run_id)
            verify = self.start_step(run_id, "verify_result", "Verify desktop result", "desktop", "verify_result")
            verify_result = {}
            if payload.get("expected_result") and hasattr(adapter, "browser_observe") and (payload.get("url") or payload.get("target_app") in {"browser", "chrome"}):
                try:
                    from szyg.integrations.browser_dom_provider import get_browser_dom_provider

                    verify_result = await get_browser_dom_provider().verify(payload.get("expected_result", ""), payload.get("target_selector", ""))
                except Exception as exc:
                    verify_result = {"success": False, "message": str(exc), "error_code": "verification_uncertain"}
            after = await adapter.observe()
            verify_artifact = ((after.get("screenshot") or {}).get("path") or screenshot_path)
            self.add_observation(run_id, verify["id"], "desktop", after.get("summary", "已完成执行后观察"), verify_artifact)
            self.add_assertion(run_id, verify["id"], "desktop_observed", bool(after.get("ok")), after.get("summary", "已完成执行后观察"))
            if verify_result and not verify_result.get("success"):
                self.add_assertion(run_id, verify["id"], "expected_result", False, verify_result.get("message", "验证不确定"))
                self.finish_step(verify, "needs_human", verify_result.get("message", "执行结果无法验证"), error_code=verify_result.get("error_code", "verification_uncertain"), artifact_path=verify_artifact)
                self.complete_run(
                    run_id,
                    "needs_human",
                    {"health": health, "observation": observation, "action": action_result, "after": after, "verification": verify_result},
                    verify_result.get("error_code", "verification_uncertain"),
                    verify_result.get("message", "执行结果无法验证"),
                )
                return
            if verify_result:
                self.add_assertion(run_id, verify["id"], "expected_result", True, verify_result.get("message", "验证通过"))
            self.finish_step(verify, "success", "执行结果已记录", artifact_path=verify_artifact)

            cleanup = self.start_step(run_id, "cleanup", "Cleanup desktop adapter", "desktop", "cleanup")
            cleanup_result = await adapter.cleanup()
            self.finish_step(cleanup, "success" if cleanup_result.get("success") else "failed", cleanup_result.get("message", "清理完成"))

            self.complete_run(
                run_id,
                "success",
                {
                    "message": action_result.get("message", "电脑使用任务已完成"),
                    "health": health,
                    "observation": observation,
                    "plan": plan,
                    "after": after,
                    "verification": verify_result,
                },
            )
        except asyncio.CancelledError as exc:
            try:
                from szyg.integrations.computer_use_adapter import get_computer_use_adapter

                await get_computer_use_adapter().cleanup()
            except Exception:
                pass
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
            "account_id": run.get("account_id", "") or (run.get("input", {}) or {}).get("account_id", ""),
            "account_label": run.get("account_label", "") or (run.get("input", {}) or {}).get("account_label", ""),
            "profile_id": run.get("profile_id", "") or (run.get("input", {}) or {}).get("profile_id", ""),
            "batch_id": run.get("batch_id", "") or (run.get("input", {}) or {}).get("batch_id", ""),
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


def _normalize_computer_use_payload(payload: dict) -> dict:
    allowed_modes = {"observe_only", "assisted", "execute"}
    mode = payload.get("mode") or "assisted"
    if mode not in allowed_modes:
        mode = "assisted"
    max_steps = int(payload.get("max_steps") or 8)
    max_steps = max(1, min(max_steps, 20))
    allowed_actions = payload.get("allowed_actions") or ["observe", "open_url", "launch", "click", "type", "hotkey", "upload_file", "wait_for", "verify"]
    if isinstance(allowed_actions, str):
        allowed_actions = [item.strip() for item in allowed_actions.split(",") if item.strip()]
    steps = payload.get("steps") or []
    if isinstance(steps, str):
        steps = []
    files = payload.get("files") or []
    if isinstance(files, str):
        files = [item.strip() for item in files.splitlines() if item.strip()]
    return {
        **payload,
        "instruction": str(payload.get("instruction", "")).strip(),
        "target_app": str(payload.get("target_app", "windows") or "windows").strip(),
        "url": str(payload.get("url", "") or "").strip(),
        "expected_result": str(payload.get("expected_result", "") or "").strip(),
        "target_selector": str(payload.get("target_selector", "") or "").strip(),
        "files": files,
        "steps": [item for item in steps if isinstance(item, dict)],
        "mode": mode,
        "max_steps": max_steps,
        "require_confirmation": bool(payload.get("require_confirmation", True)),
        "allowed_actions": allowed_actions,
        "sensitive_policy": payload.get("sensitive_policy") or "handoff",
    }


def _detect_sensitive_computer_action(payload: dict) -> bool:
    text = " ".join(
        str(payload.get(key, ""))
        for key in ("instruction", "target_app", "text", "expected_result")
    ).lower()
    sensitive_terms = [
        "发送", "群发", "私信", "付款", "支付", "转账", "删除", "清空", "注销",
        "登录", "验证码", "扫码", "加好友", "同意好友", "外发", "提交订单",
        "send", "pay", "delete", "login", "transfer",
    ]
    sensitive_apps = ["wechat", "微信", "企业微信"]
    if any(term in text for term in sensitive_terms):
        return True
    return payload.get("target_app") in sensitive_apps and payload.get("mode") == "execute"


def _has_required_computer_provider(health: dict, payload: dict, plan: dict | None = None) -> bool:
    providers = health.get("providers", {})
    actions = list((plan or {}).get("actions") or [])
    needs_browser = bool(payload.get("url")) or payload.get("target_app") in {"browser", "chrome"} or any(
        item.get("provider") == "playwright" or item.get("action") == "open_url"
        for item in actions
    )
    needs_desktop = any(
        item.get("provider") in {"terminator", "desktop"} or item.get("action") == "launch_app"
        for item in actions
    ) or (not needs_browser and payload.get("target_app") not in {"windows", "browser", "chrome"})
    browser_ok = bool((providers.get("playwright") or {}).get("available"))
    desktop_ok = bool((providers.get("terminator") or {}).get("available") or health.get("available"))
    if needs_browser and not browser_ok:
        return False
    if needs_desktop and not desktop_ok:
        return False
    return True


def _extract_safe_text_to_type(instruction: str) -> str:
    markers = ["输入", "写入", "键入"]
    for marker in markers:
        if marker in instruction:
            text = instruction.split(marker, 1)[1].strip()
            return text.strip("：:，,。 ")
    return ""


async def _execute_safe_computer_actions(adapter: Any, payload: dict) -> dict:
    target_app = payload.get("target_app", "")
    instruction = payload.get("instruction", "")
    actions = payload.get("allowed_actions") or []
    results: list[dict] = []

    if target_app and target_app != "windows" and "launch" in actions:
        launched = await adapter.launch_app(target_app)
        results.append({"action": "launch", **launched})
        if not launched.get("success"):
            return launched

    text_to_type = str(payload.get("text") or _extract_safe_text_to_type(instruction))
    safe_type_apps = {"notepad", "记事本"}
    if text_to_type and target_app in safe_type_apps and "type" in actions:
        focused = await adapter.find_element("process:notepad >> role:Document || process:notepad >> role:Edit")
        results.append({"action": "find_input", **focused})
        if not focused.get("success"):
            return focused
        typed = await adapter.type_text(text_to_type)
        results.append({"action": "type", **typed})
        if not typed.get("success"):
            return typed

    if not results:
        return {
            "success": True,
            "message": "已完成桌面观察，未执行高风险动作",
            "actions": results,
        }

    return {
        "success": all(item.get("success") for item in results),
        "message": "电脑使用动作已执行：" + "、".join(item.get("action", "action") for item in results),
        "actions": results,
    }


def _debug_screenshot_path(started: datetime) -> str:
    candidates = [
        DATA_DIR.parent / "external" / "social-auto-upload-main" / "logs" / "douyin_debug" / "publish_retry.png",
        DATA_DIR.parent / "external" / "social-auto-upload-main" / "logs" / "xiaohongshu_debug" / "note_upload_timeout.png",
        DATA_DIR.parent / "external" / "social-auto-upload-main" / "logs" / "xiaohongshu_debug" / "note_publish_timeout.png",
        DATA_DIR.parent / "external" / "social-auto-upload-main" / "logs" / "xiaohongshu_debug" / "note_publish_retry.png",
    ]
    latest = ""
    latest_time = started
    for path in candidates:
        if not path.exists():
            continue
        modified = datetime.fromtimestamp(path.stat().st_mtime)
        if modified >= latest_time:
            latest = str(path)
            latest_time = modified
    return latest


_kernel: ExecutionKernel | None = None


def get_execution_kernel() -> ExecutionKernel:
    global _kernel
    if _kernel is None:
        _kernel = ExecutionKernel()
    return _kernel
