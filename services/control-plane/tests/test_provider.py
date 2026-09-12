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


@pytest.mark.asyncio
async def test_tts_uploaded_audio_overrides_preset_voice(monkeypatch):
    monkeypatch.setattr("app.provider.httpx.AsyncClient", FakeClient)
    gateway = ProviderGateway()
    gateway.settings = SimpleNamespace(provider_speech_api_key="key", provider_speech_base_url="https://speech.test/tts")
    await gateway.tts("seed-audio-1.0", {
        "input": "今天介绍新产品。", "voice": "preset-speaker",
        "reference_audio_url": "https://media.test/profile-voice.wav",
    })
    body = FakeClient.request["json"]
    assert body["references"] == [{"audio_url": "https://media.test/profile-voice.wav"}]
    assert "@音频1" in body["text_prompt"]
    assert body["text_prompt"].endswith("今天介绍新产品。")


@pytest.mark.asyncio
async def test_tts_invalid_voice_reference_does_not_fall_back(monkeypatch):
    monkeypatch.setattr("app.provider.httpx.AsyncClient", FakeClient)
    FakeClient.request = None
    gateway = ProviderGateway()
    gateway.settings = SimpleNamespace(provider_speech_api_key="key")
    with pytest.raises(ProviderError, match="声音参考"):
        await gateway.tts("seed-audio-1.0", {"input": "你好", "reference_audio_url": "file:///voice.wav"})
    assert FakeClient.request is None


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


# ═══════════════════════════════════════════════════════════════════════
# OmniHuman1.5（视觉 CV 平台）
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_omni_human_submit_signs_request_and_returns_task_id(monkeypatch):
    gateway = ProviderGateway()
    gateway.settings = SimpleNamespace(
        provider_cv_access_key="cv-ak",
        provider_cv_secret_key="cv-sk",
        provider_cv_base_url="https://visual.volcengineapi.com",
        provider_cv_region="cn-north-1",
    )

    captured = {}

    async def fake_post(url, headers=None, content=None):
        captured["url"] = url
        captured["headers"] = dict(headers or {})
        captured["body"] = content
        resp = FakeResponse()
        resp.is_error = False
        resp.status_code = 200
        resp.headers = {"x-request-id": "omni-submit-1"}
        resp.json = staticmethod(lambda: {
            "code": 10000,
            "data": {"task_id": "omni-task-999"},
            "request_id": "omni-submit-1",
        })
        return resp

    class _Ctx:
        def __init__(self, *a, **kw): self.post = fake_post
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None

    monkeypatch.setattr("app.provider.httpx.AsyncClient", _Ctx)

    data, request_id = await gateway.omni_human_submit(
        "jimeng_realman_avatar_picture_omni_v15",
        {
            "image_url": "https://example.com/avatar.png",
            "audio_url": "https://example.com/speech.mp3",
            "output_resolution": 720,
            "duration": 4,
        },
    )

    assert data["task_id"] == "omni-task-999"
    assert request_id == "omni-submit-1"
    # 鉴权 header 必须由 V4 签名生成
    assert "Authorization" in captured["headers"]
    # URL 必须含 Action=CVSubmitTask&Version=2022-08-31
    assert "Action=CVSubmitTask" in captured["url"]
    assert "Version=2022-08-31" in captured["url"]
    # body 含 req_key + 业务字段
    import json as _json
    body = _json.loads(captured["body"])
    assert body["req_key"] == "jimeng_realman_avatar_picture_omni_v15"
    assert body["image_url"] == "https://example.com/avatar.png"
    assert body["audio_url"] == "https://example.com/speech.mp3"
    assert body["duration"] == 4


@pytest.mark.asyncio
async def test_omni_human_get_parses_status_and_video_url(monkeypatch):
    gateway = ProviderGateway()
    gateway.settings = SimpleNamespace(
        provider_cv_access_key="cv-ak",
        provider_cv_secret_key="cv-sk",
        provider_cv_base_url="https://visual.volcengineapi.com",
        provider_cv_region="cn-north-1",
    )

    captured = {}

    async def fake_post(url, headers=None, content=None):
        captured["url"] = url
        resp = FakeResponse()
        resp.headers = {"x-request-id": "omni-get-1"}
        resp.json = staticmethod(lambda: {
            "code": 10000,
            "data": {"status": "done", "video_url": "https://example.com/omni-out.mp4", "aigc_meta_tagged": True},
            "request_id": "omni-get-1",
        })
        return resp

    class _Ctx:
        def __init__(self, *a, **kw): self.post = fake_post
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None

    monkeypatch.setattr("app.provider.httpx.AsyncClient", _Ctx)

    data, _ = await gateway.omni_human_get("omni-task-999")
    assert data["status"] == "done"
    assert data["video_url"] == "https://example.com/omni-out.mp4"
    assert data["aigc_meta_tagged"] is True
    assert "Action=CVGetResult" in captured["url"]


@pytest.mark.asyncio
async def test_omni_human_submit_raises_when_cv_credentials_missing():
    gateway = ProviderGateway()
    gateway.settings = SimpleNamespace(
        provider_cv_access_key="",
        provider_cv_secret_key="",
        provider_cv_base_url="https://visual.volcengineapi.com",
        provider_cv_region="cn-north-1",
    )
    with pytest.raises(ProviderError) as exc:
        await gateway.omni_human_submit("jimeng_realman_avatar_picture_omni_v15", {"image_url": "x", "audio_url": "y"})
    assert exc.value.status_code == 503
    assert "cv_credentials_missing" in exc.value.code


@pytest.mark.asyncio
async def test_subject_detection_parses_mask_urls(monkeypatch):
    gateway = ProviderGateway()
    gateway.settings = SimpleNamespace(
        provider_cv_access_key="cv-ak",
        provider_cv_secret_key="cv-sk",
        provider_cv_base_url="https://visual.volcengineapi.com",
        provider_cv_region="cn-north-1",
    )

    async def fake_post(url, headers=None, content=None):
        resp = FakeResponse()
        resp.headers = {"x-request-id": "subj-1"}
        resp.json = staticmethod(lambda: {
            "code": 10000,
            "data": {
                "resp_data": '{"code":0,"object_detection_result":{"mask":{"url":["https://example.com/m1.png","https://example.com/m2.png"]}},"status":1}',
            },
            "request_id": "subj-1",
        })
        return resp

    class _Ctx:
        def __init__(self, *a, **kw): self.post = fake_post
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None

    monkeypatch.setattr("app.provider.httpx.AsyncClient", _Ctx)

    data, _ = await gateway.subject_detection("jimeng_realman_avatar_object_detection", "https://example.com/avatar.png")
    assert data["status"] == 1
    assert data["mask_urls"] == ["https://example.com/m1.png", "https://example.com/m2.png"]


# ═══════════════════════════════════════════════════════════════════════
# 录音文件识别 ASR（火山大模型）
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_asr_transcribe_submits_polls_and_returns_text(monkeypatch):
    gateway = ProviderGateway()
    gateway.settings = SimpleNamespace(
        provider_asr_app_key="asr-app-key",
        provider_asr_resource_id="volc.seedasr.auc",
        provider_asr_base_url="https://openspeech.bytedance.com",
    )

    submits = []
    queries = []

    def make_post(url):
        if "submit" in url:
            async def post(headers=None, json=None, content=None):
                submits.append({"url": url, "headers": dict(headers or {}), "body": json})
                resp = FakeResponse()
                resp.headers = {"X-Api-Status-Code": "20000000", "X-Api-Message": "OK", "x-request-id": "asr-1"}
                resp.json = staticmethod(lambda: {})
                return resp
        else:
            async def post(headers=None, json=None, content=None):
                queries.append({"url": url, "headers": dict(headers or {}), "body": content})
                resp = FakeResponse()
                resp.headers = {"X-Api-Status-Code": "20000000", "X-Api-Message": "OK"}
                resp.json = staticmethod(lambda: {
                    "audio_info": {"duration": 5230},
                    "result": {
                        "text": "这是字节跳动，今日头条母公司。",
                        "utterances": [
                            {"text": "这是字节跳动，", "start_time": 0, "end_time": 1705},
                        ],
                    },
                })
                return resp
        return post

    class _Ctx:
        def __init__(self, *a, **kw): self.post = make_post(kw.get("__url__", ""))
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None

    def factory(*a, **kw):
        ctx = _Ctx(*a, **kw)
        # 重写 post 动态分派到 submit/query
        async def dispatch_post(url, headers=None, json=None, content=None):
            if "submit" in url:
                submits.append({"url": url, "headers": dict(headers or {}), "body": json})
                resp = FakeResponse()
                resp.headers = {"X-Api-Status-Code": "20000000", "X-Api-Message": "OK", "x-request-id": "asr-1"}
                resp.json = staticmethod(lambda: {})
                return resp
            else:
                queries.append({"url": url, "headers": dict(headers or {}), "body": content})
                resp = FakeResponse()
                resp.headers = {"X-Api-Status-Code": "20000000", "X-Api-Message": "OK"}
                resp.json = staticmethod(lambda: {
                    "audio_info": {"duration": 5230},
                    "result": {
                        "text": "这是字节跳动，今日头条母公司。",
                        "utterances": [
                            {"text": "这是字节跳动，", "start_time": 0, "end_time": 1705},
                        ],
                    },
                })
                return resp
        ctx.post = dispatch_post
        return ctx

    monkeypatch.setattr("app.provider.httpx.AsyncClient", factory)
    # sleep 已被 my asr_transcribe 显式 import 成 `asyncio.sleep`，所以需要 patch 整个 asyncio 模块。
    import asyncio as _asyncio
    real_sleep = _asyncio.sleep
    monkeypatch.setattr(_asyncio, "sleep", lambda *_: real_sleep(0))

    data, request_id = await gateway.asr_transcribe(
        "volc.seedasr.auc",
        {"audio_url": "https://example.com/speech.mp3", "format": "mp3", "language": "zh-CN"},
        max_poll_seconds=5,
    )

    assert data["text"] == "这是字节跳动，今日头条母公司。"
    assert data["duration_ms"] == 5230
    assert len(data["utterances"]) == 1
    assert submits, "ASR submit should have been called"
    assert queries, "ASR query should have been called"
    # 鉴权 header 必须是 X-Api-Key + X-Api-Resource-Id
    assert submits[0]["headers"]["X-Api-Key"] == "asr-app-key"
    assert submits[0]["headers"]["X-Api-Resource-Id"] == "volc.seedasr.auc"


@pytest.mark.asyncio
async def test_asr_transcribe_raises_when_credentials_missing():
    gateway = ProviderGateway()
    gateway.settings = SimpleNamespace(
        provider_asr_app_key="",
        provider_asr_resource_id="volc.seedasr.auc",
        provider_asr_base_url="https://openspeech.bytedance.com",
    )
    with pytest.raises(ProviderError) as exc:
        await gateway.asr_transcribe("volc.seedasr.auc", {"audio_url": "x", "format": "mp3"})
    assert exc.value.status_code == 503
    assert "asr_credentials_missing" in exc.value.code


@pytest.mark.asyncio
async def test_asr_transcribe_rejects_invalid_format():
    gateway = ProviderGateway()
    gateway.settings = SimpleNamespace(
        provider_asr_app_key="asr-key",
        provider_asr_resource_id="volc.seedasr.auc",
        provider_asr_base_url="https://openspeech.bytedance.com",
    )
    with pytest.raises(ProviderError) as exc:
        await gateway.asr_transcribe("volc.seedasr.auc", {"audio_url": "x", "format": "flac"})
    assert exc.value.status_code == 400
    assert "invalid_audio_format" in exc.value.code
