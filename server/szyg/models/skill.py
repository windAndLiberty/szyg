"""技能相关模型。"""

from typing import Any

from pydantic import BaseModel, Field


class SkillParameter(BaseModel):
    """技能参数。"""

    name: str
    type: str = "string"
    description: str = ""
    required: bool = True
    default: Any = None


class Skill(BaseModel):
    """技能定义。"""

    name: str
    description: str
    parameters: list[SkillParameter] = []
    handler: Any = Field(default=None, exclude=True)


class SkillResult(BaseModel):
    """技能执行结果。"""

    success: bool
    data: Any = None
    error: str | None = None
    execution_time: float = 0.0
