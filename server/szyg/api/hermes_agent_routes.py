"""
超级员工接口 — 直接驱动仓库内置的 Hermes 内核（``run_agent.AIAgent``）。

这是一层 *浅封装*：把 HTTP/SSE 请求转交给 Hermes runtime，并把 Hermes 的回调
（token 级流式、工具开始/完成、reasoning 等）转成 SSE 事件返回前端。

- 业务能力以原生 toolset ``szyg`` 注册进 Hermes registry（见
  ``szyg.agent_core.szyg_toolset``），由 Hermes 内核负责调度、并发、重试、guardrail。
- LLM/工具的具体执行全部走 Hermes ``conversation_loop``，本文件不再手写 ReACT 循环。
"""

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from szyg.brain_hermes import get_brain

router = APIRouter(prefix="/api/hermes", tags=["hermes-agent"])


class HermesChatRequest(BaseModel):
    messages: list = []
    model: str | None = None
    # 按智能体覆盖：自定义系统提示词 + 是否启用 szyg 业务工具集。
    system_prompt: str | None = None
    use_tools: bool = True


# ── SSE helpers + endpoint (driven by Hermes AIAgent) ────────────────────

def _sse(d: dict) -> str:
    return f"data: {json.dumps(d, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def hermes_chat(req: HermesChatRequest):
    if not req.messages:
        return StreamingResponse(iter([_sse({"type": "error", "content": "messages required"})]), media_type="text/event-stream")
    user_msg = req.messages[-1].get("content", "")
    if not isinstance(user_msg, str) or not user_msg.strip():
        return StreamingResponse(iter([_sse({"type": "error", "content": "empty message"})]), media_type="text/event-stream")
    history = [m for m in req.messages[:-1] if isinstance(m, dict)]
    return StreamingResponse(
        _agent_stream(user_msg, history, req.model, req.system_prompt, req.use_tools),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _agent_stream(
    user_input: str,
    history: list,
    model: str | None,
    system_prompt: str | None = None,
    use_tools: bool = True,
):
    """驱动 Hermes ``AIAgent``：在线程中跑阻塞式 ``run_conversation``，
    通过线程安全队列把回调事件转成 SSE 事件流式返回。"""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    _SENTINEL = object()
    state = {"got_text": False}

    def _enqueue(event: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    def _on_delta(delta):
        # Hermes 在工具执行前会用 None 关闭文本框，过滤掉以免误判结束。
        if delta:
            state["got_text"] = True
            _enqueue({"type": "text", "content": delta})

    def _on_tool_start(tool_call_id, function_name, function_args):
        if not function_name or function_name.startswith("_"):
            return
        _enqueue({"type": "tool_start", "tool": function_name, "args": function_args})

    def _on_tool_complete(tool_call_id, function_name, function_args, function_result):
        if not function_name or function_name.startswith("_"):
            return
        if isinstance(function_result, str):
            preview = function_result
        else:
            preview = json.dumps(function_result, ensure_ascii=False, default=str)
        _enqueue({"type": "tool_result", "tool": function_name, "preview": preview[:500]})

    def _on_tool_progress(event_type, tool_name=None, preview=None, args=None, **kwargs):
        if event_type == "reasoning.available" and preview:
            _enqueue({"type": "reasoning", "content": preview})

    def _run():
        try:
            agent = get_brain().build_agent(
                model=model,
                system_prompt=system_prompt,
                use_tools=use_tools,
                stream_delta_callback=_on_delta,
                tool_start_callback=_on_tool_start,
                tool_complete_callback=_on_tool_complete,
                tool_progress_callback=_on_tool_progress,
            )
            conv_history = [
                {"role": m.get("role", "user"), "content": m.get("content", "")}
                for m in history[-10:]
            ]
            result = agent.run_conversation(user_input, conversation_history=conv_history)
            final = result.get("final_response", "") if isinstance(result, dict) else str(result or "")
            # 兜底：若 provider 未走流式（没有任何 delta），把最终回复一次性发出。
            if final and not state["got_text"]:
                _enqueue({"type": "text", "content": final})
        except Exception as exc:  # pragma: no cover - surfaced to client
            _enqueue({"type": "error", "content": str(exc)})
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)

    yield _sse({"type": "start"})
    loop.run_in_executor(None, _run)
    while True:
        event = await queue.get()
        if event is _SENTINEL:
            break
        yield _sse(event)
    yield _sse({"type": "done"})
