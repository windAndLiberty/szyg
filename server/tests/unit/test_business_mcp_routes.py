import asyncio

from szyg.api.business_mcp_routes import _dispatch, _tool_catalog


def test_catalog_exposes_guarded_business_capabilities():
    tools = _tool_catalog()
    assert tools
    publishing = next(item for item in tools if item["name"] == "publishing.video")
    assert publishing["annotations"]["destructiveHint"] is True
    assert publishing["_meta"]["szyg/confirmationRequired"] is True


def test_initialize_is_stateless_streamable_http_server():
    response = asyncio.run(_dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}))
    assert response["result"]["serverInfo"]["name"] == "szyg-business"
    assert response["result"]["capabilities"]["tools"]["listChanged"] is False


def test_unknown_tool_fails_without_execution():
    response = asyncio.run(_dispatch({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "not.real", "arguments": {}},
    }))
    assert response["error"]["code"] == -32601
