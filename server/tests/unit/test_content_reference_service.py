from pathlib import Path

import pytest

from szyg import content_reference_service as service


def _png(width: int = 640, height: int = 480) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\x0dIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
    )


@pytest.fixture
def reference_root(tmp_path, monkeypatch):
    root = tmp_path / "content_references"
    monkeypatch.setattr(service, "ROOT", root)
    monkeypatch.setattr(service, "FILES_DIR", root / "files")
    monkeypatch.setattr(service, "META_DIR", root / "metadata")
    return root


def test_image_reference_round_trip(reference_root):
    item = service.save_reference("产品图.png", "image/png", _png(), "image")

    assert item["kind"] == "image"
    assert item["width"] == 640
    assert item["height"] == 480
    assert Path(item["path"]).is_file()
    assert service.resolve_references([item["id"]], "image")[0]["id"] == item["id"]

    assert service.delete_reference(item["id"]) is True
    assert service.get_reference(item["id"]) is None


def test_image_mode_rejects_webp(reference_root):
    with pytest.raises(ValueError, match="JPG、JPEG、PNG"):
        service.save_reference("reference.webp", "image/webp", b"not-empty", "image")


def test_seedream_dimension_limit(reference_root):
    with pytest.raises(ValueError, match="4096"):
        service.save_reference("large.png", "image/png", _png(4097, 1024), "image")


def test_seedance_reference_count_limits(monkeypatch):
    def fake_get(reference_id: str):
        kind = "video" if reference_id.startswith("video") else "image"
        return {"id": reference_id, "mode": "video", "kind": kind, "path": "/tmp/ref"}

    monkeypatch.setattr(service, "get_reference", fake_get)
    with pytest.raises(ValueError, match="9 张参考图片和 3 段参考视频"):
        service.resolve_references([f"image-{index}" for index in range(10)], "video")
    with pytest.raises(ValueError, match="9 张参考图片和 3 段参考视频"):
        service.resolve_references([f"video-{index}" for index in range(4)], "video")


def test_duplicate_reference_is_rejected(monkeypatch):
    monkeypatch.setattr(service, "get_reference", lambda _reference_id: None)
    with pytest.raises(ValueError, match="不能重复"):
        service.resolve_references(["same", "same"], "image")
