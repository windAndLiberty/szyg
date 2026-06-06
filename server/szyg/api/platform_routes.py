"""
Platform Automation REST API — 平台自动化独立 REST 端点

对标数创引擎的 HTTP API 层。
让前端 Platforms.vue 可以直接管理平台适配器。
"""
from fastapi import APIRouter, HTTPException
from szyg.publisher import Platform
import asyncio
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/platforms", tags=["platforms"])


@router.get("")
async def platform_list():
    """列出所有已注册平台的状态"""
    try:
        from szyg.platforms.registry import get_registry
        registry = get_registry()
        platforms = registry.list_platforms()

        # 增强: 附加 session 信息
        from szyg.platforms.session_manager import get_session_manager
        mgr = get_session_manager()
        for p in platforms:
            pid = p["id"]
            try:
                plat = Platform(pid)
                p["session"] = mgr.get_info(plat)
            except Exception:
                p["session"] = {"has_session": False}

        return {"platforms": platforms, "total": len(platforms)}
    except Exception as e:
        return {"error": str(e), "platforms": []}


@router.get("/{platform}")
async def platform_detail(platform: str):
    """获取单个平台详细信息"""
    try:
        p = Platform(platform)
    except ValueError:
        raise HTTPException(400, f"不支持的平台: {platform}")

    try:
        from szyg.platforms.registry import get_registry
        from szyg.platforms.session_manager import get_session_manager

        registry = get_registry()
        mgr = get_session_manager()

        if not registry.is_registered(p):
            return {"platform": platform, "registered": False}

        adapter = await registry.get(p)
        login = await adapter.check_login()
        session = mgr.get_info(p)

        return {
            "platform": platform,
            "registered": True,
            "adapter": type(adapter).__name__,
            "state": adapter.state.value,
            "login": login.model_dump(),
            "session": session,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/{platform}/login")
async def platform_login(platform: str):
    """触发平台扫码登录"""
    try:
        p = Platform(platform)
    except ValueError:
        raise HTTPException(400, f"不支持的平台: {platform}")

    try:
        from szyg.platforms.registry import get_registry
        registry = get_registry()
        adapter = await registry.get(p)
        status = await adapter.login()
        return status.model_dump()
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/{platform}/publish")
async def platform_publish_direct(
    platform: str, title: str, body: str = "",
    tags: str = "", media_urls: str = ""
):
    """直接在平台发布内容 (一步: 创建+审核+发布)"""
    try:
        p = Platform(platform)
    except ValueError:
        raise HTTPException(400, f"不支持的平台: {platform}")

    from szyg.publisher import get_publisher
    pub = get_publisher()

    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    url_list = [u.strip() for u in media_urls.split(",")] if media_urls else []

    content = pub.create(
        title=title, body=body, platforms=[p],
        tags=tag_list, media_urls=url_list,
    )
    pub.submit_review(content.id)
    pub.approve(content.id)

    try:
        result = await pub.publish_async(content.id, p)
        return {
            "success": result.status == "success" if result else False,
            "content_id": content.id,
            "platform": platform,
            "platform_post_id": result.platform_post_id if result else "",
            "platform_post_url": result.platform_post_url if result else "",
            "error": result.error_msg if result else "",
        }
    except Exception as e:
        return {"success": False, "content_id": content.id, "error": str(e)}


@router.get("/logs/all")
async def platform_logs(limit: int = 50):
    """获取所有平台的发布日志"""
    from szyg.publisher import get_publisher
    pub = get_publisher()
    return pub.get_logs(limit)


@router.get("/health/all")
async def platform_health():
    """所有平台健康检查"""
    try:
        from szyg.platforms.registry import get_registry
        registry = get_registry()
        platforms = registry.list_platforms()
        results = {}

        for plat_info in platforms:
            pid = plat_info["id"]
            try:
                p = Platform(pid)
                if registry.is_registered(p):
                    adapter = await registry.get(p)
                    login = await adapter.check_login()
                    results[pid] = {
                        "state": plat_info["state"],
                        "is_logged_in": login.is_logged_in,
                        "account_name": login.account_name,
                    }
                else:
                    results[pid] = {"state": "not_registered"}
            except Exception as e:
                results[pid] = {"state": "error", "error": str(e)}

        return results
    except Exception as e:
        return {"error": str(e)}
