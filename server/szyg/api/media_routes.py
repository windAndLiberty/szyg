"""Media storage settings and generated file access."""

from __future__ import annotations

from typing import Any
from datetime import datetime
import re
import os
import subprocess

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from szyg.media_storage import (
    get_media_storage_config,
    get_media_output_dir,
    media_url_for_path,
    resolve_managed_media_path,
    resolve_media_file,
    update_media_storage_config,
)

router = APIRouter(prefix="/api/media", tags=["media"])


class MediaStorageUpdate(BaseModel):
    image_dir: str | None = None
    video_dir: str | None = None
    audio_dir: str | None = None
    document_dir: str | None = None


class DocumentSaveRequest(BaseModel):
    title: str = "content"
    content: str
    extension: str = "md"


class DocumentUpdateRequest(BaseModel):
    path: str = ""
    url: str = ""
    content: str


class MediaFileActionRequest(BaseModel):
    path: str = ""
    url: str = ""


def _safe_stem(value: str) -> str:
    stem = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", value.strip(), flags=re.UNICODE).strip("_")
    return stem[:48] or "content"


@router.get("/storage")
async def get_storage() -> dict[str, Any]:
    return get_media_storage_config()


@router.put("/storage")
async def update_storage(req: MediaStorageUpdate) -> dict[str, Any]:
    try:
        payload = req.model_dump(exclude_unset=True)
    except AttributeError:
        payload = req.dict(exclude_unset=True)
    try:
        return update_media_storage_config(payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/files/{kind}/{filename}")
async def media_file(kind: str, filename: str):
    if kind not in {"image", "video", "audio", "document"}:
        raise HTTPException(404, "Unsupported media kind")
    try:
        path, media_type = resolve_media_file(kind, filename)  # type: ignore[arg-type]
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(str(path), media_type=media_type, filename=filename)


@router.post("/documents/save")
async def save_document(req: DocumentSaveRequest) -> dict[str, Any]:
    content = req.content.strip()
    if not content:
        raise HTTPException(400, "content is required")
    ext = req.extension.lower().lstrip(".")
    if ext not in {"md", "txt"}:
        raise HTTPException(400, "Unsupported document extension")
    output_dir = get_media_output_dir("document")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{_safe_stem(req.title)}_{stamp}.{ext}"
    path = output_dir / filename
    path.write_text(content, encoding="utf-8")
    return {
        "ok": True,
        "path": str(path.resolve()),
        "url": media_url_for_path(path),
        "filename": filename,
    }


@router.post("/documents/update")
async def update_document(req: DocumentUpdateRequest) -> dict[str, Any]:
    content = req.content.strip()
    if not content:
        raise HTTPException(400, "content is required")
    try:
        path = resolve_managed_media_path(req.path or req.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if path.suffix.lower() not in {".md", ".txt"}:
        raise HTTPException(400, "Unsupported document extension")
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "File not found")
    path.write_text(content, encoding="utf-8")
    updated_at = datetime.now().isoformat()
    try:
        from szyg.api.publisher_routes import touch_generation_history
        touch_generation_history(str(path.resolve()), updated_at)
    except Exception:
        pass
    return {
        "ok": True,
        "path": str(path.resolve()),
        "url": media_url_for_path(path),
        "filename": path.name,
        "updated_at": updated_at,
    }


@router.post("/files/open")
async def open_media_file(req: MediaFileActionRequest) -> dict[str, Any]:
    try:
        path = resolve_managed_media_path(req.path or req.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "File not found")
    try:
        os.startfile(str(path))  # type: ignore[attr-defined]
    except Exception as exc:
        raise HTTPException(500, f"Failed to open file: {exc}")
    return {"ok": True, "path": str(path)}


@router.post("/files/reveal")
async def reveal_media_file(req: MediaFileActionRequest) -> dict[str, Any]:
    try:
        path = resolve_managed_media_path(req.path or req.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "File not found")
    try:
        subprocess.Popen(["explorer.exe", f"/select,{path}"])
    except Exception as exc:
        raise HTTPException(500, f"Failed to reveal file: {exc}")
    return {"ok": True, "path": str(path), "directory": str(path.parent)}


@router.post("/files/delete")
async def delete_media_file(req: MediaFileActionRequest) -> dict[str, Any]:
    try:
        path = resolve_managed_media_path(req.path or req.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not path.exists():
        return {"ok": True, "deleted": False, "path": str(path)}
    if not path.is_file():
        raise HTTPException(400, "Path is not a file")
    try:
        path.unlink()
    except Exception as exc:
        raise HTTPException(500, f"Failed to delete file: {exc}")
    return {"ok": True, "deleted": True, "path": str(path)}
