import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from szyg.api import hermes_native_routes as routes
from szyg.integrations import cloud_inference_client


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


@pytest.mark.parametrize("model_id", [
    "doubao-seed-evolving", "deepseek-v4-1-flash-economy-261017", "kimi-k3-1-pro-261024",
])
@pytest.mark.parametrize("stream", [False, True])
def test_employee_model_round_trip(monkeypatch, model_id, stream):
    monkeypatch.setenv("SZYG_OPENCLAW_MODEL_TOKEN", "test-token")
    observed = []

    async def managed_request(_self, _method, _path, payload):
        observed.append(payload)
        return {"routed_model": model_id, "data": {
            "choices": [{"message": {"content": "ok", "reasoning_content": "sample thinking"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
        }}
    monkeypatch.setattr(routes.CloudInferenceClient, "_request", managed_request)
    response = asyncio.run(routes.openclaw_chat({
        "model": "xiaoyu-managed/" + model_id, "temperature": 0.6,
        "messages": [{"role": "user", "content": "sample"}], "stream": stream,
    }, authorization="Bearer test-token"))
    assert len(observed) == 1 and observed[0]["capability"] == "text.employee." + model_id
    assert "temperature" not in observed[0]["payload"]
    if model_id == "kimi-k3-1-pro-261024":
        assert "thinking" not in observed[0]["payload"]
    else:
        assert observed[0]["payload"]["thinking"] == {"type": "disabled"}
    assert model_id.encode() in response.body and b"sample thinking" in response.body


def test_employee_model_must_match_receipt(monkeypatch):
    monkeypatch.setenv("SZYG_OPENCLAW_MODEL_TOKEN", "test-token")
    async def managed_request(*_args):
        return {"routed_model": "text.fast", "data": {"choices": []}}
    monkeypatch.setattr(routes.CloudInferenceClient, "_request", managed_request)
    for model_id, status in [("doubao-seed-evolving", 502), ("not-an-employee-model", 400)]:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(routes.openclaw_chat({"model": model_id}, authorization="Bearer test-token"))
        assert exc.value.status_code == status


@pytest.mark.parametrize(("status", "detail", "expected_status", "expected_message"), [
    (400, "能力类型与接口不匹配", 400, "请在对话中选择自动模型后重试"),
    (503, "上游推理暂不可用", 503, "所选模型暂不可用"),
])
def test_employee_model_proxy_preserves_retryability(
    monkeypatch, status, detail, expected_status, expected_message,
):
    monkeypatch.setenv("SZYG_OPENCLAW_MODEL_TOKEN", "test-token")
    monkeypatch.setattr(cloud_inference_client, "cloud_auth", SimpleNamespace(
        access_token=lambda: "account-token",
        config={"control_url": "https://example.test", "app_version": "test"},
    ))
    observed = []

    async def managed_request(self, method, url, *, headers, json):
        observed.append((method, url, json["capability"]))
        return httpx.Response(status, json={"detail": detail})

    monkeypatch.setattr(httpx.AsyncClient, "request", managed_request)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(routes.openclaw_chat(
            {"model": "doubao-seed-evolving", "stream": True},
            authorization="Bearer test-token",
        ))

    assert exc.value.status_code == expected_status
    assert expected_message in exc.value.detail
    assert observed == [("POST", "https://example.test/api/v1/inference/chat", "text.employee.doubao-seed-evolving")]


def test_employee_model_catalog_distinguishes_gateway_and_account_status():
    from szyg.employee_models import employee_model_catalog
    old = employee_model_catalog({"items": [{"alias": "text.employee.doubao-seed-evolving", "available": True}]})
    assert {item["status"] for item in old["items"]} == {"gateway_upgrade_required"}
    assert {item["status"] for item in employee_model_catalog(None)["items"]} == {"unknown"}
    current = employee_model_catalog({"employee_models_version": 1, "items": [
        {"alias": "text.employee.doubao-seed-evolving", "available": True},
        {"alias": "text.employee.kimi-k3-1-pro-261024", "available": False},
    ]})
    assert [item["available"] for item in current["items"]] == [True, False, False]
    assert current["items"][1]["pricing"]["peak"]["output"] == 6.4
