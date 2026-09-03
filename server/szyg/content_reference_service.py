"""Validated local reference assets for image and video generation."""

from __future__ import annotations

import json
import mimetypes
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from szyg.data_path import DATA_DIR


ReferenceMode = Literal["image", "video"]

ROOT = DATA_DIR / "content_references"
FILES_DIR = ROOT / "files"
META_DIR = ROOT / "metadata"

IMAGE_MODE_SUFFIXES = {".jpg", ".jpeg", ".png"}
VIDEO_MODE_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_SUFFIXES = {".mp4", ".mov"}

MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_VIDEO_BYTES = 50 * 1024 * 1024
MAX_IMAGE_REFERENCES = 10
MAX_VIDEO_IMAGES = 9
MAX_VIDEO_REFERENCES = 3
MIN_VIDEO_SECONDS = 2.0
MAX_VIDEO_SECONDS = 15.0
MAX_IMAGE_DIMENSION = 4096


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: str) -> str:
    name = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", Path(value).name, flags=re.UNICODE)
    return name[:100] or "reference"


def _image_dimensions(content: bytes, suffix: str) -> tuple[int, int] | None:
    if suffix == ".png" and len(content) >= 24 and content.startswith(b"\x89PNG\r\n\x1a\n"):
        return int.from_bytes(content[16:20], "big"), int.from_bytes(content[20:24], "big")
    if suffix in {".jpg", ".jpeg"} and content.startswith(b"\xff\xd8"):
        cursor = 2
        while cursor + 9 < len(content):
            if content[cursor] != 0xFF:
                cursor += 1
                continue
            marker = content[cursor + 1]
            cursor += 2
            if marker in {0xD8, 0xD9}:
                continue
            if cursor + 2 > len(content):
                break
            length = int.from_bytes(content[cursor:cursor + 2], "big")
            if length < 2 or cursor + length > len(content):
                break
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                return (
                    int.from_bytes(content[cursor + 5:cursor + 7], "big"),
                    int.from_bytes(content[cursor + 3:cursor + 5], "big"),
                )
            cursor += length
    return None


def _probe_video_duration(path: Path) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(path),
            ],
            capture_output=True,
            check=True,
            text=True,
            timeout=15,
        )
        return round(float(result.stdout.strip()), 3)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise ValueError("无法读取视频时长，请上传有效的 MP4 或 MOV 文件") from exc


def save_reference(
    filename: str,
    content_type: str,
    content: bytes,
    mode: ReferenceMode,
) -> dict[str, Any]:
    if mode not in {"image", "video"}:
        raise ValueError("不支持的参考素材用途")
    if not content:
        raise ValueError("参考素材文件为空")

    suffix = Path(filename).suffix.lower()
    image_suffixes = IMAGE_MODE_SUFFIXES if mode == "image" else VIDEO_MODE_IMAGE_SUFFIXES
    if suffix in image_suffixes:
        kind = "image"
        if len(content) > MAX_IMAGE_BYTES:
            raise ValueError("单张参考图片不能超过 15MB")
    elif mode == "video" and suffix in VIDEO_SUFFIXES:
        kind = "video"
        if len(content) > MAX_VIDEO_BYTES:
            raise ValueError("单段参考视频不能超过 50MB")
    else:
        supported = "JPG、JPEG、PNG" if mode == "image" else "JPG、JPEG、PNG、WEBP、MP4、MOV"
        raise ValueError(f"当前仅支持 {supported} 参考素材")

    reference_id = f"ref_{uuid.uuid4().hex[:16]}"
    stored_name = f"{reference_id}_{_safe_name(filename)}"
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)
    path = (FILES_DIR / stored_name).resolve()
    path.write_bytes(content)

    try:
        duration = _probe_video_duration(path) if kind == "video" else None
        dimensions = _image_dimensions(content, suffix) if kind == "image" else None
        if duration is not None and not MIN_VIDEO_SECONDS <= duration <= MAX_VIDEO_SECONDS:
            raise ValueError("参考视频时长需在 2–15 秒之间")
        if mode == "image" and dimensions:
            width, height = dimensions
            if max(width, height) > MAX_IMAGE_DIMENSION:
                raise ValueError("参考图片宽高不能超过 4096×4096")
            ratio = width / max(1, height)
            if ratio < 1 / 3 or ratio > 3:
                raise ValueError("参考图片宽高比需在 1:3–3:1 之间")
    except Exception:
        path.unlink(missing_ok=True)
        raise

    item = {
        "id": reference_id,
        "name": Path(filename).name,
        "kind": kind,
        "mode": mode,
        "content_type": content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
        "size": len(content),
        "path": str(path),
        "url": f"/api/media/references/{reference_id}",
        "duration": duration,
        "width": dimensions[0] if dimensions else None,
        "height": dimensions[1] if dimensions else None,
        "created_at": _now(),
    }
    (META_DIR / f"{reference_id}.json").write_text(
        json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return item


def get_reference(reference_id: str) -> dict[str, Any] | None:
    if not re.fullmatch(r"ref_[0-9a-f]{16}", reference_id or ""):
        return None
    metadata_path = META_DIR / f"{reference_id}.json"
    try:
        item = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    path = Path(str(item.get("path") or ""))
    try:
        if not path.is_file() or path.resolve().parent != FILES_DIR.resolve():
            return None
    except OSError:
        return None
    return item


def delete_reference(reference_id: str) -> bool:
    item = get_reference(reference_id)
    if not item:
        return False
    Path(str(item["path"])).unlink(missing_ok=True)
    (META_DIR / f"{reference_id}.json").unlink(missing_ok=True)
    return True


def resolve_references(reference_ids: list[str], mode: ReferenceMode) -> list[dict[str, Any]]:
    if len(reference_ids) != len(set(reference_ids)):
        raise ValueError("参考素材不能重复添加")
    items: list[dict[str, Any]] = []
    for reference_id in reference_ids:
        item = get_reference(reference_id)
        if not item:
            raise ValueError("参考素材已不存在，请重新上传")
        if item.get("mode") != mode:
            raise ValueError("参考素材与当前生成模式不匹配")
        items.append(item)

    image_count = sum(item.get("kind") == "image" for item in items)
    video_count = sum(item.get("kind") == "video" for item in items)
    if mode == "image" and (video_count or image_count > MAX_IMAGE_REFERENCES):
        raise ValueError("图片生成最多支持 10 张参考图片")
    if mode == "video" and (image_count > MAX_VIDEO_IMAGES or video_count > MAX_VIDEO_REFERENCES):
        raise ValueError("视频生成最多支持 9 张参考图片和 3 段参考视频")
    return items


__all__ = [
    "delete_reference",
    "get_reference",
    "resolve_references",
    "save_reference",
]
