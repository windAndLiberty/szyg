"""Loopback-only API around the upstream Hermes AIAgent."""

from __future__ import annotations

import asyncio
import contextvars
import json
import os
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from szyg.hermes_business_tools import (
    register_szyg_tools,
    reset_execution_context,
    set_business_approval_callback,
    set_execution_context,
)


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _failed_final_response(value: str) -> bool:
    normalized = str(value or "").strip().casefold()
    return normalized.startswith((
        "api call failed",
        "http 500",
        "http 502",
        "http 503",
        "internal server error",
        "traceback",
    ))


class TurnRequest(BaseModel):
    message: Any
    history: list[dict[str, Any]] = Field(default_factory=list)
    system_prompt: str = ""
    context_id: str
    agent_id: str = ""
    expert_prompt: str = ""


class ApprovalDecision(BaseModel):
    decision: str


class InterruptRequest(BaseModel):
    mode: str = "stop"


class ComputerActionRequest(BaseModel):
    args: dict[str, Any]
    session_id: str = "desktop-api"
    approved: bool = False
    include_frame: bool = False


class NativeOperationRequest(BaseModel):
    operation: str
    payload: dict[str, Any] = Field(default_factory=dict)


@dataclass
class RuntimeSession:
    agent: Any
    lock: threading.Lock = field(default_factory=threading.Lock)


class RuntimeState:
    def __init__(self) -> None:
        self.sessions: dict[str, RuntimeSession] = {}
        self.guard = threading.RLock()
        self.approvals: dict[str, tuple[threading.Event, dict[str, str]]] = {}
        self.active_emitters: dict[str, Any] = {}
        self.paused_sessions: set[str] = set()
        self.interrupt_modes: dict[str, str] = {}

    def session(self, session_id: str, callbacks: dict[str, Any], system_prompt: str) -> RuntimeSession:
        with self.guard:
            current = self.sessions.get(session_id)
            if current is None:
                from hermes_state import SessionDB
                from run_agent import AIAgent

                db = SessionDB()
                agent = AIAgent(
                    base_url=os.environ["SZYG_INTERNAL_API_URL"].rstrip("/") + "/api/internal/hermes/openai/v1",
                    api_key=os.environ["SZYG_HERMES_RUNTIME_TOKEN"],
                    provider="custom:szyg-cloud",
                    api_mode="chat_completions",
                    model="text.fast",
                    max_iterations=60,
                    enabled_toolsets=[
                        "szyg", "memory", "skills", "delegation", "computer_use",
                        "terminal", "web", "vision", "file", "todo",
                    ],
                    quiet_mode=True,
                    tool_progress_mode="all",
                    ephemeral_system_prompt=system_prompt,
                    session_id=session_id,
                    session_db=db,
                    checkpoints_enabled=True,
                    skip_context_files=True,
                    load_soul_identity=False,
                    **callbacks,
                )
                current = RuntimeSession(agent=agent)
                self.sessions[session_id] = current
            else:
                for name, callback in callbacks.items():
                    setattr(current.agent, name, callback)
                current.agent.ephemeral_system_prompt = system_prompt
            return current

    def request_approval(self, action: str, args: dict[str, Any], summary: str) -> str:
        text = f"{summary} {json.dumps(args, ensure_ascii=False)}".lower()
        risky = any(token in text for token in (
            "发布", "发送", "提交", "删除", "付款", "支付", "购买", "登录",
            "注册", "加好友", "关注", "批量", "publish", "send", "delete",
            "payment", "login", "follow", "friend",
        ))
        if not risky:
            return "approve_once"
        with self.guard:
            if len(self.active_emitters) != 1:
                return "deny"
            session_id, emitter = next(iter(self.active_emitters.items()))
            approval_id = f"approval_{uuid.uuid4().hex}"
            gate = threading.Event()
            decision = {"value": "deny"}
            self.approvals[approval_id] = (gate, decision)
        emitter({
            "type": "approval.required",
            "approval_id": approval_id,
            "session_id": session_id,
            "action": action,
            "content": "即将影响外部应用，请确认是否继续",
            "summary": summary,
        })
        gate.wait(timeout=300)
        with self.guard:
            self.approvals.pop(approval_id, None)
        return decision["value"]

    def decide(self, approval_id: str, value: str) -> bool:
        with self.guard:
            pending = self.approvals.get(approval_id)
            if not pending:
                return False
            gate, decision = pending
            decision["value"] = value
            gate.set()
            return True


state = RuntimeState()
_direct_action_approved: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "szyg_direct_computer_action_approved", default=False
)


def _computer_approval(action: str, args: dict[str, Any], summary: str) -> str:
    if _direct_action_approved.get():
        return "approve_once"
    return state.request_approval(action, args, summary)


def create_app() -> FastAPI:
    set_business_approval_callback(state.request_approval)
    register_szyg_tools()
    if sys.platform == "win32":
        from szyg.hermes_windows_computer import install_windows_computer_backend

        install_windows_computer_backend()
    from tools.computer_use.tool import set_approval_callback
    set_approval_callback(_computer_approval)
    app = FastAPI(title="Hermes Runtime", docs_url=None, redoc_url=None, openapi_url=None)
    expected = os.environ["SZYG_HERMES_RUNTIME_TOKEN"]

    def authorize(value: str) -> None:
        import hmac
        if not hmac.compare_digest(value or "", expected):
            raise HTTPException(401, "Unauthorized")

    @app.get("/health")
    async def health(x_szyg_hermes_token: str = Header(default="")):
        authorize(x_szyg_hermes_token)
        from szyg.hermes_capabilities import get_hermes_capability_registry

        capabilities = get_hermes_capability_registry().list()
        return {
            "status": "ok",
            "runtime": "hermes",
            "version": "0.19.1",
            "business_capabilities": len(capabilities),
            "business_domains": sorted({item["domain"] for item in capabilities}),
        }

    @app.get("/v1/computer/status")
    async def computer_status(x_szyg_hermes_token: str = Header(default="")):
        authorize(x_szyg_hermes_token)
        if sys.platform == "win32":
            return {
                "installed": True,
                "ready": True,
                "available": True,
                "platform": "win32",
                "backend": "desktop",
                "checks": [
                    {"name": "desktop", "ok": True},
                    {"name": "capture", "ok": True},
                ],
            }
        from tools.computer_use.permissions import computer_use_status
        return await asyncio.to_thread(computer_use_status)

    @app.post("/v1/computer/action")
    async def computer_action(body: ComputerActionRequest, x_szyg_hermes_token: str = Header(default="")):
        authorize(x_szyg_hermes_token)
        from tools.computer_use.tool import handle_computer_use
        marker = _direct_action_approved.set(bool(body.approved))
        try:
            result = await asyncio.to_thread(
                handle_computer_use,
                body.args,
                session_id=body.session_id,
            )
        finally:
            _direct_action_approved.reset(marker)
        frame = None
        if body.include_frame and body.args.get("action") == "capture":
            from szyg.hermes_windows_computer import latest_computer_frame

            frame = await asyncio.to_thread(latest_computer_frame, body.session_id)
        return {"result": result, "frame": frame}

    @app.post("/v1/native")
    async def native_operation(body: NativeOperationRequest, x_szyg_hermes_token: str = Header(default="")):
        authorize(x_szyg_hermes_token)

        def execute() -> dict[str, Any]:
            operation = body.operation
            payload = body.payload
            if operation == "status":
                from agent import curator
                from tools.skill_usage import agent_created_report, usage_report
                from tools.skills_tool import skills_list
                skills = json.loads(skills_list())
                return {
                    "ok": True,
                    "runtime": {"name": "Hermes", "version": "0.19.1"},
                    "memory": {"enabled": True, "provider": "local"},
                    "skills": {
                        "count": int(skills.get("count", 0)),
                        "categories": skills.get("categories", []),
                        "usage": usage_report(),
                        "agent_created": agent_created_report(),
                    },
                    "curator": {
                        "enabled": curator.is_enabled(),
                        "paused": curator.is_paused(),
                        "interval_hours": curator.get_interval_hours(),
                    },
                }
            if operation == "skills_list":
                from tools.skill_usage import usage_report
                from tools.skills_tool import skills_list
                data = json.loads(skills_list(category=payload.get("category")))
                usage = {row.get("name"): row for row in usage_report()}
                items = []
                for skill in data.get("skills", []):
                    item = dict(skill)
                    item["usage"] = usage.get(item.get("name"), {})
                    items.append(item)
                return {"items": items, "total": len(items), "categories": data.get("categories", [])}
            if operation == "skill_view":
                from tools.skills_tool import skill_view
                return json.loads(skill_view(str(payload.get("name") or ""), file_path=payload.get("file_path")))
            if operation == "skill_manage":
                from tools.skill_manager_tool import skill_manage
                return json.loads(skill_manage(
                    action=str(payload.get("action") or ""),
                    name=str(payload.get("name") or ""),
                    content=payload.get("content"),
                    category=payload.get("category"),
                    file_path=payload.get("file_path"),
                    file_content=payload.get("file_content"),
                    old_string=payload.get("old_string"),
                    new_string=payload.get("new_string"),
                    replace_all=bool(payload.get("replace_all", False)),
                    absorbed_into=payload.get("absorbed_into"),
                ))
            if operation == "curator_run":
                from agent.curator import run_curator_review
                return {"ok": True, "result": run_curator_review(None, False, False)}
            if operation == "curator_pause":
                from agent.curator import set_paused
                paused = bool(payload.get("paused"))
                set_paused(paused)
                return {"ok": True, "paused": paused}
            if operation in {"market_detail", "market_install"}:
                from tools.skills_hub import create_source_router
                identifier = str(payload.get("identifier") or "").strip()
                for source in create_source_router():
                    try:
                        meta = source.inspect(identifier)
                        if meta is None:
                            continue
                        result = {
                            "name": meta.name,
                            "description": meta.description,
                            "source": meta.source,
                            "identifier": meta.identifier,
                            "trust_level": meta.trust_level,
                            "repo": meta.repo,
                            "path": meta.path,
                            "tags": meta.tags,
                            "extra": meta.extra,
                        }
                        bundle = source.fetch(identifier)
                        if operation == "market_detail":
                            if bundle and "SKILL.md" in bundle.files:
                                skill_md = bundle.files["SKILL.md"]
                                if isinstance(skill_md, bytes):
                                    skill_md = skill_md.decode("utf-8", errors="replace")
                                result["skill_md_preview"] = "\n".join(str(skill_md).split("\n")[:80])
                                result["skill_md_full_lines"] = len(str(skill_md).split("\n"))
                            return result
                        if bundle is None:
                            continue
                        from tools.skills_guard import scan_skill, should_allow_install
                        from tools.skills_hub import install_from_quarantine, quarantine_bundle
                        quarantine_path = quarantine_bundle(bundle)
                        scan_result = scan_skill(quarantine_path, source=meta.source or "community")
                        allowed, reason = should_allow_install(scan_result, force=bool(payload.get("force")))
                        if not allowed:
                            return {"ok": False, "error": f"安装被安全策略拒绝: {reason}"}
                        install_path = install_from_quarantine(
                            quarantine_path, bundle.name, str(payload.get("category") or ""), bundle, scan_result
                        )
                        from agent.prompt_builder import clear_skills_system_prompt_cache
                        clear_skills_system_prompt_cache(clear_snapshot=True)
                        return {
                            "ok": True,
                            "skill_name": bundle.name,
                            "install_path": str(install_path),
                            "trust_level": meta.trust_level,
                            "scan_warnings": getattr(scan_result, "warnings", []),
                        }
                    except Exception:
                        continue
                return {"ok": False, "error": "技能不存在或暂时无法访问"}
            if operation == "installed_list":
                from tools.skills_hub import HubLockFile
                return {"ok": True, "installed": (HubLockFile().load() or {}).get("installed", {})}
            if operation == "skill_uninstall":
                from tools.skills_hub import uninstall_skill
                ok, message = uninstall_skill(str(payload.get("name") or ""))
                return {"ok": ok, "message": message}
            return {"ok": False, "error": "未知的运行时操作"}

        return await asyncio.to_thread(execute)

    @app.post("/v1/sessions/{session_id}/turn")
    async def turn(session_id: str, body: TurnRequest, x_szyg_hermes_token: str = Header(default="")):
        authorize(x_szyg_hermes_token)
        if session_id in state.paused_sessions:
            raise HTTPException(409, "Session is paused")
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        tool_ids: dict[str, str] = {}
        frame_stop = threading.Event()
        frame_thread: threading.Thread | None = None
        desktop_tools = {"computer_use", "szyg_open_desktop_app"}

        def emit(event: dict[str, Any]) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        def on_delta(delta: Any, *_: Any, **__: Any) -> None:
            text = str(delta or "")
            if text:
                emit({"type": "text", "content": text})

        def frame_pump() -> None:
            sequence = 0
            blocked_reported = False
            deadline = time.monotonic() + 300
            while not frame_stop.is_set():
                if time.monotonic() >= deadline:
                    emit({"type": "computer.stream.stopped", "reason": "preview_timeout"})
                    return
                try:
                    from szyg.hermes_windows_computer import latest_computer_frame

                    frame = latest_computer_frame(session_id, stream=True)
                    if frame and frame.get("blocked"):
                        if not blocked_reported:
                            emit({"type": "computer.stream.blocked", "content": frame.get("content", "")})
                            blocked_reported = True
                    elif frame:
                        blocked_reported = False
                        sequence += 1
                        emit({
                            "type": "computer.frame",
                            **frame,
                            "sequence": sequence,
                            "captured_at": time.time(),
                            "live": True,
                        })
                except Exception:
                    pass
                frame_stop.wait(0.5)

        def ensure_frame_stream() -> None:
            nonlocal frame_thread
            if frame_thread and frame_thread.is_alive():
                return
            frame_stop.clear()
            emit({"type": "computer.stream.started", "fps": 2})
            frame_thread = threading.Thread(
                target=frame_pump,
                name=f"desktop-preview-{session_id[:12]}",
                daemon=True,
            )
            frame_thread.start()

        def stop_frame_stream() -> None:
            if not frame_thread:
                return
            frame_stop.set()
            frame_thread.join(timeout=1.5)
            emit({"type": "computer.stream.stopped"})

        def on_tool_start(call_id: str, name: str, args: Any, *_: Any, **__: Any) -> None:
            tool_ids[name] = call_id
            emit({"type": "tool.started", "id": call_id, "tool": name, "args": args})
            if name in desktop_tools:
                ensure_frame_stream()

        def on_tool_complete(call_id: str, name: str, args: Any, result: Any, *_: Any, **__: Any) -> None:
            emit({"type": "tool.completed", "id": call_id, "tool": name, "args": args, "result": str(result or "")[:12000]})
            if name in desktop_tools:
                action = (args or {}).get("action", "") if name == "computer_use" else "打开应用"
                emit({
                    "type": "computer.action",
                    "id": call_id,
                    "action": action,
                    "args": args or {},
                    "content": "桌面操作已执行",
                })
                if name == "szyg_open_desktop_app" or (args or {}).get("action") == "capture":
                    try:
                        from szyg.hermes_windows_computer import latest_computer_frame

                        frame = latest_computer_frame(session_id)
                        if frame and frame.get("blocked"):
                            emit({"type": "computer.stream.blocked", "content": frame.get("content", "")})
                        elif frame:
                            emit({"type": "computer.frame", **frame})
                    except Exception:
                        pass

        def on_tool_progress(event_type: str, name: str, preview: Any = None, args: Any = None, **extra: Any) -> None:
            if event_type in {"tool.started", "tool.completed"}:
                return
            emit({"type": "tool.progress", "tool": name, "content": str(preview or ""), "args": args, **extra})

        def on_status(kind: str, message: Any = "", *_: Any, **__: Any) -> None:
            emit({"type": "status.changed", "status": kind, "content": str(message or kind)})

        callbacks = {
            "stream_delta_callback": on_delta,
            "tool_start_callback": on_tool_start,
            "tool_complete_callback": on_tool_complete,
            "tool_progress_callback": on_tool_progress,
            "status_callback": on_status,
        }
        with state.guard:
            state.active_emitters[session_id] = emit

        def run() -> None:
            token = set_execution_context(body.context_id)
            try:
                runtime_session = state.session(session_id, callbacks, body.system_prompt)
                with runtime_session.lock:
                    result = runtime_session.agent.run_conversation(
                        body.message,
                        conversation_history=body.history or None,
                        task_id=str(uuid.uuid4()),
                    )
                result_payload = result or {}
                final = str(result_payload.get("final_response") or "")
                runtime_error = str(result_payload.get("error") or "").strip()
                mode = state.interrupt_modes.pop(session_id, "")
                if result_payload.get("interrupted") is True and mode == "pause":
                    state.paused_sessions.add(session_id)
                    emit({"type": "run.paused", "content": "已暂停，当前窗口交由你操作"})
                elif result_payload.get("interrupted") is True:
                    emit({"type": "run.failed", "code": "cancelled", "content": "任务已停止"})
                elif runtime_error or _failed_final_response(final):
                    emit({"type": "run.failed", "content": runtime_error or final})
                else:
                    emit({"type": "run.completed", "content": final})
            except BaseException as exc:
                emit({"type": "run.failed", "content": str(exc)[:600]})
            finally:
                stop_frame_stream()
                with state.guard:
                    state.active_emitters.pop(session_id, None)
                reset_execution_context(token)
                loop.call_soon_threadsafe(queue.put_nowait, None)

        asyncio.create_task(asyncio.to_thread(run))

        async def events():
            yield _sse({"type": "run.started", "session_id": session_id})
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield _sse(event)

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.post("/v1/sessions/{session_id}/interrupt")
    async def interrupt(session_id: str, body: InterruptRequest, x_szyg_hermes_token: str = Header(default="")):
        authorize(x_szyg_hermes_token)
        current = state.sessions.get(session_id)
        if not current:
            raise HTTPException(404, "Session not found")
        state.interrupt_modes[session_id] = body.mode
        current.agent.interrupt("用户已暂停当前任务" if body.mode == "pause" else "用户已停止当前任务")
        return {"ok": True}

    @app.post("/v1/sessions/{session_id}/resume")
    async def resume(session_id: str, x_szyg_hermes_token: str = Header(default="")):
        authorize(x_szyg_hermes_token)
        state.paused_sessions.discard(session_id)
        return {"ok": True}

    @app.post("/v1/approvals/{approval_id}")
    async def approval(approval_id: str, body: ApprovalDecision, x_szyg_hermes_token: str = Header(default="")):
        authorize(x_szyg_hermes_token)
        allowed = {"approve_once", "approve_session", "always_approve", "deny"}
        if body.decision not in allowed:
            raise HTTPException(422, "Invalid decision")
        if not state.decide(approval_id, body.decision):
            raise HTTPException(404, "Approval no longer active")
        return {"ok": True}

    return app
