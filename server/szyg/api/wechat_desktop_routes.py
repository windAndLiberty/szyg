"""Read-only WeChat desktop endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from szyg.channel_accounts import mark_account_login
from szyg.wechat_desktop_calibration import (
    calibration_summary,
    capture_input_click,
    create_input_calibration,
    validate_calibration,
)
from szyg.integrations.weixin4_bridge import get_weixin4_bridge
from szyg.platforms.wechat_desktop import WeChatDesktopAdapter

router = APIRouter(prefix="/api/wechat/desktop", tags=["wechat-desktop"])


class CalibrationPoint(BaseModel):
    x: int | None = Field(default=None)
    y: int | None = Field(default=None)
    label: str = Field(default="input_box")


@router.get("/status")
async def api_wechat_desktop_status():
    bridge = get_weixin4_bridge()
    window = bridge.status()

    adapter = WeChatDesktopAdapter()
    initialized = await adapter.initialize()
    login = await adapter.check_login() if initialized else None

    return {
        "ok": bool(window.get("found") or (login and login.is_logged_in)),
        "mode": "weixin4_uia" if window.get("client") == "weixin4" else "wechat_desktop",
        "window": window,
        "login": login.model_dump() if login else {
            "is_logged_in": False,
            "message": "微信桌面适配器初始化失败",
        },
        "safe_actions": {
            "observe": True,
            "write_draft": False,
            "send_message": False,
            "publish_moment": False,
        },
    }


@router.get("/observe")
async def api_wechat_desktop_observe(max_children: int = Query(80, ge=1, le=200)):
    bridge = get_weixin4_bridge()
    observation = bridge.observe(max_children=max_children)
    return {
        "ok": bool(observation.get("found")),
        "observation": observation,
        "safe_actions": {
            "observe": True,
            "write_draft": False,
            "send_message": False,
            "publish_moment": False,
        },
    }


@router.post("/open")
async def api_open_wechat_desktop(wait_seconds: int = Query(12, ge=1, le=60)):
    bridge = get_weixin4_bridge()
    result = bridge.open_or_focus(wait_seconds=wait_seconds)
    return {
        "ok": bool(result.get("ok")),
        **result,
        "user_prompt": "微信已为你打开到前台。请确认当前登录的是要接入 SZYG 的微信账号。",
        "safe_actions": {
            "observe": True,
            "write_draft": False,
            "send_message": False,
            "publish_moment": False,
        },
    }


@router.get("/calibration")
async def api_wechat_desktop_calibration():
    return {"ok": True, **calibration_summary()}


@router.post("/calibration")
async def api_save_wechat_desktop_calibration(body: CalibrationPoint | None = Body(default=None)):
    point = None
    label = "input_box"
    if body:
        label = body.label or label
        if body.x is not None and body.y is not None:
            point = {"x": body.x, "y": body.y}
    try:
        calibration = create_input_calibration(point=point, label=label)
        validation = validate_calibration()
        return {
            "ok": True,
            "calibration": calibration,
            "validation": validation,
            "message": "微信输入区校准已保存",
            "safe_actions": {
                "observe": True,
                "write_draft": False,
                "send_message": False,
                "publish_moment": False,
            },
        }
    except RuntimeError as exc:
        raise HTTPException(400, str(exc))


@router.post("/capture-input-click")
async def api_capture_wechat_input_click(
    timeout_seconds: int = Query(15, ge=3, le=60),
    account_id: str = Query(""),
):
    try:
        result = capture_input_click(timeout_seconds=timeout_seconds)
        account = None
        if account_id:
            try:
                account = mark_account_login(account_id, True, "微信输入区已识别")
            except Exception:
                account = None
        return {
            "ok": True,
            **result,
            "account": account,
            "message": "微信输入区已识别",
            "safe_actions": {
                "observe": True,
                "write_draft": False,
                "send_message": False,
                "publish_moment": False,
            },
        }
    except RuntimeError as exc:
        raise HTTPException(400, str(exc))


@router.post("/validate-calibration")
async def api_validate_wechat_desktop_calibration(
    max_size_drift: float = Query(0.1, ge=0.01, le=0.5),
):
    validation = validate_calibration(max_size_drift=max_size_drift)
    return {
        "ok": bool(validation.get("ok")),
        "validation": validation,
        "safe_actions": {
            "observe": True,
            "write_draft": False,
            "send_message": False,
            "publish_moment": False,
        },
    }
