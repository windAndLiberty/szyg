"""
「域灵」数字员工系统 - 任务规划器模块

将自然语言指令拆解为可执行步骤，支持基于关键词的简易规划。
"""

from typing import Any

from szyg.models.common import ValidationError
from szyg.models.task import TaskPlan, TaskStep


class Planner:
    """任务规划器 - 将自然语言指令拆解为可执行步骤。

    基于关键词的简易规划（实际应用中应调用 LLM）。
    """

    def __init__(self, config: Any = None) -> None:
        """初始化规划器。

        Args:
            config: 配置对象，可以为 None
        """
        self.config = config
        self.max_steps = getattr(config, "max_plan_steps", 10) if config else 10

    def plan_task(self, instruction: str, context: dict | None = None) -> TaskPlan:
        """规划任务 - 将指令拆解为步骤。

        Args:
            instruction: 自然语言指令
            context: 上下文信息

        Returns:
            任务规划对象

        Raises:
            ValidationError: 指令为空时抛出
        """
        if not instruction or not instruction.strip():
            raise ValidationError("Instruction cannot be empty")

        # 基于关键词的简易规划（实际应用中应调用 LLM）
        steps = self._rule_based_plan(instruction, context or {})

        return TaskPlan(instruction=instruction, steps=steps, status="planned")

    def _rule_based_plan(self, instruction: str, context: dict) -> list[TaskStep]:
        """基于规则的任务拆解（简化版，实际应调用 LLM）。

        识别指令中的步骤关键词，如"然后"、"接着"、"第一步"等，
        将指令拆分为多个可执行步骤。

        Args:
            instruction: 自然语言指令
            context: 上下文信息

        Returns:
            任务步骤列表
        """
        steps: list[TaskStep] = []

        # 检查是否包含多个步骤关键词
        step_markers = ["然后", "接着", "第一步", "第二步", "第三步", "最后", "再"]
        has_markers = any(m in instruction for m in step_markers)

        if has_markers:
            # 按分隔词拆分
            normalized = instruction
            for marker in ["接着", "最后"]:
                normalized = normalized.replace(marker, "然后")
            parts = [p.strip() for p in normalized.split("然后") if p.strip()]

            for i, part in enumerate(parts):
                # 识别需要的工具
                tool_name = self._infer_tool(part)
                steps.append(
                    TaskStep(
                        id=i + 1,
                        description=part,
                        tool_name=tool_name,
                        dependencies=[steps[-1].id] if steps else [],
                        parameters={"query": part} if tool_name else {},
                    )
                )
        else:
            # 单步骤任务
            tool_name = self._infer_tool(instruction)
            steps.append(
                TaskStep(
                    id=1,
                    description=instruction,
                    tool_name=tool_name,
                    parameters={"query": instruction} if tool_name else {},
                )
            )

        # 限制步骤数
        if len(steps) > self.max_steps:
            steps = steps[: self.max_steps]

        return steps

    def _infer_tool(self, description: str) -> str | None:
        """从描述推断需要的工具。

        根据描述中的关键词匹配对应的工具名称。

        Args:
            description: 步骤描述

        Returns:
            工具名称，未匹配则返回 None
        """
        tool_keywords = {
            "computer-use": ["打开", "点击", "剪映", "微信客户端", "桌面", "软件"],
            "browser-use": ["网页", "登录", "上传", "抖音", "小红书", "浏览器", "网站"],
            "whisper": ["语音", "录音", "转文字", "语音识别"],
            "comfyui": ["生成图片", "封面", "配图", "AI绘画"],
            "ffmpeg": ["剪辑", "视频", "转码", "合成", "字幕"],
            "memory": ["记住", "记忆", "存储", "记录"],
        }

        for tool, keywords in tool_keywords.items():
            if any(kw in description for kw in keywords):
                return tool
        return None
