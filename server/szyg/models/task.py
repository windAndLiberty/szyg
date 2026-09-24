"""任务相关模型。"""

from typing import Literal

from pydantic import BaseModel


class TaskStep(BaseModel):
    """任务步骤。"""

    id: int
    description: str
    tool_name: str | None = None
    parameters: dict = {}
    dependencies: list[int] = []
    status: Literal["pending", "running", "completed", "failed"] = "pending"


class TaskPlan(BaseModel):
    """任务计划。"""

    instruction: str
    steps: list[TaskStep]
    status: str = "pending"
