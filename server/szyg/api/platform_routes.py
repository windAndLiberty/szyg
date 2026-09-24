"""
Platform Automation REST API — 平台自动化独立 REST 端点

对标数创引擎的 HTTP API 层。
让前端 Platforms.vue 可以直接管理平台适配器。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from szyg.publisher import Platform
import asyncio
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/platforms", tags=["platforms"])

# Platform login URLs for Electron embedded browser
PLATFORM_URLS = {
    "douyin": "https://creator.douyin.com",
    "xhs": "https://creator.xiaohongshu.com",
    "kuaishou": "https://creator.kuaishou.com",
    "bilibili": "https://member.bilibili.com",
    "weibo": "https://weibo.com",
}

PLATFORM_DOMAINS = {
    "douyin": "douyin.com",
    "xhs": "xiaohongshu.com",
    "kuaishou": "kuaishou.com",
    "bilibili": "bilibili.com",
    "weibo": "weibo.com",
}

# Risk level & execution mode metadata
PLATFORM_META = {
    "douyin": {
        "risk_level": "high",
        "risk_label": "严格",
        "login_mode": "electron_embedded",
        "publish_mode": "playwright",
        "description": "需 a_bogus 签名，行为模拟要求高",
    },
    "xhs": {
        "risk_level": "high",
        "risk_label": "严格",
        "login_mode": "electron_embedded",
        "publish_mode": "playwright",
        "description": "内容风控严格，建议后端发布",
    },
    "kuaishou": {
        "risk_level": "medium",
        "risk_label": "中等",
        "login_mode": "electron_embedded",
        "publish_mode": "playwright",
        "description": "中等风控",
    },
    "bilibili": {
        "risk_level": "medium",
        "risk_label": "中等",
        "login_mode": "electron_embedded",
        "publish_mode": "playwright",
        "description": "动态发布较宽松",
    },
    "weibo": {
        "risk_level": "low",
        "risk_label": "宽松",
        "login_mode": "electron_embedded",
        "publish_mode": "playwright",
        "description": "相对宽松",
    },
    "wechat_mp": {
        "risk_level": "n/a",
        "risk_label": "桌面客户端",
        "login_mode": "uia",
        "publish_mode": "uia",
        "description": "通过 Windows UIA 控制微信桌面版",
    },
}


def _parse_platform(platform: str) -> Platform:
    aliases = {
        "xiaohongshu": "xhs",
        "redbook": "xhs",
        "little-red-book": "xhs",
    }
    return Platform(aliases.get(platform, platform))


@router.get("")
async def platform_list():
    """列出所有已注册平台的状态"""
    try:
        from szyg.platforms.registry import get_registry
        registry = get_registry()
        platforms = registry.list_platforms()

        # 增强: 附加 session 信息 + 风控元数据
        from szyg.platforms.session_manager import get_session_manager
        mgr = get_session_manager()
        for p in platforms:
            pid = p["id"]
            try:
                plat = Platform(pid)
                p["session"] = mgr.get_info(plat)
            except Exception:
                p["session"] = {"has_session": False}
            # 附加风控与执行方式元数据
            meta = PLATFORM_META.get(pid, {})
            p["meta"] = meta

        return {"status": "ok", "platforms": platforms, "total": len(platforms)}
    except Exception as e:
        return {"status": "error", "error": str(e), "platforms": []}


@router.get("/{platform}")
async def platform_detail(platform: str):
    """获取单个平台详细信息"""
    try:
        p = _parse_platform(platform)
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
            "status": "ok",
            "platform": platform,
            "registered": True,
            "adapter": type(adapter).__name__,
            "state": adapter.state.value,
            "login": login.model_dump(),
            "session": session,
            "meta": PLATFORM_META.get(platform, {}),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


# Background login tasks (keyed by platform)
_login_tasks: dict[str, asyncio.Task] = {}

@router.post("/{platform}/login")
async def platform_login(platform: str, timeout: int = 600):
    """触发平台扫码登录。

    立即返回 pending 状态，登录操作在后台运行。
    前端轮询 GET /{platform}/status 检查是否完成。

    Query params:
        timeout: 登录等待超时秒数 (默认 600)
    """
    try:
        p = _parse_platform(platform)
    except ValueError:
        raise HTTPException(400, f"不支持的平台: {platform}")

    # Cancel existing login task for this platform
    existing = _login_tasks.pop(platform, None)
    if existing and not existing.done():
        existing.cancel()

    try:
        from szyg.platforms.registry import get_registry
        registry = get_registry()
        adapter = await registry.get(p)

        async def _do_login():
            try:
                result = await adapter.login(timeout=timeout)
                logger.info(f"[{platform}] 登录完成: {result.is_logged_in}")
                return result
            except asyncio.CancelledError:
                logger.info(f"[{platform}] 登录任务被取消")
                raise
            except Exception as e:
                logger.error(f"[{platform}] 登录后台任务异常: {e}")
                from szyg.platforms.base import LoginStatus
                return LoginStatus(is_logged_in=False, message=str(e)[:200])

        task = asyncio.create_task(_do_login())
        _login_tasks[platform] = task

        # Clean up task ref when done
        task.add_done_callback(lambda t: _login_tasks.pop(platform, None))

        return {
            "ok": True,
            "platform": platform,
            "status": "pending",
            "message": f"登录任务已启动 — 请在 {timeout}s 内于浏览器中完成登录",
            "login_url": PLATFORM_URLS.get(platform, ""),
        }
    except Exception as e:
        raise HTTPException(500, str(e))



@router.post("/{platform}/publish-preflight")
async def platform_publish_preflight(
    platform: str, title: str, body: str = "",
    tags: str = "", media_urls: str = "",
    content_type: str = "post"
):
    try:
        p = _parse_platform(platform)
    except ValueError:
        raise HTTPException(400, f"Unsupported platform: {platform}")

    allowed_types = {"post", "article", "video", "image", "video_script"}
    if content_type not in allowed_types:
        content_type = "post"

    from szyg.publisher import ContentType
    from szyg.platforms.base import PublishRequest
    from szyg.platforms.registry import get_registry

    ct_map = {
        "post": ContentType.POST,
        "article": ContentType.ARTICLE,
        "video": ContentType.VIDEO_SCRIPT,
        "video_script": ContentType.VIDEO_SCRIPT,
        "image": ContentType.IMAGE_POST,
    }
    request = PublishRequest(
        title=title,
        body=body,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        media_urls=[u.strip() for u in media_urls.split(",") if u.strip()],
        content_type=ct_map.get(content_type, ContentType.POST),
    )

    registry = get_registry()
    if not registry.is_registered(p):
        raise HTTPException(404, f"Platform not registered: {platform}")

    adapter = await registry.get(p)
    return await adapter.preflight_publish(request)


@router.post("/{platform}/publish")
async def platform_publish_direct(
    platform: str, title: str, body: str = "",
    tags: str = "", media_urls: str = "",
    content_type: str = "post",
    headless: bool = True,
):
    """直接在平台发布内容 (一步: 创建+审核+发布)。

    Args:
        platform: 平台ID (douyin/xhs/bilibili/kuaishou/wechat_mp)
        title: 标题
        body: 正文
        tags: 标签，逗号分隔
        media_urls: 媒体文件URL，逗号分隔 (图片/视频)
        content_type: 内容类型 (post/article/video/image)
    """
    try:
        p = _parse_platform(platform)
    except ValueError:
        raise HTTPException(400, f"不支持的平台: {platform}")

    # Validate content_type
    allowed_types = {"post", "article", "video", "image"}
    if content_type not in allowed_types:
        content_type = "video" if content_type == "video_script" else "post"

    from szyg.publisher import get_publisher, ContentType
    pub = get_publisher()

    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    url_list = [u.strip() for u in media_urls.split(",")] if media_urls else []

    # Map to ContentType
    ct_map = {
        "post": ContentType.POST,
        "article": ContentType.ARTICLE,
        "video": ContentType.VIDEO_SCRIPT,
        "image": ContentType.IMAGE_POST,
    }

    content = pub.create(
        title=title, body=body, platforms=[p],
        tags=tag_list, media_urls=url_list,
        content_type=ct_map.get(content_type, ContentType.POST),
        extra={"headless": headless},
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


@router.get("/{platform}/status/{post_id}")
async def platform_post_status(platform: str, post_id: str):
    """查询已发布内容在平台上的实时数据（播放量/点赞/评论等）。"""
    try:
        p = _parse_platform(platform)
    except ValueError:
        raise HTTPException(400, f"不支持的平台: {platform}")

    if not post_id or len(post_id) < 5:
        raise HTTPException(400, "post_id 无效")

    try:
        from szyg.platforms.registry import get_registry
        registry = get_registry()
        adapter = await registry.get(p)
        result = await adapter.get_status(post_id)
        return result
    except Exception as e:
        raise HTTPException(500, str(e)[:200])



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

        return {"status": "ok", "platforms": results}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/{platform}/url")
async def platform_url(platform: str):
    """获取平台登录/创作者中心 URL（供 Electron 内嵌浏览器使用）"""
    try:
        p = _parse_platform(platform)
    except ValueError:
        raise HTTPException(400, f"不支持的平台: {platform}")
    url = PLATFORM_URLS.get(platform)
    if not url:
        raise HTTPException(404, f"平台 {platform} 未配置 URL")
    return {"platform": platform, "url": url}


@router.post("/{platform}/sync-cookies")
async def platform_sync_cookies(platform: str, payload: dict):
    """
    接收 Electron 传来的 Cookie，转换为 Playwright storage_state 格式保存。
    这是 Electron 套壳浏览器与后端 Playwright 自动化之间的 Cookie 桥接接口。
    """
    try:
        p = _parse_platform(platform)
    except ValueError:
        raise HTTPException(400, f"不支持的平台: {platform}")

    from szyg.platforms.session_manager import get_session_manager
    mgr = get_session_manager()

    cookies = payload.get("cookies", [])
    target_domain = PLATFORM_DOMAINS.get(platform, "")

    # Convert Chrome/Electron cookie format → Playwright storage_state format
    def convert_cookie(c: dict) -> dict:
        # Electron cookie format: name, value, domain, path, secure, httpOnly,
        # sameSite, expirationDate (seconds since epoch, float)
        expires = c.get("expirationDate", -1)
        # Playwright expects expires as seconds since epoch (same as Electron)
        return {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ""),
            "path": c.get("path", "/"),
            "expires": int(expires) if expires and expires > 0 else -1,
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", False),
            "sameSite": c.get("sameSite", "Lax"),
        }

    filtered = [
        convert_cookie(c)
        for c in cookies
        if target_domain and target_domain in c.get("domain", "")
    ]

    # Also include session cookies without domain filter if empty
    if not filtered:
        filtered = [convert_cookie(c) for c in cookies]

    storage_state = {
        "cookies": filtered,
        "origins": []
    }

    mgr.save_raw(p, storage_state)
    logger.info(f"[{platform}] Cookie synced from Electron ({len(filtered)} cookies)")

    return {
        "success": True,
        "platform": platform,
        "cookie_count": len(filtered),
        "valid": mgr.is_valid(p),
    }


@router.delete("/{platform}/sessions")
async def platform_unbind(platform: str):
    """删除平台登录态（解绑账号）"""
    try:
        p = _parse_platform(platform)
    except ValueError:
        raise HTTPException(400, f"不支持的平台: {platform}")

    from szyg.platforms.session_manager import get_session_manager
    mgr = get_session_manager()

    mgr.invalidate(p)
    mgr.delete_account_meta(p)
    logger.info(f"[{platform}] 登录态已清除（解绑）")

    return {"ok": True, "platform": platform}
