"""
「域灵」数字员工系统 - 技能注册表模块

管理 Agent 可调用的技能，包括注册、注销、查询和执行。
"""

import time
from typing import Any, Callable

from szyg.models.common import DuplicateSkillError, SkillNotFoundError
from szyg.models.skill import Skill, SkillParameter, SkillResult


class SkillRegistry:
    """技能注册表 - 管理 Agent 可调用的技能。

    提供技能注册、注销、列出、查询和执行功能。
    """

    def __init__(self):
        """初始化空的技能注册表。"""
        self._skills: dict[str, Skill] = {}
        self._handlers: dict[str, Callable] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: list[dict] | None = None,
        handler: Callable | None = None,
    ) -> Skill:
        """注册技能。

        Args:
            name: 技能名称（唯一标识）
            description: 技能描述
            parameters: 参数定义列表，每个元素为字典
            handler: 技能处理函数

        Returns:
            注册的技能对象

        Raises:
            DuplicateSkillError: 技能已存在时抛出
        """
        if name in self._skills:
            raise DuplicateSkillError(f"Skill '{name}' already registered")
        skill = Skill(
            name=name,
            description=description,
            parameters=[SkillParameter(**p) for p in (parameters or [])],
        )
        self._skills[name] = skill
        if handler is not None:
            self._handlers[name] = handler
        return skill

    def unregister(self, name: str) -> bool:
        """注销技能。

        Args:
            name: 技能名称

        Returns:
            是否成功注销
        """
        if name not in self._skills:
            return False
        del self._skills[name]
        self._handlers.pop(name, None)
        return True

    def list_skills(self) -> list[Skill]:
        """列出所有已注册技能。

        Returns:
            技能对象列表
        """
        return list(self._skills.values())

    def get_skill(self, name: str) -> Skill:
        """获取技能定义。

        Args:
            name: 技能名称

        Returns:
            技能对象

        Raises:
            SkillNotFoundError: 技能不存在时抛出
        """
        if name not in self._skills:
            raise SkillNotFoundError(f"Skill not found: {name}")
        return self._skills[name]

    def execute(self, skill_name: str, **parameters: Any) -> SkillResult:
        """执行技能。

        Args:
            skill_name: 技能名称
            **parameters: 传递给技能处理函数的参数

        Returns:
            技能执行结果

        Raises:
            SkillNotFoundError: 技能不存在时抛出
        """
        if skill_name not in self._skills:
            raise SkillNotFoundError(f"Skill not found: {skill_name}")
        if skill_name not in self._handlers:
            return SkillResult(success=False, error=f"No handler for skill: {skill_name}")
        start = time.time()
        try:
            result = self._handlers[skill_name](**parameters)
            return SkillResult(
                success=True, data=result, execution_time=time.time() - start
            )
        except Exception as e:
            return SkillResult(
                success=False, error=str(e), execution_time=time.time() - start
            )

    def has_skill(self, name: str) -> bool:
        """检查技能是否已注册。

        Args:
            name: 技能名称

        Returns:
            是否已注册
        """
        return name in self._skills

    def get_handler(self, name: str) -> Callable | None:
        """获取技能处理函数。

        Args:
            name: 技能名称

        Returns:
            处理函数，未设置则返回 None
        """
        return self._handlers.get(name)

    def set_handler(self, name: str, handler: Callable) -> None:
        """设置技能处理函数。

        Args:
            name: 技能名称
            handler: 处理函数

        Raises:
            SkillNotFoundError: 技能不存在时抛出
        """
        if name not in self._skills:
            raise SkillNotFoundError(f"Skill not found: {name}")
        self._handlers[name] = handler
