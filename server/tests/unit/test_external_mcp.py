from fastapi import FastAPI
from fastapi.testclient import TestClient

from szyg.api.external_mcp_routes import CONNECTIONS, ENDPOINT, router
from szyg.cloud_auth import cloud_auth


def test_desktop_grant_scope_and_revocation(tmp_path, monkeypatch):
    monkeypatch.setenv("SZYG_DESKTOP_TOKEN", "desktop")
    monkeypatch.setenv("SZYG_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(cloud_auth, "_access_token", "session")
    monkeypatch.setattr(cloud_auth, "_access_expires_at", 2**40)
    monkeypatch.setattr(cloud_auth, "_profile", {"user": {"id": "owner"}})
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 1234))
    desktop = {"X-SZYG-Desktop-Token": "desktop"}
    grant = {"name": "Research", "tools": ["knowledge.stats"]}
    assert client.post(CONNECTIONS, json=grant).status_code == 403
    assert client.post(CONNECTIONS, json=grant, headers=desktop | {"Origin": "https://example.org"}).status_code == 403
    assert client.post(CONNECTIONS, json=grant | {"tools": ["publishing.video"]}, headers=desktop).status_code == 422
    created = client.post(CONNECTIONS, json=grant, headers=desktop)
    assert created.status_code == 201
    key = created.json()["id"]
    token = created.json()["token"]
    assert token not in client.get(CONNECTIONS, headers=desktop).text
    bearer = {"Authorization": f"Bearer {token}"}
    call = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    assert client.post(ENDPOINT, headers=desktop, json=call).status_code == 401
    assert client.post(ENDPOINT, headers=bearer | {"Origin": "null"}, json=call).status_code == 403
    tools = client.post(ENDPOINT, headers=bearer, json=call).json()["result"]["tools"]
    assert [t["name"] for t in tools] == ["knowledge_stats"]
    denied = call | {"method": "tools/call", "params": {"name": "knowledge_ingest", "arguments": {"confirmed": True}}}
    assert "error" in client.post(ENDPOINT, headers=bearer, json=denied).json()
    assert client.get(CONNECTIONS, headers=bearer).status_code == 403
    assert client.post(ENDPOINT, headers=bearer, json={"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code == 202
    monkeypatch.setattr(cloud_auth, "_profile", {"user": {"id": "other"}})
    assert client.get(CONNECTIONS, headers=desktop).json()["connections"] == []
    assert client.post(ENDPOINT, headers=bearer, json=call).status_code == 401
    monkeypatch.setattr(cloud_auth, "_profile", {"user": {"id": "owner"}})
    assert client.delete(CONNECTIONS + "/" + key, headers=desktop).status_code == 204
    assert client.post(ENDPOINT, headers=bearer, json=call).status_code == 401
