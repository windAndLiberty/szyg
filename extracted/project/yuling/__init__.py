"""
「域灵」数字员工系统

一个支持深度研究、内容创作、多模态处理和多平台部署的AI数字员工系统。
"""

from yuling.version import VERSION
from yuling.config.settings import YuLingSettings, get_settings
from yuling.agent_core.planner import Planner
from yuling.agent_core.memory import Memory
from yuling.agent_core.skill_registry import SkillRegistry
from yuling.agent_core.model_router import ModelRouter

__version__ = VERSION
__all__ = [
    "VERSION",
    "YuLingSettings",
    "get_settings",
    "Planner",
    "Memory",
    "SkillRegistry",
    "ModelRouter",
]
