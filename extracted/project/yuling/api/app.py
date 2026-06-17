from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from yuling.api.routes import router
from yuling.api.frontend_routes import router as frontend_router
from yuling.api.image_endpoint import router as image_router
from yuling.version import VERSION


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    app = FastAPI(
        title="域灵数字员工系统 API",
        description="OpenAI兼容API - 支持多模型调度、流式响应",
        version=VERSION,
        docs_url="/docs" if True else None,
        redoc_url="/redoc" if True else None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(router, prefix="/v1")
    app.include_router(frontend_router)  # /api/knowledge, /api/sop, /api/config
    app.include_router(image_router)     # /api/image/generate, /api/image/styles

    @app.get("/health", tags=["health"])
    async def health_check():
        return {"status": "ok", "version": VERSION}

    @app.get("/", tags=["root"])
    async def root():
        return {"name": "域灵数字员工系统", "version": VERSION, "docs": "/docs"}

    return app
