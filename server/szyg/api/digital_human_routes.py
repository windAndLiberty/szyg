"""Digital presenter creation API."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from szyg.digital_human_service import (
    ASSET_ROLES,
    analyze_inspiration,
    create_render,
    delete_asset,
    delete_inspiration,
    delete_profile,
    delete_project,
    generate_scene_image,
    get_asset,
    get_project,
    get_render,
    list_assets,
    list_inspirations,
    list_profiles,
    list_projects,
    list_renders,
    plan_project,
    public_config,
    refresh_render,
    retry_segment,
    save_asset,
    save_inspiration,
    save_profile,
    save_project,
)
from szyg.integrations.cloud_inference_client import CloudInferenceError

router = APIRouter(prefix="/api/digital-human", tags=["digital-human"])


class ProfilePayload(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    profile_type: Literal["virtual", "real"] = "virtual"
    avatar_asset_ids: list[str] = Field(min_length=1, max_length=10)
    voice_asset_id: str = ""
    cover_asset_id: str = ""
    default_style: str = Field(default="自然、可信的商业口播", max_length=500)
    outfit: str = Field(default="", max_length=300)
    notes: str = Field(default="", max_length=1000)


class InspirationPayload(BaseModel):
    name: str = Field(default="灵感视频素材", max_length=100)
    asset_id: str = ""
    source_url: str = Field(default="", max_length=2000)


class ScenePayload(BaseModel):
    id: str = ""
    spoken_text: str = Field(default="", max_length=3000)
    visual_prompt: str = Field(default="", max_length=3000)
    duration: int = Field(default=5, ge=1, le=30)
    presenter_mode: Literal["full", "pip", "hidden"] = "full"
    visual_mode: Literal["presenter", "full_image", "product_closeup", "integrated", "creative_cutaway"] = "presenter"
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=50)
    transition: str = Field(default="自然衔接", max_length=200)
    subtitle: bool = True
    sound_prompt: str = Field(default="保留清晰自然的人声", max_length=500)


class ProjectPayload(BaseModel):
    name: str = Field(default="未命名数字人作品", max_length=100)
    profile_id: str = ""
    inspiration_ids: list[str] = Field(default_factory=list, max_length=20)
    scenes: list[ScenePayload] = Field(default_factory=list, max_length=30)
    ratio: Literal["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"] = "9:16"
    size: Literal["480p", "720p"] = "720p"
    visual_style: str = Field(default="现代、自然、可信", max_length=500)
    subtitle_enabled: bool = True
    subtitle_style: str = Field(default="清晰简洁", max_length=300)


class PlanPayload(BaseModel):
    instruction: str = Field(default="", max_length=3000)


class SceneImagePayload(BaseModel):
    scene_id: str
    prompt: str = Field(min_length=1, max_length=3000)


def _dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def _raise(exc: Exception) -> None:
    if isinstance(exc, ValueError):
        raise HTTPException(400, str(exc))
    if isinstance(exc, CloudInferenceError):
        raise HTTPException(exc.status_code, str(exc))
    raise HTTPException(500, "操作未完成，请稍后重试")


@router.get("/config")
def config():
    return public_config()


@router.get("/assets")
def assets(profile_id: str = "", project_id: str = ""):
    return {"items": list_assets(profile_id=profile_id, project_id=project_id)}


@router.post("/assets")
async def upload_asset(
    file: UploadFile = File(...),
    role: str = Form(...),
    profile_id: str = Form(""),
    project_id: str = Form(""),
):
    if role not in ASSET_ROLES:
        raise HTTPException(400, "不支持的素材用途")
    if not file.filename:
        raise HTTPException(400, "请选择素材文件")
    try:
        item = save_asset(
            file.filename, file.content_type or "", await file.read(), role,
            profile_id=profile_id, project_id=project_id,
        )
        return {"ok": True, "asset": item}
    except Exception as exc:
        _raise(exc)


@router.get("/assets/{asset_id}")
def read_asset(asset_id: str):
    item = get_asset(asset_id)
    if not item:
        raise HTTPException(404, "素材不存在")
    return FileResponse(str(item["path"]), media_type=str(item.get("content_type") or "application/octet-stream"))


@router.delete("/assets/{asset_id}")
def remove_asset(asset_id: str):
    return {"ok": True, "removed": delete_asset(asset_id)}


@router.get("/profiles")
def profiles():
    return {"items": list_profiles()}


@router.post("/profiles")
def create_profile(payload: ProfilePayload):
    try:
        return save_profile(_dump(payload))
    except Exception as exc:
        _raise(exc)


@router.put("/profiles/{profile_id}")
def update_profile(profile_id: str, payload: ProfilePayload):
    try:
        return save_profile(_dump(payload), profile_id)
    except Exception as exc:
        _raise(exc)


@router.delete("/profiles/{profile_id}")
def remove_profile(profile_id: str):
    return {"ok": True, "removed": delete_profile(profile_id)}


@router.get("/inspirations")
def inspirations():
    return {"items": list_inspirations()}


@router.post("/inspirations/import")
def import_inspiration(payload: InspirationPayload):
    try:
        return save_inspiration(_dump(payload))
    except Exception as exc:
        _raise(exc)


@router.post("/inspirations/{inspiration_id}/analyze")
async def run_inspiration_analysis(inspiration_id: str):
    try:
        return await analyze_inspiration(inspiration_id)
    except Exception as exc:
        _raise(exc)


@router.delete("/inspirations/{inspiration_id}")
def remove_inspiration(inspiration_id: str):
    return {"ok": True, "removed": delete_inspiration(inspiration_id)}


@router.get("/projects")
def projects():
    return {"items": list_projects()}


@router.post("/projects")
def create_project(payload: ProjectPayload):
    try:
        return save_project(_dump(payload))
    except Exception as exc:
        _raise(exc)


@router.get("/projects/{project_id}")
def project(project_id: str):
    item = get_project(project_id)
    if not item:
        raise HTTPException(404, "项目不存在")
    return item


@router.put("/projects/{project_id}")
def update_project(project_id: str, payload: ProjectPayload):
    try:
        return save_project(_dump(payload), project_id)
    except Exception as exc:
        _raise(exc)


@router.delete("/projects/{project_id}")
def remove_project(project_id: str):
    return {"ok": True, "removed": delete_project(project_id)}


@router.post("/projects/{project_id}/plan")
async def project_plan(project_id: str, payload: PlanPayload):
    try:
        return await plan_project(project_id, payload.instruction)
    except Exception as exc:
        _raise(exc)


@router.post("/projects/{project_id}/scene-images")
async def scene_image(project_id: str, payload: SceneImagePayload):
    try:
        return await generate_scene_image(project_id, payload.scene_id, payload.prompt)
    except Exception as exc:
        _raise(exc)


@router.get("/projects/{project_id}/renders")
def project_renders(project_id: str):
    return {"items": list_renders(project_id)}


@router.post("/projects/{project_id}/renders")
async def start_render(project_id: str):
    try:
        return await create_render(project_id)
    except Exception as exc:
        _raise(exc)


@router.get("/renders/{render_id}")
async def render(render_id: str, refresh: bool = True):
    try:
        item = await refresh_render(render_id) if refresh else get_render(render_id)
        if not item:
            raise ValueError("生成任务不存在")
        return item
    except Exception as exc:
        _raise(exc)


@router.post("/renders/{render_id}/segments/{segment_id}/retry")
async def rerun_segment(render_id: str, segment_id: str):
    try:
        return await retry_segment(render_id, segment_id)
    except Exception as exc:
        _raise(exc)
