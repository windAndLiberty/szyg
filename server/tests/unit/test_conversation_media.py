import asyncio
import io
import shutil
import subprocess
import wave
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from szyg import conversation_media, media_storage
from szyg.api import media_routes
from szyg.api.business_mcp_routes import _dispatch, _tool_catalog


@pytest.fixture
def application(tmp_path, monkeypatch):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg and FFprobe are required to exercise real media validation")

    def output_dir(kind):
        output = tmp_path / kind
        output.mkdir(exist_ok=True)
        return output

    monkeypatch.setattr(media_storage, "get_media_output_dir", output_dir)
    monkeypatch.setattr(conversation_media, "get_media_output_dir", output_dir)
    monkeypatch.setattr(conversation_media, "_get_ffmpeg", lambda: shutil.which("ffmpeg"))
    vision_calls, audio_calls = [], []

    class Provider:
        def __init__(self, **kwargs):
            pass

        async def responses_text(self, messages, **kwargs):
            vision_calls.append(messages)
            return {"message": {"content": "画面中央是蓝色方块。"}}

        async def upload_reference(self, path):
            audio = Path(path)
            assert audio.suffix == ".mp3" and audio.stat().st_size > 100
            audio_calls.append(path)
            return "fixture-asr"

        async def asr_transcribe(self, url, **kwargs):
            assert url == "fixture-asr" and kwargs["audio_format"] == "mp3"
            return {"text": "这是一段测试语音。"}

    monkeypatch.setattr(conversation_media, "CloudInferenceClient", Provider)
    app = FastAPI()
    app.include_router(media_routes.router)
    return app, vision_calls, audio_calls


def upload(client, filename, payload, mime):
    response = client.post("/api/media/conversation-assets", files={"file": (filename, payload, mime)})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["size"] == len(payload)
    assert client.get(data["url"]).content == payload
    return data


def test_local_image_goes_through_mcp_to_the_vision_provider(application, monkeypatch):
    app, vision_calls, audio_calls = application
    img = io.BytesIO()
    Image.new("RGB", (72, 72), (0, 90, 254)).save(img, "PNG")
    with TestClient(app) as client:
        image = upload(client, "square.png", img.getvalue(), "image/png")
        assert image["kind"] == "image" and image["name"] == "square.png"
        assert not vision_calls and not audio_calls

    async_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: async_client(transport=httpx.ASGITransport(app=app), **kwargs))
    catalog = next(item for item in _tool_catalog() if item["name"] == "materials.inspect")
    assert catalog["inputSchema"]["required"] == ["source"]
    result = asyncio.run(_dispatch({"id": 1, "method": "tools/call", "params": {
        "name": "materials.inspect", "arguments": {"source": image["url"], "question": "画面是什么颜色？"},
    }}))["result"]
    assert not result["isError"]
    assert result["structuredContent"]["visual_observation"] == "画面中央是蓝色方块。"
    content = vision_calls[0][0]["content"]
    assert "画面是什么颜色？" in content[0]["text"]
    assert content[1]["type"] == "input_image" and content[1]["image_url"].startswith("data:image/jpeg;base64,")
    assert not audio_calls


def test_speech_is_transcribed_and_temporary_derivative_is_removed(application):
    app, vision_calls, audio_calls = application
    wav = io.BytesIO()
    with wave.open(wav, "wb") as handle:
        handle.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        handle.writeframes(b"\0\0" * 16000)
    with TestClient(app) as client:
        audio = upload(client, "test.wav", wav.getvalue(), "audio/wav")
        assert audio["kind"] == "audio"
        result = client.post("/api/media/conversation-inspect", json={"source": audio["url"]})
        assert result.status_code == 200, result.text
        assert result.json()["speech_transcript"] == "这是一段测试语音。"
        assert result.json()["audio_window_seconds"] == 1
    assert len(audio_calls) == 1 and not Path(audio_calls[0]).exists()
    assert not vision_calls


def test_video_inspection_sends_sampled_frames_and_detects_missing_audio(application, tmp_path):
    app, vision_calls, audio_calls = application
    source = tmp_path / "silent.mp4"
    subprocess.run([shutil.which("ffmpeg"), "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=blue:s=96x96:d=2", "-an", "-c:v", "mpeg4", str(source)], check=True, timeout=10)
    with TestClient(app) as client:
        video = upload(client, source.name, source.read_bytes(), "video/mp4")
        analysis = client.post("/api/media/conversation-inspect", json={"source": video["url"]})
        assert analysis.status_code == 200, analysis.text
        assert analysis.json()["sampled_at_seconds"] == [0.0, 1.0, 1.7]
        assert len([item for item in vision_calls[0][0]["content"] if item["type"] == "input_image"]) == 3
        failed = client.post("/api/media/conversation-inspect", json={"source": video["url"], "focus": "audio"})
        assert failed.status_code == 422 and "音轨" in failed.json()["detail"]
    assert not audio_calls


def test_bad_refs_and_bad_files_do_not_contact_the_provider(application):
    app, vision_calls, audio_calls = application
    with TestClient(app) as client:
        for source in ("https://outside.invalid/photo.jpg", "/etc/hosts", "/api/media/files/image/../photo.jpg", "/api/media/files/audio/picture.jpg"):
            assert client.post("/api/media/conversation-inspect", json={"source": source}).status_code == 400
        assert client.post("/api/media/conversation-inspect", json={"source": "/api/media/files/image/missing.jpg"}).status_code == 404
        assert client.post("/api/media/conversation-assets", files={"file": ("bad.png", b"not an image", "image/png")}).status_code == 422
    assert not vision_calls and not audio_calls
