#!/usr/bin/env python3
"""
域灵数字员工系统 - 主入口

启动命令:
    python -m yuling.main
    或
    uvicorn yuling.main:app --host 0.0.0.0 --port 8000
"""

import asyncio
import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from yuling.api.app import create_app
from yuling.version import VERSION
from yuling.config.settings import get_settings

# 全局应用实例
_app: FastAPI | None = None


def get_app() -> FastAPI:
    """获取（或创建）FastAPI应用实例"""
    global _app
    if _app is None:
        _app = create_app()
    return _app


# ASGI入口
app = get_app()


def handle_signal(sig, frame):
    """信号处理 - 优雅关闭"""
    print(f"\n收到信号 {sig}，正在关闭...")
    sys.exit(0)


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


async def main():
    """主入口"""
    import uvicorn

    settings = get_settings()

    print(f"🤖 域灵数字员工系统 v{VERSION}")
    print(f"📡 API服务: http://{settings.api.host}:{settings.api.port}")
    print(f"📚 数据目录: {settings.data_dir}")

    config = uvicorn.Config(
        "yuling.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
        workers=settings.api.workers,
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
