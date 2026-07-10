"""social-auto-upload API routes — exposes SAU adapter to the frontend."""

import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/sau", tags=["social-auto-upload"])


class SAUUploadVideo(BaseModel):
    platform: str
    file_path: str
    title: str
    desc: str = ""
    tags: list[str] = []
    thumbnail_path: Optional[str] = None
    schedule: Optional[str] = None
    headless: bool = True


class SAUUploadNote(BaseModel):
    platform: str
    image_paths: list[str]
    title: str
    note: str = ""
    tags: list[str] = []
    schedule: Optional[str] = None
    headless: bool = True


@router.get("/platforms")
async def list_platforms():
    """列出 sau 支持的所有平台及登录状态。"""
    from szyg.integrations.social_auto_upload_adapter import get_sau_adapter
    adapter = get_sau_adapter()
    return {"platforms": adapter.list_platforms()}


@router.post("/upload-video")
async def upload_video(body: SAUUploadVideo):
    """上传视频到指定平台。"""
    from szyg.integrations.social_auto_upload_adapter import get_sau_adapter
    adapter = get_sau_adapter()
    sched = datetime.strptime(body.schedule, "%Y-%m-%d %H:%M") if body.schedule else None
    result = await adapter.upload_video(
        platform=body.platform,
        file_path=body.file_path,
        title=body.title,
        desc=body.desc,
        tags=body.tags,
        thumbnail_path=body.thumbnail_path,
        schedule=sched,
        headless=body.headless,
    )
    return result


@router.post("/upload-video-async")
async def upload_video_async(body: SAUUploadVideo):
    """Create an observable ExecutionRun for a background video upload."""
    from szyg.execution_kernel import get_execution_kernel

    payload = {
        "platform": body.platform,
        "file_path": body.file_path,
        "title": body.title,
        "desc": body.desc,
        "tags": body.tags,
        "thumbnail_path": body.thumbnail_path,
        "schedule": body.schedule,
        "headless": body.headless,
    }
    kernel = get_execution_kernel()
    run = kernel.create_sau_upload_video_run(payload)
    task = kernel.sau_compatible_task(run)
    return {"ok": True, "task_id": run["id"], "execution_id": run["id"], "task": task, "run": run}


@router.post("/upload-note")
async def upload_note(body: SAUUploadNote):
    """上传图文到指定平台。"""
    from szyg.integrations.social_auto_upload_adapter import get_sau_adapter
    adapter = get_sau_adapter()
    sched = datetime.strptime(body.schedule, "%Y-%m-%d %H:%M") if body.schedule else None
    result = await adapter.upload_note(
        platform=body.platform,
        image_paths=body.image_paths,
        title=body.title,
        note=body.note,
        tags=body.tags,
        schedule=sched,
        headless=body.headless,
    )
    return result


@router.post("/upload-note-async")
async def upload_note_async(body: SAUUploadNote):
    """Create an observable ExecutionRun for a background note upload."""
    from szyg.execution_kernel import get_execution_kernel

    payload = {
        "platform": body.platform,
        "image_paths": body.image_paths,
        "title": body.title,
        "note": body.note,
        "tags": body.tags,
        "schedule": body.schedule,
        "headless": body.headless,
    }
    kernel = get_execution_kernel()
    run = kernel.create_sau_upload_note_run(payload)
    task = kernel.sau_compatible_task(run)
    return {"ok": True, "task_id": run["id"], "execution_id": run["id"], "task": task, "run": run}


@router.get("/tasks")
async def list_sau_tasks(limit: int = Query(50, ge=1, le=200)):
    """List recent social-auto-upload compatible background tasks."""
    from szyg.execution_kernel import get_execution_kernel

    tasks = get_execution_kernel().sau_compatible_tasks(limit=limit)
    try:
        from szyg.integrations.sau_task_manager import get_sau_task_manager
        seen = {task.get("id") for task in tasks}
        for item in get_sau_task_manager().list_tasks(limit=limit):
            if item.get("id") not in seen:
                tasks.append(item)
    except Exception:
        pass
    return {"tasks": tasks[:limit]}


@router.get("/tasks/{task_id}")
async def get_sau_task(task_id: str):
    """Get one social-auto-upload background task."""
    from szyg.execution_kernel import get_execution_kernel

    kernel = get_execution_kernel()
    task = next((item for item in kernel.sau_compatible_tasks(limit=200) if item.get("id") == task_id), None)
    if not task:
        try:
            from szyg.integrations.sau_task_manager import get_sau_task_manager
            task = get_sau_task_manager().get_task(task_id)
        except Exception:
            task = None
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.get("/check-login/{platform}")
async def check_login(platform: str):
    """检查平台登录状态。"""
    from szyg.integrations.social_auto_upload_adapter import get_sau_adapter
    adapter = get_sau_adapter()
    return await adapter.check_login(platform)


@router.post("/login/{platform}")
async def login(platform: str, headless: bool = Query(False)):
    """触发平台扫码登录。"""
    from szyg.integrations.social_auto_upload_adapter import get_sau_adapter
    adapter = get_sau_adapter()
    return await adapter.login(platform, headless=headless)
