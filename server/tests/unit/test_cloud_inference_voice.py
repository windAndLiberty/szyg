import asyncio
from pathlib import Path

from szyg.integrations.cloud_inference_client import CloudInferenceClient


def test_seed_audio_passes_uploaded_reference_through_gateway(tmp_path, monkeypatch):
    calls = []

    async def fake_request(self, method, path, payload):
        calls.append((path, payload))
        return {"data": {"audio_base64": "YXVkaW8="}}

    monkeypatch.setattr(CloudInferenceClient, "_request", fake_request)
    client = CloudInferenceClient(output_dir=str(tmp_path))
    path, _ = asyncio.run(client.seed_audio_text_to_speech(
        "新台词", voice_id="preset", reference_audio_url="https://media.test/voice.wav",
        output_dir=str(tmp_path),
    ))
    payload = calls[0][1]["payload"]
    assert calls[0][0] == "/api/v1/inference/tts"
    assert payload["reference_audio_url"] == "https://media.test/voice.wav"
    assert payload["input"] == "新台词"
    assert "voice" not in payload
    assert Path(path).read_bytes() == b"audio"
