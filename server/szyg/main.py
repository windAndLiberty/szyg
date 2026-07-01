#!/usr/bin/env python3
"""szyg 智能矩阵运营系统 — 主入口"""
import asyncio, signal, sys, logging
from fastapi import FastAPI
from szyg.api.app import create_app
from szyg.version import VERSION

logger = logging.getLogger("szyg")

_app: FastAPI | None = None


def _setup_lifecycle(app: FastAPI) -> None:
    """配置应用启动/关闭事件"""

    @app.on_event("startup")
    async def on_startup():
        """应用启动: 初始化平台适配器 + 启动调度器后台循环"""
        logger.info(f"szyg v{VERSION} starting...")

        # Initialize platform adapter registry
        try:
            from szyg.platforms.registry import get_registry
            registry = get_registry()
            platforms = registry.list_platforms()
            logger.info(f"Platform adapters: {len(platforms)} registered")
            for p in platforms:
                logger.info(f"  [{p['id']}] {p['adapter']} — {p['state']}")
        except Exception as e:
            logger.warning(f"Platform adapter init skipped: {e}")

        # Start scheduler background loop
        try:
            from szyg.scheduler_engine import get_scheduler
            scheduler = get_scheduler()
            await scheduler.start()
            logger.info("Scheduler background loop started")
        except Exception as e:
            logger.warning(f"Scheduler loop start failed: {e}")

    @app.on_event("shutdown")
    async def on_shutdown():
        """应用关闭: 停止调度器 + 释放平台适配器资源"""
        logger.info("szyg shutting down...")

        try:
            from szyg.scheduler_engine import get_scheduler
            await get_scheduler().stop()
        except Exception as e:
            logger.warning("Error stopping scheduler during shutdown: %s", e)

        try:
            from szyg.platforms.registry import get_registry
            await get_registry().close_all()
        except Exception as e:
            logger.warning("Error closing platform registry during shutdown: %s", e)

        logger.info("szyg closed")


def get_app() -> FastAPI:
    global _app
    if _app is None:
        _app = create_app()
        _setup_lifecycle(_app)
    return _app


app = get_app()

signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))


async def main():
    import uvicorn
    from szyg.config.settings import get_settings
    settings = get_settings()
    print(f"szyg v{VERSION}  http://{settings.api.host}:{settings.api.port}")
    config = uvicorn.Config("szyg.main:app", host=settings.api.host,
                            port=settings.api.port, reload=settings.api.reload)
    await uvicorn.Server(config).serve()

if __name__ == "__main__":
    asyncio.run(main())
