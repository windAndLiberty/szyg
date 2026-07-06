"""
超级员工工具冒烟测试

对只读/安全工具执行真实调用，验证工具能正常返回结果。
需要后端服务器运行在 127.0.0.1:8000。

用法:
  # 启动后端后运行
  uv run pytest tests/unit/test_tool_smoke.py -v

  # 跳过需要服务器的测试
  uv run pytest tests/unit/test_tool_smoke.py -v -m "not requires_server"

标记:
  requires_server — 需要后端服务器运行
  read_only       — 只读工具，无副作用
  aigc            — 需要火山引擎 API Key
"""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from szyg.api.hermes_chat import _execute_tool, _call_direct, HERMES_TOOLS


# =============================================================================
# 辅助
# =============================================================================

def _args(**kwargs) -> str:
    return json.dumps(kwargs, ensure_ascii=False)


def _ok(result: str) -> bool:
    """检查工具返回是否成功（不含错误标记）。"""
    return "错误" not in result and "不被允许" not in result


def _parse(result: str):
    try:
        return json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return result


# 检查服务器是否在线
def _server_online() -> bool:
    try:
        r = httpx.get("http://127.0.0.1:8000/api/oem/config/default", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


SERVER_ONLINE = _server_online()
skip_if_no_server = pytest.mark.skipif(
    not SERVER_ONLINE,
    reason="后端服务器未运行在 127.0.0.1:8000",
)


# =============================================================================
# 安全只读工具 — 对真实服务器冒烟测试
# =============================================================================

@skip_if_no_server
@pytest.mark.requires_server
@pytest.mark.read_only
class TestReadOnlyToolsSmoke:
    """对只读工具执行真实调用，验证返回格式正确。"""

    @pytest.mark.asyncio
    async def test_content_list(self):
        result = await _execute_tool("content_list", _args())
        assert _ok(result), f"content_list 失败: {result}"

    @pytest.mark.asyncio
    async def test_content_stats(self):
        result = await _execute_tool("content_stats", _args())
        assert _ok(result), f"content_stats 失败: {result}"

    @pytest.mark.asyncio
    async def test_platform_list(self):
        result = await _execute_tool("platform_list", _args())
        assert _ok(result), f"platform_list 失败: {result}"

    @pytest.mark.asyncio
    async def test_platform_health(self):
        result = await _execute_tool("platform_health", _args())
        assert _ok(result), f"platform_health 失败: {result}"

    @pytest.mark.asyncio
    async def test_scheduler_list(self):
        result = await _execute_tool("scheduler_list", _args())
        assert _ok(result), f"scheduler_list 失败: {result}"

    @pytest.mark.asyncio
    async def test_scheduler_stats(self):
        result = await _execute_tool("scheduler_stats", _args())
        assert _ok(result), f"scheduler_stats 失败: {result}"

    @pytest.mark.asyncio
    async def test_scheduler_history(self):
        result = await _execute_tool("scheduler_history", _args())
        assert _ok(result), f"scheduler_history 失败: {result}"

    @pytest.mark.asyncio
    async def test_tools_catalog(self):
        result = await _execute_tool("tools_catalog", _args())
        assert _ok(result), f"tools_catalog 失败: {result}"

    @pytest.mark.asyncio
    async def test_tools_categories(self):
        result = await _execute_tool("tools_categories", _args())
        assert _ok(result), f"tools_categories 失败: {result}"

    @pytest.mark.asyncio
    async def test_tools_installed(self):
        result = await _execute_tool("tools_installed", _args())
        assert _ok(result), f"tools_installed 失败: {result}"

    @pytest.mark.asyncio
    async def test_tools_stats(self):
        result = await _execute_tool("tools_stats", _args())
        assert _ok(result), f"tools_stats 失败: {result}"

    @pytest.mark.asyncio
    async def test_oem_config(self):
        result = await _execute_tool("oem_config", _args())
        assert _ok(result), f"oem_config 失败: {result}"

    @pytest.mark.asyncio
    async def test_agents_list(self):
        result = await _execute_tool("agents_list", _args())
        assert _ok(result), f"agents_list 失败: {result}"

    @pytest.mark.asyncio
    async def test_knowledge_stats(self):
        result = await _execute_tool("knowledge_stats", _args())
        assert _ok(result), f"knowledge_stats 失败: {result}"

    @pytest.mark.asyncio
    async def test_local_ollama_models(self):
        result = await _execute_tool("local_ollama_models", _args())
        # Ollama 可能未安装，允许错误但不允许崩溃
        assert isinstance(result, str), f"local_ollama_models 返回类型错误: {type(result)}"

    @pytest.mark.asyncio
    async def test_runtime_list(self):
        result = await _execute_tool("runtime_list", _args())
        assert _ok(result), f"runtime_list 失败: {result}"


# =============================================================================
# 直接调用工具 — 无需服务器
# =============================================================================

class TestDirectCallSmoke:
    """直接调用 skill 工具，无需服务器。"""

    def test_video_templates(self):
        result = _call_direct("video_templates", {})
        data = _parse(result)
        assert isinstance(data, (list, dict)), f"video_templates 返回异常: {result}"

    def test_video_fonts(self):
        result = _call_direct("video_fonts", {})
        data = _parse(result)
        assert isinstance(data, (list, dict)), f"video_fonts 返回异常: {result}"

    def test_canvas_get_fonts(self):
        result = _call_direct("canvas_get_fonts", {})
        data = _parse(result)
        assert isinstance(data, (list, dict)), f"canvas_get_fonts 返回异常: {result}"

    def test_canvas_preview_config(self):
        result = _call_direct("canvas_preview_config", {})
        data = _parse(result)
        assert isinstance(data, dict), f"canvas_preview_config 返回异常: {result}"

    def test_skills_list(self):
        result = _call_direct("skills_list", {})
        data = _parse(result)
        assert isinstance(data, (list, dict)), f"skills_list 返回异常: {result}"

    def test_oem_themes(self):
        result = _call_direct("oem_themes", {})
        data = _parse(result)
        assert isinstance(data, (list, dict)), f"oem_themes 返回异常: {result}"

    def test_agents_tiers(self):
        result = _call_direct("agents_tiers", {})
        data = _parse(result)
        assert isinstance(data, (list, dict)), f"agents_tiers 返回异常: {result}"

    def test_agents_categories(self):
        result = _call_direct("agents_categories", {})
        data = _parse(result)
        assert isinstance(data, (list, dict)), f"agents_categories 返回异常: {result}"

    def test_agents_get_empty(self):
        result = _call_direct("agents_get", {"agent_id": ""})
        data = _parse(result)
        # 空ID可能返回空结果或错误，但不应崩溃
        assert data is not None, f"agents_get 崩溃: {result}"

    def test_video_info_nonexistent(self):
        result = _call_direct("video_info", {"file_path": "/nonexistent/video.mp4"})
        data = _parse(result)
        # 路径被安全重定向到 data/ 目录，文件不存在时返回空元数据
        assert data.get("duration", 0) == 0 or "error" in data, f"video_info 应返回空元数据或错误: {result}"

    def test_docx_extract_text_nonexistent(self):
        result = _call_direct("docx_extract_text", {"file_path": "/nonexistent/doc.docx"})
        data = _parse(result)
        assert "error" in data, f"docx_extract_text 应拒绝不存在路径: {result}"

    def test_xlsx_read_nonexistent(self):
        try:
            result = _call_direct("xlsx_read", {"file_path": "/nonexistent/data.xlsx"})
            data = _parse(result)
            assert "error" in data, f"xlsx_read 应拒绝不存在路径: {result}"
        except ModuleNotFoundError:
            pytest.skip("openpyxl 未安装")

    def test_pdf_extract_nonexistent(self):
        result = _call_direct("pdf_extract", {"file_path": "/nonexistent/doc.pdf"})
        data = _parse(result)
        assert "error" in data, f"pdf_extract 应拒绝不存在路径: {result}"

    def test_video_cut_nonexistent(self):
        result = _call_direct("video_cut", {"file_path": "/nonexistent/video.mp4", "start": 0, "duration": 5})
        data = _parse(result)
        assert "error" in data, f"video_cut 应拒绝不存在路径: {result}"


# =============================================================================
# 路径安全测试
# =============================================================================

class TestPathSafety:
    """验证文件路径安全校验。"""

    def test_reject_absolute_system_path(self):
        """应拒绝系统绝对路径（如 /etc/passwd）。"""
        result = _call_direct("docx_extract_text", {"file_path": "/etc/passwd"})
        data = _parse(result)
        assert "error" in data or "Invalid" in str(data), \
            f"应拒绝系统路径 /etc/passwd: {result}"

    def test_reject_windows_system_path(self):
        """应拒绝 Windows 系统路径。"""
        result = _call_direct("pdf_extract", {"file_path": "C:\\Windows\\System32\\config\\SAM"})
        data = _parse(result)
        assert "error" in data or "Invalid" in str(data), \
            f"应拒绝 Windows 系统路径: {result}"

    def test_reject_directory_traversal(self):
        """应拒绝目录穿越路径。"""
        try:
            result = _call_direct("xlsx_read", {"file_path": "../../../etc/passwd"})
            data = _parse(result)
            assert "error" in data or "Invalid" in str(data), \
                f"应拒绝目录穿越路径: {result}"
        except ModuleNotFoundError:
            pytest.skip("openpyxl 未安装")


# =============================================================================
# 参数清洗测试
# =============================================================================

class TestArgSanitization:
    """验证参数清洗逻辑。"""

    @pytest.mark.asyncio
    async def test_empty_args(self):
        """空参数应正常处理（不崩溃）。"""
        result = await _execute_tool("content_list", "{}")
        # 空参数对只读工具应该可以工作
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_malformed_json_args(self):
        """畸形 JSON 参数应被安全处理。"""
        result = await _execute_tool("content_list", "not-json{{{")
        assert isinstance(result, str)
        # 不应崩溃，可能返回错误信息

    @pytest.mark.asyncio
    async def test_extra_args_ignored(self):
        """多余参数应被忽略。"""
        result = await _execute_tool("content_list", _args(status="published", extra="ignored", hack="true"))
        # 多余参数不应影响工具执行
        assert isinstance(result, str)
