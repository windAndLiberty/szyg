#!/usr/bin/env python3
"""szyg 智能矩阵运营系统 — 主入口"""
import asyncio, signal, sys
from fastapi import FastAPI
from szyg.api.app import create_app
from szyg.version import VERSION

_app: FastAPI | None = None

def get_app() -> FastAPI:
    global _app
    if _app is None:
        _app = create_app()
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
