"""
超级员工工具分发单元测试

使用 mock httpx 验证 HTTP 路由工具的请求构造和响应解析。
直接调用工具（_call_direct）使用真实 skill 函数测试。
火山引擎 AIGC 工具使用 mock client 测试。

运行: uv run pytest tests/unit/test_tool_dispatch.py -v
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from szyg.api.hermes_chat import _execute_tool, _call_direct


# =============================================================================
# 辅助函数
# =============================================================================

def _args(**kwargs) -> str:
    """构造 JSON 参数字符串。"""
    return json.dumps(kwargs, ensure_ascii=False)


def _parse_result(result: str) -> dict:
    """解析工具返回的 JSON 字符串。"""
    return json.loads(result)


# =============================================================================
# HTTP 路由工具 — Mock httpx 响应
# =============================================================================

class TestHTTPTools:
    """测试通过 httpx 调用内部 API 的工具。"""

    @pytest.mark.asyncio
    async def test_content_list(self):
        """content_list 应调用 GET /api/publisher/contents。"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"contents": [], "total": 0}
        mock_resp.raise_for_status = MagicMock()

        with patch("szyg.api.hermes_chat._internal_client") as mock_client:
            mock_client.get.return_value = mock_resp
            result = await _execute_tool("content_list", _args(status="published"))
            data = _parse_result(result)
            assert "contents" in data
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_content_create(self):
        """content_create 应调用 POST /api/publisher/contents。"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": "c1", "title": "测试"}
        mock_resp.raise_for_status = MagicMock()

        with patch("szyg.api.hermes_chat._internal_client") as mock_client:
            mock_client.post.return_value = mock_resp
            result = await _execute_tool("content_create", _args(title="测试标题", body="内容"))
            data = _parse_result(result)
            assert data["id"] == "c1"
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_platform_list(self):
        """platform_list 应调用 GET /api/platforms。"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"platforms": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("szyg.api.hermes_chat._internal_client") as mock_client:
            mock_client.get.return_value = mock_resp
            result = await _execute_tool("platform_list", _args())
            data = _parse_result(result)
            assert "platforms" in data

    @pytest.mark.asyncio
    async def test_platform_status(self):
        """platform_status 应调用 GET /api/platforms/{platform}。"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"platform": "douyin", "is_logged_in": True}
        mock_resp.raise_for_status = MagicMock()

        with patch("szyg.api.hermes_chat._internal_client") as mock_client:
            mock_client.get.return_value = mock_resp
            result = await _execute_tool("platform_status", _args(platform="douyin"))
            data = _parse_result(result)
            assert data["platform"] == "douyin"

    @pytest.mark.asyncio
    async def test_scheduler_list(self):
        """scheduler_list 应调用 GET /api/scheduler/jobs。"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"jobs": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("szyg.api.hermes_chat._internal_client") as mock_client:
            mock_client.get.return_value = mock_resp
            result = await _execute_tool("scheduler_list", _args())
            data = _parse_result(result)
            assert "jobs" in data

    @pytest.mark.asyncio
    async def test_scheduler_create(self):
        """scheduler_create 应调用 POST /api/scheduler/jobs。"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": "j1", "name": "测试任务"}
        mock_resp.raise_for_status = MagicMock()

        with patch("szyg.api.hermes_chat._internal_client") as mock_client:
            mock_client.post.return_value = mock_resp
            result = await _execute_tool("scheduler_create", _args(name="测试任务", action="custom"))
            data = _parse_result(result)
            assert data["id"] == "j1"

    @pytest.mark.asyncio
    async def test_tools_catalog(self):
        """tools_catalog 应调用 GET /api/tools/catalog。"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"soft_id": "t1", "name": "工具1"}]
        mock_resp.raise_for_status = MagicMock()

        with patch("szyg.api.hermes_chat._internal_client") as mock_client:
            mock_client.get.return_value = mock_resp
            result = await _execute_tool("tools_catalog", _args())
            data = _parse_result(result)
            assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_oem_config(self):
        """oem_config 应调用 GET /api/oem/config/default。"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"name": "szyg"}
        mock_resp.raise_for_status = MagicMock()

        with patch("szyg.api.hermes_chat._internal_client") as mock_client:
            mock_client.get.return_value = mock_resp
            result = await _execute_tool("oem_config", _args())
            data = _parse_result(result)
            assert data["name"] == "szyg"

    @pytest.mark.asyncio
    async def test_agents_list(self):
        """agents_list 应调用 GET /api/agents/list。"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"agents": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("szyg.api.hermes_chat._internal_client") as mock_client:
            mock_client.get.return_value = mock_resp
            result = await _execute_tool("agents_list", _args())
            data = _parse_result(result)
            assert "agents" in data


# =============================================================================
# 安全验证 — 白名单拒绝
# =============================================================================

class TestToolAllowlist:
    """验证白名单安全机制。"""

    @pytest.mark.asyncio
    async def test_unknown_tool_rejected(self):
        """不在白名单中的工具名应被拒绝。"""
        result = await _execute_tool("nonexistent_tool", _args())
        assert "不被允许" in result or "错误" in result

    @pytest.mark.asyncio
    async def test_empty_tool_name_rejected(self):
        """空工具名应被拒绝。"""
        result = await _execute_tool("", _args())
        assert "不被允许" in result or "错误" in result


# =============================================================================
# 直接调用工具 — Skills（无 HTTP 依赖）
# =============================================================================

class TestDirectCallTools:
    """测试 _call_direct 中的本地 skill 工具。"""

    def test_video_templates(self):
        """video_templates 应返回模板列表。"""
        result = _call_direct("video_templates", {})
        data = _parse_result(result)
        assert isinstance(data, (list, dict))

    def test_video_fonts(self):
        """video_fonts 应返回字体列表。"""
        result = _call_direct("video_fonts", {})
        data = _parse_result(result)
        assert isinstance(data, (list, dict))

    def test_canvas_get_fonts(self):
        """canvas_get_fonts 应返回字体列表。"""
        result = _call_direct("canvas_get_fonts", {})
        data = _parse_result(result)
        assert isinstance(data, (list, dict))

    def test_canvas_preview_config(self):
        """canvas_preview_config 应返回配置预览。"""
        result = _call_direct("canvas_preview_config", {})
        data = _parse_result(result)
        assert isinstance(data, dict)

    def test_skills_list(self):
        """skills_list 应返回技能列表。"""
        result = _call_direct("skills_list", {})
        data = _parse_result(result)
        assert isinstance(data, (list, dict))

    def test_oem_themes(self):
        """oem_themes 应返回主题列表。"""
        result = _call_direct("oem_themes", {})
        data = _parse_result(result)
        assert isinstance(data, (list, dict))

    def test_agents_tiers(self):
        """agents_tiers 应返回层级列表。"""
        result = _call_direct("agents_tiers", {})
        data = _parse_result(result)
        assert isinstance(data, (list, dict))

    def test_agents_categories(self):
        """agents_categories 应返回分类列表。"""
        result = _call_direct("agents_categories", {})
        data = _parse_result(result)
        assert isinstance(data, (list, dict))

    def test_video_info_invalid_path(self):
        """video_info 对不存在文件应返回空元数据（路径被重定向到安全目录）。"""
        result = _call_direct("video_info", {"file_path": "/nonexistent/video.mp4"})
        data = _parse_result(result)
        # 路径被安全重定向到 data/ 目录，文件不存在时返回空元数据
        assert data.get("duration", 0) == 0 or "error" in data

    def test_docx_extract_text_invalid_path(self):
        """docx_extract_text 对无效路径应返回错误。"""
        result = _call_direct("docx_extract_text", {"file_path": "/nonexistent/doc.docx"})
        data = _parse_result(result)
        assert "error" in data


# =============================================================================
# 火山引擎 AIGC 工具 — Mock client
# =============================================================================

class TestAIGCTools:
    """测试火山引擎 AIGC 工具调用。"""

    @pytest.mark.asyncio
    async def test_ai_image_generate_mock(self):
        """ai_image_generate 应调用 VolcEngineClient.generate_image。"""
        mock_client = MagicMock()
        mock_client.generate_image = AsyncMock(return_value="/tmp/test_image.png")
        mock_client.close = AsyncMock()

        with patch("szyg.integrations.volcengine_client.VolcEngineClient", return_value=mock_client):
            with patch("szyg.api.hermes_chat.VOLCENGINE_ENDPOINTS", {"doubao-image": "ep-xxx"}):
                with patch("szyg.api.hermes_chat.VOLCENGINE_API_KEY", "test-key"):
                    with patch("szyg.api.hermes_chat.VOLCENGINE_BASE_URL", "https://test.com"):
                        result = await _execute_tool("ai_image_generate", _args(
                            prompt="赛博朋克城市",
                            style="cyberpunk",
                            size="1920x1920",
                        ))
                        data = _parse_result(result)
                        assert data.get("ok") is True
                        assert "url" in data

    @pytest.mark.asyncio
    async def test_ai_image_generate_no_endpoint(self):
        """ai_image_generate 在未配置 endpoint 时应返回友好错误。"""
        mock_client = MagicMock()
        mock_client.close = AsyncMock()

        with patch("szyg.integrations.volcengine_client.VolcEngineClient", return_value=mock_client):
            with patch("szyg.api.hermes_chat.VOLCENGINE_ENDPOINTS", {}):
                with patch("szyg.api.hermes_chat.VOLCENGINE_API_KEY", ""):
                    with patch("szyg.api.hermes_chat.VOLCENGINE_BASE_URL", ""):
                        result = await _execute_tool("ai_image_generate", _args(
                            prompt="测试图片",
                        ))
                        data = _parse_result(result)
                        assert data.get("ok") is False
                        assert "error" in data

    @pytest.mark.asyncio
    async def test_ai_image_styles(self):
        """ai_image_styles 应返回风格列表。"""
        mock_client = MagicMock()
        mock_client.close = AsyncMock()

        with patch("szyg.integrations.volcengine_client.VolcEngineClient", return_value=mock_client):
            with patch("szyg.api.hermes_chat.VOLCENGINE_ENDPOINTS", {}):
                with patch("szyg.api.hermes_chat.VOLCENGINE_API_KEY", ""):
                    with patch("szyg.api.hermes_chat.VOLCENGINE_BASE_URL", ""):
                        result = await _execute_tool("ai_image_styles", _args())
                        data = _parse_result(result)
                        assert "styles" in data or isinstance(data, list)


# =============================================================================
# Adapter 工具 — Mock adapter
# =============================================================================

class TestAdapterTools:
    """测试直接调用 adapter 的工具（acq_*, sau_*）。"""

    @pytest.mark.asyncio
    async def test_acq_platforms(self):
        """acq_platforms 应返回支持的平台列表。"""
        with patch("szyg.integrations.acquisition_adapters.list_acquisition_platforms",
                    return_value=["douyin", "xhs", "bilibili"]):
            result = await _execute_tool("acq_platforms", _args())
            data = _parse_result(result)
            assert "platforms" in data
            assert "douyin" in data["platforms"]

    @pytest.mark.asyncio
    async def test_sau_list_platforms(self):
        """sau_list_platforms 应返回支持的平台列表。"""
        mock_adapter = MagicMock()
        mock_adapter.list_platforms.return_value = {"douyin": True, "xhs": False}

        with patch("szyg.integrations.social_auto_upload_adapter.get_sau_adapter",
                    return_value=mock_adapter):
            result = await _execute_tool("sau_list_platforms", _args())
            data = _parse_result(result)
            assert "platforms" in data
