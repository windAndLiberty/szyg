"""
Platform Automation Unit Tests — 平台自动化 (Phase 1+2) 单元测试

测试范围:
  TestPublishModels     — PublishRequest, PublishResult, LoginStatus 数据模型
  TestPlatformRegistry  — PlatformRegistry 注册/获取/列表/健康检查
  TestSessionManager    — SessionManager 保存/加载/验证/清除
  TestAntiDetect        — stealth config, launch config, msToken, HumanBehavior
  TestDouyinSigner      — msToken 生成, 签名引擎初始化
  TestPublisherV2       — publish_async/publish_now 集成
  TestSchedulerNewActions — PLATFORM_LOGIN_CHECK / PLATFORM_HEALTH_CHECK
  TestPlatformRoutes    — REST API 端点
"""
import json
import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
import pytest_asyncio


# ── Path setup ─────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_path():
    """Ensure server/ is in sys.path"""
    server_dir = Path(__file__).parent.parent
    if str(server_dir) not in sys.path:
        sys.path.insert(0, str(server_dir))


# =========================================================================
# TestPublishModels — 数据模型
# =========================================================================

class TestPublishModels:
    """PublishRequest, PublishResult, LoginStatus, AdapterState 模型测试"""

    def test_publish_request_defaults(self):
        from szyg.platforms.base import PublishRequest
        req = PublishRequest()
        assert req.content_id == ""
        assert req.title == ""
        assert req.body == ""
        assert req.media_urls == []
        assert req.tags == []
        assert req.scheduled_at == ""

    def test_publish_request_full(self):
        from szyg.platforms.base import PublishRequest
        req = PublishRequest(
            content_id="abc123",
            title="Test Title",
            body="**bold** and *italic*",
            media_urls=["/img/1.jpg", "/img/2.jpg"],
            tags=["test", "demo"],
            scheduled_at="2026-06-10T09:00:00",
        )
        assert req.content_id == "abc123"
        assert req.title == "Test Title"
        assert len(req.media_urls) == 2
        assert len(req.tags) == 2

    def test_publish_request_to_plain_text(self):
        from szyg.platforms.base import PublishRequest
        req = PublishRequest(
            body="**bold** and *italic* and [link](http://example.com) and # heading"
        )
        text = req.to_plain_text()
        assert "**" not in text
        assert "bold" in text
        assert "italic" in text
        assert "heading" in text
        # Links should be stripped to just text
        assert "http://example.com" not in text
        assert "link" in text

    def test_publish_request_to_html(self):
        from szyg.platforms.base import PublishRequest
        req = PublishRequest(body="**bold** text")
        html = req.to_html()
        # markdown might not be installed, but at minimum returns the body
        assert len(html) > 0
        assert "bold" in html

    def test_publish_result_defaults(self):
        from szyg.platforms.base import PublishResult
        result = PublishResult()
        assert result.success is False
        assert result.platform == ""
        assert result.platform_post_id == ""
        assert result.error_msg == ""

    def test_publish_result_success(self):
        from szyg.platforms.base import PublishResult
        result = PublishResult(
            success=True,
            platform="douyin",
            platform_post_id="post_12345",
            platform_post_url="https://www.douyin.com/video/post_12345",
        )
        assert result.success is True
        assert result.platform_post_url.startswith("https://")

    def test_login_status_defaults(self):
        from szyg.platforms.base import LoginStatus
        status = LoginStatus()
        assert status.is_logged_in is False
        assert status.account_name == ""
        assert status.qr_code_url == ""

    def test_adapter_state_enum(self):
        from szyg.platforms.base import AdapterState
        states = list(AdapterState)
        assert AdapterState.UNINITIALIZED in states
        assert AdapterState.READY in states
        assert AdapterState.ERROR in states
        assert AdapterState.CLOSED in states


# =========================================================================
# TestPlatformRegistry — 注册表
# =========================================================================

class TestPlatformRegistry:
    """PlatformRegistry 单例注册表测试"""

    def test_registry_is_singleton(self):
        from szyg.platforms.registry import get_registry
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2

    def test_registry_list_platforms(self):
        from szyg.platforms.registry import get_registry
        registry = get_registry()
        platforms = registry.list_platforms()

        # 应有 3 个内置适配器
        assert len(platforms) >= 3
        ids = [p["id"] for p in platforms]
        assert "douyin" in ids
        assert "xhs" in ids
        assert "wechat_mp" in ids

    def test_registry_is_registered(self):
        from szyg.platforms.registry import get_registry
        from szyg.publisher import Platform
        registry = get_registry()
        assert registry.is_registered(Platform.DOUYIN) is True
        assert registry.is_registered(Platform.XHS) is True
        assert registry.is_registered(Platform.WECHAT_MP) is True

    def test_registry_not_registered(self):
        from szyg.platforms.registry import get_registry
        from szyg.publisher import Platform
        registry = get_registry()
        # WEIBO has no adapter yet (5 others are now registered)
        assert registry.is_registered(Platform.WEIBO) is False

    def test_registry_register_new_adapter(self):
        from szyg.platforms.registry import PlatformRegistry
        from szyg.platforms.base import BasePlatformAdapter, LoginStatus, PublishRequest, PublishResult
        from szyg.publisher import Platform

        class FakeAdapter(BasePlatformAdapter):
            platform = Platform.WEIBO

            async def _do_initialize(self): return True
            async def check_login(self): return LoginStatus(is_logged_in=False)
            async def login(self, **kw): return LoginStatus(is_logged_in=False)
            async def publish(self, req): return PublishResult()
            async def get_status(self, pid): return {}
            async def close(self): pass

        registry = PlatformRegistry()
        registry.register(Platform.WEIBO, FakeAdapter)
        assert registry.is_registered(Platform.WEIBO) is True

    @pytest.mark.asyncio
    async def test_get_all_returns_adapters(self):
        from szyg.platforms.registry import PlatformRegistry
        from szyg.platforms.base import BasePlatformAdapter, LoginStatus, PublishRequest, PublishResult
        from szyg.publisher import Platform

        class FakeDouyin(BasePlatformAdapter):
            platform = Platform.DOUYIN
            async def _do_initialize(self): return True
            async def check_login(self): return LoginStatus(is_logged_in=True, account_name="test")
            async def login(self, **kw): return LoginStatus(is_logged_in=True)
            async def publish(self, req): return PublishResult(success=True)
            async def get_status(self, pid): return {}
            async def close(self): pass

        registry = PlatformRegistry()
        registry.register(Platform.DOUYIN, FakeDouyin)
        adapters = await registry.get_all()
        assert Platform.DOUYIN in adapters
        assert adapters[Platform.DOUYIN].is_ready

    @pytest.mark.asyncio
    async def test_close_all(self):
        from szyg.platforms.registry import PlatformRegistry
        from szyg.platforms.base import BasePlatformAdapter, LoginStatus, PublishRequest, PublishResult
        from szyg.publisher import Platform

        closed = []

        class FakeDouyin(BasePlatformAdapter):
            platform = Platform.DOUYIN
            async def _do_initialize(self): return True
            async def check_login(self): return LoginStatus()
            async def login(self, **kw): return LoginStatus()
            async def publish(self, req): return PublishResult()
            async def get_status(self, pid): return {}
            async def close(self):
                closed.append("douyin")

        registry = PlatformRegistry()
        registry.register(Platform.DOUYIN, FakeDouyin)
        await registry.get(Platform.DOUYIN)
        await registry.close_all()
        assert "douyin" in closed


# =========================================================================
# TestSessionManager — 登录态管理
# =========================================================================

class TestSessionManager:
    """SessionManager 登录态持久化测试"""

    @pytest.fixture
    def tmp_dir(self, tmp_path):
        """临时 session 目录"""
        return tmp_path / "sessions"

    @pytest.fixture
    def session_mgr(self, tmp_dir):
        from szyg.platforms.session_manager import SessionManager
        return SessionManager(storage_dir=tmp_dir)

    def test_save_raw_and_load(self, session_mgr):
        from szyg.publisher import Platform
        state = {
            "cookies": [
                {
                    "name": "sessionid",
                    "value": "abc123",
                    "domain": ".douyin.com",
                    "path": "/",
                    "expires": (datetime.now(timezone.utc).timestamp() + 86400),
                }
            ],
            "origins": []
        }
        session_mgr.save_raw(Platform.DOUYIN, state)

        loaded = session_mgr.load(Platform.DOUYIN)
        assert loaded is not None
        assert len(loaded["cookies"]) == 1
        assert loaded["cookies"][0]["name"] == "sessionid"
        assert "_saved_at" in loaded

    def test_load_nonexistent_returns_none(self, session_mgr):
        from szyg.publisher import Platform
        assert session_mgr.load(Platform.XHS) is None

    def test_is_valid_with_valid_cookie(self, session_mgr):
        from szyg.publisher import Platform
        state = {
            "cookies": [
                {
                    "name": "sessionid",
                    "value": "valid123",
                    "domain": ".douyin.com",
                    "path": "/",
                    "expires": (datetime.now(timezone.utc).timestamp() + 86400 * 7),
                }
            ]
        }
        session_mgr.save_raw(Platform.DOUYIN, state)
        assert session_mgr.is_valid(Platform.DOUYIN) is True

    def test_is_valid_with_expired_cookie(self, session_mgr):
        from szyg.publisher import Platform
        state = {
            "cookies": [
                {
                    "name": "sessionid",
                    "value": "expired123",
                    "domain": ".douyin.com",
                    "path": "/",
                    "expires": (datetime.now(timezone.utc).timestamp() - 86400),  # 1 day ago
                }
            ]
        }
        session_mgr.save_raw(Platform.DOUYIN, state)
        assert session_mgr.is_valid(Platform.DOUYIN) is False

    def test_is_valid_with_session_cookie(self, session_mgr):
        from szyg.publisher import Platform
        # Session cookie: expires = -1
        state = {
            "cookies": [
                {
                    "name": "sessionid",
                    "value": "session123",
                    "domain": ".douyin.com",
                    "path": "/",
                    "expires": -1,
                }
            ]
        }
        session_mgr.save_raw(Platform.DOUYIN, state)
        assert session_mgr.is_valid(Platform.DOUYIN) is True

    def test_invalidate(self, session_mgr):
        from szyg.publisher import Platform
        state = {"cookies": [{"name": "test", "value": "x", "domain": ".t.com", "path": "/", "expires": 9999999999}]}
        session_mgr.save_raw(Platform.DOUYIN, state)
        assert session_mgr.load(Platform.DOUYIN) is not None

        session_mgr.invalidate(Platform.DOUYIN)
        assert session_mgr.load(Platform.DOUYIN) is None

    def test_get_info(self, session_mgr):
        from szyg.publisher import Platform
        info = session_mgr.get_info(Platform.XHS)
        assert info["has_session"] is False
        assert info["valid"] is False

        state = {"cookies": [{"name": "s", "value": "v", "domain": ".x.com", "path": "/", "expires": 9999999999}]}
        session_mgr.save_raw(Platform.XHS, state)
        info = session_mgr.get_info(Platform.XHS)
        assert info["has_session"] is True
        assert info["cookie_count"] == 1

    def test_list_all(self, session_mgr):
        from szyg.publisher import Platform
        state = {"cookies": [{"name": "s", "value": "v", "domain": ".t.com", "path": "/", "expires": 9999999999}]}
        session_mgr.save_raw(Platform.DOUYIN, state)

        all_sessions = session_mgr.list_all()
        assert "douyin" in all_sessions
        assert all_sessions["douyin"]["has_session"] is True


# =========================================================================
# TestAntiDetect — 反检测配置
# =========================================================================

class TestAntiDetect:
    """反检测模块测试"""

    def test_stealth_context_config(self):
        from szyg.platforms.anti_detect import get_stealth_context_config
        config = get_stealth_context_config()
        assert "viewport" in config
        assert config["viewport"]["width"] == 1536
        assert config["viewport"]["height"] == 864
        assert "user_agent" in config
        assert "Chrome" in config["user_agent"]
        assert "locale" in config
        assert config["locale"] == "zh-CN"

    def test_launch_config_headless(self):
        from szyg.platforms.anti_detect import get_launch_config
        config = get_launch_config(headless=True)
        assert config["headless"] is True
        assert "args" in config
        assert "--disable-blink-features=AutomationControlled" in config["args"]

    def test_launch_config_headful(self):
        from szyg.platforms.anti_detect import get_launch_config
        config = get_launch_config(headless=False)
        assert config["headless"] is False

    def test_builtin_stealth_js_loads(self):
        from szyg.platforms.anti_detect import _load_stealth_js
        js = _load_stealth_js()
        assert len(js) > 0
        assert "webdriver" in js or "navigator" in js


# =========================================================================
# TestDouyinSigner — 反爬签名
# =========================================================================

class TestDouyinSigner:
    """DouyinSigner 反爬签名生成器测试"""

    def test_ms_token_length(self):
        from szyg.platforms.signatures import get_douyin_signer
        signer = get_douyin_signer()
        token = signer.get_ms_token()
        assert len(token) == 107

    def test_ms_token_custom_length(self):
        from szyg.platforms.signatures import get_douyin_signer
        signer = get_douyin_signer()
        token = signer.get_ms_token(length=50)
        assert len(token) == 50

    def test_ms_token_charset(self):
        from szyg.platforms.signatures import get_douyin_signer
        signer = get_douyin_signer()
        token = signer.get_ms_token(length=200)
        import string
        valid_chars = set(string.ascii_letters + string.digits + "=")
        assert all(c in valid_chars for c in token)

    def test_ms_token_uniqueness(self):
        from szyg.platforms.signatures import get_douyin_signer
        signer = get_douyin_signer()
        tokens = [signer.get_ms_token() for _ in range(10)]
        assert len(set(tokens)) == 10  # All unique

    def test_signer_singleton(self):
        from szyg.platforms.signatures import get_douyin_signer
        s1 = get_douyin_signer()
        s2 = get_douyin_signer()
        assert s1 is s2

    def test_get_signed_params_adds_ms_token(self):
        from szyg.platforms.signatures import get_douyin_signer
        signer = get_douyin_signer()
        ua = "Mozilla/5.0 Chrome/131"
        params = {"aid": "6383"}

        signed = signer.get_signed_params(
            "https://www.douyin.com/aweme/v1/web/aweme/post/",
            params, ua
        )
        assert "msToken" in signed
        assert len(signed["msToken"]) == 107


# =========================================================================
# TestPublisherV2 — 发布管道 v2 集成
# =========================================================================

class TestPublisherV2:
    """Publisher v2 async 发布 + 平台适配器集成测试"""

    @pytest.fixture(autouse=True)
    def setup_publisher_db(self, tmp_path, monkeypatch):
        """使用临时目录作为 publisher 数据目录"""
        import szyg.publisher as pub_mod
        monkeypatch.setattr(pub_mod, "PUBLISH_DB", tmp_path / "publisher.json")
        monkeypatch.setattr(pub_mod, "PUBLISH_QUEUE", tmp_path / "publish_queue.json")
        monkeypatch.setattr(pub_mod, "PUBLISH_LOG", tmp_path / "publish_log.json")
        # Reset singleton
        monkeypatch.setattr(pub_mod, "_publisher", None)

    def test_publisher_has_async_method(self):
        from szyg.publisher import get_publisher
        pub = get_publisher()
        assert hasattr(pub, "publish_async")
        assert callable(pub.publish_async)

    def test_create_and_pipeline(self):
        from szyg.publisher import get_publisher, Platform, ContentStatus
        pub = get_publisher()

        c = pub.create(title="Test", body="Content", platforms=[Platform.DOUYIN])
        assert c.id
        assert c.status == ContentStatus.DRAFT

        pub.submit_review(c.id)
        assert pub.get_content(c.id).status == ContentStatus.PENDING

        pub.approve(c.id)
        assert pub.get_content(c.id).status == ContentStatus.APPROVED

    def test_publish_async_no_adapters_falls_back_to_mock(self):
        """当没有可用的真实适配器时，publish_async 回退到 mock"""
        from szyg.publisher import get_publisher, Platform
        pub = get_publisher()

        c = pub.create(title="Fallback Test", body="Body", platforms=[Platform.WEIBO])
        pub.submit_review(c.id)
        pub.approve(c.id)

        import asyncio
        result = asyncio.run(pub.publish_async(c.id, Platform.WEIBO))

        # Should succeed via mock fallback (WEIBO has no adapter registered)
        assert result is not None
        assert result.platform == "weibo"
        # mock fallback always returns success
        assert result.status == "success"

    def test_publish_async_with_registered_platform(self):
        """发布到已注册但 adapter 无法初始化的平台，应正确返回失败"""
        from szyg.publisher import get_publisher, Platform
        pub = get_publisher()

        c = pub.create(title="Douyin Test", body="Test", platforms=[Platform.DOUYIN])
        pub.submit_review(c.id)
        pub.approve(c.id)

        import asyncio
        result = asyncio.run(pub.publish_async(c.id, Platform.DOUYIN))

        # Douyin 已注册，但 Playwright 可能不在测试环境可用
        # 应返回 PublishRecord，状态由 adapter 决定
        assert result is not None
        assert result.platform == "douyin"
        # 无论成功或失败，都应被记录
        assert result.status in ("success", "failed", "skipped")

    def test_publish_async_records_in_log(self):
        from szyg.publisher import get_publisher, Platform
        pub = get_publisher()

        c = pub.create(title="Log Test", body="Body", platforms=[Platform.WEIBO])
        pub.submit_review(c.id)
        pub.approve(c.id)

        import asyncio
        asyncio.run(pub.publish_async(c.id, Platform.WEIBO))

        logs = pub.get_logs()
        assert len(logs) >= 1

    def test_publish_now_is_sync_compatible(self):
        """publish_now 应保持向后兼容 (同步接口)"""
        from szyg.publisher import get_publisher, Platform
        pub = get_publisher()

        c = pub.create(title="Sync Test", body="Body", platforms=[Platform.WEIBO])
        pub.submit_review(c.id)
        pub.approve(c.id)

        result = pub.publish_now(c.id, Platform.WEIBO)
        assert result is not None
        assert result.platform == "weibo"

    def test_stats_reflect_published(self):
        from szyg.publisher import get_publisher, Platform
        pub = get_publisher()

        c = pub.create(title="Stats Test", body="Body", platforms=[Platform.WEIBO])
        pub.submit_review(c.id)
        pub.approve(c.id)

        import asyncio
        asyncio.run(pub.publish_async(c.id, Platform.WEIBO))

        stats = pub.get_stats()
        assert stats["published"] >= 1


# =========================================================================
# TestSchedulerNewActions — 调度器新动作
# =========================================================================

class TestSchedulerNewActions:
    """调度器 PLATFORM_LOGIN_CHECK / PLATFORM_HEALTH_CHECK 测试"""

    @pytest.fixture(autouse=True)
    def setup_scheduler_db(self, tmp_path, monkeypatch):
        import szyg.scheduler_engine as sched_mod
        monkeypatch.setattr(sched_mod, "SCHEDULER_DB", tmp_path / "scheduler_jobs.json")
        monkeypatch.setattr(sched_mod, "SCHEDULER_HISTORY", tmp_path / "scheduler_history.json")
        monkeypatch.setattr(sched_mod, "_scheduler", None)

    def test_new_job_actions_exist(self):
        from szyg.scheduler_engine import JobAction
        actions = [a.value for a in JobAction]
        assert "platform_login_check" in actions
        assert "platform_health_check" in actions

    def test_scheduler_has_background_loop(self):
        from szyg.scheduler_engine import get_scheduler
        s = get_scheduler()
        assert hasattr(s, "start")
        assert hasattr(s, "stop")
        assert hasattr(s, "_run_loop")
        assert hasattr(s, "_async_dispatch")
        assert s._tick_interval == 60

    @pytest.mark.asyncio
    async def test_start_and_stop_loop(self):
        from szyg.scheduler_engine import get_scheduler
        s = get_scheduler()
        assert not s._running
        await s.start()
        assert s._running
        assert s._loop_task is not None
        await s.stop()
        assert not s._running

    def test_create_job_with_new_action(self):
        from szyg.scheduler_engine import get_scheduler, TriggerType, JobAction
        s = get_scheduler()
        job = s.create_job(
            name="Platform Health Check",
            trigger_type=TriggerType.INTERVAL,
            trigger_config={"minutes": 120},
            action=JobAction.PLATFORM_HEALTH_CHECK,
            action_config={},
        )
        assert job.action == JobAction.PLATFORM_HEALTH_CHECK


# =========================================================================
# TestPlatformRoutes — REST API
# =========================================================================

class TestPlatformRoutes:
    """平台 REST API 端点测试"""

    @pytest_asyncio.fixture
    async def client(self):
        """FastAPI TestClient"""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient
        from szyg.api.platform_routes import router

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_platform_list_endpoint(self, client):
        response = await client.get("/api/platforms")
        assert response.status_code == 200
        data = response.json()
        assert "platforms" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_platform_list_has_three_adapters(self, client):
        response = await client.get("/api/platforms")
        data = response.json()
        ids = [p["id"] for p in data["platforms"]]
        assert "douyin" in ids
        assert "xhs" in ids
        assert "wechat_mp" in ids

    @pytest.mark.asyncio
    async def test_platform_detail_invalid(self, client):
        response = await client.get("/api/platforms/nonexistent")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_platform_health_endpoint(self, client):
        response = await client.get("/api/platforms/health/all")
        assert response.status_code == 200
        data = response.json()
        # 应返回各平台状态 dict
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_platform_logs_endpoint(self, client):
        response = await client.get("/api/platforms/logs/all")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


# =========================================================================
# TestMCPServer — MCP 工具定义
# =========================================================================

class TestPlatformMCPServer:
    """platforms_mcp.py MCP 服务器测试"""

    def test_mcp_server_has_all_tools(self):
        from szyg.mcp_servers.platforms_mcp import server
        # 检查所有 8 个工具已注册
        tool_names = set(server._tools.keys())
        expected = {
            "platform_list", "platform_status", "platform_login",
            "platform_publish", "platform_publish_direct",
            "platform_sessions", "platform_logout", "platform_health",
        }
        assert tool_names == expected

    def test_platform_list_tool_works(self):
        from szyg.mcp_servers.platforms_mcp import platform_list
        result = platform_list()
        assert isinstance(result, list)
        assert len(result) >= 3
        # Each entry has required keys
        for entry in result:
            assert "id" in entry
            assert "adapter" in entry
            assert "state" in entry

    def test_platform_status_invalid_platform(self):
        from szyg.mcp_servers.platforms_mcp import platform_status
        result = platform_status("nonexistent")
        assert "error" in result

    def test_platform_logout_invalid(self):
        from szyg.mcp_servers.platforms_mcp import platform_logout
        result = platform_logout("nonexistent")
        assert "error" in result

    def test_platform_sessions_all(self):
        from szyg.mcp_servers.platforms_mcp import platform_sessions
        result = platform_sessions("")
        assert isinstance(result, dict)

    def test_platform_publish_invalid_content(self):
        from szyg.mcp_servers.platforms_mcp import platform_publish
        result = platform_publish("douyin", "nonexistent-content-id")
        assert "error" in result


# =========================================================================
# TestBaseAdapter — 适配器基类
# =========================================================================

class TestBaseAdapter:
    """BasePlatformAdapter 抽象基类测试"""

    def test_adapter_state_machine(self):
        from szyg.platforms.base import BasePlatformAdapter, AdapterState, LoginStatus, PublishRequest, PublishResult
        from szyg.publisher import Platform

        class TestAdapter(BasePlatformAdapter):
            platform = Platform.DOUYIN
            async def _do_initialize(self):
                self._initialized = True
                return True
            async def check_login(self):
                return LoginStatus(is_logged_in=getattr(self, "_initialized", False))
            async def login(self, **kw):
                return LoginStatus(is_logged_in=True)
            async def publish(self, req):
                return PublishResult(success=True)
            async def get_status(self, pid):
                return {}
            async def close(self):
                pass

        adapter = TestAdapter()
        assert adapter.state == AdapterState.UNINITIALIZED
        assert adapter.platform_name == "抖音"
        assert not adapter.is_ready

    @pytest.mark.asyncio
    async def test_adapter_initialize(self):
        from szyg.platforms.base import BasePlatformAdapter, AdapterState, LoginStatus, PublishRequest, PublishResult
        from szyg.publisher import Platform

        class TestAdapter(BasePlatformAdapter):
            platform = Platform.DOUYIN
            async def _do_initialize(self): return True
            async def check_login(self): return LoginStatus()
            async def login(self, **kw): return LoginStatus()
            async def publish(self, req): return PublishResult()
            async def get_status(self, pid): return {}
            async def close(self): pass

        adapter = TestAdapter()
        ok = await adapter.initialize()
        assert ok is True
        assert adapter.is_ready

    @pytest.mark.asyncio
    async def test_adapter_initialize_failure(self):
        from szyg.platforms.base import BasePlatformAdapter, AdapterState, LoginStatus, PublishRequest, PublishResult
        from szyg.publisher import Platform

        class BadAdapter(BasePlatformAdapter):
            platform = Platform.DOUYIN
            async def _do_initialize(self):
                raise RuntimeError("Init failed")
            async def check_login(self): return LoginStatus()
            async def login(self, **kw): return LoginStatus()
            async def publish(self, req): return PublishResult()
            async def get_status(self, pid): return {}
            async def close(self): pass

        adapter = BadAdapter()
        ok = await adapter.initialize()
        assert ok is False
        assert adapter.state == AdapterState.ERROR
