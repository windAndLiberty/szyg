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
import uuid
from datetime import datetime
from typing import Any

from szyg.agent_core.memory import Memory
from szyg.agent_core.skill_registry import SkillRegistry


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
    ):
        self.id = sop_id or str(uuid.uuid4())[:8]
        self.name = name
        self.description = description
        self.steps = steps
        self.created_at = datetime.now().isoformat()

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
        self._memory = Memory(db_path)
        self._load_from_memory()

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
        """持久化 SOP 到 Memory。"""
        self._memory.store(
            content=sop.name,
            metadata={
                "type": "sop",
                "sop_id": sop.id,
                "sop_data": json.dumps(sop.to_dict(), ensure_ascii=False),
            },
        )

    def _load_from_memory(self):
        """从 Memory 恢复已保存的 SOP。"""
        try:
            results = self._memory.search_by_metadata("type", "sop", limit=100)
            for r in results:
                try:
                    data = json.loads(r.metadata.get("sop_data", "{}"))
                    sop = SOP.from_dict(data)
                    self._sops[sop.name] = sop
                except (json.JSONDecodeError, KeyError):
                    pass
        except Exception:
            pass  # 首次使用，无已存储 SOP

    # ── 查询 ──────────────────────────────────────────────────────────────

    def list_sops(self) -> list[SOP]:
        """列出所有 SOP。"""
        return list(self._sops.values())

    def get_sop(self, name: str) -> SOP | None:
        """按名称获取 SOP。"""
        return self._sops.get(name)

    def find_sops_for_task(self, task_description: str) -> list[SOP]:
        """根据任务描述搜索匹配的 SOP（FTS5 搜索）。"""
        results = self._memory.search(task_description, limit=5)
        matched = []
        for r in results:
            sop_name = r.content
            if sop_name in self._sops:
                matched.append(self._sops[sop_name])
        return matched

    def delete(self, name: str) -> bool:
        """删除 SOP。"""
        if name not in self._sops:
            return False
        sop = self._sops.pop(name)
        # 从 Memory 中删除
        results = self._memory.search(name, limit=1)
        for r in results:
            if r.metadata.get("sop_id") == sop.id:
                self._memory.delete(r.id)
                break
        return True

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
        self._memory.close()
