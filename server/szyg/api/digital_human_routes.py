"""Digital presenter creation API."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from szyg.digital_human_service import ASSET_ROLES, create_render, delete_asset, get_asset, public_config, save_asset

router = APIRouter(prefix="/api/digital-human", tags=["digital-human"])


class DigitalHumanCreateRequest(BaseModel):
    script: str = Field(min_length=1, max_length=3000)
    asset_ids: list[str] = Field(min_length=1, max_length=50)
    asset_aliases: dict[str, str] = Field(default_factory=dict)
    duration: int = Field(default=15, ge=4, le=30)
    size: Literal["720p", "1080p", "4K"] = "1080p"
    ratio: Literal["9:16", "16:9", "1:1"] = "9:16"
    native_audio: bool = True
    style: str = Field(default="professional", max_length=300)
    avatar_position: Literal["center", "left", "right", "full"] = "center"
    background_prompt: str = ""


@router.get("/config")
async def get_digital_human_config():
    return public_config()


@router.post("/assets")
async def upload_digital_human_asset(file: UploadFile = File(...), role: str = Form(...)):
    if role not in ASSET_ROLES:
        raise HTTPException(400, "不支持的素材用途")
    if not file.filename:
        raise HTTPException(400, "请选择素材文件")
    try:
        return {"ok": True, "asset": save_asset(file.filename, file.content_type or "", await file.read(), role)}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/assets/{asset_id}")
async def digital_human_asset(asset_id: str):
    item = get_asset(asset_id)
    if not item:
        raise HTTPException(404, "素材不存在")
    return FileResponse(str(item["path"]), media_type=str(item.get("content_type") or "application/octet-stream"))


@router.delete("/assets/{asset_id}")
async def remove_digital_human_asset(asset_id: str):
    return {"ok": True, "removed": delete_asset(asset_id)}


@router.post("/create")
async def create_digital_human(req: DigitalHumanCreateRequest):
    try:
        payload = req.model_dump()
    except AttributeError:
        payload = req.dict()
    try:
        return await create_render(payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        raise HTTPException(500, "数字人口播提交失败，请稍后重试")
