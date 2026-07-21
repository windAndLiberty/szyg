"""Thin integration layer for Hermes native memory and skill capabilities.

SZYG owns the product surface. Hermes remains the single source of truth for
persistent conversational memory, procedural skills, and skill curation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _config() -> Dict[str, Any]:
    from hermes_cli.config import load_config

    config = load_config()
    return config if isinstance(config, dict) else {}


def _tool_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": "function", "function": schema}


def native_skill_tool_schemas() -> List[Dict[str, Any]]:
    from tools.skill_manager_tool import SKILL_MANAGE_SCHEMA
    from tools.skills_tool import SKILLS_LIST_SCHEMA, SKILL_VIEW_SCHEMA

    return [_tool_schema(SKILLS_LIST_SCHEMA), _tool_schema(SKILL_VIEW_SCHEMA), _tool_schema(SKILL_MANAGE_SCHEMA)]


@dataclass
class HermesRuntimeSession:
    session_id: str
    memory_store: Any = None
    memory_manager: Any = None
    memory_enabled: bool = False
    user_profile_enabled: bool = False
    provider_name: str = ""
    warnings: List[str] = field(default_factory=list)

    @classmethod
    def create(cls, session_id: str, *, include_provider: bool = True) -> "HermesRuntimeSession":
        runtime = cls(session_id=session_id or "szyg-default")
        memory_config = _config().get("memory") or {}
        runtime.memory_enabled = bool(memory_config.get("memory_enabled", False))
        runtime.user_profile_enabled = bool(memory_config.get("user_profile_enabled", False))
        runtime.provider_name = str(memory_config.get("provider") or "").strip()

        if runtime.memory_enabled or runtime.user_profile_enabled:
            try:
                from tools.memory_tool import MemoryStore

                runtime.memory_store = MemoryStore(
                    memory_char_limit=int(memory_config.get("memory_char_limit", 2200)),
                    user_char_limit=int(memory_config.get("user_char_limit", 1375)),
                )
                runtime.memory_store.load_from_disk()
            except Exception as exc:
                logger.warning("Hermes built-in memory unavailable: %s", exc)
                runtime.warnings.append(f"内置记忆加载失败: {exc}")

        if include_provider and runtime.provider_name:
            try:
                from agent.memory_manager import MemoryManager
                from hermes_constants import get_hermes_home
                from plugins.memory import load_memory_provider

                provider = load_memory_provider(runtime.provider_name)
                if provider is None or not provider.is_available():
                    runtime.warnings.append(f"记忆提供方 {runtime.provider_name} 尚未就绪")
                else:
                    manager = MemoryManager()
                    manager.add_provider(provider)
                    provider.initialize(
                        runtime.session_id,
                        platform="szyg",
                        hermes_home=str(get_hermes_home()),
                        agent_context="primary",
                        agent_workspace="szyg",
                    )
                    runtime.memory_manager = manager
            except Exception as exc:
                logger.warning("Hermes memory provider initialization failed: %s", exc)
                runtime.warnings.append(f"记忆提供方初始化失败: {exc}")
        return runtime

    def system_context(self, query: str) -> str:
        blocks: List[str] = []
        if self.memory_store is not None:
            if self.memory_enabled:
                memory = self.memory_store.format_for_system_prompt("memory")
                if memory:
                    blocks.append(memory)
            if self.user_profile_enabled:
                user = self.memory_store.format_for_system_prompt("user")
                if user:
                    blocks.append(user)
        if self.memory_manager is not None:
            static = self.memory_manager.build_system_prompt()
            recalled = self.memory_manager.prefetch_all(query, session_id=self.session_id)
            if static:
                blocks.append(static)
            if recalled:
                from agent.memory_manager import build_memory_context_block

                blocks.append(build_memory_context_block(recalled))
        return "\n\n".join(blocks)

    def tool_schemas(self) -> List[Dict[str, Any]]:
        schemas: List[Dict[str, Any]] = []
        if self.memory_store is not None:
            from tools.memory_tool import MEMORY_SCHEMA

            schemas.append(_tool_schema(MEMORY_SCHEMA))
        if self.memory_manager is not None:
            schemas.extend(_tool_schema(schema) for schema in self.memory_manager.get_all_tool_schemas())
        return schemas

    def handles_tool(self, name: str) -> bool:
        return name == "memory" or bool(self.memory_manager and self.memory_manager.has_tool(name))

    def execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        if name == "memory":
            from tools.memory_tool import memory_tool

            return memory_tool(
                action=str(args.get("action") or ""),
                target=str(args.get("target") or "memory"),
                content=args.get("content"),
                old_text=args.get("old_text"),
                store=self.memory_store,
            )
        if self.memory_manager and self.memory_manager.has_tool(name):
            return self.memory_manager.handle_tool_call(name, args, session_id=self.session_id)
        return json.dumps({"success": False, "error": f"Unknown Hermes memory tool: {name}"}, ensure_ascii=False)

    def complete_turn(self, user_content: str, assistant_content: str, messages: List[Dict[str, Any]]) -> None:
        if self.memory_manager is None:
            return
        self.memory_manager.sync_all(
            user_content,
            assistant_content,
            session_id=self.session_id,
            messages=messages,
        )
        self.memory_manager.queue_prefetch_all(user_content, session_id=self.session_id)

    def close(self) -> None:
        if self.memory_manager is not None:
            self.memory_manager.shutdown_all()


def execute_native_skill_tool(name: str, args: Dict[str, Any]) -> str:
    if name == "skills_list":
        from tools.skills_tool import skills_list

        return skills_list(category=args.get("category"), task_id=args.get("task_id"))
    if name == "skill_view":
        from tools.skills_tool import skill_view

        result = skill_view(
            name=str(args.get("name") or ""),
            file_path=args.get("file_path"),
        )
        try:
            parsed = json.loads(result)
            if parsed.get("success"):
                from tools.skill_usage import bump_use, bump_view

                bump_view(str(args.get("name") or ""))
                bump_use(str(args.get("name") or ""))
        except Exception:
            pass
        return result
    if name == "skill_manage":
        from tools.skill_manager_tool import skill_manage

        return skill_manage(
            action=str(args.get("action") or ""),
            name=str(args.get("name") or ""),
            content=args.get("content"),
            category=args.get("category"),
            file_path=args.get("file_path"),
            file_content=args.get("file_content"),
            old_string=args.get("old_string"),
            new_string=args.get("new_string"),
            replace_all=bool(args.get("replace_all", False)),
            absorbed_into=args.get("absorbed_into"),
        )
    return json.dumps({"success": False, "error": f"Unknown Hermes skill tool: {name}"}, ensure_ascii=False)


def runtime_status() -> Dict[str, Any]:
    from agent import curator
    from hermes_constants import get_hermes_home
    from plugins.memory import discover_memory_providers
    from tools.skill_usage import agent_created_report, usage_report
    from tools.skills_tool import skills_list

    config = _config()
    memory_config = config.get("memory") or {}
    skill_data = json.loads(skills_list())
    provider_rows = [
        {"name": name, "description": description, "available": available}
        for name, description, available in discover_memory_providers()
    ]
    curator_state = curator.load_state()
    return {
        "ok": True,
        "hermes_home": str(get_hermes_home()),
        "memory": {
            "enabled": bool(memory_config.get("memory_enabled", False)),
            "user_profile_enabled": bool(memory_config.get("user_profile_enabled", False)),
            "provider": str(memory_config.get("provider") or ""),
            "providers": provider_rows,
        },
        "skills": {
            "count": int(skill_data.get("count", 0)),
            "categories": skill_data.get("categories", []),
            "usage": usage_report(),
            "agent_created": agent_created_report(),
        },
        "curator": {
            "enabled": curator.is_enabled(),
            "paused": curator.is_paused(),
            "interval_hours": curator.get_interval_hours(),
            "stale_after_days": curator.get_stale_after_days(),
            "archive_after_days": curator.get_archive_after_days(),
            **curator_state,
        },
    }


def maybe_run_native_curator() -> None:
    try:
        from agent.curator import maybe_run_curator

        maybe_run_curator()
    except Exception as exc:
        logger.debug("Hermes curator check skipped: %s", exc)
