"""
「域灵」SOP 管理器 — 用户定义标准操作流程。

SOP (Standard Operating Procedure) 是用户自定义的工作流模板。
每个 SOP 包含名称、描述、有序步骤列表，每步引用一个技能。

与 Planner + SkillRegistry 协作:
    - 用户定义 SOP → 存为结构化模板
    - Planner 匹配 SOP → 按步骤依次执行
    - SkillRegistry 执行每一步

用法:
    sop = SOPManager(skill_registry)
    sop.define("视频创作SOP", "自动创建短视频", [
        {"skill": "生成脚本", "params": {"topic": "..."}},
        {"skill": "生成封面", "params": {"theme": "..."}},
        {"skill": "合成视频", "params": {"output": "output.mp4"}},
    ])
    result = await sop.execute("视频创作SOP", topic="AI趋势")
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from szyg.agent_core.skill_registry import SkillRegistry

logger = logging.getLogger(__name__)


class SOPStep:
    """SOP 步骤定义。"""

    def __init__(
        self,
        skill: str,
        params: dict | None = None,
        description: str = "",
        on_failure: str = "stop",  # stop | skip | retry
    ):
        self.skill = skill
        self.params = params or {}
        self.description = description
        self.on_failure = on_failure

    def to_dict(self) -> dict:
        return {
            "skill": self.skill,
            "params": self.params,
            "description": self.description,
            "on_failure": self.on_failure,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SOPStep":
        return cls(**d)


class SOP:
    """标准操作流程。"""

    def __init__(
        self,
        name: str,
        description: str,
        steps: list[SOPStep],
        sop_id: str = None,
        created_at: str | None = None,
    ):
        self.id = sop_id or str(uuid.uuid4())[:8]
        self.name = name
        self.description = description
        self.steps = steps
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SOP":
        return cls(
            name=d["name"],
            description=d["description"],
            steps=[SOPStep.from_dict(s) for s in d["steps"]],
            sop_id=d.get("id"),
            created_at=d.get("created_at"),
        )


class SOPManager:
    """SOP 管理器 — 定义、存储、执行标准操作流程。"""

    def __init__(
        self,
        skill_registry: SkillRegistry | None = None,
        db_path: str = "./data/sop.db",
    ):
        self.registry = skill_registry or SkillRegistry()
        self._sops: dict[str, SOP] = {}
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_db()
        self._load()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                DROP TRIGGER IF EXISTS memories_ai;
                DROP TRIGGER IF EXISTS memories_ad;
                DROP TRIGGER IF EXISTS memories_au;
                DROP TABLE IF EXISTS memories_fts;
                DROP TABLE IF EXISTS memories;
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sops (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    # ── 定义 ──────────────────────────────────────────────────────────────

    def define(self, name: str, description: str, steps: list[dict]) -> SOP:
        """定义新 SOP。

        Args:
            name: SOP 名称（如 "短视频创作标准流程"）
            description: 描述
            steps: 步骤列表，每项 {"skill": "技能名", "params": {...}, "on_failure": "stop"}

        Returns:
            SOP: 创建的 SOP 对象

        Raises:
            ValueError: 同名 SOP 已存在
        """
        if name in self._sops:
            raise ValueError(f"SOP '{name}' already exists")

        sop = SOP(
            name=name,
            description=description,
            steps=[SOPStep(**s) for s in steps],
        )
        self._sops[name] = sop
        self._save_sop(sop)
        return sop

    def _save_sop(self, sop: SOP):
        """Persist SOP in its own domain table."""
        now = datetime.now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sops(id,name,data_json,created_at,updated_at)
                VALUES (?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    data_json=excluded.data_json,
                    updated_at=excluded.updated_at
                """,
                (sop.id, sop.name, json.dumps(sop.to_dict(), ensure_ascii=False), sop.created_at, now),
            )

    def _load(self):
        """Load persisted SOP definitions."""
        try:
            with self._connect() as connection:
                rows = connection.execute("SELECT data_json FROM sops ORDER BY created_at").fetchall()
            for row in rows:
                try:
                    data = json.loads(row["data_json"])
                    sop = SOP.from_dict(data)
                    self._sops[sop.name] = sop
                except (json.JSONDecodeError, KeyError) as e:
                    logger.debug("Skipping malformed SOP entry: %s", e)
        except Exception as e:
            logger.debug("No stored SOPs found or load failed: %s", e)

    # ── 查询 ──────────────────────────────────────────────────────────────

    def list_sops(self) -> list[SOP]:
        """列出所有 SOP。"""
        return list(self._sops.values())

    def get_sop(self, name: str) -> SOP | None:
        """按名称获取 SOP。"""
        return self._sops.get(name)

    def find_sops_for_task(self, task_description: str) -> list[SOP]:
        """Find SOPs by name, description, and step text."""
        terms = [part.lower() for part in task_description.split() if part.strip()]
        if not terms:
            return []
        scored: list[tuple[int, SOP]] = []
        for sop in self._sops.values():
            text = json.dumps(sop.to_dict(), ensure_ascii=False).lower()
            score = sum(text.count(term) for term in terms)
            if score:
                scored.append((score, sop))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [sop for _, sop in scored[:5]]

    def delete(self, name: str) -> bool:
        """删除 SOP。"""
        if name not in self._sops:
            return False
        sop = self._sops.pop(name)
        with self._connect() as connection:
            connection.execute("DELETE FROM sops WHERE id=?", (sop.id,))
        return True

    def save(self, sop: SOP) -> SOP:
        """Persist changes to an existing SOP."""
        existing_name = next((name for name, item in self._sops.items() if item.id == sop.id), None)
        if existing_name and existing_name != sop.name:
            self._sops.pop(existing_name, None)
        self._sops[sop.name] = sop
        self._save_sop(sop)
        return sop

    # ── 执行 ──────────────────────────────────────────────────────────────

    async def execute(
        self, sop_name: str, **variables
    ) -> list[dict]:
        """按 SOP 步骤依次执行。

        Args:
            sop_name: SOP 名称
            **variables: 变量值，会替换步骤参数中的 {变量名}

        Returns:
            list[dict]: 每一步的执行结果 {"step": int, "skill": str, "success": bool, "output": any}
        """
        sop = self._sops.get(sop_name)
        if sop is None:
            raise ValueError(f"SOP not found: {sop_name}")

        results = []
        for i, step in enumerate(sop.steps):
            # 替换参数中的变量
            params = {}
            for k, v in step.params.items():
                if isinstance(v, str) and "{" in v:
                    params[k] = v.format(**variables)
                else:
                    params[k] = v

            result = self.registry.execute(step.skill, **params)

            step_result = {
                "step": i + 1,
                "skill": step.skill,
                "success": result.success,
                "output": result.data if result.success else result.error,
            }
            results.append(step_result)

            if not result.success:
                if step.on_failure == "stop":
                    break
                elif step.on_failure == "retry":
                    result = self.registry.execute(step.skill, **params)
                    step_result["success"] = result.success
                    step_result["output"] = result.data if result.success else result.error
                    if not result.success:
                        break

        return results

    def close(self):
        return None
