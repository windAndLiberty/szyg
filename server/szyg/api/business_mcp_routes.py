"""Authenticated loopback Streamable HTTP MCP facade for Xiaoyu business tools.

The OpenClaw sidecar connects to one aggregate endpoint instead of spawning the
individual Python MCP modules. Business behavior remains in the existing
capability registry and therefore shares validation, approvals and audit paths
with the rest of the application.
"""

from __future__ import annotations

import hmac
import json
import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from szyg.hermes_capabilities import get_hermes_capability_registry


router = APIRouter(tags=["szyg-business-mcp"])
_PROTOCOL_VERSION = "2025-03-26"


def _authorized(authorization: str) -> bool:
    expected = (os.environ.get("SZYG_BUSINESS_MCP_TOKEN", "") or "").strip()
    supplied = authorization.removeprefix("Bearer ").strip()
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


def _result(request_id: Any, value: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": value}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool_catalog() -> list[dict[str, Any]]:
    tools = []
    for item in get_hermes_capability_registry().list():
        confirmation_required = bool(item.get("confirmation_required"))
        tools.append({
            "name": str(item["name"]),
            "title": str(item.get("title") or item["name"]),
            "description": str(item.get("description") or ""),
            "inputSchema": {
                "type": "object",
                "properties": item.get("parameters") or {},
                "additionalProperties": True,
            },
            "annotations": {
                "readOnlyHint": item.get("risk") == "read",
                "destructiveHint": confirmation_required,
                "idempotentHint": item.get("risk") in {"read", "analysis"},
                "openWorldHint": item.get("risk") == "external",
            },
            "_meta": {
                "szyg/domain": item.get("domain"),
                "szyg/risk": item.get("risk"),
                "szyg/confirmationRequired": confirmation_required,
            },
        })
    return tools


async def _dispatch(payload: dict[str, Any]) -> dict[str, Any] | None:
    request_id = payload.get("id")
    method = str(payload.get("method") or "")
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}

    if method == "initialize":
        return _result(request_id, {
            "protocolVersion": _PROTOCOL_VERSION,
            "serverInfo": {"name": "szyg-business", "version": "1.0.0"},
            "capabilities": {"tools": {"listChanged": False}},
            "instructions": (
                "小妤本地业务能力。真实外发、发布、任务恢复等能力必须先取得用户明确确认，"
                "再按工具结果要求传入 confirmed=true。工具返回失败时不得声称成功。"
            ),
        })
    if method in {"notifications/initialized", "notifications/cancelled"}:
        return None
    if method == "ping":
        return _result(request_id, {})
    if method == "tools/list":
        return _result(request_id, {"tools": _tool_catalog()})
    if method == "tools/call":
        name = str(params.get("name") or "")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        known = {item["name"] for item in get_hermes_capability_registry().list()}
        if name not in known:
            return _error(request_id, -32601, f"Unknown business tool: {name}")
        desktop_token = (os.environ.get("SZYG_DESKTOP_TOKEN", "") or "").strip()
        headers = {"X-SZYG-Desktop-Token": desktop_token} if desktop_token else {}
        raw = await get_hermes_capability_registry().execute(name, arguments, headers)
        try:
            structured = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            structured = {"result": str(raw)}
        is_error = structured.get("ok") is False
        return _result(request_id, {
            "content": [{"type": "text", "text": json.dumps(structured, ensure_ascii=False)}],
            "structuredContent": structured,
            "isError": is_error,
        })
    return _error(request_id, -32601, f"Method not found: {method}")


@router.post("/api/mcp/szyg-business")
async def business_mcp(
    request: Request,
    authorization: str = Header(default=""),
):
    if not _authorized(authorization):
        raise HTTPException(401, "Unauthorized")
    try:
        payload = await request.json()
    except Exception as exc:
        return JSONResponse(_error(None, -32700, "Invalid JSON"), status_code=400)

    if isinstance(payload, list):
        responses = []
        for item in payload[:100]:
            if isinstance(item, dict):
                response = await _dispatch(item)
                if response is not None:
                    responses.append(response)
        if not responses:
            return Response(status_code=202)
        return JSONResponse(responses, media_type="application/json")
    if not isinstance(payload, dict):
        return JSONResponse(_error(None, -32600, "Invalid request"), status_code=400)
    response = await _dispatch(payload)
    if response is None:
        return Response(status_code=202)
    return JSONResponse(response, media_type="application/json")


@router.get("/api/mcp/szyg-business")
async def business_mcp_stream(authorization: str = Header(default="")):
    if not _authorized(authorization):
        raise HTTPException(401, "Unauthorized")
    # This server is stateless. OpenClaw uses POST responses for all exchanges;
    # an SSE stream is intentionally not allocated when no server push exists.
    return Response(status_code=405, headers={"Allow": "POST"})


@router.delete("/api/mcp/szyg-business")
async def business_mcp_close(authorization: str = Header(default="")):
    if not _authorized(authorization):
        raise HTTPException(401, "Unauthorized")
    return Response(status_code=204)
