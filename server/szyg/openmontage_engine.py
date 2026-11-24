"""Persist local director projects and compose their media with OpenMontage."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import yaml

from szyg import openmontage_runtime as runtime
from szyg.media_storage import (
    get_media_output_dir,
    media_url_for_path,
    resolve_managed_media_path,
)

_ASPECTS = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (960, 960)}
_IMAGE = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
_VIDEO = {".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi"}
_AUDIO = {".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac", ".opus"}
_PATH_KEYS = set(
    """input_path source thumbnail_path subtitles_path srt_path subtitle_path speaker_path background_path original_audio_path video_paths image_path image_paths mask_path first_frame_path last_frame_path end_image_path
reference_image_path reference_image_paths reference_video_path reference_audio_path input_reference_path audio_path
video_path music_path primary_audio secondary_audio clips""".split()
)
_TOOL_CACHE = (0.0, [])
install_runtime = runtime.install_runtime


def _guides():
    paths = runtime.runtime()
    if not paths:
        return {}
    source = paths[0]
    result = {}
    for file in sorted((source / "pipeline_defs").glob("*.yaml")):
        if file.stem != "framework-smoke":
            result["pipeline:" + file.stem] = file
    for file in sorted((source / "styles").rglob("*.yaml")):
        result[
            "style:" + file.relative_to(source / "styles").with_suffix("").as_posix()
        ] = file
    for folder in ("skills", ".agents/skills"):
        for file in sorted((source / folder).rglob("*.md")):
            if file.is_file() and file.resolve().is_relative_to(source):
                result["skill:" + file.relative_to(source).as_posix()] = file
    return result


def _tools():
    global _TOOL_CACHE
    if not runtime.runtime():
        return []
    if time.monotonic() - _TOOL_CACHE[0] > 60 or not _TOOL_CACHE[1]:
        with tempfile.TemporaryDirectory() as work:
            rows = runtime.invoke({"op": "catalog"}, Path(work), timeout=75)
        _TOOL_CACHE = (time.monotonic(), rows)
    return _TOOL_CACHE[1]


def capabilities() -> dict:
    status = runtime.capabilities()
    status["limits"] = {
        "max_scenes": 60,
        "min_scene_seconds": 0.5,
        "max_scene_seconds": 30,
        "max_export_seconds": 600,
        "aspect_resolutions": _ASPECTS,
    }
    status["tool_states"] = {
        "ready": "工具已接入，对应依赖与配置通过上游检查。",
        "needs_setup": "工具已接入，可在工具详情查看所需凭证、依赖或模型。",
        "reference_only": "可查阅原版契约，当前会话没有该工具的执行入口。",
    }
    tools = _tools() if status["installed"] else []
    callable_count = sum(1 for item in tools if item["executable"])
    ready = sum(1 for item in tools if item["available"])
    status["tool_counts"] = {
        "discovered": len(tools),
        "ready": ready,
        "needs_setup": callable_count - ready,
        "executable": callable_count,
        "reference_only": len(tools) - callable_count,
    }
    return status


def catalog(
    query: str = "", kind: str = "all", limit: int = 30, offset: int = 0
) -> dict:
    if kind not in {"all", "tool", "skill", "pipeline", "style"}:
        raise ValueError("无效的目录类型")
    items = []
    if kind in ("all", "pipeline", "skill", "style"):
        for key, file in _guides().items():
            category, name = key.split(":", 1)
            if kind in ("all", category):
                items.append({
                    "kind": category,
                    "key": key,
                    "name": file.parent.name if file.stem == "SKILL" else file.stem,
                    "description": name,
                })
    if kind in ("all", "tool"):
        for tool in _tools():
            items.append({
                k: tool[k]
                for k in (
                    "key",
                    "name",
                    "kind",
                    "description",
                    "status",
                    "capability",
                    "provider",
                    "available",
                    "executable",
                    "requires_approval",
                )
            })
    words = query.lower().split()
    matched = [
        item
        for item in items
        if all(
            word in " ".join(str(v) for v in item.values()).lower() for word in words
        )
    ]
    start = max(0, offset)
    end = start + max(1, min(limit, 200))
    return {
        "items": matched[start:end],
        "total": len(matched),
        "next_offset": end if end < len(matched) else None,
    }


def guide(key: str, offset: int = 0, limit: int = 9000) -> dict:
    file = _guides().get(key)
    if not file:
        raise ValueError("找不到该制作手册或管线")
    content = file.read_text(encoding="utf-8")
    start = max(0, offset)
    end = min(len(content), start + max(1, min(16000, limit)))
    return {
        "key": key,
        "content": content[start:end],
        "next_offset": end if end < len(content) else None,
        "source_url": runtime.SOURCE
        + "/blob/"
        + runtime.COMMIT
        + "/"
        + file.relative_to(runtime.runtime()[0]).as_posix(),
    }


def tool_info(key: str) -> dict:
    for row in _tools():
        if row["key"] == key:
            return row
    raise ValueError("找不到该工具，请先安装导演引擎")


def _identifier(value: str) -> str:
    if not isinstance(value, str) or str(uuid.UUID(value)) != value:
        raise ValueError("无效的项目或请求编号")
    return value


def _project(key: str) -> Path:
    path = runtime.STORE / "projects" / _identifier(key)
    if not (path / "project.json").is_file():
        raise ValueError("项目不存在")
    return path


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, value: dict):
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", delete=False, dir=path.parent
    ) as handle:
        json.dump(value, handle, ensure_ascii=False, allow_nan=False)
        temp = Path(handle.name)
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def list_projects() -> list[dict]:
    paths = sorted(
        (runtime.STORE / "projects").glob("*/project.json"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return [
        {
            k: row[k]
            for k in (
                "id",
                "title",
                "brief",
                "pipeline",
                "aspect_ratio",
                "revision",
                "updated_at",
            )
        }
        for row in map(_read, paths)
    ]


def get_project(project_id: str) -> dict:
    return _read(_project(project_id) / "project.json")


def create_project(
    title: str,
    brief: str,
    pipeline: str = "documentary-montage",
    aspect_ratio: str = "16:9",
) -> dict:
    if not title.strip() or len(title) > 120 or not brief.strip() or len(brief) > 8000:
        raise ValueError("请提供项目名称（120 字以内）和创作需求（8,000 字以内）")
    if aspect_ratio not in _ASPECTS:
        raise ValueError("画幅应为 16:9、9:16 或 1:1")
    guides = _guides()
    definition = guides.get("pipeline:" + pipeline)
    if definition is None:
        raise ValueError("找不到该制作管线，请检查安装状态和管线名称")
    workflow = yaml.safe_load(definition.read_text(encoding="utf-8"))
    stages = []
    for stage in workflow.get("stages", []):
        if not isinstance(stage, dict):
            continue
        skill = "skill:skills/" + str(stage.get("skill", "")) + ".md"
        stages.append({
            "name": stage["name"],
            "guide_key": skill if skill in guides else None,
            "produces": stage.get("produces", []),
            "tools": stage.get("tools_available", []),
            "review": stage.get("review_focus", []),
            "checkpoint": bool(stage.get("checkpoint_required")),
        })
    key = str(uuid.uuid4())
    directory = runtime.STORE / "projects" / key
    directory.mkdir(parents=True)
    row = {
        "id": key,
        "title": title.strip(),
        "brief": brief.strip(),
        "pipeline": pipeline,
        "pipeline_guide": "pipeline:" + pipeline,
        "stages": stages,
        "aspect_ratio": aspect_ratio,
        "revision": 1,
        "scenes": [],
        "audio": "",
        "updated_at": time.time(),
        "deliverable": None,
    }
    _save(directory / "project.json", row)
    return row


def _media(value: str, types: set[str]) -> Path:
    if not isinstance(value, str) or not re.fullmatch(
        r"/api/media/files/(image|video|audio|document)/[^/\\?#]+", value
    ):
        raise ValueError("请选择已导入小妤素材库的文件")
    path = resolve_managed_media_path(value)
    if (
        not path.is_file()
        or path.suffix.lower() not in types
        or path.stat().st_size == 0
    ):
        raise ValueError("素材不存在或类型不支持")
    return path


def _number(value, minimum, maximum, label):
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise ValueError(f"{label}须在 {minimum} 到 {maximum} 之间")
    return float(value)


def edit_project(
    project_id: str,
    scenes: list[dict],
    aspect_ratio: str | None = None,
    audio: str | None = None,
    expected_revision: int | None = None,
) -> dict:
    directory = _project(project_id)
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= 60:
        raise ValueError("分镜表需要 1–60 个镜头")
    if aspect_ratio is not None and aspect_ratio not in _ASPECTS:
        raise ValueError("画幅应为 16:9、9:16 或 1:1")
    if audio:
        _media(audio, _AUDIO)
    shots = []
    for scene in scenes:
        if not isinstance(scene, dict) or set(scene) - {
            "caption",
            "duration",
            "source",
            "start",
        }:
            raise ValueError("镜头格式无效")
        caption = scene.get("caption", "")
        if not isinstance(caption, str) or len(caption) > 480:
            raise ValueError("镜头字幕最多 480 字")
        source = scene.get("source") or ""
        if source:
            _media(source, _IMAGE | _VIDEO)
        elif not caption.strip():
            raise ValueError("请为每个镜头提供素材或字幕卡内容")
        shots.append({
            "caption": caption.strip(),
            "duration": _number(scene.get("duration"), 0.5, 30, "时长"),
            "start": _number(scene.get("start", 0), 0, 86400, "起点"),
            "source": source,
        })
    if sum(scene["duration"] for scene in shots) > 600:
        raise ValueError("一次导出最长十分钟")
    with runtime.file_lock(directory / ".project.lock"):
        row = get_project(project_id)
        if expected_revision is not None and row["revision"] != expected_revision:
            raise ValueError("项目版本已变更，请重新读取后保存")
        row.update(
            scenes=shots,
            aspect_ratio=aspect_ratio or row["aspect_ratio"],
            audio=audio if audio is not None else row["audio"],
            revision=row["revision"] + 1,
            updated_at=time.time(),
            deliverable=None,
        )
        _save(directory / "project.json", row)
        return row


def _ffmpeg(args: list[str], timeout=240):
    command = runtime.media_command("ffmpeg")
    if not command:
        raise ValueError("请安装 FFmpeg 再试")
    result = subprocess.run(
        [command, "-y", "-nostdin", "-v", "error", *args],
        capture_output=True,
        timeout=timeout,
    )
    if result.returncode:
        raise ValueError("无法处理该素材，请检查素材的格式或长度。")


def _probe(path: Path) -> dict:
    command = runtime.media_command("ffprobe")
    if not command:
        raise ValueError("请安装 ffprobe 再试")
    result = subprocess.run(
        [
            command,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        timeout=15,
    )
    if result.returncode:
        raise ValueError("无法读取素材")
    return json.loads(result.stdout)


def _srt_time(seconds: float) -> str:
    ms = round(seconds * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def _published_file(source: Path, name: str, kind: str) -> Path:
    output = get_media_output_dir(kind) / name
    with tempfile.NamedTemporaryFile(
        dir=output.parent, delete=False, prefix=".director-"
    ) as tmp:
        stage = Path(tmp.name)
    try:
        shutil.copyfile(source, stage)
        stage.replace(output)
    finally:
        stage.unlink(missing_ok=True)
    return output


def render_project(project_id: str, expected_revision: int | None = None) -> dict:
    directory = _project(project_id)
    with runtime.file_lock(directory / ".project.lock"):
        row = get_project(project_id)
        if expected_revision is not None and row["revision"] != expected_revision:
            raise ValueError("待导出的分镜已被修改，请按最新版本重新导出")
        if row["deliverable"] and Path(row["deliverable"]["path"]).is_file():
            return row["deliverable"]
        if not row["scenes"]:
            raise ValueError("请先保存分镜")
        width, height = _ASPECTS[row["aspect_ratio"]]
        with tempfile.TemporaryDirectory(dir=directory, prefix="render-") as tmp:
            work = Path(tmp)
            cuts, subtitles, total = [], [], 0.0
            for index, scene in enumerate(row["scenes"]):
                duration, start = scene["duration"], scene["start"]
                source = (
                    _media(scene["source"], _IMAGE | _VIDEO)
                    if scene["source"]
                    else None
                )
                if source and source.suffix.lower() in _VIDEO:
                    available = float(
                        _probe(source).get("format", {}).get("duration", 0)
                    )
                    if start + duration > available + 0.09:
                        raise ValueError(
                            f"镜头 {index + 1} 超出原素材时长 {available:.2f} 秒"
                        )
                else:
                    if source:
                        args = [
                            "-loop",
                            "1",
                            "-framerate",
                            "30",
                            "-i",
                            str(source),
                            "-vf",
                            f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1",
                        ]
                    else:
                        args = [
                            "-f",
                            "lavfi",
                            "-i",
                            f"color=c=0x172235:s={width}x{height}:r=30",
                        ]
                    source = work / f"shot-{index:03}.mp4"
                    _ffmpeg([
                        *args,
                        "-t",
                        str(duration),
                        "-an",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "ultrafast",
                        "-pix_fmt",
                        "yuv420p",
                        str(source),
                    ])
                    start = 0
                cuts.append({
                    "source": str(source),
                    "in_seconds": start,
                    "out_seconds": start + duration,
                })
                caption = scene["caption"]
                if caption:
                    # SRT captions stay plain text across FFmpeg / libass.
                    caption = (
                        " "
                        .join(caption.split())
                        .replace("<", "‹")
                        .replace(">", "›")
                        .replace("{", "（")
                        .replace("}", "）")
                    )
                    lines = textwrap.fill(caption, width=34 if width > height else 22)
                    subtitles.append(
                        f"{len(subtitles) + 1}\n{_srt_time(total)} --> {_srt_time(total + duration)}\n{lines}\n\n"
                    )
                total += duration
            output = work / "film.mp4"
            settings = {
                "operation": "compose",
                "output_path": str(output),
                "preset": "veryfast",
                "edit_decisions": {
                    "metadata": {
                        "compose_target": {
                            "width": width,
                            "height": height,
                            "fit": "pad",
                        }
                    },
                    "cuts": cuts,
                },
            }
            if subtitles:
                sub = work / "captions.srt"
                sub.write_text("".join(subtitles), encoding="utf-8")
                settings["subtitle_path"] = str(sub)
            if row["audio"]:
                audio = _media(row["audio"], _AUDIO)
                track = work / "soundtrack.m4a"
                _ffmpeg([
                    "-i",
                    str(audio),
                    "-af",
                    "apad",
                    "-t",
                    str(total),
                    "-c:a",
                    "aac",
                    str(track),
                ])
                settings["audio_path"] = str(track)
            runtime.invoke({"op": "compose", "settings": settings}, work, timeout=1800)
            probe = _probe(output)
            actual = float(probe.get("format", {}).get("duration", 0))
            if abs(actual - total) > max(0.3, 0.045 * len(cuts)) or not any(
                s.get("width") == width and s.get("height") == height
                for s in probe["streams"]
            ):
                raise ValueError("成片未通过时长或画幅校验")
            published = _published_file(
                output, f"director-{project_id}-r{row['revision']}.mp4", "video"
            )
        deliverable = {
            "project_id": project_id,
            "revision": row["revision"],
            "path": str(published),
            "url": media_url_for_path(published),
            "duration_seconds": actual,
            "width": width,
            "height": height,
            "engine": "OpenMontage/video_compose",
        }
        row.update(deliverable=deliverable, updated_at=time.time())
        _save(directory / "project.json", row)
        return deliverable


def _public_data(value, paths, depth=0):
    # Preserve upstream analysis measurements, without provider URLs or local scratch paths.
    if depth > 6:
        return None
    if isinstance(value, dict):
        return {
            k: _public_data(v, paths, depth + 1)
            for k, v in list(value.items())[:100]
            if k.lower()
            not in {
                "headers",
                "raw",
                "request",
                "response",
                "credentials",
                "authorization",
                "provider_response",
            }
            and not re.search(r"api.?key|token|password|secret", k, re.I)
        }
    if isinstance(value, list):
        return [_public_data(v, paths, depth + 1) for v in value[:128]]
    if isinstance(value, str):
        if value in paths:
            return paths[value]
        if value.startswith(("https://", "http://")) or os.path.isabs(value):
            return None
        value = re.sub(
            r"https?://\S+|Bearer\s+[A-Za-z0-9_.-]+", "[redacted]", value, flags=re.I
        )
        return re.sub(
            r"([?&](?:api_key|access_token|token|signature|key)=)[^&\s]+",
            r"\1[redacted]",
            value,
            flags=re.I,
        )[:2000]
    return value


def run_tool(project_id: str, key: str, settings: dict, request_id: str) -> dict:
    directory = _project(project_id)
    request_id = _identifier(request_id)
    if (
        not isinstance(settings, dict)
        or len(json.dumps(settings, allow_nan=False)) > 40000
    ):
        raise ValueError("工具参数过大或无效")
    fingerprint = hashlib.sha256(
        json.dumps([key, settings], sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    receipt = directory / "requests" / (request_id + ".json")
    receipt.parent.mkdir(exist_ok=True)
    with runtime.file_lock(receipt.with_suffix(".lock")):
        if receipt.is_file():
            previous = _read(receipt)
            if previous["arguments"] != fingerprint:
                raise ValueError("同一个请求编号不能用于不同操作")
            if previous.get("result"):
                return previous["result"]
            raise ValueError(
                "此请求已记录，请检查原作业结果后再决定是否使用新的请求编号"
            )
        tool = tool_info(key)
        if not tool["available"] or not tool["executable"]:
            raise ValueError("此工具当前不可运行，请检查工具详情中的依赖和配置")
        if set(settings) - tool["input_schema"]["properties"].keys():
            raise ValueError("参数包含未开放的字段，请查看工具参数说明")
        with tempfile.TemporaryDirectory(dir=directory, prefix="tool-") as temp:
            work = Path(temp)
            inputs = work / "inputs"
            inputs.mkdir()

            def stage(value, field):
                source = _media(
                    value,
                    {".srt", ".vtt"}
                    if field in {"subtitle_path", "subtitles_path", "srt_path"}
                    else _VIDEO | _IMAGE | _AUDIO,
                )
                dst = inputs / (uuid.uuid4().hex + source.suffix.lower())
                shutil.copyfile(source, dst)
                return str(dst)

            safe = dict(settings)
            for k, value in settings.items():
                if k in _PATH_KEYS:
                    if isinstance(value, list):
                        if not 1 <= len(value) <= 12:
                            raise ValueError("每次最多支持十二个素材")
                        safe[k] = [stage(v, k) for v in value]
                    else:
                        safe[k] = stage(value, k)
            _save(receipt, {"arguments": fingerprint, "state": "started"})
            try:
                if key == "dashscope_asr":
                    from szyg.integrations.cloud_inference_client import (
                        CloudInferenceClient,
                    )

                    audio_path = _media(safe.get("audio_url", ""), _AUDIO)
                    safe["audio_url"] = asyncio.run(
                        CloudInferenceClient().upload_reference(str(audio_path))
                    )
                response = runtime.invoke(
                    {"op": "run", "key": key, "settings": safe}, work, timeout=1200
                )
                artifacts = []
                published_paths = {}
                for index, path in enumerate(sorted(work.rglob("*"))):
                    if (
                        not path.is_file()
                        or path.is_symlink()
                        or not path.resolve().is_relative_to(work)
                        or path.is_relative_to(inputs)
                    ):
                        continue
                    ext = path.suffix.lower()
                    if ext in _VIDEO:
                        kind = "video"
                    elif ext in _IMAGE:
                        kind = "image"
                    elif ext in _AUDIO:
                        kind = "audio"
                    elif ext in {".srt", ".vtt", ".glb", ".json"} or (
                        key == "export_bundle" and ext in {".md", ".txt"}
                    ):
                        kind = "document"
                    else:
                        continue
                    if ext == ".json" and key not in {
                        "export_bundle",
                        "character_spec_generator",
                        "svg_rig_builder",
                        "pose_library_builder",
                        "action_timeline_compiler",
                    }:
                        # Provider sidecars can contain signed URLs and full request metadata.
                        continue
                    name = f"director-{project_id}-{request_id}-{index}{ext}"
                    output = _published_file(path, name, kind)
                    published_paths[str(path)] = media_url_for_path(output)
                    artifacts.append({
                        "kind": kind,
                        "url": media_url_for_path(output),
                        "name": name,
                    })
                data = _public_data(response["data"], published_paths)
                if key == "direct_clip_search":
                    # Keep license, creator, and a durable attribution link for every imported clip.
                    for original, clip in zip(
                        response["data"].get("clips", []), data.get("clips", [])
                    ):
                        link = urlsplit(original.get("source_url") or "")
                        if (
                            link.scheme in {"http", "https"}
                            and link.hostname
                            and not link.username
                        ):
                            clip["source_url"] = urlunsplit((
                                link.scheme,
                                link.hostname,
                                link.path,
                                "",
                                "",
                            ))
                result = {
                    "project_id": project_id,
                    "key": key,
                    "request_id": request_id,
                    "artifacts": artifacts,
                    "data": data,
                    "upstream_cost_usd": response["cost_usd"],
                }
                _save(
                    receipt,
                    {"arguments": fingerprint, "state": "succeeded", "result": result},
                )
                return result
            except Exception:
                _save(receipt, {"arguments": fingerprint, "state": "failed"})
                raise
