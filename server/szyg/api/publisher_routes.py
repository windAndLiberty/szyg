"""Content Publisher API routes"""
from fastapi import APIRouter, HTTPException, Depends
from szyg.publisher import (get_publisher, Content, ContentType, ContentStatus,
                             Platform, PublishRecord)
from szyg.auth import User
from szyg.api.auth_routes import require_admin, optional_user

router = APIRouter(prefix="/api/publisher", tags=["publisher"])


def _parse_platform(platform: str) -> Platform:
    aliases = {
        "xiaohongshu": "xhs",
        "redbook": "xhs",
        "little-red-book": "xhs",
    }
    return Platform(aliases.get(platform, platform))


@router.get("/contents", response_model=list[Content])
async def list_contents(status: str = "", content_type: str = "", search: str = "", limit: int = 50):
    return get_publisher().list_contents(status, content_type, search, limit)


@router.get("/contents/{content_id}", response_model=Content)
async def get_content(content_id: str):
    c = get_publisher().get_content(content_id)
    if not c:
        raise HTTPException(404, "内容不存在")
    return c


@router.post("/contents", response_model=Content)
async def create_content(title: str, body: str = "", content_type: str = "post",
                          platforms: str = "all", tags: str = "",
                          user: User = Depends(optional_user)):
    plat_list = [Platform(p) for p in platforms.split(",")] if platforms != "all" else [Platform.ALL]
    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    return get_publisher().create(
        title=title, body=body, content_type=content_type,
        platforms=plat_list, tags=tag_list,
        created_by=user.username if user else "admin",
    )


@router.put("/contents/{content_id}", response_model=Content)
async def update_content(content_id: str, title: str = "", body: str = "",
                          platforms: str = "", tags: str = ""):
    kwargs = {}
    if title: kwargs["title"] = title
    if body: kwargs["body"] = body
    if platforms:
        kwargs["platforms"] = [Platform(p) for p in platforms.split(",")]
    if tags: kwargs["tags"] = [t.strip() for t in tags.split(",")]
    c = get_publisher().update(content_id, **kwargs)
    if not c: raise HTTPException(404, "内容不存在")
    return c


@router.delete("/contents/{content_id}")
async def delete_content(content_id: str, admin: User = Depends(require_admin)):
    if get_publisher().delete(content_id):
        return {"ok": True}
    raise HTTPException(404, "内容不存在")


# Review Pipeline
@router.post("/contents/{content_id}/submit")
async def submit_review(content_id: str):
    c = get_publisher().submit_review(content_id)
    if not c: raise HTTPException(404, "内容不存在")
    return c


@router.post("/contents/{content_id}/approve")
async def approve_content(content_id: str, comment: str = "", admin: User = Depends(require_admin)):
    c = get_publisher().approve(content_id, comment)
    if not c: raise HTTPException(404, "内容不存在")
    return c


@router.post("/contents/{content_id}/reject")
async def reject_content(content_id: str, comment: str = "", admin: User = Depends(require_admin)):
    c = get_publisher().reject(content_id, comment)
    if not c: raise HTTPException(404, "内容不存在")
    return c


# Schedule
@router.post("/contents/{content_id}/schedule")
async def schedule_content(content_id: str, scheduled_at: str):
    c = get_publisher().schedule(content_id, scheduled_at)
    if not c: raise HTTPException(404, "内容不存在")
    return c


# Publish
@router.post("/contents/{content_id}/publish")
async def publish_content(content_id: str, platform: str = ""):
    p = _parse_platform(platform) if platform else None
    try:
        rec = await get_publisher().publish_async(content_id, p)
        return {"ok": True, "record": rec}
    except ValueError as e:
        raise HTTPException(404, str(e))


# AI Generate
@router.post("/ai-generate", response_model=Content)
async def ai_generate(topic: str, agent_id: str = "copywriter", content_type: str = "post"):
    return await get_publisher().ai_generate(topic, agent_id, content_type)


# Calendar
@router.get("/calendar")
async def calendar(month: str = ""):
    return get_publisher().get_calendar(month)


# Stats
@router.get("/stats")
async def stats():
    return get_publisher().get_stats()


# Logs
@router.get("/logs")
async def logs(limit: int = 50):
    return get_publisher().get_logs(limit)


# ── Platform Status (v2: 平台适配器状态) ───────────────────

@router.get("/platforms")
async def platform_list():
    """列出所有已注册的平台适配器及其状态"""
    try:
        from szyg.platforms.registry import get_registry
        registry = get_registry()
        return registry.list_platforms()
    except Exception as e:
        return {"error": str(e), "platforms": []}


@router.get("/platforms/{platform}/status")
async def platform_status(platform: str):
    """查询指定平台的登录状态"""
    try:
        from szyg.platforms.registry import get_adapter
        p = _parse_platform(platform)
        adapter = await get_adapter(p)
        status = await adapter.check_login()
        return status.model_dump()
    except ValueError as e:
        raise HTTPException(400, f"不支持的平台: {platform}")
    except Exception as e:
        return {"is_logged_in": False, "message": str(e)}


@router.post("/platforms/{platform}/login")
async def platform_login(platform: str):
    """触发平台登录 (打开浏览器等待扫码)"""
    try:
        from szyg.platforms.registry import get_adapter
        p = _parse_platform(platform)
        adapter = await get_adapter(p)
        status = await adapter.login()
        return status.model_dump()
    except ValueError as e:
        raise HTTPException(400, f"不支持的平台: {platform}")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/platforms/{platform}/sessions")
async def platform_session_info(platform: str):
    """查询平台登录态详细信息"""
    try:
        from szyg.platforms.session_manager import get_session_manager
        p = _parse_platform(platform)
        mgr = get_session_manager()
        return mgr.get_info(p)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/platforms/{platform}/sessions")
async def platform_logout(platform: str):
    """清除平台登录态"""
    try:
        from szyg.platforms.session_manager import get_session_manager
        p = _parse_platform(platform)
        mgr = get_session_manager()
        mgr.invalidate(p)
        return {"ok": True, "message": f"{platform} 登录态已清除"}
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── Materials (素材库) ───────────────────────────────────────

import json
from pathlib import Path
from szyg.data_path import DATA_DIR
from fastapi import File, UploadFile
from szyg.media_storage import get_media_output_dir, infer_media_kind, media_url_for_path

_MATERIALS_FILE = DATA_DIR / "materials.json"


def _load_materials() -> list:
    if _MATERIALS_FILE.exists():
        return json.loads(_MATERIALS_FILE.read_text(encoding="utf-8"))
    return []


def _save_materials(data: list):
    _MATERIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _MATERIALS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _material_type_for_kind(kind: str) -> str:
    return "text" if kind == "document" else kind


def _scan_generated_materials() -> list[dict]:
    items: list[dict] = []
    for kind in ("image", "video", "audio", "document"):
        root = get_media_output_dir(kind)  # type: ignore[arg-type]
        if not root.exists():
            continue
        for path in root.iterdir():
            if not path.is_file():
                continue
            actual_kind = infer_media_kind(path)
            if kind != "document" and actual_kind != kind:
                continue
            stat = path.stat()
            items.append({
                "id": f"generated:{kind}:{path.name}",
                "name": path.name,
                "type": _material_type_for_kind(actual_kind),
                "tags": ["AI生成"],
                "platform": "all",
                "url": media_url_for_path(path),
                "path": str(path.resolve()),
                "size": stat.st_size,
                "created_at": __import__("datetime").datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "source": "generated",
            })
    return items


@router.get("/materials")
async def list_materials(mtype: str = "", platform: str = ""):
    items = [*(_load_materials()), *_scan_generated_materials()]
    if mtype:
        items = [m for m in items if m.get("type") == mtype]
    if platform and platform != "all":
        items = [m for m in items if m.get("platform") in (platform, "all")]
    items.sort(key=lambda item: item.get("created_at", item.get("createdAt", "")), reverse=True)
    return {"items": items, "materials": items, "total": len(items)}


@router.post("/materials")
async def create_material(body: dict):
    items = _load_materials()
    import uuid
    item = {
        "id": str(uuid.uuid4())[:8],
        "name": body.get("name", ""),
        "type": body.get("type", "document"),
        "tags": body.get("tags", []),
        "platform": body.get("platform", "all"),
        "url": body.get("url", ""),
        "created_at": __import__("datetime").datetime.now().isoformat(),
    }
    items.append(item)
    _save_materials(items)
    return item


@router.post("/materials/upload")
async def upload_material(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "No file provided")
    filename = Path(file.filename).name
    kind = infer_media_kind(filename)
    output_dir = get_media_output_dir(kind)
    path = output_dir / filename
    if path.exists():
        stem = path.stem
        suffix = path.suffix
        stamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
        path = output_dir / f"{stem}_{stamp}{suffix}"
    content = await file.read()
    path.write_bytes(content)
    item = {
        "id": f"generated:{kind}:{path.name}",
        "name": path.name,
        "type": _material_type_for_kind(kind),
        "tags": ["上传"],
        "platform": "all",
        "url": media_url_for_path(path),
        "path": str(path.resolve()),
        "size": path.stat().st_size,
        "created_at": __import__("datetime").datetime.now().isoformat(),
        "source": "upload",
    }
    return {"ok": True, "material": item}


@router.delete("/materials/{material_id}")
async def delete_material(material_id: str):
    items = _load_materials()
    items = [m for m in items if m.get("id") != material_id]
    _save_materials(items)
    return {"ok": True}


# ── Content Assets & Copy Library ────────────────────────────

_CONTENT_ASSETS_FILE = DATA_DIR / "content_assets.json"
_COPY_LIBRARY_FILE = DATA_DIR / "copy_library.json"


def _load_json_file(path: Path) -> list:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def _save_json_file(path: Path, data: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("/content-assets")
async def list_content_assets():
    items = _load_json_file(_CONTENT_ASSETS_FILE)
    return {"items": items, "total": len(items)}


@router.post("/content-assets")
async def create_content_asset(body: dict):
    items = _load_json_file(_CONTENT_ASSETS_FILE)
    import uuid
    item = {
        "id": str(uuid.uuid4())[:8],
        "name": body.get("name", ""),
        "type": body.get("type", "content"),
        "platform": body.get("platform", "all"),
        "status": body.get("status", "draft"),
        "created_at": __import__("datetime").datetime.now().isoformat(),
    }
    items.append(item)
    _save_json_file(_CONTENT_ASSETS_FILE, items)
    return item


@router.get("/copy-library")
async def list_copy_library():
    items = _load_json_file(_COPY_LIBRARY_FILE)
    return {"items": items, "total": len(items)}


@router.post("/copy-library")
async def create_copy_entry(body: dict):
    items = _load_json_file(_COPY_LIBRARY_FILE)
    import uuid
    item = {
        "id": str(uuid.uuid4())[:8],
        "title": body.get("title", ""),
        "content": body.get("content", ""),
        "tags": body.get("tags", []),
        "created_at": __import__("datetime").datetime.now().isoformat(),
    }
    items.append(item)
    _save_json_file(_COPY_LIBRARY_FILE, items)
    return item
