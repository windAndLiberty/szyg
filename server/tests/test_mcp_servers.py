"""MCP Server 单元测试 — leads_mcp + scripts_mcp。

测试每个工具的 JSON-RPC 调用，验证输入输出正确性。
"""

import json
import subprocess
import sys
import pytest

PYTHON = sys.executable
SERVER_DIR = "server/szyg/mcp_servers"


def _call_tool(server_file: str, tool_name: str, arguments: dict | None = None) -> dict:
    """通过 stdio JSON-RPC 调用 MCP 工具。"""
    request = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments or {}},
    })
    result = subprocess.run(
        [PYTHON, f"{SERVER_DIR}/{server_file}"],
        input=request, capture_output=True, text=True,
        env={**__import__("os").environ, "PYTHONPATH": "server"},
        timeout=10,
    )
    response = json.loads(result.stdout.strip() or "{}")
    if "error" in response:
        raise RuntimeError(f"MCP error: {response['error']}")
    content = response["result"]["content"]
    return json.loads(content[0]["text"])


# ── leads_mcp tests ──────────────────────────────────────

class TestLeadsMCP:
    def test_lead_search(self):
        result = _call_tool("leads_mcp.py", "lead_search", {"limit": 10})
        assert isinstance(result, list)

    def test_lead_score_high_intent(self):
        result = _call_tool("leads_mcp.py", "lead_score", {
            "platform": "douyin",
            "content": "这个多少钱？怎么买？方便加微信吗",
        })
        assert result["intent_score"] >= 0.5
        assert result["intent_level"] == "high"
        assert result["should_follow_up"] is True
        assert len(result["suggested_reply"]) > 10

    def test_lead_score_cold(self):
        result = _call_tool("leads_mcp.py", "lead_score", {
            "platform": "douyin",
            "content": "嗯",
        })
        assert result["intent_level"] == "cold"
        assert result["should_follow_up"] is False

    def test_lead_create_and_update(self):
        result = _call_tool("leads_mcp.py", "lead_create", {
            "platform": "wechat",
            "account": "test_user_123",
            "name": "MCP测试客户",
            "content": "测试创建",
        })
        lead_id = result["id"]
        assert lead_id.startswith("lead_")

        updated = _call_tool("leads_mcp.py", "lead_update", {
            "lead_id": lead_id,
            "stage": "contacted",
            "notes": "MCP测试更新",
        })
        assert updated["stage"] == "contacted"
        assert updated["notes"] == "MCP测试更新"

    def test_lead_stats(self):
        result = _call_tool("leads_mcp.py", "lead_stats")
        assert "total" in result
        assert "by_intent" in result
        assert "by_stage" in result


# ── scripts_mcp tests ────────────────────────────────────

class TestScriptsMCP:
    def test_script_industries(self):
        result = _call_tool("scripts_mcp.py", "script_industries")
        assert len(result["industries"]) >= 5
        assert result["template_count"] >= 4

    def test_script_list_by_industry(self):
        result = _call_tool("scripts_mcp.py", "script_list", {"industry": "零售"})
        assert len(result) >= 2
        for s in result:
            assert s["industry"] == "零售"

    def test_script_list_by_search(self):
        result = _call_tool("scripts_mcp.py", "script_list", {"search": "价格"})
        assert len(result) >= 1

    def test_script_generate(self):
        result = _call_tool("scripts_mcp.py", "script_generate", {
            "industry": "零售",
            "scenario": "价格咨询",
            "product_info": "智能AI客服机器人，提升客服效率70%，降低成本35%",
            "customer_context": "客户在抖音看到广告后评论问价",
        })
        assert result["template_id"] is not None
        assert len(result["steps"]) >= 4
        assert "智能AI客服" in result["steps"].get("greeting", "") or \
               "智能AI客服" in str(result["steps"])


# ── Pipeline tests ───────────────────────────────────────

class TestPipeline:
    def test_check_stale_leads_runs(self):
        result = subprocess.run(
            [PYTHON, "server/szyg/pipelines/check_stale_leads.py"],
            capture_output=True, text=True,
            env={**__import__("os").environ, "PYTHONPATH": "server"},
            timeout=10,
        )
        assert result.returncode == 0
        assert "NO_STALE_LEADS" in result.stdout or "发现" in result.stdout
