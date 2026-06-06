"""
Platform Registry — 平台适配器注册表

管理所有平台适配器实例，按需延迟加载。
对标数创引擎 core/client.pyd 中的 Api 类集中调度模式。
"""
import logging
from typing import Type, Optional

from szyg.publisher import Platform
from szyg.platforms.base import BasePlatformAdapter, AdapterState

logger = logging.getLogger(__name__)


class PlatformRegistry:
    """
    平台适配器注册表 (Singleton)

    Usage:
        registry = PlatformRegistry()

        # 注册适配器
        registry.register(Platform.DOUYIN, DouyinAdapter)

        # 获取适配器实例 (延迟初始化)
        douyin = await registry.get(Platform.DOUYIN)

        # 发布内容
        result = await douyin.publish(request)
    """

    def __init__(self):
        self._adapters: dict[Platform, BasePlatformAdapter] = {}
        self._factories: dict[Platform, Type[BasePlatformAdapter]] = {}
        self._initialized: set[Platform] = set()

    def register(self, platform: Platform, factory: Type[BasePlatformAdapter]) -> None:
        """
        注册平台适配器工厂。

        Args:
            platform: 平台标识
            factory: 适配器类 (未实例化)
        """
        self._factories[platform] = factory
        logger.debug(f"注册平台适配器: {platform.value} → {factory.__name__}")

    def is_registered(self, platform: Platform) -> bool:
        """检查平台是否已注册适配器"""
        return platform in self._factories

    async def get(self, platform: Platform) -> BasePlatformAdapter:
        """
        获取平台适配器实例 (延迟初始化)。

        Raises:
            ValueError: 平台未注册
            RuntimeError: 初始化失败
        """
        # 处理 ALL 平台
        if platform == Platform.ALL:
            raise ValueError(
                "Platform.ALL 不能直接使用。请遍历具体平台: "
                "[p for p in Platform if p != Platform.ALL]"
            )

        # 已缓存
        if platform in self._adapters:
            adapter = self._adapters[platform]
            if not adapter.is_ready and platform not in self._initialized:
                await adapter.initialize()
                self._initialized.add(platform)
            return adapter

        # 未注册
        if platform not in self._factories:
            raise ValueError(
                f"平台 '{platform.value}' 未注册适配器。"
                f"可用平台: {list(self._factories.keys())}"
            )

        # 创建新实例
        factory = self._factories[platform]
        adapter = factory()
        self._adapters[platform] = adapter

        # 初始化
        ok = await adapter.initialize()
        if not ok:
            raise RuntimeError(f"平台 '{platform.value}' 适配器初始化失败")
        self._initialized.add(platform)

        logger.info(f"平台适配器就绪: {adapter}")
        return adapter

    async def get_all(self) -> dict[Platform, BasePlatformAdapter]:
        """获取所有已注册平台的适配器"""
        result = {}
        for platform in self._factories:
            try:
                result[platform] = await self.get(platform)
            except Exception as e:
                logger.warning(f"跳过平台 {platform.value}: {e}")
        return result

    async def close_all(self) -> None:
        """关闭所有适配器"""
        for platform, adapter in list(self._adapters.items()):
            try:
                await adapter.close()
                logger.info(f"已关闭: {adapter}")
            except Exception as e:
                logger.error(f"关闭 {platform.value} 失败: {e}")
        self._adapters.clear()
        self._initialized.clear()

    async def health_check(self) -> dict[str, bool]:
        """检查所有平台健康状态"""
        result = {}
        for platform in self._factories:
            try:
                adapter = await self.get(platform)
                result[platform.value] = await adapter.health_check()
            except Exception:
                result[platform.value] = False
        return result

    def list_platforms(self) -> list[dict]:
        """列出所有已注册平台及其状态"""
        platforms = []
        for platform, factory in self._factories.items():
            adapter = self._adapters.get(platform)
            platforms.append({
                "id": platform.value,
                "name": getattr(factory, 'platform_name', platform.value),
                "adapter": factory.__name__,
                "state": adapter.state.value if adapter else AdapterState.UNINITIALIZED.value,
                "initialized": platform in self._initialized,
            })
        return platforms


# ── Global Singleton ─────────────────────────────────────────

_registry: PlatformRegistry | None = None


def get_registry() -> PlatformRegistry:
    """获取全局 PlatformRegistry 单例"""
    global _registry
    if _registry is None:
        _registry = PlatformRegistry()
        _register_builtin_adapters(_registry)
    return _registry


async def get_adapter(platform: Platform) -> BasePlatformAdapter:
    """快捷方法：获取指定平台的适配器实例"""
    return await get_registry().get(platform)


def _register_builtin_adapters(registry: PlatformRegistry) -> None:
    """注册内置平台适配器 (延迟导入避免循环依赖)"""
    try:
        from szyg.platforms.douyin import DouyinAdapter
        registry.register(Platform.DOUYIN, DouyinAdapter)
    except ImportError as e:
        logger.warning(f"DouyinAdapter 不可用: {e}")

    try:
        from szyg.platforms.xiaohongshu import XiaohongshuAdapter
        registry.register(Platform.XHS, XiaohongshuAdapter)
    except ImportError as e:
        logger.warning(f"XiaohongshuAdapter 不可用: {e}")

    try:
        from szyg.platforms.wechat_desktop import WeChatDesktopAdapter
        registry.register(Platform.WECHAT_MP, WeChatDesktopAdapter)
    except ImportError as e:
        logger.warning(f"WeChatDesktopAdapter 不可用: {e}")

    try:
        from szyg.platforms.bilibili import BilibiliAdapter
        registry.register(Platform.BILIBILI, BilibiliAdapter)
    except ImportError as e:
        logger.warning(f"BilibiliAdapter 不可用: {e}")

    try:
        from szyg.platforms.kuaishou import KuaishouAdapter
        registry.register(Platform.KUAISHOU, KuaishouAdapter)
    except ImportError as e:
        logger.warning(f"KuaishouAdapter 不可用: {e}")
