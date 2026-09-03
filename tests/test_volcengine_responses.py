import pytest

import szyg.integrations.volcengine_client as volcengine


@pytest.mark.asyncio
async def test_responses_api_uses_nested_reasoning_payload(tmp_path, monkeypatch):
    captured = {}

    class FakeResponse:
        is_error = False

        def json(self):
            return {
                "model": "doubao-seed-2-0-lite-260428",
                "output": [{"content": [{"type": "output_text", "text": '{"ok":true}'}]}],
                "usage": {},
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, headers, json):
            captured["payload"] = json
            return FakeResponse()

    monkeypatch.setattr(volcengine.httpx, "AsyncClient", FakeAsyncClient)
    client = volcengine.VolcEngineClient(api_key="test-key", output_dir=str(tmp_path))

    result = await client.responses_text(
        [{"role": "user", "content": [{"type": "input_text", "text": "test"}]}],
        model="doubao-seed-2-0-lite-260428",
        reasoning_effort="minimal",
    )

    assert result["message"]["content"] == '{"ok":true}'
    assert captured["payload"]["reasoning"] == {"effort": "minimal"}
    assert "reasoning_effort" not in captured["payload"]
