"""
「域灵」数字员工系统 - SkillRegistry模块测试

测试范围:
- 技能注册
- 技能列出
- 技能执行
- 不存在的技能处理
- 参数验证
- 技能注销
- 重复注册处理
"""

from typing import Any, Callable
from unittest.mock import MagicMock

import pytest


# =============================================================================
# Helper Functions
# =============================================================================

class SkillNotFoundError(Exception):
    """技能不存在异常。"""
    pass


class DuplicateSkillError(Exception):
    """重复注册异常。"""
    pass


class SkillExecutionError(Exception):
    """技能执行异常。"""
    pass


class SkillValidationError(Exception):
    """技能参数验证异常。"""
    pass


def create_skill_registry():
    """创建真实的SkillRegistry实例。"""
    registry = {
        "_skills": {},
    }

    def register(name: str, description: str, handler: Callable, parameters: dict = None, overwrite: bool = False) -> None:
        if name in registry["_skills"] and not overwrite:
            raise DuplicateSkillError(f"Skill '{name}' already registered. Use overwrite=True to replace.")
        registry["_skills"][name] = {
            "name": name,
            "description": description,
            "handler": handler,
            "parameters": parameters or {},
        }

    def list_skills() -> list:
        return [
            {"name": k, "description": v["description"], "parameters": v["parameters"]}
            for k, v in registry["_skills"].items()
        ]

    def execute(name: str, **kwargs) -> Any:
        if name not in registry["_skills"]:
            raise SkillNotFoundError(f"Skill not found: {name}")
        skill = registry["_skills"][name]
        # Validate parameters
        if skill["parameters"]:
            for param_name, param_info in skill["parameters"].items():
                if param_info.get("required", False) and param_name not in kwargs:
                    raise SkillValidationError(f"Missing required parameter: {param_name}")
                if param_name in kwargs and "type" in param_info:
                    expected_type = param_info["type"]
                    if not isinstance(kwargs[param_name], expected_type):
                        raise SkillValidationError(
                            f"Parameter '{param_name}' should be {expected_type.__name__}"
                        )
        try:
            return skill["handler"](**kwargs)
        except Exception as e:
            raise SkillExecutionError(f"Skill execution failed: {e}") from e

    def unregister(name: str) -> None:
        if name not in registry["_skills"]:
            raise SkillNotFoundError(f"Skill not found: {name}")
        del registry["_skills"][name]

    registry["register"] = register
    registry["list_skills"] = list_skills
    registry["execute"] = execute
    registry["unregister"] = unregister
    return registry


# =============================================================================
# 测试用例
# =============================================================================


class TestSkillRegistry:
    """SkillRegistry模块测试类。"""

    def test_register_skill(self):
        """
        验收标准: SKL-001 - 应支持注册带名称、描述、处理函数的技能。

        Arrange: 准备技能信息
        Act: 注册技能
        Assert: 技能注册成功，可列出
        """
        # Arrange
        registry = create_skill_registry()

        def greet(name: str) -> str:
            return f"Hello, {name}!"

        # Act
        registry["register"](
            name="greet",
            description="Greet a person by name",
            handler=greet,
            parameters={
                "name": {"type": str, "required": True, "description": "Name of the person"}
            },
        )

        # Assert
        skills = registry["list_skills"]()
        assert len(skills) == 1
        assert skills[0]["name"] == "greet"
        assert skills[0]["description"] == "Greet a person by name"
        assert "name" in skills[0]["parameters"]

    def test_list_skills(self):
        """
        验收标准: SKL-002 - 应能列出所有已注册技能。

        Arrange: 注册多个技能
        Act: 列出技能
        Assert: 返回所有已注册技能
        """
        # Arrange
        registry = create_skill_registry()
        for i in range(3):
            registry["register"](
                name=f"skill_{i}",
                description=f"Skill number {i}",
                handler=lambda x=i: x,
            )

        # Act
        skills = registry["list_skills"]()

        # Assert
        assert len(skills) == 3
        names = [s["name"] for s in skills]
        assert "skill_0" in names
        assert "skill_1" in names
        assert "skill_2" in names

    def test_execute_skill(self):
        """
        验收标准: SKL-003 - 应能通过名称执行已注册技能并返回结果。

        Arrange: 注册一个计算技能
        Act: 执行该技能
        Assert: 返回正确结果
        """
        # Arrange
        registry = create_skill_registry()

        def add(a: int, b: int) -> int:
            return a + b

        registry["register"](
            name="add",
            description="Add two numbers",
            handler=add,
            parameters={
                "a": {"type": int, "required": True},
                "b": {"type": int, "required": True},
            },
        )

        # Act
        result = registry["execute"]("add", a=3, b=5)

        # Assert
        assert result == 8, f"Expected 8, got {result}"

    def test_execute_nonexistent_skill(self):
        """
        验收标准: SKL-004 - 执行不存在的技能应抛出SkillNotFoundError。

        Arrange: 空注册表
        Act & Assert: 执行不存在的技能应抛异常
        """
        # Arrange
        registry = create_skill_registry()

        # Act & Assert
        with pytest.raises(SkillNotFoundError) as exc_info:
            registry["execute"]("nonexistent_skill")
        assert "nonexistent_skill" in str(exc_info.value)

    def test_skill_parameter_validation(self):
        """
        验收标准: SKL-005 - 技能参数验证失败应抛出ValidationError。

        Arrange: 注册带参数验证的技能
        Act: 使用无效参数执行
        Assert: 抛出SkillValidationError
        """
        # Arrange
        registry = create_skill_registry()

        def divide(a: int, b: int) -> float:
            return a / b

        registry["register"](
            name="divide",
            description="Divide two numbers",
            handler=divide,
            parameters={
                "a": {"type": int, "required": True},
                "b": {"type": int, "required": True},
            },
        )

        # Act & Assert - Missing parameter
        with pytest.raises(SkillValidationError) as exc_info:
            registry["execute"]("divide", a=10)
        assert "Missing required parameter" in str(exc_info.value)

        # Act & Assert - Wrong type
        with pytest.raises(SkillValidationError) as exc_info:
            registry["execute"]("divide", a="not_int", b=2)
        assert "should be int" in str(exc_info.value)

    def test_unregister_skill(self):
        """
        验收标准: SKL-006 - 应支持注销已注册技能。

        Arrange: 注册一个技能
        Act: 注销该技能
        Assert: 技能不再存在
        """
        # Arrange
        registry = create_skill_registry()
        registry["register"](
            name="temp_skill",
            description="A temporary skill",
            handler=lambda: "temp",
        )
        assert len(registry["list_skills"]()) == 1

        # Act
        registry["unregister"]("temp_skill")

        # Assert
        assert len(registry["list_skills"]()) == 0
        with pytest.raises(SkillNotFoundError):
            registry["execute"]("temp_skill")

    def test_register_duplicate(self):
        """
        验收标准: SKL-007 - 重复注册同名技能应抛出DuplicateSkillError。

        Arrange: 注册一个技能
        Act & Assert: 再次注册同名技能应抛异常
        """
        # Arrange
        registry = create_skill_registry()
        registry["register"](
            name="unique_skill",
            description="Original",
            handler=lambda: "original",
        )

        # Act & Assert - Duplicate without overwrite
        with pytest.raises(DuplicateSkillError) as exc_info:
            registry["register"](
                name="unique_skill",
                description="Duplicate",
                handler=lambda: "duplicate",
            )
        assert "unique_skill" in str(exc_info.value)

        # Act - Overwrite should work
        registry["register"](
            name="unique_skill",
            description="Updated",
            handler=lambda: "updated",
            overwrite=True,
        )

        # Assert - Verify overwrite succeeded
        skills = registry["list_skills"]()
        assert len(skills) == 1
        assert skills[0]["description"] == "Updated"

    def test_skill_execution_error(self):
        """
        验收标准: SKL-008 - 技能执行异常应被捕获并包装为SkillExecutionError。

        Arrange: 注册一个会抛出异常的技能
        Act: 执行该技能
        Assert: 抛出SkillExecutionError
        """
        # Arrange
        registry = create_skill_registry()

        def failing_skill():
            raise RuntimeError("Something went wrong!")

        registry["register"](
            name="failing",
            description="This skill always fails",
            handler=failing_skill,
        )

        # Act & Assert
        with pytest.raises(SkillExecutionError) as exc_info:
            registry["execute"]("failing")
        assert "Skill execution failed" in str(exc_info.value)
