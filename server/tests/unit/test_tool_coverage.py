"""
超级员工工具覆盖率测试

验证 HERMES_TOOLS 中声明的每一个工具在 _execute_tool 中都有对应的处理逻辑。
防止"声明了但没实现"的幽灵工具。

运行: uv run pytest tests/unit/test_tool_coverage.py -v
"""

import ast
import inspect
import textwrap
from pathlib import Path

import pytest


def _extract_source(func) -> str:
    """提取函数源码并统一缩进。"""
    src = inspect.getsource(func)
    return textwrap.dedent(src)


def _find_tool_names_in_source(source: str) -> set[str]:
    """从源码中提取所有被分支处理的工具名。

    匹配模式:
      - name == "xxx"
      - name == 'xxx'
    """
    tree = ast.parse(source)
    tool_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            if (
                isinstance(node.left, ast.Name)
                and node.left.id == "name"
                and len(node.ops) == 1
                and isinstance(node.ops[0], ast.Eq)
                and len(node.comparators) == 1
                and isinstance(node.comparators[0], ast.Constant)
                and isinstance(node.comparators[0].value, str)
            ):
                tool_names.add(node.comparators[0].value)
    return tool_names


def _find_tool_names_in_call_direct(source: str) -> set[str]:
    """从 _call_direct 源码中提取工具名。"""
    return _find_tool_names_in_source(source)


class TestToolCoverage:
    """验证每个 HERMES_TOOLS 声明都有对应的执行处理器。"""

    @pytest.fixture(scope="class")
    def hermes_tool_names(self) -> set[str]:
        """从 HERMES_TOOLS 提取所有声明的工具名。"""
        from szyg.api.hermes_chat import HERMES_TOOLS
        return {t["function"]["name"] for t in HERMES_TOOLS}

    @pytest.fixture(scope="class")
    def execute_tool_names(self) -> set[str]:
        """从 _execute_tool 源码中提取所有被处理的工具名。"""
        from szyg.api.hermes_chat import _execute_tool
        source = _extract_source(_execute_tool)
        return _find_tool_names_in_source(source)

    @pytest.fixture(scope="class")
    def call_direct_names(self) -> set[str]:
        """从 _call_direct 源码中提取所有被处理的工具名。"""
        from szyg.api.hermes_chat import _call_direct
        source = _extract_source(_call_direct)
        return _find_tool_names_in_source(source)

    @pytest.fixture(scope="class")
    def allowed_names(self) -> set[str]:
        """从 ALLOWED 集合提取所有被允许的工具名。"""
        from szyg.api.hermes_chat import _execute_tool
        source = _extract_source(_execute_tool)
        # 解析 ALLOWED = { ... } 集合字面量
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "ALLOWED":
                        if isinstance(node.value, ast.Set):
                            return {
                                el.value
                                for el in node.value.elts
                                if isinstance(el, ast.Constant) and isinstance(el.value, str)
                            }
        return set()

    def test_all_tools_in_allowed(self, hermes_tool_names, allowed_names):
        """HERMES_TOOLS 中的每个工具都应该在 ALLOWED 白名单中。"""
        missing = hermes_tool_names - allowed_names
        assert not missing, f"工具未在 ALLOWED 白名单中: {sorted(missing)}"

    def test_all_tools_have_handler(self, hermes_tool_names, execute_tool_names, call_direct_names):
        """HERMES_TOOLS 中的每个工具都应该在 _execute_tool 或 _call_direct 中有处理分支。"""
        all_handlers = execute_tool_names | call_direct_names
        missing = hermes_tool_names - all_handlers
        assert not missing, f"工具声明了但没有处理逻辑（幽灵工具）: {sorted(missing)}"

    def test_no_phantom_handlers(self, hermes_tool_names, execute_tool_names, call_direct_names):
        """_execute_tool / _call_direct 中的工具名应该在 HERMES_TOOLS 中有声明。"""
        all_handlers = execute_tool_names | call_direct_names
        phantom = all_handlers - hermes_tool_names
        # 允许一些内部工具不在 HERMES_TOOLS 中（如 acq_*, sau_*, pipeline_* 等）
        # 这些是 Phase B/C/D 扩展工具，可能尚未暴露给 LLM
        known_unexposed = {
            # Phase B: SOP/公告/Brain/配置
            "sop_list", "sop_define",
            "announce_list", "announce_create", "announce_delete",
            "brain_status", "brain_prompt", "brain_mcp",
            "models_list", "system_config", "oem_config_update",
            # Phase C: 流水线
            "pipeline_list", "pipeline_get",
            "pipeline_video_create", "pipeline_content_create", "pipeline_image_set",
            # Phase D: 流量引擎
            "acquisition_search", "acquisition_intercept", "acquisition_generate_comments",
            "acquisition_deai", "acquisition_preflight", "acquisition_comment_send",
            "acquisition_queue", "acquisition_stats",
            "acquisition_monitor_list", "acquisition_monitor_add",
            "acquisition_monitor_start", "acquisition_monitor_stop",
            "acquisition_ab_start", "acquisition_ab_list",
            "acquisition_leads", "acquisition_lead_score",
            "acquisition_auto_reply", "acquisition_funnel",
            "acquisition_strategy", "acquisition_strategy_apply",
            # Acquisition MCP
            "acq_platforms", "acq_search", "acq_get_comments",
            "acq_send_comment", "acq_batch_send_comments", "acq_send_dm",
            # social-auto-upload
            "sau_list_platforms", "sau_upload_video", "sau_upload_note",
            "sau_check_login", "sau_login",
        }
        truly_phantom = phantom - known_unexposed
        assert not truly_phantom, f"有处理逻辑但未在 HERMES_TOOLS 声明（且不在已知扩展列表中）: {sorted(truly_phantom)}"

    def test_tool_count_reasonable(self, hermes_tool_names):
        """工具总数应该在合理范围内（防止意外删除大量工具）。"""
        count = len(hermes_tool_names)
        assert count >= 50, f"工具数量过少（{count}），可能 HERMES_TOOLS 被意外截断"
        assert count <= 150, f"工具数量过多（{count}），可能重复声明"
