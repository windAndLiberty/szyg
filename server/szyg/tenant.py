"""
Multi-Tenant Data Isolation — 多租户数据隔离

Usage:
    from szyg.tenant import get_current_tenant, set_current_tenant, TenantContext

    with TenantContext("oem_abc"):
        data_dir = get_tenant_data_dir()  # -> data/oem_abc/

    # In FastAPI middleware:
    tenant_id = request.headers.get("X-OEM-ID", "default")
    set_current_tenant(tenant_id)

All data operations (publisher, scheduler, tools) use get_tenant_data_dir()
to scope their data to the current tenant.
"""
import contextvars
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Context variable — thread/async safe ──────────────

_current_tenant: contextvars.ContextVar[str] = contextvars.ContextVar(
    "szyg_tenant", default="default"
)

DEFAULT_TENANT = "default"


def get_current_tenant() -> str:
    """Get current tenant ID from request context"""
    return _current_tenant.get()


def set_current_tenant(tenant_id: str) -> None:
    """Set current tenant ID for this request/context"""
    _current_tenant.set(tenant_id or DEFAULT_TENANT)


class TenantContext:
    """Context manager for tenant-scoped operations"""
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id or DEFAULT_TENANT
        self._token = None

    def __enter__(self):
        self._token = _current_tenant.set(self.tenant_id)
        return self

    def __exit__(self, *args):
        if self._token:
            _current_tenant.reset(self._token)


# ── Tenant-aware data path ─────────────────────────────

def get_tenant_data_dir() -> Path:
    """Get the data directory for the current tenant"""
    from szyg.data_path import DATA_DIR
    tenant = get_current_tenant()
    if tenant == DEFAULT_TENANT:
        return DATA_DIR
    tenant_dir = DATA_DIR / "tenants" / tenant
    tenant_dir.mkdir(parents=True, exist_ok=True)
    return tenant_dir


def get_tenant_data_file(filename: str) -> Path:
    """Get a scoped data file path for the current tenant"""
    return get_tenant_data_dir() / filename


# ── OEM ID resolver ────────────────────────────────────

def resolve_oem_from_request(request) -> str:
    """Extract OEM/tenant ID from HTTP request.

    Priority:
    1. X-OEM-ID header
    2. ?oem_id query parameter
    3. JWT token claim (if present)
    4. Default ("default")
    """
    # Header
    oem_id = request.headers.get("X-OEM-ID", "").strip()
    if oem_id:
        return oem_id

    # Query param
    oem_id = (request.query_params or {}).get("oem_id", "").strip()
    if oem_id:
        return oem_id

    # JWT token
    try:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            import jose.jwt
            token = auth[7:]
            # Try to decode without verification just to read claim
            claims = jose.jwt.get_unverified_claims(token)
            oem_id = claims.get("oem_id", "") or claims.get("tenant", "")
            if oem_id:
                return oem_id
    except Exception as e:
        logger.debug("Failed to extract tenant from JWT: %s", e)

    return DEFAULT_TENANT


# ── FastAPI Middleware ──────────────────────────────────

class TenantMiddleware:
    """ASGI middleware for automatic tenant resolution"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Extract OEM from headers
            headers = dict(scope.get("headers", []))
            oem_header = headers.get(b"x-oem-id", b"").decode("utf-8", errors="ignore")
            tenant = oem_header.strip() if oem_header else DEFAULT_TENANT
            set_current_tenant(tenant)
        await self.app(scope, receive, send)


def setup_tenant_middleware(app):
    """Add tenant middleware to FastAPI app"""
    app.add_middleware(TenantMiddleware)
    logger.info("Multi-tenant middleware installed")
