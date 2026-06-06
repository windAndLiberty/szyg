"""
Platform Adapter System — 平台适配器系统

对标数创引擎的 douyin.pyd / xhs.pyd / wxauto 框架，
使用 Playwright 浏览器自动化 + Windows UIA 桌面自动化实现
微信、抖音、小红书自动营销发布功能。

Usage:
    from szyg.platforms import get_adapter, Platform
    adapter = get_adapter(Platform.DOUYIN)
    result = await adapter.publish(request)
"""

from szyg.platforms.base import (
    BasePlatformAdapter,
    PublishRequest,
    PublishResult,
    LoginStatus,
    AdapterState,
)
from szyg.platforms.registry import get_adapter, get_registry, PlatformRegistry
from szyg.platforms.anti_detect import (
    inject_stealth,
    HumanBehavior,
    get_stealth_context_config,
    get_launch_config,
)
from szyg.platforms.session_manager import get_session_manager, SessionManager
from szyg.publisher import Platform

__all__ = [
    "BasePlatformAdapter",
    "PublishRequest",
    "PublishResult",
    "LoginStatus",
    "AdapterState",
    "get_adapter",
    "get_registry",
    "PlatformRegistry",
    "inject_stealth",
    "HumanBehavior",
    "get_stealth_context_config",
    "get_launch_config",
    "get_session_manager",
    "SessionManager",
    "Platform",
]
