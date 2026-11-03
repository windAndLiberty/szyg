import asyncio

import pytest
from fastapi import HTTPException

from szyg.api import hermes_native_routes as routes


def test_openclaw_runtime_token_fails_closed(monkeypatch):
    monkeypatch.delenv("SZYG_OPENCLAW_MODEL_TOKEN", raising=False)
    with pytest.raises(HTTPException) as missing:
        routes._verify_openclaw_runtime("anything")
    assert missing.value.status_code == 401

    monkeypatch.setenv("SZYG_OPENCLAW_MODEL_TOKEN", "expected-token")
    with pytest.raises(HTTPException) as wrong:
        routes._verify_openclaw_runtime("wrong-token")
    assert wrong.value.status_code == 401
    routes._verify_openclaw_runtime("expected-token")


def test_openclaw_proxy_uses_managed_inference(monkeypatch):
    monkeypatch.setenv("SZYG_OPENCLAW_MODEL_TOKEN", "expected-token")
    observed = {}

    async def fake_request(_self, method, path, payload):
        observed.update(method=method, path=path, payload=payload)
        return {
            "data": {
                "id": "managed-response",
                "choices": [{
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }],
                "usage": {"total_tokens": 3},
            }
        }

    monkeypatch.setattr(routes.CloudInferenceClient, "_request", fake_request)
    response = asyncio.run(routes.openclaw_chat(
        {"model": "text.reasoning", "messages": [{"role": "user", "content": "ping"}], "stream": False},
        authorization="Bearer expected-token",
    ))
    assert response.status_code == 200
    assert observed["method"] == "POST"
    assert observed["path"] == "/api/v1/inference/chat"
    assert observed["payload"]["capability"] == "text.reasoning"


def test_openclaw_proxy_fast_model_overrides_disabled_reasoning_metadata(monkeypatch):
    monkeypatch.setenv("SZYG_OPENCLAW_MODEL_TOKEN", "expected-token")
    observed = {}

    async def fake_request(_self, _method, _path, payload):
        observed.update(payload=payload)
        return {
            "data": {
                "id": "managed-fast-response",
                "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 3},
            }
        }

    monkeypatch.setattr(routes.CloudInferenceClient, "_request", fake_request)
    response = asyncio.run(routes.openclaw_chat(
        {
            "model": "text.fast",
            "reasoning_effort": "off",
            "messages": [{"role": "user", "content": "ping"}],
            "stream": False,
        },
        authorization="Bearer expected-token",
    ))
    assert response.status_code == 200
    assert observed["payload"]["capability"] == "text.fast"


def test_openclaw_stream_has_finite_sse_terminal_boundary(monkeypatch):
    monkeypatch.setenv("SZYG_OPENCLAW_MODEL_TOKEN", "expected-token")

    async def fake_request(_self, _method, _path, _payload):
        return {
            "data": {
                "id": "managed-stream-response",
                "choices": [{
                    "message": {"role": "assistant", "content": "stream ok"},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 2, "completion_tokens": 2, "total_tokens": 4},
            }
        }

    monkeypatch.setattr(routes.CloudInferenceClient, "_request", fake_request)
    response = asyncio.run(routes.openclaw_chat(
        {"model": "text.reasoning", "messages": [{"role": "user", "content": "ping"}], "stream": True},
        authorization="Bearer expected-token",
    ))
    body = response.body.decode("utf-8")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert int(response.headers["content-length"]) == len(response.body)
    assert '"finish_reason": "stop"' in body
    assert body.endswith("data: [DONE]\n\n")
