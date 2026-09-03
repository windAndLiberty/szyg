"""Hermes tool for the Electron-managed browser work view."""

from __future__ import annotations

import json
import os
from typing import Any, Callable

import httpx


ApprovalCallback = Callable[[str, dict[str, Any], str], str]


async def _browser_action(payload: dict[str, Any]) -> dict[str, Any]:
    base_url = os.environ.get("SZYG_BROWSER_CONTROL_URL", "").rstrip("/")
    token = os.environ.get("SZYG_BROWSER_CONTROL_TOKEN", "")
    if not base_url or not token:
        raise RuntimeError("浏览器操作仅可在领鹿员工桌面版中使用")
    async with httpx.AsyncClient(timeout=90, trust_env=False) as client:
        response = await client.post(
            base_url + "/v1/action",
            headers={"X-SZYG-Browser-Token": token},
            json=payload,
        )
    data = response.json()
    if response.status_code >= 400 or not data.get("ok"):
        raise RuntimeError(str(data.get("error") or "浏览器操作未完成"))
    return data.get("result") or {}


async def _approval_for_target(
    payload: dict[str, Any], callback: ApprovalCallback | None
) -> bool:
    if payload.get("action") not in {"click", "type"}:
        return True
    observation = await _browser_action({"action": "observe"})
    ref = str(payload.get("ref") or "")
    target = next(
        (row for row in observation.get("elements", []) if str(row.get("ref")) == ref),
        {},
    )
    description = " ".join(
        str(target.get(key) or "") for key in ("text", "role", "type", "name")
    ).casefold()
    risky = any(
        token in description
        for token in (
            "登录", "注册", "发送", "发布", "提交", "确认", "删除", "付款", "支付",
            "购买", "关注", "加好友", "批量", "password", "login", "sign in",
            "send", "publish", "submit", "delete", "pay", "purchase", "follow",
        )
    )
    if not risky:
        return True
    if callback is None:
        return False
    decision = callback("browser." + str(payload.get("action")), payload, "确认网页操作")
    return decision in {"approve", "approve_once", "allow"}


def register_browser_tool(approval_callback: ApprovalCallback | None = None) -> None:
    from tools.registry import registry

    schema = {
        "name": "szyg_browser",
        "description": (
            "在领鹿员工右侧的可见浏览器中操作网页。所有网页任务都使用此工具，"
            "先 navigate 打开页面，再 observe 获取元素 ref，之后 click、type、press 或 scroll；"
            "需要读取长回答和引用时使用 read。"
            "不要使用电脑桌面工具。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "navigate", "observe", "click", "type", "scroll",
                        "press", "read", "back", "forward", "refresh",
                    ],
                },
                "url": {"type": "string", "description": "navigate 时使用的网页地址"},
                "ref": {"type": "string", "description": "observe 返回的页面元素编号"},
                "text": {"type": "string", "description": "type 时填写的内容"},
                "key": {"type": "string", "description": "press 时使用的按键，例如 Enter"},
                "clear": {"type": "boolean", "default": True},
                "delta_y": {"type": "integer", "description": "滚动距离，正数向下、负数向上"},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    }

    async def handler(args: dict[str, Any], **_: Any) -> str:
        payload = dict(args or {})
        try:
            if not await _approval_for_target(payload, approval_callback):
                return json.dumps(
                    {"ok": False, "status": "cancelled", "message": "用户未确认这项网页操作"},
                    ensure_ascii=False,
                )
            result = await _browser_action(payload)
            return json.dumps({"ok": True, "result": result}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    registry.register(
        name="szyg_browser",
        toolset="szyg",
        schema=schema,
        handler=handler,
        is_async=True,
        description=schema["description"],
    )
