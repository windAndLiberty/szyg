"""
Unit tests for szyg.tenant — multi-tenant data isolation.
"""

import contextvars
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from szyg.tenant import (
    DEFAULT_TENANT,
    TenantContext,
    TenantMiddleware,
    get_current_tenant,
    get_tenant_data_dir,
    get_tenant_data_file,
    resolve_oem_from_request,
    set_current_tenant,
    setup_tenant_middleware,
)


class TestGetSetCurrentTenant:
    def test_default_tenant(self):
        # Reset to default first
        set_current_tenant("")
        assert get_current_tenant() == DEFAULT_TENANT

    def test_set_and_get(self):
        set_current_tenant("oem_123")
        assert get_current_tenant() == "oem_123"
        # Cleanup
        set_current_tenant(DEFAULT_TENANT)

    def test_empty_string_resets_to_default(self):
        set_current_tenant("tenant_x")
        set_current_tenant("")
        assert get_current_tenant() == DEFAULT_TENANT

    def test_none_resets_to_default(self):
        set_current_tenant("tenant_x")
        set_current_tenant(None)
        assert get_current_tenant() == DEFAULT_TENANT


class TestTenantContext:
    def test_context_manager_sets_and_resets(self):
        set_current_tenant(DEFAULT_TENANT)
        with TenantContext("ctx_tenant"):
            assert get_current_tenant() == "ctx_tenant"
        assert get_current_tenant() == DEFAULT_TENANT

    def test_nested_contexts(self):
        set_current_tenant(DEFAULT_TENANT)
        with TenantContext("outer"):
            assert get_current_tenant() == "outer"
            with TenantContext("inner"):
                assert get_current_tenant() == "inner"
            assert get_current_tenant() == "outer"
        assert get_current_tenant() == DEFAULT_TENANT

    def test_empty_tenant_uses_default(self):
        with TenantContext(""):
            assert get_current_tenant() == DEFAULT_TENANT

    def test_none_tenant_uses_default(self):
        with TenantContext(None):
            assert get_current_tenant() == DEFAULT_TENANT


class TestGetTenantDataDir:
    def test_default_tenant_returns_data_dir(self, tmp_path: Path):
        set_current_tenant(DEFAULT_TENANT)
        with patch("szyg.data_path.DATA_DIR", tmp_path):
            result = get_tenant_data_dir()
            # For default tenant, returns DATA_DIR directly
            assert result == tmp_path

    def test_custom_tenant_returns_scoped_dir(self, tmp_path: Path):
        with patch("szyg.data_path.DATA_DIR", tmp_path):
            set_current_tenant("oem_abc")
            result = get_tenant_data_dir()
            assert "tenants" in str(result)
            assert "oem_abc" in str(result)
            assert result.exists()
            # Cleanup
            set_current_tenant(DEFAULT_TENANT)


class TestGetTenantDataFile:
    def test_returns_file_in_tenant_dir(self, tmp_path: Path):
        with patch("szyg.data_path.DATA_DIR", tmp_path):
            set_current_tenant(DEFAULT_TENANT)
            result = get_tenant_data_file("tasks.json")
            assert result.name == "tasks.json"
            set_current_tenant(DEFAULT_TENANT)


class TestResolveOemFromRequest:
    def test_untrusted_header_is_ignored(self):
        request = MagicMock()
        request.headers = {"X-OEM-ID": "header_oem"}
        request.query_params = {"oem_id": "query_oem"}
        assert resolve_oem_from_request(request) == DEFAULT_TENANT

    def test_untrusted_query_param_is_ignored(self):
        request = MagicMock()
        request.headers = {"X-OEM-ID": "", "Authorization": ""}
        request.query_params = {"oem_id": "query_oem"}
        assert resolve_oem_from_request(request) == DEFAULT_TENANT

    def test_returns_default_when_nothing(self):
        request = MagicMock()
        request.headers = {"X-OEM-ID": "", "Authorization": ""}
        request.query_params = {}
        assert resolve_oem_from_request(request) == DEFAULT_TENANT

    def test_unverified_oem_jwt_claim_is_ignored(self):
        from jose import jwt as jose_jwt
        token = jose_jwt.encode({"oem_id": "jwt_oem"}, "secret", algorithm="HS256")
        request = MagicMock()
        request.headers = {"X-OEM-ID": "", "Authorization": f"Bearer {token}"}
        request.query_params = {}
        assert resolve_oem_from_request(request) == DEFAULT_TENANT

    def test_unverified_tenant_jwt_claim_is_ignored(self):
        from jose import jwt as jose_jwt
        token = jose_jwt.encode({"tenant": "jwt_tenant"}, "secret", algorithm="HS256")
        request = MagicMock()
        request.headers = {"X-OEM-ID": "", "Authorization": f"Bearer {token}"}
        request.query_params = {}
        assert resolve_oem_from_request(request) == DEFAULT_TENANT

    def test_invalid_jwt_falls_to_default(self):
        request = MagicMock()
        request.headers = {"X-OEM-ID": "", "Authorization": "Bearer invalid.token.here"}
        request.query_params = {}
        assert resolve_oem_from_request(request) == DEFAULT_TENANT

    def test_whitespace_header_is_ignored(self):
        request = MagicMock()
        request.headers = {"X-OEM-ID": "  spaced_oem  "}
        request.query_params = {}
        assert resolve_oem_from_request(request) == DEFAULT_TENANT


class TestTenantMiddleware:
    @pytest.mark.asyncio
    async def test_ignores_tenant_header(self):
        app_called = []

        async def mock_app(scope, receive, send):
            app_called.append(get_current_tenant())

        middleware = TenantMiddleware(mock_app)
        scope = {
            "type": "http",
            "headers": [(b"x-oem-id", b"middleware_tenant")],
        }
        await middleware(scope, None, None)
        assert app_called[0] == DEFAULT_TENANT
        # Cleanup
        set_current_tenant(DEFAULT_TENANT)

    @pytest.mark.asyncio
    async def test_defaults_when_no_header(self):
        app_called = []

        async def mock_app(scope, receive, send):
            app_called.append(get_current_tenant())

        middleware = TenantMiddleware(mock_app)
        scope = {
            "type": "http",
            "headers": [],
        }
        await middleware(scope, None, None)
        assert app_called[0] == DEFAULT_TENANT

    @pytest.mark.asyncio
    async def test_non_http_scope_passes_through(self):
        called = []

        async def mock_app(scope, receive, send):
            called.append(True)

        middleware = TenantMiddleware(mock_app)
        scope = {"type": "websocket", "headers": [(b"x-oem-id", b"ws_oem")]}
        await middleware(scope, None, None)
        assert called == [True]


class TestSetupTenantMiddleware:
    def test_adds_middleware(self):
        app = MagicMock()
        setup_tenant_middleware(app)
        app.add_middleware.assert_called_once_with(TenantMiddleware)
