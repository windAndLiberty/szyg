"""Windows media storage settings for generated assets."""

from __future__ import annotations

import json
import mimetypes
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Literal

from szyg.data_path import DATA_DIR

MediaKind = Literal["image", "video", "audio", "document"]

_CONFIG_PATH = DATA_DIR / "media_storage.json"
_LOCK = threading.Lock()

_KEYS: dict[MediaKind, str] = {
    "image": "image_dir",
    "video": "video_dir",
    "audio": "audio_dir",
    "document": "document_dir",
}

_LABELS: dict[MediaKind, str] = {
    "image": "Pictures",
    "video": "Videos",
    "audio": "Music",
    "document": "Documents",
}


def _default_dir(kind: MediaKind) -> Path:
    configured_home = str(os.environ.get("SZYG_USER_HOME") or "").strip()
    home = Path(configured_home).expanduser() if configured_home else Path.home()
    if kind == "image":
        return home / "Pictures" / "SZYG"
    if kind == "video":
        return home / "Videos" / "SZYG"
    if kind == "audio":
        return home / "Music" / "SZYG"
    return home / "Documents" / "SZYG"


def _defaults() -> dict[str, str]:
    return {key: str(_default_dir(kind)) for kind, key in _KEYS.items()}


def _read_config_unlocked() -> dict[str, str]:
    config = _defaults()
    if _CONFIG_PATH.exists():
        try:
            raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for key in config:
                    value = str(raw.get(key, "")).strip()
                    if value:
                        config[key] = value
        except (OSError, json.JSONDecodeError):
            pass
    return config


def _write_config_unlocked(config: dict[str, str]) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _CONFIG_PATH.with_suffix(_CONFIG_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_CONFIG_PATH)


def _normalize_dir(value: str) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError("Path must be absolute on Windows")
    path.mkdir(parents=True, exist_ok=True)
    return str(path.resolve())


def get_media_storage_config() -> dict[str, Any]:
    with _LOCK:
        config = _read_config_unlocked()
        normalized = {}
        kind_by_key = {key: kind for kind, key in _KEYS.items()}
        for key, value in config.items():
            try:
                normalized[key] = _normalize_dir(value)
            except (ValueError, OSError):
                fallback = DATA_DIR / "generated_media" / kind_by_key[key]
                normalized[key] = _normalize_dir(str(fallback))
        if normalized != config:
            _write_config_unlocked(normalized)
        config = normalized

    return {
        **config,
        "defaults": _defaults(),
        "locations": [
            {
                "kind": kind,
                "key": key,
                "label": _LABELS[kind],
                "path": config[key],
                "default_path": str(_default_dir(kind)),
            }
            for kind, key in _KEYS.items()
        ],
    }


def update_media_storage_config(payload: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        config = _read_config_unlocked()
        for key in _KEYS.values():
            if key in payload:
                value = str(payload.get(key, "")).strip()
                config[key] = _normalize_dir(value) if value else _defaults()[key]
        _write_config_unlocked(config)
    return get_media_storage_config()


def get_media_output_dir(kind: MediaKind) -> Path:
    key = _KEYS[kind]
    config = get_media_storage_config()
    path = Path(config[key])
    path.mkdir(parents=True, exist_ok=True)
    probe = path / f".szyg-write-{uuid.uuid4().hex}.tmp"
    try:
        probe.write_bytes(b"")
        probe.unlink(missing_ok=True)
        return path
    except OSError:
        probe.unlink(missing_ok=True)
        fallback = DATA_DIR / "generated_media" / kind
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def infer_media_kind(path: str | Path) -> MediaKind:
    ext = Path(path).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
        return "image"
    if ext in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
        return "video"
    if ext in {".mp3", ".wav", ".m4a", ".aac", ".flac"}:
        return "audio"
    return "document"


def media_url_for_path(path: str | Path) -> str:
    p = Path(path)
    name = p.name
    if not name:
        return str(path)
    kind = infer_media_kind(p)
    try:
        resolved = p.resolve()
        output_dir = get_media_output_dir(kind).resolve()
        if resolved == output_dir or output_dir in resolved.parents:
            return f"/api/media/files/{kind}/{name}"
    except OSError:
        pass

    normalized = str(path).replace("\\", "/")
    if "/server/data/volcengine_output/" in normalized:
        return f"/api/files/server_volcengine_output/{name}"
    if "/volcengine_output/" in normalized:
        return f"/api/files/volcengine_output/{name}"
    return str(path)


def resolve_media_file(kind: MediaKind, filename: str) -> tuple[Path, str]:
    if "/" in filename or "\\" in filename or ".." in filename:
        raise ValueError("Invalid filename")
    path = (get_media_output_dir(kind) / filename).resolve()
    root = get_media_output_dir(kind).resolve()
    if path != root and root not in path.parents:
        raise ValueError("Invalid path")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return path, media_type


def resolve_managed_media_path(path_or_url: str) -> Path:
    value = (path_or_url or "").strip()
    if not value:
        raise ValueError("File path is required")

    normalized = value.replace("\\", "/")
    if normalized.startswith("/api/media/files/"):
        parts = normalized.split("/")
        if len(parts) >= 5:
            kind = parts[3]
            filename = parts[4]
            if kind in _KEYS:
                path, _media_type = resolve_media_file(kind, filename)  # type: ignore[arg-type]
                return path

    path = Path(value).expanduser().resolve()
    for kind in _KEYS:
        root = get_media_output_dir(kind).resolve()
        if path == root or root in path.parents:
            return path
    raise ValueError("File is outside managed media folders")
