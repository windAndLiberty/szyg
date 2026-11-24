"""Media storage settings and generated file access."""

from __future__ import annotations

from typing import Any, Literal
from datetime import datetime
import re
import os
import subprocess
import io
import tempfile
import wave
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from szyg.media_storage import (
    get_media_storage_config,
    get_media_output_dir,
    media_url_for_path,
    resolve_managed_media_path,
    resolve_media_file,
    update_media_storage_config,
)
from szyg.integrations.cloud_inference_client import CloudInferenceClient, CloudInferenceError
from szyg.content_reference_service import delete_reference, get_reference, save_reference
from szyg.conversation_media import import_conversation_asset, inspect_conversation_media

router = APIRouter(prefix="/api/media", tags=["media"])


@router.post("/conversation-assets")
def upload_conversation_asset(file: UploadFile):
    return import_conversation_asset(file)


class MediaInspection(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source: str = Field(min_length=1, max_length=320)
    question: str = Field(default="", max_length=1200)
    focus: Literal["auto", "visual", "audio", "both"] = "auto"


@router.post("/conversation-inspect")
async def inspect_conversation_asset(body: MediaInspection):
    return await inspect_conversation_media(body.source, body.question, body.focus)


@router.post("/dictation/{recording_id}")
async def transcribe_dictation(recording_id: UUID, request: Request) -> dict[str, str]:
    """Transcribe a short mono 16 kHz voice draft without adding it to the media library."""
    if request.headers.get("content-type", "").split(";")[0] != "audio/wav":
        raise HTTPException(415, "需要 WAV 录音")
    max_frames = 120 * 16000
    data = bytearray()
    async for part in request.stream():
        if len(data) + len(part) > max_frames * 2 + 4096:
            raise HTTPException(413, "单段录音最长为两分钟")
        data.extend(part)
    try:
        with wave.open(io.BytesIO(data), "rb") as source:
            frames = source.getnframes()
            if (source.getnchannels(), source.getframerate(), source.getsampwidth()) != (1, 16000, 2):
                raise ValueError()
            if not 0 < frames <= max_frames:
                raise ValueError()
            samples = source.readframes(frames)
            if len(samples) != frames * 2:
                raise ValueError()
    except (ValueError, wave.Error, EOFError) as exc:
        raise HTTPException(422, "录音无效，请重新录制") from exc

    client = CloudInferenceClient(timeout=120)
    try:
        with tempfile.TemporaryDirectory(prefix="xiaoyu-dictation-") as directory:
            path = Path(directory) / "dictation.wav"
            with wave.open(str(path), "wb") as output:
                output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                output.writeframes(samples)
            url = await client.upload_reference(str(path))
            result = await client.asr_transcribe(url, audio_format="wav", idempotency_key=str(recording_id))
    except CloudInferenceError as exc:
        raise HTTPException(exc.status_code or 503, str(exc)) from exc
    text = result["text"].strip()
    if not text:
        raise HTTPException(422, "没有识别到语音，请重新录制")
    return {"text": text}


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


@router.post("/references")
async def upload_content_reference(
    file: UploadFile = File(...),
    mode: str = Form(...),
) -> dict[str, Any]:
    if mode not in {"image", "video"}:
        raise HTTPException(400, "不支持的参考素材用途")
    if not file.filename:
        raise HTTPException(400, "请选择参考素材")
    try:
        item = save_reference(
            file.filename,
            file.content_type or "",
            await file.read(),
            mode,  # type: ignore[arg-type]
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "reference": item}


@router.get("/references/{reference_id}")
async def content_reference_file(reference_id: str):
    item = get_reference(reference_id)
    if not item:
        raise HTTPException(404, "参考素材不存在")
    return FileResponse(
        str(item["path"]),
        media_type=str(item.get("content_type") or "application/octet-stream"),
        filename=str(item.get("name") or "reference"),
    )


@router.delete("/references/{reference_id}")
async def remove_content_reference(reference_id: str) -> dict[str, Any]:
    return {"ok": True, "removed": delete_reference(reference_id)}


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
