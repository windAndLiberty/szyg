import asyncio
from pathlib import Path

import pytest

from szyg import digital_human_service as service
from szyg.integrations.public_media_resolver import ResolvedPublicMedia


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
    })
    monkeypatch.setattr(service, "_owner", lambda: "test-user")
    return root


def _profile(profile_type="virtual"):
    avatar = service.save_asset("avatar.png", "image/png", b"image", "avatar_reference")
    voice = service.save_asset("voice.mp3", "audio/mpeg", b"audio", "voice_reference")
    return service.save_profile({
        "name": "测试数字人",
        "profile_type": profile_type,
        "avatar_asset_ids": [avatar["id"]],
        "voice_asset_id": voice["id"],
        "cover_asset_id": avatar["id"],
    })


def test_profile_is_local_and_real_profile_cannot_render(isolated_store):
    profile = _profile("real")
    project = service.save_project({
        "name": "真人测试",
        "profile_id": profile["id"],
        "scenes": [{"spoken_text": "你好", "visual_prompt": "室内口播", "duration": 5}],
    })
    with pytest.raises(ValueError, match="仅支持虚拟人物"):
        asyncio.run(service.create_render(project["id"]))


def test_45_second_project_is_split_and_reuses_voice(isolated_store, monkeypatch):
    profile = _profile()
    project = service.save_project({
        "name": "分段测试",
        "profile_id": profile["id"],
        "scenes": [
            {"spoken_text": "第一段", "visual_prompt": "产品开场", "duration": 20},
            {"spoken_text": "第二段", "visual_prompt": "功能说明", "duration": 25},
        ],
    })
    submitted = []

    async def fake_upload(self, path):
        return f"https://example.test/{Path(path).name}"

    async def fake_generate(self, prompt, references, **kwargs):
        submitted.append((prompt, references, kwargs))
        return {"task_id": f"task-{len(submitted)}", "status": "queued"}

    monkeypatch.setattr(service.CloudInferenceClient, "upload_reference", fake_upload)
    monkeypatch.setattr(service.CloudInferenceClient, "generate_presenter_video", fake_generate)
    job = asyncio.run(service.create_render(project["id"]))

    assert [segment["duration"] for segment in job["segments"]] == [20, 25]
    assert len(submitted) == 2
    assert all(any(item["role"] == "reference_audio" for item in refs) for _, refs, _ in submitted)
    assert "{第一段}" in submitted[0][0]
    assert "【第二段】" in submitted[1][0]


def test_reference_limits_are_enforced(isolated_store):
    profile = _profile()
    project = {"scenes": []}
    extra = []
    for index in range(31):
        extra.append(service.save_asset(f"image-{index}.png", "image/png", b"image", "scene_reference"))
    scene = {"reference_asset_ids": [item["id"] for item in extra]}
    with pytest.raises(ValueError, match="图片参考"):
        service._render_assets(project, profile, [scene])


def test_save_asset_file_moves_download_without_reading_it_all(isolated_store, tmp_path):
    downloaded = tmp_path / "download.mp4"
    downloaded.write_bytes(b"video-bytes")

    asset = service.save_asset_file(
        downloaded,
        "inspiration.mp4",
        "video/mp4",
        "inspiration_reference",
        source="public_link",
    )

    assert asset["kind"] == "video"
    assert asset["source"] == "public_link"
    assert Path(asset["path"]).read_bytes() == b"video-bytes"
    assert not downloaded.exists()


def test_public_page_is_resolved_before_inspiration_analysis(isolated_store, monkeypatch):
    inspiration = service.save_inspiration({"source_url": "https://example.test/work/123"})

    async def fake_resolve(url):
        return ResolvedPublicMedia(
            url="https://cdn.example.test/final-output.mp4",
            page_url=url,
            title="测试灵感视频",
            content_type="video/mp4",
            score=155,
        )

    async def fake_download(resolved, destination_dir, *, max_bytes):
        destination_dir.mkdir(parents=True, exist_ok=True)
        path = destination_dir / "resolved.mp4"
        path.write_bytes(b"resolved-video")
        return path, "resolved.mp4", "video/mp4"

    async def fake_upload(self, path):
        assert Path(path).read_bytes() == b"resolved-video"
        return "https://uploads.example.test/reference.mp4"

    async def fake_responses(self, messages, **kwargs):
        content = messages[0]["content"]
        assert content[0] == {
            "type": "input_video",
            "video_url": "https://uploads.example.test/reference.mp4",
        }
        return {"message": {"content": '{"transcript":"测试文案","segments":[]}'}}

    monkeypatch.setattr(service, "resolve_public_media", fake_resolve)
    monkeypatch.setattr(service, "download_public_media", fake_download)
    monkeypatch.setattr(service.CloudInferenceClient, "upload_reference", fake_upload)
    monkeypatch.setattr(service.CloudInferenceClient, "responses_text", fake_responses)

    analyzed = asyncio.run(service.analyze_inspiration(inspiration["id"]))

    assert analyzed["status"] == "analyzed"
    assert analyzed["name"] == "测试灵感视频"
    assert service.get_asset(analyzed["asset_id"])["source"] == "public_link"
