"""Content Publisher API routes"""
from fastapi import APIRouter, HTTPException, Depends
from szyg.publisher import (get_publisher, Content, ContentType, ContentStatus,
                             Platform, PublishRecord)
from szyg.auth import User
from szyg.api.auth_routes import require_admin, optional_user

router = APIRouter(prefix="/api/publisher", tags=["publisher"])


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
    p = Platform(platform) if platform else None
    try:
        rec = get_publisher().publish_now(content_id, p)
        return {"ok": True, "record": rec}
    except ValueError as e:
        raise HTTPException(404, str(e))


# AI Generate
@router.post("/ai-generate", response_model=Content)
async def ai_generate(topic: str, agent_id: str = "copywriter", content_type: str = "post"):
    return get_publisher().ai_generate(topic, agent_id, content_type)


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
