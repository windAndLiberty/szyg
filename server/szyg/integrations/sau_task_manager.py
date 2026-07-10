"""Background task manager for social-auto-upload publishing."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from szyg.atomic_file import atomic_read, atomic_write
from szyg.data_path import DATA_DIR

TASKS_FILE = DATA_DIR / "sau_publish_tasks.json"


def _now() -> str:
    return datetime.now().isoformat()


def _read_tasks() -> list[dict]:
    TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    return atomic_read(TASKS_FILE)


def _write_tasks(tasks: list[dict]) -> None:
    TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(TASKS_FILE, tasks)


def _clean_result(result: dict) -> dict:
    cleaned = dict(result or {})
    stdout = cleaned.get("stdout")
    stderr = cleaned.get("stderr")
    if isinstance(stdout, str) and len(stdout) > 4000:
        cleaned["stdout_tail"] = stdout[-4000:]
        cleaned.pop("stdout", None)
    if isinstance(stderr, str) and len(stderr) > 4000:
        cleaned["stderr_tail"] = stderr[-4000:]
        cleaned.pop("stderr", None)
    return cleaned


def _debug_screenshot_path(started: datetime) -> str:
    path = DATA_DIR.parent / "external" / "social-auto-upload-main" / "logs" / "douyin_debug" / "publish_retry.png"
    if not path.exists():
        return ""
    modified = datetime.fromtimestamp(path.stat().st_mtime)
    return str(path) if modified >= started else ""


class SAUPublishTaskManager:
    def __init__(self) -> None:
        self._running: dict[str, asyncio.Task] = {}

    def list_tasks(self, limit: int = 50) -> list[dict]:
        tasks = _read_tasks()
        tasks.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return tasks[:limit]

    def get_task(self, task_id: str) -> dict | None:
        for item in _read_tasks():
            if item.get("id") == task_id:
                return item
        return None

    def _upsert(self, task: dict) -> dict:
        tasks = _read_tasks()
        for index, item in enumerate(tasks):
            if item.get("id") == task["id"]:
                tasks[index] = task
                _write_tasks(tasks)
                return task
        tasks.append(task)
        _write_tasks(tasks)
        return task

    def _patch(self, task_id: str, **updates: Any) -> dict:
        task = self.get_task(task_id)
        if not task:
            raise KeyError(task_id)
        task.update(updates)
        task["updated_at"] = _now()
        return self._upsert(task)

    def create_upload_video_task(self, payload: dict) -> dict:
        return self._create_task("upload_video", payload)

    def create_upload_note_task(self, payload: dict) -> dict:
        return self._create_task("upload_note", payload)

    def _create_task(self, kind: str, payload: dict) -> dict:
        task_id = str(uuid.uuid4())[:8]
        task = {
            "id": task_id,
            "kind": kind,
            "platform": payload.get("platform", ""),
            "title": payload.get("title", ""),
            "status": "queued",
            "progress": "queued",
            "created_at": _now(),
            "updated_at": _now(),
            "started_at": "",
            "finished_at": "",
            "duration_ms": 0,
            "payload": payload,
            "result": {},
            "error": "",
            "debug_screenshot": "",
        }
        self._upsert(task)
        self._running[task_id] = asyncio.create_task(self._run_task(task_id))
        return task

    async def _run_task(self, task_id: str) -> None:
        started = datetime.now()
        self._patch(task_id, status="running", progress="starting", started_at=started.isoformat())
        try:
            from szyg.integrations.social_auto_upload_adapter import get_sau_adapter

            task = self.get_task(task_id)
            if not task:
                return
            payload = dict(task.get("payload") or {})
            if payload.get("schedule"):
                payload["schedule"] = datetime.strptime(payload["schedule"], "%Y-%m-%d %H:%M")
            adapter = get_sau_adapter()
            if task.get("kind") == "upload_video":
                self._patch(task_id, progress="uploading_video")
                result = await adapter.upload_video(**payload)
            elif task.get("kind") == "upload_note":
                self._patch(task_id, progress="uploading_note")
                result = await adapter.upload_note(**payload)
            else:
                raise ValueError(f"Unsupported SAU task kind: {task.get('kind')}")

            finished = datetime.now()
            status = "success" if result.get("success") else "failed"
            self._patch(
                task_id,
                status=status,
                progress="completed" if status == "success" else "failed",
                finished_at=finished.isoformat(),
                duration_ms=int((finished - started).total_seconds() * 1000),
                result=_clean_result(result),
                error="" if status == "success" else result.get("message", "social-auto-upload failed"),
                debug_screenshot=_debug_screenshot_path(started),
            )
        except Exception as exc:
            finished = datetime.now()
            self._patch(
                task_id,
                status="failed",
                progress="failed",
                finished_at=finished.isoformat(),
                duration_ms=int((finished - started).total_seconds() * 1000),
                error=str(exc),
                debug_screenshot=_debug_screenshot_path(started),
            )
        finally:
            self._running.pop(task_id, None)


_manager: SAUPublishTaskManager | None = None


def get_sau_task_manager() -> SAUPublishTaskManager:
    global _manager
    if _manager is None:
        _manager = SAUPublishTaskManager()
    return _manager
