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


def test_employee_can_read_experts_without_switching_the_active_expert(monkeypatch):
    from fastapi import FastAPI
    import httpx

    from szyg.api import agency_routes

    app = FastAPI()
    app.include_router(agency_routes.router)
    client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client(transport=httpx.ASGITransport(app=app), **kwargs))
    monkeypatch.setattr(agency_routes, "_cache_active_expert", lambda *args: (_ for _ in ()).throw(AssertionError("global role accessed")))

    def read(name, arguments):
        response = asyncio.run(_dispatch({"id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}}))
        return response["result"]

    rows = read("experts.search", {})["structuredContent"]["experts"]
    assert len(rows) == 10
    expert = read("experts.search", {"search": "douyin", "limit": 1})["structuredContent"]["experts"][0]
    detail = read("experts.profile", {"slug": expert["slug"]})["structuredContent"]
    assert detail["slug"] == expert["slug"] and detail["prompt"]
    assert read("experts.profile", {"slug": "../"})["isError"]
    assert read("experts.search", {"limit": 101})["isError"]


def test_receipt_tool_is_read_only_and_validates_task_id():
    receipt = next(tool for tool in _tool_catalog() if tool["name"] == "publishing.receipt")
    assert receipt["annotations"]["readOnlyHint"] is True
    response = asyncio.run(_dispatch({"id": 1, "method": "tools/call", "params": {"name": "publishing.receipt", "arguments": {"task_id": "../"}}}))
    assert response["result"]["isError"] is True
