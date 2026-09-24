"""Account-level publishing channel APIs."""

from __future__ import annotations

import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from szyg.channel_accounts import (
    MAX_ACCOUNTS_PER_PLATFORM,
    MAX_TOTAL_ACCOUNTS,
    create_account,
    delete_account_session,
    delete_profile,
    get_account,
    list_accounts,
    list_profiles,
    mark_account_login,
    patch_account,
    save_profile,
)
from szyg.account_profile_sync import sync_account_profile
from szyg.platforms.tencent_channels_desktop import (
    TENCENT_CHANNELS_LOGIN_URL,
    TENCENT_CHANNELS_PUBLISH_URL,
    TencentPublishPayload,
    get_tencent_channels_desktop_assistant,
)
from szyg.platforms.weibo_desktop import WEIBO_HOME_URL, get_weibo_desktop_publisher

router = APIRouter(tags=["platform-accounts"])

AVATAR_ALLOWED_HOSTS = {
    "i0.hdslb.com",
    "i1.hdslb.com",
    "i2.hdslb.com",
    "i3.hdslb.com",
    "i4.hdslb.com",
    "i5.hdslb.com",
    "i6.hdslb.com",
    "i7.hdslb.com",
    "i8.hdslb.com",
    "i9.hdslb.com",
}
AVATAR_ALLOWED_SUFFIXES = {
    ".sinaimg.cn",
}


class CreateChannelAccountRequest(BaseModel):
    platform: str
    label: str = ""


class SavePublishingProfileRequest(BaseModel):
    name: str
    account_ids: list[str] = Field(default_factory=list)
    description: str = ""


class OpenPublishRequest(BaseModel):
    title: str = ""
    desc: str = ""
    tags: list[str] = Field(default_factory=list)
    file_path: str = ""
    asset_paths: list[str] = Field(default_factory=list)
    mode: str = "video"
    auto_publish: bool = True


@router.get("/api/platform-accounts")
async def api_list_platform_accounts(platform: str = Query("")):
    accounts = list_accounts(platform=platform, include_defaults=True)
    return {
        "ok": True,
        "accounts": accounts,
        "total": len(accounts),
        "limits": {
            "per_platform": MAX_ACCOUNTS_PER_PLATFORM,
            "total": MAX_TOTAL_ACCOUNTS,
        },
    }


@router.get("/api/platform-accounts/metrics")
async def api_platform_account_metrics(days: int = Query(30, ge=1, le=365), account_id: str = Query("")):
    """Return trend snapshots for the customer's own managed accounts."""
    from szyg.account_metrics import account_metrics_overview

    return {"ok": True, **account_metrics_overview(days=days, account_id=account_id)}


@router.get("/api/platform-accounts/avatar")
async def api_proxy_platform_avatar(url: str = Query(...)):
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname or ""
    allowed = hostname in AVATAR_ALLOWED_HOSTS or any(hostname.endswith(suffix) for suffix in AVATAR_ALLOWED_SUFFIXES)
    if parsed.scheme not in {"https", "http"} or not allowed:
        raise HTTPException(400, "不支持的头像地址")
    referer = "https://weibo.com/" if hostname.endswith(".sinaimg.cn") else "https://space.bilibili.com/"
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": referer,
            },
        )
        with urllib.request.urlopen(request, timeout=12) as remote:
            content_type = remote.headers.get("Content-Type") or "image/jpeg"
            if not content_type.startswith("image/"):
                raise HTTPException(400, "头像地址不是图片")
            return Response(
                content=remote.read(),
                media_type=content_type,
                headers={"Cache-Control": "public, max-age=86400"},
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"头像加载失败：{exc}")


@router.post("/api/platform-accounts")
async def api_create_platform_account(body: CreateChannelAccountRequest):
    try:
        account = create_account(body.platform, body.label)
        return {"ok": True, "account": account}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/api/platform-accounts/{account_id}/login")
async def api_login_platform_account(account_id: str, timeout: int = Query(900), headless: bool = Query(False)):
    account = get_account(account_id)
    if not account:
        raise HTTPException(404, "账号不存在")
    if account.get("platform") == "tencent":
        launch = get_tencent_channels_desktop_assistant().open_login()
        if not launch.get("ok"):
            raise HTTPException(500, launch.get("error") or launch.get("message") or "打开视频号助手失败")
        message = "已用真实桌面浏览器打开视频号助手，请完成登录；视频号将作为桌面辅助渠道使用。"
        updated = patch_account(
            account_id,
            status="connected",
            desktop_assist=True,
            login_url=TENCENT_CHANNELS_LOGIN_URL,
            publish_url=TENCENT_CHANNELS_PUBLISH_URL,
            last_message=message,
        )
        try:
            updated = await sync_account_profile(account_id, force=True)
        except Exception:
            pass
        return {
            "ok": True,
            "account": updated,
            "result": {
                "success": False,
                "login_started": True,
                "desktop_assist": True,
                "platform": "tencent",
                "login_url": TENCENT_CHANNELS_LOGIN_URL,
                "publish_url": TENCENT_CHANNELS_PUBLISH_URL,
                "desktop_browser": launch,
                "message": message,
            },
            "message": message,
        }
    if account.get("platform") == "weibo":
        launch = get_weibo_desktop_publisher().open_login(account)
        if not launch.get("ok"):
            raise HTTPException(500, launch.get("error") or launch.get("message") or "打开微博失败")
        message = "已用真实桌面浏览器打开微博，请完成登录；微博将作为桌面辅助发布渠道使用。"
        updated = patch_account(
            account_id,
            status="connected",
            desktop_assist=True,
            login_url=WEIBO_HOME_URL,
            publish_url=WEIBO_HOME_URL,
            desktop_profile_key=launch.get("profile_key", ""),
            last_message=message,
        )
        try:
            updated = await sync_account_profile(account_id, force=True)
        except Exception:
            pass
        return {
            "ok": True,
            "account": updated,
            "result": {
                "success": False,
                "login_started": True,
                "desktop_assist": True,
                "platform": "weibo",
                "login_url": WEIBO_HOME_URL,
                "desktop_browser": launch,
                "message": message,
            },
            "message": message,
        }
    try:
        from szyg.integrations.social_auto_upload_adapter import get_sau_adapter

        adapter = get_sau_adapter()
        result = await adapter.login(
            account["platform"],
            headless=headless,
            account_id=account_id,
            account_file=account.get("session_path"),
            account_name=account.get("sau_account_name"),
            timeout_seconds=timeout,
            force=True,
        )
        login_started = bool(result.get("login_started"))
        updated = mark_account_login(account_id, bool(result.get("success")), result.get("message", ""))
        if result.get("success"):
            try:
                updated = await sync_account_profile(account_id, force=True)
            except Exception:
                pass
        return {
            "ok": bool(result.get("success", False) or login_started),
            "account": updated,
            "result": result,
            "message": result.get("message", ""),
        }
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.post("/api/platform-accounts/{account_id}/open-publish")
async def api_open_platform_account_publish(account_id: str, body: OpenPublishRequest | None = None):
    account = get_account(account_id)
    if not account:
        raise HTTPException(404, "账号不存在")
    if account.get("platform") != "tencent":
        raise HTTPException(400, "当前仅视频号使用桌面辅助打开")
    payload = body or OpenPublishRequest()
    assistant = get_tencent_channels_desktop_assistant()
    result = await assistant.open_publish(
        account,
        TencentPublishPayload(
            title=payload.title,
            desc=payload.desc,
            tags=payload.tags,
            file_path=payload.file_path,
            asset_paths=payload.asset_paths,
            mode=payload.mode,
            auto_publish=payload.auto_publish,
        ),
    )
    if not result.get("ok"):
        raise HTTPException(500, result.get("message") or "打开视频号发布页失败")
    updated = patch_account(
        account_id,
        status="connected",
        desktop_assist=True,
        publish_url=result.get("url") or TENCENT_CHANNELS_PUBLISH_URL,
        last_message=result.get("message", ""),
    )
    return {
        "ok": True,
        "account": updated,
        **result,
    }


@router.post("/api/platform-accounts/{account_id}/sync-profile")
async def api_sync_platform_account_profile(account_id: str, force: bool = Query(True)):
    try:
        account = await sync_account_profile(account_id, force=force)
        return {
            "ok": account.get("sync_status") == "success",
            "account": account,
            "message": account.get("sync_message", ""),
        }
    except KeyError:
        raise HTTPException(404, "账号不存在")


@router.delete("/api/platform-accounts/{account_id}/session")
async def api_delete_platform_account_session(account_id: str):
    try:
        account = delete_account_session(account_id)
        return {"ok": True, "account": account}
    except KeyError:
        raise HTTPException(404, "账号不存在")


@router.get("/api/publishing-profiles")
async def api_list_publishing_profiles():
    return {"ok": True, "profiles": list_profiles()}


@router.post("/api/publishing-profiles")
async def api_create_publishing_profile(body: SavePublishingProfileRequest):
    try:
        profile = save_profile(body.name, body.account_ids, description=body.description)
        return {"ok": True, "profile": profile}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.put("/api/publishing-profiles/{profile_id}")
async def api_update_publishing_profile(profile_id: str, body: SavePublishingProfileRequest):
    try:
        profile = save_profile(body.name, body.account_ids, profile_id=profile_id, description=body.description)
        return {"ok": True, "profile": profile}
    except KeyError:
        raise HTTPException(404, "配置档案不存在")
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.delete("/api/publishing-profiles/{profile_id}")
async def api_delete_publishing_profile(profile_id: str):
    try:
        delete_profile(profile_id)
        return {"ok": True, "profile_id": profile_id}
    except KeyError:
        raise HTTPException(404, "配置档案不存在")
