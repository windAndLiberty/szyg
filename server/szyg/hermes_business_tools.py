"""Register SZYG business capabilities in Hermes without importing business state."""

from __future__ import annotations

import contextvars
import json
import os
from typing import Any, Callable

import httpx


_execution_context: contextvars.ContextVar[str] = contextvars.ContextVar(
    "szyg_hermes_execution_context", default=""
)
_registered = False
_approval_callback: Callable[[str, dict[str, Any], str], str] | None = None


def set_business_approval_callback(callback: Callable[[str, dict[str, Any], str], str]) -> None:
    global _approval_callback
    _approval_callback = callback


def set_execution_context(context_id: str):
    return _execution_context.set(context_id)


def reset_execution_context(token) -> None:
    _execution_context.reset(token)


async def _call_capability(name: str, args: dict[str, Any]) -> str:
    base_url = os.environ["SZYG_INTERNAL_API_URL"].rstrip("/")
    runtime_token = os.environ["SZYG_HERMES_RUNTIME_TOKEN"]
    context_id = _execution_context.get()
    if not context_id:
        return json.dumps({"ok": False, "error": "当前任务上下文已失效"}, ensure_ascii=False)
    async with httpx.AsyncClient(timeout=240, trust_env=False) as client:
        response = await client.post(
            f"{base_url}/api/internal/hermes/capabilities/{name}",
            headers={
                "X-SZYG-Hermes-Token": runtime_token,
                "X-SZYG-Hermes-Context": context_id,
            },
            json=args,
        )
    if response.status_code >= 400:
        return json.dumps({
            "ok": False,
            "error": "业务能力暂时不可用",
            "status_code": response.status_code,
        }, ensure_ascii=False)
    payload = response.json()
    return payload.get("result", json.dumps(payload, ensure_ascii=False))


def register_szyg_tools() -> None:
    global _registered
    if _registered:
        return
    from tools.registry import registry
    from szyg.hermes_capabilities import get_hermes_capability_registry

    for item in get_hermes_capability_registry().list():
        name = str(item["name"])
        tool_name = "szyg_" + name.replace(".", "_").replace("-", "_")
        properties = dict(item.get("parameters") or {})
        needs_confirmation = bool(item.get("confirmation_required"))
        schema = {
            "name": tool_name,
            "description": item["description"],
            "parameters": {
                "type": "object",
                "properties": properties,
                "additionalProperties": False,
            },
        }

        async def handler(
            args: dict[str, Any],
            _name: str = name,
            _title: str = str(item.get("title") or name),
            _needs_confirmation: bool = needs_confirmation,
            **_: Any,
        ) -> str:
            payload = dict(args or {})
            if _needs_confirmation:
                callback = _approval_callback
                decision = callback(_name, payload, _title) if callback else "deny"
                if decision not in {"approve", "approve_once", "allow"}:
                    return json.dumps({
                        "ok": False,
                        "status": "cancelled",
                        "message": "用户未确认这项操作",
                    }, ensure_ascii=False)
                payload["confirmed"] = True
            return await _call_capability(_name, payload)

        registry.register(
            name=tool_name,
            toolset="szyg",
            schema=schema,
            handler=handler,
            is_async=True,
            description=item["description"],
        )

    def open_desktop_app_handler(args: dict[str, Any], session_id: str = "", **_: Any) -> str:
        from szyg.hermes_windows_computer import open_desktop_app

        return json.dumps(
            open_desktop_app(str((args or {}).get("app") or ""), session_id=session_id),
            ensure_ascii=False,
        )

    registry.register(
        name="szyg_open_desktop_app",
        toolset="szyg",
        schema={
            "name": "szyg_open_desktop_app",
            "description": "打开用户可见的 Windows 桌面应用。用户要求打开记事本或计算器时必须使用此能力。",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {
                        "type": "string",
                        "enum": ["notepad", "calculator"],
                        "description": "要打开的应用：notepad 为记事本，calculator 为计算器。",
                    },
                },
                "required": ["app"],
                "additionalProperties": False,
            },
        },
        handler=open_desktop_app_handler,
        description="打开记事本或计算器，并展示应用窗口。",
    )
    _registered = True
