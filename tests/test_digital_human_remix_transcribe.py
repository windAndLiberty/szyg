import pytest

from szyg.digital_human_service import _remix_transcribe
from szyg.integrations.cloud_inference_client import CloudInferenceError


class StubClient:
    def __init__(
        self,
        asr_result: dict | None = None,
        asr_error: Exception | None = None,
        vision_text: str = "",
    ) -> None:
        self.asr_result = asr_result or {}
        self.asr_error = asr_error
        self.vision_text = vision_text
        self.asr_kwargs: dict = {}
        self.vision_calls: list[list[dict]] = []

    async def asr_transcribe(self, audio_url: str, **kwargs) -> dict:
        self.asr_kwargs = kwargs
        if self.asr_error is not None:
            raise self.asr_error
        return self.asr_result

    async def responses_text(self, input_items: list[dict], **kwargs) -> dict:
        self.vision_calls.append(input_items)
        return {"message": {"role": "assistant", "content": self.vision_text}}


@pytest.mark.asyncio
async def test_remix_transcribe_lets_asr_autodetect_language():
    client = StubClient(asr_result={"text": "  Hello and welcome.  ", "utterances": [], "duration_ms": 1200})

    text = await _remix_transcribe(client, "https://example.com/audio.wav")

    assert text == "Hello and welcome."
    # 关键回归点：不再强制 zh-CN，留空让大模型 ASR 自动识别中英文
    assert client.asr_kwargs.get("language") == ""
    assert client.vision_calls == []


@pytest.mark.asyncio
async def test_remix_transcribe_falls_back_when_asr_returns_empty():
    client = StubClient(asr_result={"text": "", "utterances": [], "duration_ms": 0}, vision_text="Hello world")

    text = await _remix_transcribe(client, "https://example.com/audio.wav")

    assert text == "Hello world"
    assert len(client.vision_calls) == 1


@pytest.mark.asyncio
async def test_remix_transcribe_falls_back_on_any_asr_error():
    client = StubClient(
        asr_error=CloudInferenceError("未检测到人声", status_code=400),
        vision_text="Spoken line",
    )

    text = await _remix_transcribe(client, "https://example.com/audio.wav")

    assert text == "Spoken line"


@pytest.mark.asyncio
async def test_remix_transcribe_returns_empty_when_all_paths_fail():
    class FailingClient(StubClient):
        async def responses_text(self, input_items: list[dict], **kwargs) -> dict:
            raise RuntimeError("vision unavailable")

    client = FailingClient(asr_error=CloudInferenceError("能力未开放", status_code=403))

    text = await _remix_transcribe(client, "https://example.com/audio.wav")

    assert text == ""
