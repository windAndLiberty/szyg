import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest

from szyg import digital_human_service as service


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    root = tmp_path / "digital_human"
    monkeypatch.setattr(service, "ROOT", root)
    monkeypatch.setattr(service, "ASSET_DIR", root / "assets")
    monkeypatch.setattr(service, "RENDER_DIR", root / "renders")
    monkeypatch.setattr(service, "FILES", {
        "assets": root / "assets.json",
        "profiles": root / "profiles.json",
        "inspirations": root / "inspirations.json",
        "projects": root / "projects.json",
        "renders": root / "render_jobs.json",
        "remixes": root / "remix_jobs.json",
    })
    monkeypatch.setattr(service, "_owner", lambda: "test-user")
    return root


def _profile(profile_type="virtual", voice_ark_id=""):
    avatar = service.save_asset("avatar.png", "image/png", b"image", "avatar_reference")
    voice = service.save_asset("voice.mp3", "audio/mpeg", b"audio", "voice_reference")
    payload = {
        "name": "测试数字人",
        "profile_type": profile_type,
        "avatar_asset_ids": [avatar["id"]],
        "voice_asset_id": voice["id"],
        "cover_asset_id": avatar["id"],
    }
    if voice_ark_id:
        payload["voice_ark_id"] = voice_ark_id
    return service.save_profile(payload)


def _has_ffmpeg() -> bool:
    return bool(shutil.which("ffmpeg"))


def _has_ffprobe() -> bool:
    return bool(shutil.which("ffprobe"))


def _make_video(tmp_path, name="source.mp4", duration=5) -> Path:
    target = tmp_path / name
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        subprocess.run([
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=320x240:rate=30",
            "-f", "lavfi", "-i", f"sine=frequency=1000:duration={duration}",
            "-pix_fmt", "yuv420p", str(target),
        ], check=True, capture_output=True, timeout=60)
    else:
        target.write_bytes(b"fake-video")
    return target


def test_create_remix_rejects_real_profile(isolated_store):
    profile = _profile("real")
    source = service.save_asset("source.mp4", "video/mp4", b"video", "inspiration_reference")
    with pytest.raises(ValueError, match="仅支持虚拟人物"):
        asyncio.run(service.create_remix(profile["id"], source["id"]))


def test_create_remix_rejects_profile_without_voice(isolated_store):
    avatar = service.save_asset("avatar.png", "image/png", b"image", "avatar_reference")
    profile = service.save_profile({
        "name": "无声数字人",
        "profile_type": "virtual",
        "avatar_asset_ids": [avatar["id"]],
        "voice_asset_id": "",
    })
    source = service.save_asset("source.mp4", "video/mp4", b"video", "inspiration_reference")
    with pytest.raises(ValueError, match="没有可用声音"):
        asyncio.run(service.create_remix(profile["id"], source["id"]))


def test_voice_reference_uses_profile_upload_even_with_preset(isolated_store, tmp_path, monkeypatch):
    profile = _profile(voice_ark_id="custom_voice_id")
    source = service.get_asset(profile["voice_asset_id"])["path"]
    calls = []

    def fake_extract(input_path, output_path, **kwargs):
        calls.append((input_path, kwargs))
        Path(output_path).write_bytes(b"wav" * 100)

    monkeypatch.setattr(service, "extract_audio", fake_extract)
    reference = service._remix_prepare_voice_reference(profile, tmp_path)
    assert reference.is_file()
    assert calls == [(source, {"sample_rate": 24000, "channels": 1, "max_duration": 20})]


def test_voice_reference_missing_file_fails_instead_of_using_default(isolated_store, tmp_path):
    profile = _profile()
    Path(service.get_asset(profile["voice_asset_id"])["path"]).unlink()
    with pytest.raises(ValueError, match="声音"):
        service._remix_prepare_voice_reference(profile, tmp_path)


def test_remix_sends_profile_voice_reference_to_tts(isolated_store, monkeypatch):
    profile = _profile(voice_ark_id="ignored-preset")
    source = service.save_asset("source.mp4", "video/mp4", b"source-video", "inspiration_reference")
    service._upsert("remixes", {"id": "remix_voice", "owner_id": "test-user", "profile_id": profile["id"], "source_asset_id": source["id"]})
    uploads, extracted, spoken = [], [], []

    def fake_extract(input_path, output_path, **kwargs):
        extracted.append(input_path)
        Path(output_path).write_bytes(b"wav" * 100)

    async def fake_upload(self, path):
        uploads.append(path)
        return "https://media.test/" + Path(path).name

    async def fake_asr(self, url, **kwargs):
        return {"text": "新的台词"}

    async def fake_tts(self, text, **kwargs):
        spoken.append((text, kwargs))
        path = Path(kwargs["output_dir"]) / kwargs["output_name"]
        path.write_bytes(b"generated-audio")
        return str(path), 99.0

    async def fake_omni(self, **kwargs):
        return {"task_id": "omni-1", "status": "queued"}

    async def fake_poll(self, task_id):
        raise service.CloudInferenceError("provider still processing", status_code=502)

    monkeypatch.setattr(service, "extract_audio", fake_extract)
    monkeypatch.setattr(service, "_remix_probe_duration", lambda path: 5.0)
    monkeypatch.setattr(service.CloudInferenceClient, "upload_reference", fake_upload)
    monkeypatch.setattr(service.CloudInferenceClient, "asr_transcribe", fake_asr)
    monkeypatch.setattr(service.CloudInferenceClient, "seed_audio_text_to_speech", fake_tts)
    monkeypatch.setattr(service.CloudInferenceClient, "omni_human_image_audio_drive", fake_omni)
    monkeypatch.setattr(service.CloudInferenceClient, "get_omni_task", fake_poll)
    monkeypatch.setattr(service, "cut_video", lambda src, start, duration, out: Path(out).write_bytes(b"chunk"))
    asyncio.run(service._remix_pipeline("remix_voice"))
    job = service.get_remix("remix_voice")
    assert job["status"] == "rendering", job.get("error")
    assert job["tts_duration"] == 5.0
    assert service.get_asset(profile["voice_asset_id"])["path"] in extracted
    assert any(Path(path).name == "voice_reference.wav" for path in uploads)
    assert spoken[0][0] == "新的台词"
    assert spoken[0][1]["reference_audio_url"] == "https://media.test/voice_reference.wav"
    assert "voice_id" not in spoken[0][1]


@pytest.mark.skipif(not _has_ffprobe(), reason="ffprobe not installed")
def test_probe_duration_reads_valid_video(isolated_store, tmp_path):
    video = _make_video(tmp_path, "source.mp4")
    duration = service._remix_probe_duration(str(video))
    assert duration >= 4.5


@pytest.mark.skipif(not _has_ffmpeg(), reason="ffmpeg not installed")
def test_extract_audio_creates_wav(isolated_store, tmp_path):
    video = _make_video(tmp_path, "source.mp4")
    output = tmp_path / "source.wav"
    service._remix_extract_audio_ffmpeg(video, output)
    assert output.exists()
    assert output.stat().st_size > 0


def test_remix_job_creation_and_persistence(isolated_store, tmp_path, monkeypatch):
    profile = _profile()
    video = _make_video(tmp_path, "source.mp4")
    source = service.save_asset_file(video, "source.mp4", "video/mp4", "inspiration_reference")

    # Mock the probe so create_remix validation passes.
    monkeypatch.setattr(service, "_remix_probe_duration", lambda path: 5.0)
    # Prevent the background pipeline from running in this test.
    monkeypatch.setattr(service, "_remix_pipeline", lambda remix_id: asyncio.sleep(0))

    job = asyncio.run(service.create_remix(profile["id"], source["id"]))
    assert job["id"].startswith("remix_")
    assert job["profile_id"] == profile["id"]
    assert job["source_asset_id"] == source["id"]
    assert job["status"] == "queued"
    assert job["progress"] == 0

    # Verify persistence: get_remix should return the same job.
    fetched = service.get_remix(job["id"])
    assert fetched is not None
    assert fetched["id"] == job["id"]


def test_remix_refresh_polls_and_downloads(isolated_store, tmp_path, monkeypatch):
    profile = _profile()
    work_dir = tmp_path / "remix_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Pre-create a job with one segment that has a task_id.
    job_id = "remix_test123"
    job = {
        "id": job_id,
        "owner_id": "test-user",
        "profile_id": profile["id"],
        "source_asset_id": "",
        "background_asset_id": "",
        "background_mode": "auto",
        "source_duration": 5.0,
        "transcript": "hello",
        "tts_audio_path": str(work_dir / "tts.mp3"),
        "tts_duration": 5.0,
        "segments": [{
            "index": 1, "start": 0, "duration": 5, "task_id": "omni-task-1",
            "status": "queued", "video_path": "", "error": "",
        }],
        "output_path": "", "output_url": "", "material": None,
        "status": "rendering", "progress": 40, "error": "",
        "created_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-01T00:00:00Z",
    }
    service._upsert("remixes", job)
    (work_dir / "tts.mp3").write_bytes(b"tts")

    downloaded = []
    async def fake_get_omni(self, task_id):
        return {"task_id": task_id, "status": "succeeded", "video_url": "https://example.test/seg.mp4", "progress": 100, "error": ""}

    async def fake_download(self, video_url, output_name="", output_dir=None):
        path = work_dir / output_name
        path.write_bytes(b"seg-video")
        downloaded.append(str(path))
        return str(path)

    monkeypatch.setattr(service.CloudInferenceClient, "get_omni_task", fake_get_omni)
    monkeypatch.setattr(service.CloudInferenceClient, "download_video", fake_download)
    monkeypatch.setattr(service, "_remix_work_dir", lambda rid: work_dir)
    monkeypatch.setattr(service, "get_media_output_dir", lambda kind: work_dir)
    monkeypatch.setattr(service, "media_url_for_path", lambda p: f"/api/media/files/video/{Path(p).name}")
    monkeypatch.setattr(service, "_register_material", lambda path, project, render_id: {"id": f"digital-human:{render_id}", "name": "test.mp4", "type": "video", "url": f"/api/media/files/video/{Path(path).name}", "path": str(path), "size": 0, "created_at": "2025-01-01T00:00:00Z"})

    refreshed = asyncio.run(service.refresh_remix(job_id))
    assert refreshed["status"] == "succeeded"
    assert refreshed["output_path"]
    assert downloaded, "download_video should have been called"


def test_remix_transcribe_prefers_asr_and_falls_back_to_vision(monkeypatch):
    """_remix_transcribe 优先用 speech.asr，失败时回退到 text.vision。"""
    from szyg.integrations.cloud_inference_client import CloudInferenceError

    # 场景 1：ASR 成功
    async def fake_asr(self, audio_url, **kwargs):
        return {"text": "这是ASR结果", "utterances": [], "duration_ms": 4000}

    monkeypatch.setattr(service.CloudInferenceClient, "asr_transcribe", fake_asr)
    text = asyncio.run(service._remix_transcribe(service.CloudInferenceClient(), "https://x/audio.wav"))
    assert text == "这是ASR结果"

    # 场景 2：ASR 返回 403（未开通），回退到 text.vision
    async def fake_asr_403(self, audio_url, **kwargs):
        raise CloudInferenceError("录音文件识别未配置", status_code=403)

    async def fake_vision(self, items, **kwargs):
        return {"message": {"role": "assistant", "content": "这是vision结果"}, "raw": {}}

    monkeypatch.setattr(service.CloudInferenceClient, "asr_transcribe", fake_asr_403)
    monkeypatch.setattr(service.CloudInferenceClient, "responses_text", fake_vision)
    text = asyncio.run(service._remix_transcribe(service.CloudInferenceClient(), "https://x/audio.wav"))
    assert text == "这是vision结果"

    # 场景 3：ASR 短暂不可用时仍回退到多模态转写
    async def fake_asr_500(self, audio_url, **kwargs):
        raise CloudInferenceError("服务暂时不可用", status_code=500)

    monkeypatch.setattr(service.CloudInferenceClient, "asr_transcribe", fake_asr_500)
    text = asyncio.run(service._remix_transcribe(service.CloudInferenceClient(), "https://x/audio.wav"))
    assert text == "这是vision结果"


def test_remix_segments_respect_configured_provider_concurrency(tmp_path, monkeypatch):
    active = 0
    maximum = 0

    async def fake_submit(**kwargs):
        segment = kwargs["segment"]
        segment["task_id"] = f"task-{segment['index']}"
        segment["status"] = "queued"

    async def fake_poll(client, segment, remix_id, work_dir, **kwargs):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        try:
            await asyncio.sleep(0.02)
            segment["status"] = "succeeded"
            segment["video_path"] = str(tmp_path / f"segment-{segment['index']}.mp4")
        finally:
            active -= 1

    monkeypatch.setattr(service, "REMIX_OMNIHUMAN_MAX_CONCURRENCY", 2)
    monkeypatch.setattr(service, "_REMIX_PROVIDER_SEMAPHORE", None)
    monkeypatch.setattr(service, "_REMIX_PROVIDER_SEMAPHORE_LOOP", None)
    monkeypatch.setattr(service, "_omni_submit_segment", fake_submit)
    monkeypatch.setattr(service, "_omni_poll_segment", fake_poll)
    segments = [
        {"index": index, "status": "pending", "task_id": "", "video_path": ""}
        for index in range(1, 5)
    ]

    asyncio.run(service._run_remix_segments(
        client=object(),
        segments=segments,
        remix_id="remix_parallel",
        work_dir=tmp_path,
        tts_audio_path=str(tmp_path / "tts.mp3"),
        profile={},
        image_url="https://example.test/avatar.png",
        background_url="",
    ))

    assert maximum == 2
    assert all(segment["status"] == "succeeded" for segment in segments)
