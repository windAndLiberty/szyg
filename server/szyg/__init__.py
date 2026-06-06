"""
szyg — 智能矩阵运营系统
"""
from szyg.version import VERSION
from szyg.config.settings import YuLingSettings, get_settings

__version__ = VERSION

# Lazy imports — core modules loaded on demand
def get_planner():
    from szyg.agent_core.planner import Planner
    return Planner

def get_memory():
    from szyg.agent_core.memory import Memory
    return Memory

def get_skill_registry():
    from szyg.agent_core.skill_registry import SkillRegistry
    return SkillRegistry

def get_model_router():
    from szyg.agent_core.model_router import ModelRouter
    return ModelRouter

__all__ = ["VERSION", "YuLingSettings", "get_settings"]
