from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from szyg.api.auth_routes import router as auth_router
from szyg.api.tools_routes import router as tools_router
from szyg.api.oem_routes import router as oem_router
from szyg.version import VERSION
import os, logging

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

    # Multi-tenant — OEM isolation
    from szyg.tenant import TenantMiddleware
    app.add_middleware(TenantMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
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
    from szyg.api.platform_routes import router as platform_router

    app.include_router(agent_router)
    app.include_router(hub_router)
    app.include_router(announce_router)
    # AI Brain (nanobot)
    from szyg.api.brain_routes import router as brain_router

    # AI Chat — raw Ollama
    from szyg.api.chat import router as chat_api_router
    app.include_router(chat_api_router)

    # Hermes Chat — 超级AI员工 (Ollama + szyg MCP tools)
    from szyg.api.hermes_chat import router as hermes_chat_router
    app.include_router(hermes_chat_router)

    # Client-side local AI & runtime
    from szyg.api.client_routes import router as client_router

    app.include_router(publisher_router)
    app.include_router(scheduler_router)
    app.include_router(platform_router)
    app.include_router(brain_router)
    app.include_router(client_router)

    # Optional routes (may need openai, edge_tts, etc.)
    _try_include(app, "szyg.api.routes", prefix="/v1")
    _try_include(app, "szyg.api.frontend_routes")
    _try_include(app, "szyg.api.image_endpoint")
    _try_include(app, "szyg.api.models_endpoint", prefix="/api")

    # Pipeline — Multi-model AIGC orchestration
    try:
        from szyg.api.pipeline_endpoint import router as pipeline_router
        app.include_router(pipeline_router)
    except Exception as e:
        logger.warning(f"Skipped pipeline_endpoint: {e}")

    # Video — use direct import to ensure it loads
    try:
        from szyg.api.video_endpoint import router as video_router
        app.include_router(video_router)
    except Exception as e:
        logger.warning(f"Skipped video_endpoint: {e}")

    # Acquisition — 流量引擎 + 客户转化
    try:
        from szyg.api.acquisition_routes import router as acquisition_router
        app.include_router(acquisition_router)
        from szyg.api.acquisition_routes import _video_router
        app.include_router(_video_router)
        logger.info("Acquisition routes loaded")
    except Exception as e:
        logger.warning(f"Skipped acquisition_routes: {e}")

    # Skills Market — Hermes Skills Hub bridge
    try:
        from szyg.api.skills_routes import router as skills_router
        app.include_router(skills_router)
        logger.info("Skills market routes loaded")
    except Exception as e:
        logger.warning(f"Skipped skills_routes: {e}")

    # Infra — Sandbox lifecycle, browser node telemetry
    try:
        from szyg.api.infra_routes import router as infra_router
        app.include_router(infra_router)
        logger.info("Infra routes loaded")
    except Exception as e:
        logger.warning(f"Skipped infra_routes: {e}")

    # Memory — Long-term memory CRUD
    try:
        from szyg.api.memory_routes import router as memory_router
        app.include_router(memory_router)
        logger.info("Memory routes loaded")
    except Exception as e:
        logger.warning(f"Skipped memory_routes: {e}")

    # Risk Control — Anti-detect configuration
    try:
        from szyg.api.risk_control_routes import router as risk_control_router
        app.include_router(risk_control_router)
        logger.info("Risk control routes loaded")
    except Exception as e:
        logger.warning(f"Skipped risk_control_routes: {e}")

    # social-auto-upload — 多平台视频/图文发布
    try:
        from szyg.api.sau_routes import router as sau_router
        app.include_router(sau_router)
        logger.info("SAU routes loaded")
    except Exception as e:
        logger.warning(f"Skipped sau_routes: {e}")

    # AI Staff — 员工状态、任务管理、配置持久化
    try:
        from szyg.api.staff_routes import router as staff_router
        app.include_router(staff_router)
        logger.info("Staff routes loaded")
    except Exception as e:
        logger.warning(f"Skipped staff_routes: {e}")

    # Conversation persistence — 超级员工对话历史
    try:
        from szyg.api.conversation_routes import router as conversation_router
        app.include_router(conversation_router)
        logger.info("Conversation routes loaded")
    except Exception as e:
        logger.warning(f"Skipped conversation_routes: {e}")

    # 统一前端数据 API — 所有页面真实数据持久化
    try:
        from szyg.api.data_routes import router as data_router
        app.include_router(data_router)
        logger.info("Data routes loaded")
    except Exception as e:
        logger.warning(f"Skipped data_routes: {e}")

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

    # Serve generated assets (images, videos, audio from AIGC pipelines)
    data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
    volc_output = os.path.join(data_dir, "volcengine_output")
    if not os.path.isdir(volc_output):
        os.makedirs(volc_output, exist_ok=True)
    app.mount("/api/files/volcengine_output", StaticFiles(directory=volc_output), name="volcengine_output")

    # Serve built SPA (static files + client-side routing fallback)
    spa_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "web", "dist")
    if os.path.isdir(spa_dir):
        app.mount("/assets", StaticFiles(directory=os.path.join(spa_dir, "assets")), name="assets")

        @app.get("/favicon.svg")
        async def serve_favicon():
            """Serve favicon as a single file."""
            favicon_path = os.path.join(spa_dir, "favicon.svg")
            if os.path.isfile(favicon_path):
                return FileResponse(favicon_path, media_type="image/svg+xml")
            return FileResponse(os.path.join(spa_dir, "index.html"))

        @app.get("/login")
        @app.get("/dashboard")
        @app.get("/tools")
        @app.get("/agents")
        @app.get("/hub")
        @app.get("/scheduler")
        @app.get("/publisher")
        @app.get("/chat")
        @app.get("/admin")
        @app.get("/oem")
        @app.get("/image")
        @app.get("/video")
        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str = ""):
            # API paths already matched by routers above. Anything reaching here:
            index_path = os.path.join(spa_dir, "index.html")
            if os.path.isfile(index_path):
                return FileResponse(index_path)
            return {"name": "szyg", "version": VERSION, "docs": "/docs"}
    else:
        @app.get("/")
        async def root():
            return {"name": "szyg", "version": VERSION, "docs": "/docs"}

    return app
