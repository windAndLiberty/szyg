"""Public Hermes agent API and private loopback bridges."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from szyg.execution_kernel import get_execution_kernel
from szyg.hermes_capabilities import get_hermes_capability_registry
from szyg.hermes_process_manager import hermes_process_manager
from szyg.integrations.cloud_inference_client import CloudInferenceClient
from szyg.models.common import IntegrationError


router = APIRouter()
execution_kernel = get_execution_kernel()


async def _ensure_runtime() -> None:
    try:
        await asyncio.to_thread(hermes_process_manager.ensure_started)
    except RuntimeError as exc:
        raise HTTPException(
            503,
            "智能员工运行组件启动失败，请检查本地开发环境依赖",
        ) from exc


class HermesChatRequest(BaseModel):
    model: str = "text.fast"
    messages: list[dict[str, Any]] = Field(default_factory=list)
    stream: bool = True
    agent_id: str = ""
    expert_prompt: str = ""
    session_id: str = ""


class CaseCardRequest(BaseModel):
    recent_titles: list[str] = Field(default_factory=list)
    limit: int = 3


_case_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


async def _case_keyword(context: str, basis: str) -> str:
    if basis != "knowledge":
        return "人工智能 最新资讯"
    try:
        client = CloudInferenceClient(timeout=45)
        result = await client.chat([{
            "role": "user",
            "content": (
                "根据以下企业资料提炼一个适合短视频平台检索的高相关主题词。"
                "要求6到16个字，包含具体行业、产品或目标人群，只返回主题词。\n\n"
                + context[:3000]
            ),
        }], max_tokens=80, temperature=0.2)
        keyword = str((result.get("message") or {}).get("content") or "").strip().strip('"\'')
        if 4 <= len(keyword) <= 20:
            return keyword
    except Exception:
        pass
    from szyg.case_recommendations import knowledge_fallback_keyword
    return knowledge_fallback_keyword(context)


@router.post("/api/hermes/case-cards")
async def case_cards(body: CaseCardRequest):
    from szyg.case_recommendations import knowledge_case_context, normalized_count, select_diverse_videos
    from szyg.integrations.acquisition_adapters import get_acquisition_adapter

    context, basis = await asyncio.to_thread(knowledge_case_context)
    keyword = await _case_keyword(context, basis)
    key = hashlib.sha1(f"{basis}:{keyword}:{context}".encode("utf-8")).hexdigest()
    cached = _case_cache.get(key)
    if cached and time.time() - cached[0] < 1800:
        return {"cards": cached[1], "keyword": keyword, "source": "multi-platform", "basis": basis}

    async def search(platform: str) -> list[dict[str, Any]]:
        try:
            adapter = get_acquisition_adapter(platform)
            return await asyncio.wait_for(adapter.search(keyword, limit=8), timeout=35)
        except Exception:
            return []

    batches = await asyncio.gather(*(search(item) for item in ("bilibili", "douyin", "kuaishou")))
    selected = select_diverse_videos([row for batch in batches for row in batch], keyword, context, min(body.limit, 3))
    cards = [{
        "title": str(item.get("title") or "")[:50],
        "cover_url": str(item.get("cover") or ""),
        "video_url": str(item.get("url") or ""),
        "author": str(item.get("author") or ""),
        "likes": normalized_count(item.get("likes", 0)),
        "source": str(item.get("platform") or ""),
    } for item in selected]
    _case_cache[key] = (time.time(), cards)
    return {"cards": cards, "keyword": keyword, "source": "multi-platform", "basis": basis}


def _verify_runtime(value: str) -> None:
    import hmac
    if not value or not hmac.compare_digest(value, hermes_process_manager.token):
        raise HTTPException(401, "Unauthorized")


def _system_prompt(agent_id: str, expert_prompt: str) -> str:
    role = {
        "content": "你负责内容策划、生成、素材组合与发布协作。",
        "acquisition": "你负责公域获客、线索判断、评论策略和客户跟进。",
        "conversion": "你负责需求判断、销售跟进和客户转化。",
        "ops": "你负责运营复盘、数据洞察和工作流执行。",
    }.get(agent_id, "你是数字员工的超级数字员工，负责理解目标并调用可用能力完成工作。")
    expert = f"\n\n当前专家职责：\n{expert_prompt[:6000]}" if expert_prompt else ""
    return (
        f"{role}{expert}\n\n"
        "用自然、明确的中文与用户协作。优先使用数字员工业务工具取得真实数据，不编造执行结果。"
        "需要打开、浏览或操作网页时，必须使用右侧可见的浏览器操作能力；先打开网页并理解当前页面，"
        "再根据页面返回的元素完成点击或填写，任务结束前重新理解页面以确认真实结果。"
        "不要使用命令行启动浏览器，也不要尝试操作用户电脑上的其他应用。"
        "涉及外发、删除、登录、付款、加好友或批量操作时必须等待用户明确确认。"
        "不要向用户暴露模型、工具协议、运行时或内部技术名称。"
        "完成浏览器操作后，只用一到两句话说明结果和仍需用户处理的事项，不复述操作过程，"
        "不使用‘已完成操作’等机械前缀，也不要声称未通过画面确认的结果。"
    )


@router.post("/api/hermes/chat")
async def hermes_chat(body: HermesChatRequest, request: Request):
    if not body.messages:
        raise HTTPException(422, "messages required")
    await _ensure_runtime()
    latest = body.messages[-1].get("content", "")
    session_id = body.session_id or f"session-{uuid.uuid4().hex}"
    auth_headers: dict[str, str] = {}
    authorization = request.headers.get("Authorization", "")
    if authorization:
        auth_headers["Authorization"] = authorization
    desktop_token = request.headers.get("X-SZYG-Desktop-Token", "") or request.cookies.get("szyg_desktop_token", "")
    if desktop_token:
        auth_headers["X-SZYG-Desktop-Token"] = desktop_token

    run = execution_kernel.create_run(
        "agent_turn",
        "local",
        "agent",
        {"session_id": session_id, "agent_id": body.agent_id},
        title=str(latest)[:80],
    )
    step = execution_kernel.start_step(run["id"], "agent_loop", "理解并执行任务", "agent", "agent_loop")
    context_id = hermes_process_manager.register_context({
        "run_id": run["id"],
        "session_id": session_id,
        "auth_headers": auth_headers,
    })
    payload = {
        "message": latest,
        "history": body.messages[:-1],
        "system_prompt": _system_prompt(body.agent_id, body.expert_prompt),
        "context_id": context_id,
        "agent_id": body.agent_id,
        "expert_prompt": body.expert_prompt,
    }

    async def events():
        terminal = False
        try:
            async with httpx.AsyncClient(timeout=None, trust_env=False) as client:
                async with client.stream(
                    "POST",
                    f"{hermes_process_manager.base_url}/v1/sessions/{session_id}/turn",
                    headers=hermes_process_manager.headers,
                    json=payload,
                ) as response:
                    if response.status_code >= 400:
                        detail = (await response.aread()).decode("utf-8", errors="replace")
                        raise RuntimeError(detail[:500])
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        raw = line[6:]
                        try:
                            event = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        event["run_id"] = run["id"]
                        kind = event.get("type")
                        if kind == "tool.started":
                            execution_kernel.add_audit(run["id"], str(event.get("id") or ""), str(event.get("tool") or "tool"), "running", "开始执行")
                        elif kind == "tool.completed":
                            execution_kernel.add_audit(run["id"], str(event.get("id") or ""), str(event.get("tool") or "tool"), "success", "执行完成")
                        elif kind == "run.completed":
                            terminal = True
                            execution_kernel.finish_step(step, "success", "任务完成")
                            execution_kernel.complete_run(run["id"], "success", {"session_id": session_id})
                        elif kind == "run.paused":
                            terminal = True
                            execution_kernel.finish_step(step, "paused", "等待用户接管")
                            execution_kernel.pause_run(run["id"], "用户正在接管电脑")
                        elif kind == "run.failed":
                            terminal = True
                            message = str(event.get("content") or "任务未完成")
                            execution_kernel.finish_step(step, "failed", message, error_code="agent_runtime_failed")
                            execution_kernel.complete_run(run["id"], "failed", error_code="agent_runtime_failed", error_message=message)
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            try:
                async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                    await client.post(
                        f"{hermes_process_manager.base_url}/v1/sessions/{session_id}/interrupt",
                        headers=hermes_process_manager.headers,
                        json={"mode": "stop"},
                    )
            finally:
                execution_kernel.complete_run(run["id"], "cancelled", error_code="cancelled", error_message="用户已停止任务")
            raise
        except Exception as exc:
            message = str(exc)[:500] or "智能员工暂时不可用"
            execution_kernel.finish_step(step, "failed", message, error_code="agent_runtime_unavailable")
            execution_kernel.complete_run(run["id"], "failed", error_code="agent_runtime_unavailable", error_message=message)
            yield f"data: {json.dumps({'type': 'run.failed', 'content': '智能服务暂时不可用', 'run_id': run['id']}, ensure_ascii=False)}\n\n"
        finally:
            if not terminal:
                current = execution_kernel.get_run(run["id"])
                if current and current.get("status") not in {"failed", "cancelled", "success"}:
                    execution_kernel.complete_run(run["id"], "needs_human", error_code="stream_interrupted", error_message="任务连接已中断")
            hermes_process_manager.release_context(context_id)

    return StreamingResponse(events(), media_type="text/event-stream")


async def _interrupt_session(session_id: str, mode: str):
    await _ensure_runtime()
    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
        response = await client.post(
            f"{hermes_process_manager.base_url}/v1/sessions/{session_id}/interrupt",
            headers=hermes_process_manager.headers,
            json={"mode": mode},
        )
    if response.status_code >= 400:
        raise HTTPException(response.status_code, "当前任务无法停止")
    return {"ok": True}


@router.post("/api/hermes/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    return await _interrupt_session(session_id, "stop")


@router.post("/api/hermes/sessions/{session_id}/takeover")
async def takeover_session(session_id: str):
    return await _interrupt_session(session_id, "pause")


@router.post("/api/hermes/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    await _ensure_runtime()
    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
        response = await client.post(
            f"{hermes_process_manager.base_url}/v1/sessions/{session_id}/resume",
            headers=hermes_process_manager.headers,
        )
    if response.status_code >= 400:
        raise HTTPException(response.status_code, "当前任务无法继续")
    return {"ok": True}


@router.post("/api/hermes/approvals/{approval_id}")
async def decide_approval(approval_id: str, body: dict[str, Any]):
    await _ensure_runtime()
    decision = str(body.get("decision") or "deny")
    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
        response = await client.post(
            f"{hermes_process_manager.base_url}/v1/approvals/{approval_id}",
            headers=hermes_process_manager.headers,
            json={"decision": decision},
        )
    if response.status_code >= 400:
        raise HTTPException(response.status_code, "这项确认已失效")
    return {"ok": True}


@router.post("/api/internal/hermes/capabilities/{name:path}")
async def call_capability(
    name: str,
    args: dict[str, Any],
    x_szyg_hermes_token: str = Header(default=""),
    x_szyg_hermes_context: str = Header(default=""),
):
    _verify_runtime(x_szyg_hermes_token)
    context = hermes_process_manager.get_context(x_szyg_hermes_context)
    if not context:
        raise HTTPException(401, "Task context expired")
    result = await get_hermes_capability_registry().execute(
        name,
        args,
        context.get("auth_headers") or {},
    )
    return {"ok": True, "result": result}


def _normalize_tools(tools: Any) -> list[dict[str, Any]]:
    """把扁平或嵌套 tools schema 统一为云网关可解析的嵌套格式。

    云网关要求 OpenAI 风格的 ``{"type": "function", "function": {...}}``。
    部分调用方（Hermes 运行时）会传扁平结构 ``{"type": "function", "name": ...}``，
    网关无法解析并返回 502。此处统一改写后再转发。
    """
    normalized: list[dict[str, Any]] = []
    for item in tools or []:
        row = dict(item) if isinstance(item, dict) else {}
        fn = row.get("function")
        if isinstance(fn, dict) and isinstance(fn.get("name"), str):
            normalized.append(row)
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        normalized.append({
            "type": "function",
            "function": {
                "name": name,
                "description": str(row.get("description") or ""),
                "parameters": row.get("parameters") or {"type": "object", "properties": {}},
            },
        })
    return normalized


def _normalize_tool_calls(calls: Any) -> list[dict[str, Any]]:
    normalized = []
    for item in calls or []:
        row = dict(item) if isinstance(item, dict) else {}
        fn = dict(row.get("function") or {})
        arguments = fn.get("arguments", "{}")
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments, ensure_ascii=False)
        normalized.append({
            "id": str(row.get("id") or f"call_{uuid.uuid4().hex[:16]}"),
            "type": "function",
            "function": {"name": str(fn.get("name") or ""), "arguments": arguments},
        })
    return normalized


@router.post("/api/internal/hermes/openai/v1/chat/completions")
async def openai_chat(body: dict[str, Any], authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ").strip()
    _verify_runtime(token)
    client = CloudInferenceClient(timeout=90)
    payload = {
        "messages": body.get("messages") or [],
        "stream": False,
        "max_tokens": int(body.get("max_completion_tokens") or body.get("max_tokens") or 8192),
        "temperature": float(body.get("temperature", 0.6)),
    }
    if body.get("tools"):
        payload["tools"] = _normalize_tools(body["tools"])
    if body.get("tool_choice") is not None:
        payload["tool_choice"] = body["tool_choice"]
    capability = "text.reasoning" if body.get("reasoning_effort") or body.get("reasoning") else "text.fast"
    try:
        result = await client._request("POST", "/api/v1/inference/chat", client._body(capability, payload))
    except IntegrationError as exc:
        message = str(exc)
        status_code = int(getattr(exc, "status_code", 503))
        raise HTTPException(status_code=status_code, detail=message) from exc
    data = result.get("data") or {}
    choice = (data.get("choices") or [{}])[0]
    message = dict(choice.get("message") or {"role": "assistant", "content": ""})
    message["role"] = "assistant"
    if message.get("tool_calls"):
        message["tool_calls"] = _normalize_tool_calls(message["tool_calls"])
    completion_id = str(data.get("id") or f"chatcmpl-{uuid.uuid4().hex}")
    model = "text.reasoning" if capability == "text.reasoning" else "text.fast"
    if not body.get("stream"):
        return JSONResponse({
            "id": completion_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "message": message, "finish_reason": choice.get("finish_reason") or ("tool_calls" if message.get("tool_calls") else "stop")}],
            "usage": data.get("usage") or {},
        })

    async def chunks():
        base = {"id": completion_id, "object": "chat.completion.chunk", "created": int(time.time()), "model": model}
        yield f"data: {json.dumps({**base, 'choices': [{'index': 0, 'delta': {'role': 'assistant'}, 'finish_reason': None}]})}\n\n"
        if message.get("tool_calls"):
            delta_calls = []
            for index, item in enumerate(message["tool_calls"]):
                delta_calls.append({"index": index, **item})
            yield f"data: {json.dumps({**base, 'choices': [{'index': 0, 'delta': {'tool_calls': delta_calls}, 'finish_reason': None}]}, ensure_ascii=False)}\n\n"
            finish = "tool_calls"
        else:
            content = str(message.get("content") or "")
            for offset in range(0, len(content), 80):
                delta = content[offset:offset + 80]
                yield f"data: {json.dumps({**base, 'choices': [{'index': 0, 'delta': {'content': delta}, 'finish_reason': None}]}, ensure_ascii=False)}\n\n"
            finish = "stop"
        yield f"data: {json.dumps({**base, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': finish}], 'usage': data.get('usage') or {}}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(chunks(), media_type="text/event-stream")
