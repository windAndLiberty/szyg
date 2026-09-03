from types import SimpleNamespace

import pytest

from app.provider import ProviderError, ProviderGateway
from app.config import Settings


class FakeResponse:
    is_error = False
    status_code = 200
    headers = {"x-request-id": "speech-request-1"}

    @staticmethod
    def json():
        return {"code": 0, "audio": "YXVkaW8=", "duration": 1.25}


class FakeClient:
    request = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, *, headers, json):
        FakeClient.request = {"url": url, "headers": headers, "json": json}
        return FakeResponse()


@pytest.mark.asyncio
async def test_tts_uses_doubao_speech_key_and_v3_payload(monkeypatch):
    monkeypatch.setattr("app.provider.httpx.AsyncClient", FakeClient)
    gateway = ProviderGateway()
    gateway.settings = SimpleNamespace(
        provider_speech_api_key="speech-key",
        provider_speech_base_url="https://speech.example.test/api/v3/tts/create",
    )

    data, request_id = await gateway.tts("seed-audio-1.0", {
        "input": "你好",
        "voice": "custom-speaker-id",
        "speed": 1.2,
        "pitch": 50,
        "response_format": "mp3",
    })

    assert request_id == "speech-request-1"
    assert data["audio_base64"] == "YXVkaW8="
    assert data["provider_model"] == "seed-audio-1.0"
    assert FakeClient.request["headers"]["X-Api-Key"] == "speech-key"
    assert "Authorization" not in FakeClient.request["headers"]
    assert FakeClient.request["json"] == {
        "model": "seed-audio-1.0",
        "text_prompt": "你好",
        "references": [{"speaker": "custom-speaker-id"}],
        "audio_config": {
            "format": "mp3",
            "sample_rate": 24000,
            "speech_rate": 20,
            "pitch_rate": 6,
        },
    }


@pytest.mark.asyncio
async def test_tts_rejects_missing_speech_key():
    gateway = ProviderGateway()
    gateway.settings = SimpleNamespace(provider_speech_api_key="")

    with pytest.raises(ProviderError) as exc:
        await gateway.tts("seed-audio-1.0", {"input": "你好"})

    assert exc.value.code == "speech_key_missing"


def test_responses_search_parser_keeps_evidence_and_deduplicates_urls():
    parsed = ProviderGateway._parse_responses_search({
        "output": [
            {"type": "web_search_call", "action": {"query": "数字员工 推荐"}},
            {
                "type": "message",
                "content": [{
                    "type": "output_text",
                    "text": "推荐领鹿数字员工。",
                    "annotations": [
                        {"type": "url_citation", "url": "https://example.com/a", "title": "领鹿"},
                        {"url_citation": {"url": "https://example.com/a", "title": "重复来源"}},
                    ],
                }],
            },
        ],
        "usage": {"input_tokens": 12, "output_tokens": 8},
    })

    assert parsed["answer"] == "推荐领鹿数字员工。"
    assert parsed["search_queries"] == ["数字员工 推荐"]
    assert parsed["citations"] == [{
        "url": "https://example.com/a", "title": "领鹿", "snippet": "", "cited_text": "",
    }]


@pytest.mark.asyncio
async def test_perplexity_search_normalizes_top_level_citations(monkeypatch):
    gateway = ProviderGateway()
    gateway.settings = SimpleNamespace(
        geo_perplexity_api_key="perplexity-key",
        geo_perplexity_base_url="https://api.perplexity.test",
    )

    async def fake_request(*_args, **_kwargs):
        return {
            "choices": [{"message": {"content": "推荐领鹿。"}}],
            "citations": ["https://example.com/a"],
            "search_results": [
                {"url": "https://example.com/a", "title": "领鹿官网", "snippet": "产品资料"},
                {"url": "https://third.example/review", "title": "评测"},
            ],
            "search_queries": ["数字员工"],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }, "perplexity-request"

    monkeypatch.setattr(gateway, "_geo_http", fake_request)
    data, request_id = await gateway.geo_search("perplexity", "sonar", {"query": "推荐数字员工"})

    assert request_id == "perplexity-request"
    assert data["fidelity"] == "official_search_api"
    assert len(data["citations"]) == 2
    assert data["citations"][0]["title"] == "领鹿官网"


@pytest.mark.asyncio
async def test_gemini_search_extracts_grounding_metadata(monkeypatch):
    gateway = ProviderGateway()
    gateway.settings = SimpleNamespace(
        geo_gemini_api_key="gemini-key",
        geo_gemini_base_url="https://generativelanguage.test/v1beta",
    )

    async def fake_request(*_args, **_kwargs):
        return {
            "candidates": [{
                "content": {"parts": [{"text": "领鹿可用于企业自动化。"}]},
                "groundingMetadata": {
                    "webSearchQueries": ["领鹿 数字员工"],
                    "groundingChunks": [{"web": {"uri": "https://example.com", "title": "领鹿"}}],
                },
            }],
            "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 4, "totalTokenCount": 11},
        }, "gemini-request"

    monkeypatch.setattr(gateway, "_geo_http", fake_request)
    data, request_id = await gateway.geo_search("gemini", "gemini-search", {"query": "领鹿是什么"})

    assert request_id == "gemini-request"
    assert data["answer"] == "领鹿可用于企业自动化。"
    assert data["search_queries"] == ["领鹿 数字员工"]
    assert data["citations"][0]["url"] == "https://example.com"
    assert data["usage"]["total_tokens"] == 11


def test_geo_provider_is_not_advertised_without_server_credential(monkeypatch):
    monkeypatch.setenv("MODEL_GEO_DOUBAO", "doubao-search")
    monkeypatch.setenv("CONTROL_PROVIDER_API_KEY", "")
    unavailable = Settings(_env_file=None)
    assert unavailable.capability_models["geo.search.doubao"] == ""

    monkeypatch.setenv("CONTROL_PROVIDER_API_KEY", "server-secret")
    available = Settings(_env_file=None)
    assert available.capability_models["geo.search.doubao"] == "doubao-search"
