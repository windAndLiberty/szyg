from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from szyg.api.auth_routes import router as auth_router
from szyg.api.tools_routes import router as tools_router
from szyg.api.oem_routes import router as oem_router
from szyg.version import VERSION
import os, logging

_CORS_ORIGINS_ENV = os.environ.get("SZYG_CORS_ORIGINS", "")

logger = logging.getLogger(__name__)


def _try_include(app: FastAPI, module_path: str, prefix: str = "") -> bool:
    """Safely include a router — returns False if deps missing"""
    try:
        import importlib
        mod = importlib.import_module(module_path)
        app.include_router(mod.router, prefix=prefix)
        return True
    except ImportError as e:
        logger.warning(f"Skipped {module_path}: {e}")
        return False


def create_app() -> FastAPI:
    app = FastAPI(
        title="szyg API",
        description="智能矩阵运营系统 - 自托管AI工具平台",
        version=VERSION,
        docs_url="/docs",
    )

    cors_origins = (
        [o.strip() for o in _CORS_ORIGINS_ENV.split(",") if o.strip()]
        if _CORS_ORIGINS_ENV
        else ["http://localhost:5173", "http://localhost:8000", "http://127.0.0.1:5173", "http://127.0.0.1:8000"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Always-available routes
    app.include_router(auth_router)
    app.include_router(tools_router)
    app.include_router(oem_router)

    # Agent marketplace, AI tools hub, announcements
    from szyg.api.agent_routes import router as agent_router
    from szyg.api.hub_routes import router as hub_router
    from szyg.api.announce_routes import router as announce_router

    # Content publisher & smart scheduler
    from szyg.api.publisher_routes import router as publisher_router
    from szyg.api.scheduler_routes import router as scheduler_router

    app.include_router(agent_router)
    app.include_router(hub_router)
    app.include_router(announce_router)
    # AI Brain (nanobot)
    from szyg.api.brain_routes import router as brain_router

    # Client-side local AI & runtime
    from szyg.api.client_routes import router as client_router

    app.include_router(publisher_router)
    app.include_router(scheduler_router)
    app.include_router(brain_router)
    app.include_router(client_router)

    # Optional routes (may need openai, edge_tts, etc.)
    _try_include(app, "szyg.api.routes", prefix="/v1")
    _try_include(app, "szyg.api.frontend_routes")
    _try_include(app, "szyg.api.image_endpoint")

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": VERSION, "service": "szyg"}

    @app.get("/api/config")
    async def config():
        try:
            from szyg.config.loader import load_config
            cfg = load_config()
            return {"debug": cfg.debug, "log_level": cfg.log_level}
        except Exception:
            return {}

    @app.get("/")
    async def root():
        return {"name": "szyg", "version": VERSION, "docs": "/docs"}

    return app
