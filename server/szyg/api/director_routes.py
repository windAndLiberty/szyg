"""Local video projects, media handoff, and background jobs for Xiaoyu Director."""
from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import tempfile
from functools import partial
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field, field_validator

from szyg import director_jobs
from szyg.conversation_media import MEDIA_FORMATS, import_conversation_asset, validate_media_source
from szyg.integrations.cloud_inference_client import CloudInferenceClient
from szyg.media_storage import resolve_managed_media_path
from szyg.video_cut_engine import _get_ffmpeg

router = APIRouter(prefix="/api/director", tags=["director"])


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class ProjectCreate(Input):
    title: str = Field(min_length=1, max_length=120)
    brief: str = Field(min_length=1, max_length=8000)
    pipeline: str = Field(default="documentary-montage", min_length=1, max_length=96)
    aspect_ratio: Literal["16:9","9:16","1:1"] = "16:9"


class Scene(Input):
    caption: str = Field(default="", max_length=480)
    duration: float = Field(ge=.5, le=30)
    source: str | None = None
    start: float = Field(default=0, ge=0, le=86400)

    @field_validator("source")
    @classmethod
    def validate_source(cls, value):
        return validate_media_source(value, {"image", "video"}) if value is not None else None


class ProjectEdit(Input):
    scenes: list[Scene] = Field(min_length=1, max_length=60)
    aspect_ratio: Literal["16:9","9:16","1:1"] | None = None
    audio: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)

    @field_validator("audio")
    @classmethod
    def validate_audio(cls, value):
        return validate_media_source(value, {"audio"}) if value else value


class Export(Input):
    request_id: UUID | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class AdvancedTool(Input):
    request_id: UUID
    key: str = Field(min_length=1, max_length=120)
    settings: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False


class Installation(Input):
    confirmed: Literal[True]
    request_id: UUID


class Transcription(Input):
    source: str
    request_id: UUID
    confirmed: Literal[True]

    @field_validator("source")
    @classmethod
    def validate_source(cls, value):
        return validate_media_source(value, {"audio", "video"})


def _engine():
    from szyg import openmontage_engine
    return openmontage_engine


def _call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)[:400]) from exc
    except (KeyError, ValueError) as exc:
        raise HTTPException(422, str(exc)[:400]) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)[:400]) from exc


@router.get("/capabilities")
def capabilities():
    return _call(_engine().capabilities)


@router.get("/catalog")
def catalog(query: str = Query("", max_length=160), kind: Literal["all", "skill", "tool", "pipeline", "style"] = "all",
            limit: int = Query(30, ge=1, le=200), offset: int = Query(0, ge=0)):
    return _call(_engine().catalog, query=query, kind=kind, limit=limit, offset=offset)


@router.get("/guide")
def guide(key: str = Query(min_length=1, max_length=256), offset: int = Query(0, ge=0),
          limit: int = Query(9000, ge=1, le=16000)):
    return _call(_engine().guide, key, offset=offset, limit=limit)


@router.get("/tool")
def tool_info(key: str = Query(min_length=1, max_length=120)):
    return _call(_engine().tool_info, key)


@router.get("/projects")
def projects():
    return _call(_engine().list_projects)


@router.post("/projects")
def create_project(body: ProjectCreate):
    return _call(_engine().create_project, **body.model_dump())


@router.get("/projects/{project_id}")
def project(project_id: UUID):
    return _call(_engine().get_project, str(project_id))


@router.put("/projects/{project_id}")
def edit_project(project_id: UUID, body: ProjectEdit):
    return _call(_engine().edit_project, str(project_id), **body.model_dump(exclude_none=True))


@router.post("/projects/{project_id}/render")
def render(project_id: UUID, body: Export):
    pid = str(project_id)
    revision = body.expected_revision or _call(_engine().get_project, pid)["revision"]
    signature = f"render:{pid}:{revision}"
    return director_jobs.submit(str(body.request_id or signature), signature,
                                partial(_engine().render_project, pid, expected_revision=revision),
                                result_available=None if body.request_id else lambda row: Path(row.get("path", "")).is_file())


@router.post("/projects/{project_id}/tools")
def run_tool(project_id: UUID, body: AdvancedTool):
    tool = _call(_engine().tool_info, body.key)
    if tool.get("requires_approval", True) and body.confirmed is not True:
        return {"ok": False, "status": "confirmation_required", "key": body.key,
                "provider": tool.get("provider"), "message": "运行前请告知用户将交给此服务商的素材和任务、可能产生的费用，取得同意后确认执行。"}
    args = json.dumps(body.settings, ensure_ascii=False, sort_keys=True, allow_nan=False)
    if len(args) > 40000:
        raise HTTPException(422, "工具参数过长")
    sig = f"tool:{project_id}:{body.key}:" + hashlib.sha256(args.encode()).hexdigest()
    return director_jobs.submit(str(body.request_id), sig, partial(
        _engine().run_tool, str(project_id), body.key, body.settings, str(body.request_id)))


@router.post("/install")
def install(body: Installation):
    return director_jobs.submit(str(body.request_id), "install", _engine().install_runtime)


@router.get("/jobs/{job_id}")
def job(job_id: UUID):
    return director_jobs.status(str(job_id))


@router.get("/jobs/{job_id}/render")
def render_receipt(job_id: UUID):
    return director_jobs.render_status(str(job_id))


@router.post("/assets")
def import_asset(file: UploadFile):
    return import_conversation_asset(file)


def _transcribe(source: str, request_id: UUID):
    path = resolve_managed_media_path(source)
    if not path.is_file():
        raise ValueError("素材已移除")
    demuxer = MEDIA_FORMATS[path.suffix.lower()][1]
    with tempfile.TemporaryDirectory(prefix="director-asr-") as directory:
        audio = Path(directory) / "voice.mp3"
        # Extract just the audio; the original video never needs to leave this machine.
        subprocess.run([_get_ffmpeg(), "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe",
            "-f", demuxer, "-i", str(path), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000",
            "-b:a", "64k", "-f", "mp3", str(audio)], capture_output=True, check=True, timeout=180)
        if audio.stat().st_size > 50 * 1024 * 1024:
            raise ValueError("待转写的音频过长，请先剪成较短片段")
        async def recognize():
            client = CloudInferenceClient(timeout=120)
            reference = await client.upload_reference(str(audio))
            return await client.asr_transcribe(reference, audio_format="mp3", idempotency_key=str(request_id))
        return asyncio.run(recognize())


@router.post("/transcribe")
def transcribe(body: Transcription):
    return director_jobs.submit(str(body.request_id), "asr:" + body.source, partial(_transcribe, body.source, body.request_id))


class Narration(Input):
    text: str = Field(min_length=1, max_length=3000)
    voice: str = Field(default="warm_female", min_length=1, max_length=64)
    speed: float = Field(default=1, ge=.5, le=2)
    request_id: UUID
    confirmed: Literal[True]


@router.post("/narrate")
def narrate(body: Narration):
    from szyg.api.tts_routes import TtsRequest, synthesize
    args = body.model_dump(exclude={"request_id", "confirmed"})
    def make_audio():
        return asyncio.run(synthesize(TtsRequest(**args), response="json")).model_dump()
    sig = hashlib.sha256(json.dumps(args, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return director_jobs.submit(str(body.request_id), "narrate:" + sig, make_audio)
