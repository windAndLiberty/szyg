import io
import wave
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from szyg.api import media_routes


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(media_routes.router)
    with TestClient(app) as http:
        yield http


def recording(frames=3200, rate=16000):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        output.writeframes(b"\x00\x00" * frames)
    return buffer.getvalue()


def test_dictation_returns_editable_text_and_cleans_temporary_audio(client, monkeypatch):
    audio = recording()
    recording_id = str(uuid4())
    upload_paths = []

    async def upload(_self, filename):
        path = Path(filename)
        upload_paths.append(path)
        assert path.read_bytes() == audio
        return "https://audio.test/temporary"

    async def recognize(_self, url, *, audio_format, idempotency_key):
        assert (url, audio_format, idempotency_key) == ("https://audio.test/temporary", "wav", recording_id)
        return {"text": "  准备一份草稿。 "}

    monkeypatch.setattr(media_routes.CloudInferenceClient, "upload_reference", upload)
    monkeypatch.setattr(media_routes.CloudInferenceClient, "asr_transcribe", recognize)
    result = client.post(f"/api/media/dictation/{recording_id}", content=audio, headers={"Content-Type": "audio/wav"})
    assert result.status_code == 200
    assert result.json() == {"text": "准备一份草稿。"}
    assert len(upload_paths) == 1 and not upload_paths[0].exists()


@pytest.mark.parametrize(("content", "mime", "status"), [
    (b"data", "audio/webm", 415),
    (b"data", "audio/wav", 422),
    (recording(frames=0), "audio/wav", 422),
    (recording(rate=44100), "audio/wav", 422),
    (recording()[:-2], "audio/wav", 422),
    (recording(frames=120 * 16000 + 1), "audio/wav", 422),
    (bytes(120 * 32000 + 4097), "audio/wav", 413),
], ids=["wrong-type", "invalid", "empty", "format", "truncated", "too-long", "too-large"])
def test_dictation_rejects_invalid_recordings_without_uploading(client, monkeypatch, content, mime, status):
    async def must_not_upload(*args):
        pytest.fail("Invalid audio was uploaded")

    monkeypatch.setattr(media_routes.CloudInferenceClient, "upload_reference", must_not_upload)
    response = client.post(f"/api/media/dictation/{uuid4()}", content=content, headers={"Content-Type": mime})
    assert response.status_code == status
