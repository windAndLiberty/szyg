#!/usr/bin/env python3
"""MCP Server: Platform Automation — 平台自动化工具

对标数创引擎 core/client.pyd 的 Api 类集中调度模式。
提供 8 个 MCP 工具，让 Hermes Agent 可以调度抖音/小红书/微信自动发布。
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from szyg.mcp_server import MCPServer

server = MCPServer(
    "szyg-platforms",
    "Multi-platform automation: Douyin, Xiaohongshu, WeChat publishing"
)


@server.tool("platform_list", "列出所有已注册平台适配器及其状态")
def platform_list():
    """返回每个平台的 id、adapter、state、是否已初始化"""
    from szyg.platforms.registry import get_registry
    registry = get_registry()
    return registry.list_platforms()


@server.tool("platform_status", "查询指定平台的登录状态和账号信息")
def platform_status(platform: str):
    """返回 is_logged_in, account_name, cookie_valid_until, message"""
    import asyncio
    from szyg.publisher import Platform

    try:
        p = Platform(platform)
    except ValueError:
        return {"error": f"不支持的平台: {platform}，可用: douyin, xhs, wechat_mp"}

    try:
        from szyg.platforms.registry import get_registry
        registry = get_registry()
        if not registry.is_registered(p):
            return {"platform": platform, "is_logged_in": False,
                    "message": f"平台 '{platform}' 适配器未注册"}

        async def _check():
            adapter = await registry.get(p)
            status = await adapter.check_login()
            return status.model_dump()
        return asyncio.run(_check())
    except Exception as e:
        return {"platform": platform, "is_logged_in": False, "message": str(e)}


@server.tool("platform_login", "触发平台扫码登录 (需要在Windows桌面操作)")
def platform_login(platform: str):
    """打开浏览器/微信窗口等待用户扫码登录。返回登录结果。"""
    import asyncio
    from szyg.publisher import Platform

    try:
        p = Platform(platform)
    except ValueError:
        return {"error": f"不支持的平台: {platform}"}

    try:
        from szyg.platforms.registry import get_registry
        registry = get_registry()

        async def _login():
            adapter = await registry.get(p)
            status = await adapter.login()
            return status.model_dump()
        return asyncio.run(_login())
    except Exception as e:
        return {"platform": platform, "success": False, "message": str(e)}


@server.tool("platform_publish", "通过内容ID发布到指定平台 (使用已有content)")
def platform_publish(platform: str, content_id: str):
    """从publisher数据库取content并发布。返回发布结果。"""
    import asyncio
    from szyg.publisher import get_publisher, Platform

    try:
        p = Platform(platform)
    except ValueError:
        return {"error": f"不支持的平台: {platform}"}

    pub = get_publisher()
    content = pub.get_content(content_id)
    if not content:
        return {"error": f"内容 {content_id} 不存在"}

    try:
        async def _pub():
            result = await pub.publish_async(content_id, p)
            return {
                "success": result.status == "success" if result else False,
                "platform": platform,
                "content_id": content_id,
                "title": content.title,
                "platform_post_id": result.platform_post_id if result else "",
                "error": result.error_msg if result else "",
            }
        return asyncio.run(_pub())
    except Exception as e:
        return {"error": str(e), "platform": platform, "content_id": content_id}


@server.tool("platform_publish_direct", "直接创建内容并发布到指定平台")
def platform_publish_direct(platform: str, title: str, body: str = "",
                             tags: str = "", media_urls: str = ""):
    """
    一步完成: 创建content → 发布到指定平台。
    适合 Hermes Agent 快速执行发布任务。

    Args:
        platform: 目标平台 (douyin, xhs, wechat_mp)
        title: 标题
        body: 正文内容
        tags: 逗号分隔的标签
        media_urls: 逗号分隔的图片/视频URL
    """
    import asyncio
    from szyg.publisher import get_publisher, Platform

    try:
        p = Platform(platform)
    except ValueError:
        return {"error": f"不支持的平台: {platform}"}

    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    url_list = [u.strip() for u in media_urls.split(",")] if media_urls else []

    pub = get_publisher()
    content = pub.create(
        title=title, body=body, platforms=[p],
        tags=tag_list, media_urls=url_list,
    )

    pub.submit_review(content.id)
    pub.approve(content.id)

    try:
        async def _pub():
            result = await pub.publish_async(content.id, p)
            return {
                "success": result.status == "success" if result else False,
                "platform": platform,
                "content_id": content.id,
                "title": title,
                "platform_post_id": result.platform_post_id if result else "",
                "platform_post_url": result.platform_post_url if result else "",
                "error": result.error_msg if result else "",
            }
        return asyncio.run(_pub())
    except Exception as e:
        return {"error": str(e), "content_id": content.id}


@server.tool("platform_sessions", "查看指定平台或所有平台的登录态详情")
def platform_sessions(platform: str = ""):
    """返回 cookie 数量、有效期、本地 session 文件信息"""
    from szyg.platforms.session_manager import get_session_manager
    from szyg.publisher import Platform

    mgr = get_session_manager()

    if platform:
        try:
            p = Platform(platform)
            result = mgr.get_info(p)
            result["platform"] = platform
            return result
        except ValueError:
            return {"error": f"不支持的平台: {platform}"}
    else:
        return mgr.list_all()


@server.tool("platform_logout", "清除指定平台的登录态")
def platform_logout(platform: str):
    """删除本地存储的 cookies 和 session 文件"""
    from szyg.platforms.session_manager import get_session_manager
    from szyg.publisher import Platform

    try:
        p = Platform(platform)
    except ValueError:
        return {"error": f"不支持的平台: {platform}"}

    mgr = get_session_manager()
    mgr.invalidate(p)
    return {"platform": platform, "logged_out": True,
            "message": f"{platform} 登录态已清除"}


@server.tool("platform_health", "所有平台健康检查 (登录态 + 适配器状态)")
def platform_health():
    """返回每个平台的健康状态: ok/warning/error"""
    import asyncio
    from szyg.platforms.registry import get_registry

    registry = get_registry()
    platforms = registry.list_platforms()

    async def _check_all():
        results = {}
        for plat_info in platforms:
            pid = plat_info["id"]
            try:
                from szyg.publisher import Platform
                p = Platform(pid)
                if registry.is_registered(p):
                    adapter = await registry.get(p)
                    login = await adapter.check_login()
                    results[pid] = {
                        "state": plat_info["state"],
                        "is_logged_in": login.is_logged_in,
                        "account_name": login.account_name,
                        "adapter_ready": adapter.is_ready,
                    }
                else:
                    results[pid] = {"state": "not_registered"}
            except Exception as e:
                results[pid] = {"state": "error", "error": str(e)}
        return results

    try:
        loop = asyncio.get_running_loop()
        return {"error": "请在同步上下文外调用"}
    except RuntimeError:
        return asyncio.run(_check_all())


if __name__ == "__main__":
    server.run()
