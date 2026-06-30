"""
前后端联调验收测试

目标：验证前端 dev server 与后端真实联通，关键页面能加载、API 能代理。

注意：本测试需要同时运行：
  - 后端: uv run python -m szyg.main (默认 8000)
  - 前端: npm run dev (默认 5173)
如果任一服务未启动，对应测试会失败，请诚实记录。
"""

import pytest
import httpx

BASE_BACKEND = "http://localhost:8000"
BASE_FRONTEND = "http://localhost:5173"


@pytest.fixture
async def backend_client():
    async with httpx.AsyncClient(base_url=BASE_BACKEND, timeout=10.0, trust_env=False) as c:
        yield c


@pytest.fixture
async def frontend_client():
    async with httpx.AsyncClient(base_url=BASE_FRONTEND, timeout=10.0, trust_env=False) as c:
        yield c


class TestBackendHealth:
    """后端基础可用性。"""

    async def test_health(self, backend_client):
        resp = await backend_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"
        assert "version" in data

    async def test_data_routes_available(self, backend_client):
        """data_routes 已注册并返回数据。"""
        resp = await backend_client.get("/api/data/team/list")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data.get("data"), list)


class TestFrontendProxy:
    """前端代理到后端的关键接口。"""

    async def test_frontend_index_loads(self, frontend_client):
        """前端首页可加载。"""
        resp = await frontend_client.get("/")
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "html" in content_type or "text" in content_type

    async def test_frontend_proxy_to_backend_data(self, frontend_client):
        """/api/data/* 通过前端代理到后端。"""
        resp = await frontend_client.get("/api/data/team/list")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data.get("data"), list)

    async def test_frontend_proxy_to_backend_health(self, frontend_client):
        """健康检查通过前端代理可达。"""
        resp = await frontend_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"


class TestFrontendPages:
    """关键前端路由页面可加载（SPA 应返回 index.html）。"""

    ROUTES = ["/", "/content-studio", "/customer-assets", "/conversion-studio", "/ops-studio", "/settings/team"]

    @pytest.mark.parametrize("route", ROUTES)
    async def test_page_loads(self, frontend_client, route):
        resp = await frontend_client.get(route)
        assert resp.status_code == 200
        assert "<html" in resp.text.lower() or "<!doctype" in resp.text.lower()
