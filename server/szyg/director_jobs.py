"""Persist long-running director operations and deduplicate MCP retries."""
from __future__ import annotations

import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import closing
from typing import Callable
from uuid import UUID, uuid4

from fastapi import HTTPException
import psutil

from szyg.data_path import get_data_dir

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="director")


def _db():
    db = sqlite3.connect(get_data_dir() / "director-jobs.sqlite3", timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS director_jobs (
        id TEXT PRIMARY KEY, request_key TEXT UNIQUE, signature TEXT, status TEXT,
        pid INTEGER, started REAL, result TEXT)""")
    return db


def _recover(db):
    for row in db.execute("SELECT DISTINCT pid,started FROM director_jobs WHERE status IN ('queued','running')"):
        try:
            if psutil.Process(row["pid"]).create_time() == row["started"]:
                continue
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            continue
        db.execute("""UPDATE director_jobs SET status='interrupted'
            WHERE pid=? AND started=? AND status IN ('queued','running')""", tuple(row))


def _job(job_id: str) -> sqlite3.Row:
    with closing(_db()) as db, db:
        _recover(db)
        row = db.execute("SELECT signature,status,result FROM director_jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "导演任务不存在")
    return row


def status(job_id: str) -> dict:
    row = _job(job_id)
    return _status_payload(job_id, row)


def _status_payload(job_id: str, row: sqlite3.Row) -> dict:
    state = row["status"]
    info = json.loads(row["result"]) if row["result"] and state in {"succeeded", "failed"} else {}
    if state == "interrupted":
        info["error"] = "应用在任务完成前关闭，请检查已有产物或服务商回执后再决定是否重新发起。"
    return {**info, "job_id": job_id, "status": state, "ok": state not in {"failed", "interrupted"}}


def render_status(job_id: str) -> dict:
    """Project only the local render receipt suitable for a conversation card."""
    from szyg.media_storage import resolve_media_file

    row = _job(job_id)
    try:
        action, project_id, version = (row["signature"] or "").split(":")
        if action != "render" or project_id != str(UUID(project_id)) or int(version) < 1:
            raise ValueError
    except (ValueError, TypeError):
        raise HTTPException(404, "未找到此渲染任务") from None

    payload = _status_payload(job_id, row)
    card = {"job_id": job_id, "project_id": project_id, "revision": int(version),
            "status": row["status"]}
    if not payload["ok"]:
        card["error"] = str(payload.get("error") or "渲染未完成")[:500]
    if row["status"] == "succeeded":
        url = payload.get("url")
        if isinstance(url, str) and url.startswith("/api/media/files/video/"):
            filename = url.removeprefix("/api/media/files/video/")
            if filename.endswith(".mp4"):
                try:
                    path, _ = resolve_media_file("video", filename)
                    if path.is_file():
                        card["url"] = url
                except (OSError, ValueError):
                    pass
        if "url" not in card:
            card["error"] = "成片文件已移除或当前不可访问"
    return card


def _run(job_id: str, operation: Callable[[], dict]):
    with closing(_db()) as db, db:
        db.execute("UPDATE director_jobs SET status='running' WHERE id=?", (job_id,))
    try:
        result = operation()
        state = "failed" if result.get("ok") is False else "succeeded"
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
    except Exception as exc:
        state = "failed"
        encoded = json.dumps({"error": str(exc)[:500] or type(exc).__name__}, ensure_ascii=False)
    with closing(_db()) as db, db:
        db.execute("UPDATE director_jobs SET status=?,result=? WHERE id=?", (state, encoded, job_id))


def submit(request_key: str, signature: str, operation: Callable[[], dict], *,
           result_available: Callable[[dict], bool] | None = None) -> dict:
    with closing(_db()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        _recover(db)
        row = db.execute("SELECT id,signature,status,result FROM director_jobs WHERE request_key=?", (request_key,)).fetchone()
        if row and row["signature"] != signature:
            raise HTTPException(409, "相同请求 ID 已用于不同参数")
        if row and row["status"] == "succeeded" and result_available and not result_available(json.loads(row["result"])):
            # Only the local render cache uses this. Preserve the original receipt and
            # regenerate a removed export; external/paid actions never replay this way.
            db.execute("UPDATE director_jobs SET request_key=NULL WHERE id=?", (row["id"],))
            row = None
        if row:
            job_id = row["id"]
        else:
            active = db.execute("SELECT COUNT(*) FROM director_jobs WHERE status IN ('queued','running')").fetchone()[0]
            if active >= 8:
                raise HTTPException(429, "当前制作队列已满，请稍后再试")
            job_id = str(uuid4())
            db.execute("INSERT INTO director_jobs VALUES (?,?,?,'queued',?,?,NULL)",
                       (job_id, request_key, signature, os.getpid(), psutil.Process().create_time()))
    if not row:
        future = _pool.submit(_run, job_id, operation)
        try:
            future.result(timeout=3)
        except TimeoutError:
            pass
    return status(job_id)
