from __future__ import annotations

import httpx
import pytest
from types import SimpleNamespace

from szyg.integrations.cloud_inference_client import CloudInferenceClient


@pytest.mark.asyncio
async def test_cloud_inference_refreshes_expired_access_token(monkeypatch, tmp_path):
    tokens: list[tuple[bool, str]] = []

    def access_token(*, force_refresh: bool = False) -> str:
        token = "fresh-token" if force_refresh else "expired-token"
        tokens.append((force_refresh, token))
        return token

    async def request(self, method, url, *, headers=None, json=None):
        del self, method, url, json
        status = 200 if headers == {"Authorization": "Bearer fresh-token"} else 401
        return httpx.Response(status, json={"ok": True}, request=httpx.Request("POST", "https://example.test"))

    monkeypatch.setattr(
        "szyg.integrations.cloud_inference_client.cloud_auth",
        SimpleNamespace(
            access_token=access_token,
            config={
                "enabled": True,
                "control_url": "https://example.test",
                "app_version": "test",
            },
        ),
    )
    monkeypatch.setattr(httpx.AsyncClient, "request", request)

    client = CloudInferenceClient(output_dir=str(tmp_path))
    result = await client._request("POST", "/api/v1/inference/chat", {"payload": {}})

    assert result == {"ok": True}
    assert tokens == [(False, "expired-token"), (True, "fresh-token")]
