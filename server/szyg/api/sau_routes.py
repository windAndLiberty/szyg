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
