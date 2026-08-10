from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from szyg.api.auth_routes import router as auth_router
from szyg.api.tools_routes import router as tools_router
from szyg.api.oem_routes import router as oem_router
from szyg.version import VERSION
import hmac
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
    production = os.environ.get("SZYG_PRODUCTION", "").lower() in {"1", "true", "yes"}
    app = FastAPI(
        title="szyg API",
        description="智能矩阵运营系统 - 自托管AI工具平台",
        version=VERSION,
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
    )

    desktop_token = os.environ.get("SZYG_DESKTOP_TOKEN", "").strip()

    @app.middleware("http")
    async def protect_desktop_api(request: Request, call_next):
        """Keep the loopback API private to the Electron session in production."""
        protected = request.url.path.startswith(("/api/", "/v1/"))
        exempt = request.url.path == "/api/health" or request.method == "OPTIONS"
        if request.url.path.startswith("/api/internal/hermes/"):
            from szyg.hermes_process_manager import hermes_process_manager
            internal_token = request.headers.get("X-SZYG-Hermes-Token", "")
            bearer = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            supplied_internal = internal_token or bearer
            if supplied_internal and hermes_process_manager.token and hmac.compare_digest(
                supplied_internal, hermes_process_manager.token
            ):
                exempt = True
        if desktop_token and protected and not exempt:
            supplied = request.cookies.get("szyg_desktop_token", "")
            if not supplied:
                supplied = request.headers.get("X-SZYG-Desktop-Token", "")
            if not hmac.compare_digest(supplied, desktop_token):
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=401, content={"detail": "Desktop session required"})
        return await call_next(request)

    # Multi-tenant — OEM isolation
    from szyg.tenant import TenantMiddleware
    app.add_middleware(TenantMiddleware)

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
    from szyg.cloud_auth import cloud_auth
    local_auth_enabled = os.environ.get("SZYG_LOCAL_AUTH_ENABLED", "").lower() in {"1", "true", "yes"}
    if not cloud_auth.config["enabled"] or local_auth_enabled:
        app.include_router(auth_router)
    app.include_router(tools_router)
    app.include_router(oem_router)
    from szyg.api.cloud_routes import router as cloud_router
    app.include_router(cloud_router)

    # Agent marketplace, AI tools hub, announcements
    from szyg.api.agent_routes import router as agent_router
    from szyg.api.hub_routes import router as hub_router
    from szyg.api.announce_routes import router as announce_router

    # Content publisher. Business automation is exposed by workflow_routes.
    from szyg.api.publisher_routes import router as publisher_router
    from szyg.api.platform_routes import router as platform_router

    app.include_router(agent_router)
    app.include_router(hub_router)
    app.include_router(announce_router)

    # Agency 专家市场 — 155 个领域专家（集成 Agency 开源项目）
    from szyg.api.agency_routes import router as agency_router
    app.include_router(agency_router)
    # AI Brain (nanobot)
    from szyg.api.brain_routes import router as brain_router

    # AI Chat — raw Ollama
    from szyg.api.chat import router as chat_api_router
    app.include_router(chat_api_router)

    # Hermes Chat — isolated upstream agent loop + guarded SZYG capabilities
    from szyg.api.hermes_native_routes import router as hermes_chat_router
    app.include_router(hermes_chat_router)

    # Client-side local AI & runtime
    from szyg.api.client_routes import router as client_router

    app.include_router(publisher_router)
    app.include_router(platform_router)
    app.include_router(brain_router)
    app.include_router(client_router)

    # Optional routes (may need openai, edge_tts, etc.)
    _try_include(app, "szyg.api.routes", prefix="/v1")
    _try_include(app, "szyg.api.frontend_routes")
    _try_include(app, "szyg.api.workflow_routes")
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

    try:
        from szyg.api.digital_human_routes import router as digital_human_router
        app.include_router(digital_human_router)
        logger.info("Digital human routes loaded")
    except Exception as e:
        logger.warning(f"Skipped digital_human_routes: {e}")

    try:
        from szyg.api.content_copy_routes import router as content_copy_router
        app.include_router(content_copy_router)
        logger.info("Content copy routes loaded")
    except Exception as e:
        logger.warning(f"Skipped content_copy_routes: {e}")

    try:
        from szyg.api.content_graphic_routes import router as content_graphic_router
        app.include_router(content_graphic_router)
        logger.info("Content graphic routes loaded")
    except Exception as e:
        logger.warning(f"Skipped content_graphic_routes: {e}")

    try:
        from szyg.api.tts_routes import router as tts_router
        app.include_router(tts_router)
        logger.info("TTS routes loaded")
    except Exception as e:
        logger.warning(f"Skipped tts_routes: {e}")

    # Acquisition — 流量引擎 + 客户转化
    try:
        from szyg.api.acquisition_routes import router as acquisition_router
        app.include_router(acquisition_router)
        from szyg.api.acquisition_routes import _video_router
        app.include_router(_video_router)
        logger.info("Acquisition routes loaded")
    except Exception as e:
        logger.warning(f"Skipped acquisition_routes: {e}")

    try:
        from szyg.api.intelligence_routes import router as intelligence_router
        app.include_router(intelligence_router)
        logger.info("Intelligence routes loaded")
    except Exception as e:
        logger.warning(f"Skipped intelligence_routes: {e}")

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

    # Platform Accounts — account-level channel publishing
    try:
        from szyg.api.platform_account_routes import router as platform_account_router
        app.include_router(platform_account_router)
        logger.info("Platform account routes loaded")
    except Exception as e:
        logger.warning(f"Skipped platform_account_routes: {e}")

    # Execution Kernel — observable automation run state
    try:
        from szyg.api.execution_routes import router as execution_router
        app.include_router(execution_router)
        logger.info("Execution routes loaded")
    except Exception as e:
        logger.warning(f"Skipped execution_routes: {e}")

    # Computer Use — controlled Windows desktop automation
    try:
        from szyg.api.computer_use_routes import router as computer_use_router
        app.include_router(computer_use_router)
        logger.info("Computer-use routes loaded")
    except Exception as e:
        logger.warning(f"Skipped computer_use_routes: {e}")

    # WeChat desktop — read-only local client detection
    try:
        from szyg.api.wechat_desktop_routes import router as wechat_desktop_router
        app.include_router(wechat_desktop_router)
        logger.info("WeChat desktop routes loaded")
    except Exception as e:
        logger.warning(f"Skipped wechat_desktop_routes: {e}")

    # Private domain — AI sales workspace
    try:
        from szyg.api.private_domain_routes import router as private_domain_router
        app.include_router(private_domain_router)
        logger.info("Private domain routes loaded")
    except Exception as e:
        logger.warning(f"Skipped private_domain_routes: {e}")

    # Local small model — bundled llama.cpp runtime
    try:
        from szyg.api.local_llm_routes import router as local_llm_router
        app.include_router(local_llm_router)
        logger.info("Local LLM routes loaded")
    except Exception as e:
        logger.warning(f"Skipped local_llm_routes: {e}")

    # Media storage — Windows user folders for generated assets
    try:
        from szyg.api.media_routes import router as media_router
        app.include_router(media_router)
        logger.info("Media storage routes loaded")
    except Exception as e:
        logger.warning(f"Skipped media_routes: {e}")

    # AI Staff — 员工状态、任务管理、配置持久化
    try:
        from szyg.api.staff_routes import router as staff_router
        app.include_router(staff_router)
        logger.info("Staff routes loaded")
    except Exception as e:
        logger.warning(f"Skipped staff_routes: {e}")

    # Task Board — 任务看板
    try:
        from szyg.api.task_routes import router as task_router
        app.include_router(task_router)
        logger.info("Task board routes loaded")
    except Exception as e:
        logger.warning(f"Skipped task_routes: {e}")

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

    # 仪表盘 / 数字员工聚合 API — 为 szyg-frontend 提供真实聚合数据
    try:
        from szyg.api.dashboard_routes import router as dashboard_router
        app.include_router(dashboard_router)
        logger.info("Dashboard routes loaded")
    except Exception as e:
        logger.warning(f"Skipped dashboard_routes: {e}")

    # Global insights — knowledge, internal operations, and market evidence
    try:
        from szyg.api.insights_routes import router as insights_router
        app.include_router(insights_router)
        logger.info("Insights routes loaded")
    except Exception as e:
        logger.warning(f"Skipped insights_routes: {e}")


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
    data_dir = os.environ.get("SZYG_DATA_DIR") or os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "data"
    )
    volc_output = os.path.join(data_dir, "volcengine_output")
    if not os.path.isdir(volc_output):
        os.makedirs(volc_output, exist_ok=True)
    app.mount("/api/files/volcengine_output", StaticFiles(directory=volc_output), name="volcengine_output")
    legacy_volc_output = os.path.join(os.path.dirname(__file__), "..", "..", "data", "volcengine_output")
    if os.path.isdir(legacy_volc_output):
        app.mount(
            "/api/files/server_volcengine_output",
            StaticFiles(directory=legacy_volc_output),
            name="server_volcengine_output",
        )

    # Serve built SPA (static files + client-side routing fallback)
    spa_dir = os.environ.get("SZYG_FRONTEND_DIST") or os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "szyg-frontend", "dist"
    )
    if os.path.isdir(spa_dir):
        app.mount("/assets", StaticFiles(directory=os.path.join(spa_dir, "assets")), name="assets")
        avatars_dir = os.path.join(spa_dir, "avatars")
        if os.path.isdir(avatars_dir):
            app.mount("/avatars", StaticFiles(directory=avatars_dir), name="avatars")

        @app.get("/favicon.svg")
        async def serve_favicon():
            """Serve favicon as a single file."""
            favicon_path = os.path.join(spa_dir, "favicon.svg")
            if os.path.isfile(favicon_path):
                return FileResponse(favicon_path, media_type="image/svg+xml")
            return FileResponse(os.path.join(spa_dir, "index.html"))

        @app.get("/logo1.png")
        async def serve_logo1():
            """Serve logo1 branding image."""
            logo_path = os.path.join(spa_dir, "logo1.png")
            if os.path.isfile(logo_path):
                return FileResponse(logo_path, media_type="image/png")
            return FileResponse(os.path.join(spa_dir, "index.html"))

        # szyg-frontend (React Router) 路由
        @app.get("/")
        @app.get("/digital-human")
        @app.get("/settings")
        @app.get("/super-agent")
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
