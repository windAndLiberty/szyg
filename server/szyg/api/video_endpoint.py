"""AI 视频生成 API — 火山引擎 Seedance 视频生成。"""

import base64
import io
import json
import mimetypes
import os
import re
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from szyg.data_path import DATA_DIR
from szyg.media_storage import get_media_output_dir, media_url_for_path, resolve_managed_media_path, resolve_media_file
from szyg.models.common import IntegrationError

router = APIRouter(prefix="/api/video", tags=["video"])

ALLOWED_DURATIONS = range(3, 31)
ALLOWED_SIZES = {"720p", "1080p", "4K"}
ALLOWED_RATIOS = {"16:9", "1:1", "9:16"}
MAX_OUTPUTS = 4
MAX_COMPOSE_ASSETS = 5
MATERIALS_FILE = DATA_DIR / "materials.json"
DEFAULT_VIDEO_MODEL = "doubao-seedance-1.5-pro"
DEFAULT_COMPOSE_VIDEO_MODEL = "doubao-seedance-1.5-pro"
SEEDANCE_15_MODEL = "doubao-seedance-1.5-pro"
SEEDANCE_25_MODEL = "doubao-seedance-2.5"
VISION_ANALYZE_MODEL = "doubao-seed-2-0-pro"
COMPOSE_PLANNER_MODEL = "doubao-seed-2-0-lite"
STORYBOARD_REMOTE_MODEL = "doubao-seed-1-6-lite-251015"
PROMPT_OPTIMIZE_MODEL = "doubao-seed-2-0-lite-260428"
VIDEO_MODEL_PROFILES = {
    "doubao-video": {
        "model": SEEDANCE_15_MODEL,
        "label": "Seedance 1.5 Pro",
        "sizes": {"720p"},
        "min_duration": 4,
        "max_duration": 12,
        "native_audio": True,
    },
    "doubao-seedance-1.5-pro": {
        "model": SEEDANCE_15_MODEL,
        "label": "Seedance 1.5 Pro",
        "sizes": {"720p"},
        "min_duration": 4,
        "max_duration": 12,
        "native_audio": True,
    },
    "doubao-seedance-2.0-fast": {
        "model": "doubao-seedance-2.0-fast",
        "label": "Seedance 2.0 Fast",
        "sizes": {"720p"},
        "min_duration": 4,
        "max_duration": 15,
        "native_audio": True,
    },
    "doubao-seedance-2.0": {
        "model": "doubao-seedance-2.0",
        "label": "Seedance 2.0",
        "sizes": {"720p", "1080p"},
        "min_duration": 4,
        "max_duration": 15,
        "native_audio": True,
    },
    "doubao-seedance-2.5": {
        "model": SEEDANCE_25_MODEL,
        "label": "Seedance 2.5",
        "sizes": {"720p", "1080p", "4K"},
        "min_duration": 3,
        "max_duration": 30,
        "native_audio": True,
    },
}


def _video_generation_config() -> dict[str, Any]:
    try:
        from szyg.config.loader import load_config
        return load_config().get("video", {}).get("generation", {}) or {}
    except Exception:
        return {}


def _configured_video_defaults() -> dict[str, Any]:
    cfg = _video_generation_config()
    defaults = cfg.get("defaults") if isinstance(cfg.get("defaults"), dict) else {}
    return {
        "model": str(cfg.get("default_model") or DEFAULT_VIDEO_MODEL),
        "compose_model": str(cfg.get("compose_default_model") or cfg.get("default_model") or DEFAULT_COMPOSE_VIDEO_MODEL),
        "duration": int(defaults.get("duration") or 15),
        "size": str(defaults.get("size") or "720p"),
        "ratio": str(defaults.get("ratio") or "9:16"),
        "native_audio": bool(defaults.get("native_audio", True)),
        "count": int(defaults.get("count") or 1),
    }


def _configured_compose_model(key: str, fallback: str) -> str:
    cfg = _video_generation_config()
    value = cfg.get(key)
    return str(value or fallback)


def _configured_storyboard_remote_model() -> str:
    return _configured_compose_model("storyboard_remote_model", STORYBOARD_REMOTE_MODEL)


def _configured_prompt_optimize_model() -> str:
    return _configured_compose_model("prompt_optimize_model", PROMPT_OPTIMIZE_MODEL)


def _configured_video_profiles() -> dict[str, dict[str, Any]]:
    profiles = {key: {**value, "sizes": set(value.get("sizes", set()))} for key, value in VIDEO_MODEL_PROFILES.items()}
    cfg = _video_generation_config()
    models = cfg.get("models") if isinstance(cfg.get("models"), dict) else {}
    for model_id, item in models.items():
        if not isinstance(item, dict):
            continue
        base = profiles.get(model_id, {})
        sizes = item.get("sizes", base.get("sizes", {"720p"}))
        profiles[model_id] = {
            **base,
            "model": str(item.get("provider_model") or item.get("model") or base.get("model") or model_id),
            "label": str(item.get("label") or base.get("label") or model_id),
            "sizes": set(sizes if isinstance(sizes, (list, tuple, set)) else [sizes]),
            "min_duration": int(item.get("min_duration") or base.get("min_duration") or 3),
            "max_duration": int(item.get("max_duration") or base.get("max_duration") or 15),
            "native_audio": bool(item.get("native_audio", base.get("native_audio", False))),
        }
    return profiles


class CreateRequest(BaseModel):
    prompt: str
    duration: int = 6
    size: str = "720p"          # 720p | 1080p | 4K
    ratio: str = "9:16"         # 16:9 | 1:1 | 9:16
    count: int = 1
    native_audio: bool = False
    prompt_optimize: bool = True
    final_prompt: str = ""
    model: str = DEFAULT_VIDEO_MODEL
    image_url: str = ""          # 图生视频 (可选)


class ComposeAssetRef(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    url: str = ""
    path: str = ""


class ComposeAnalyzeRequest(BaseModel):
    assets: list[ComposeAssetRef]


class ComposeQuestionOption(BaseModel):
    label: str
    value: str


class ComposeQuestion(BaseModel):
    id: str
    question: str
    type: str = "single"
    options: list[ComposeQuestionOption] = []
    recommended: str = ""


class ComposeAssetAnalysis(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    role: str = ""
    summary: str = ""
    status: str = "pending"
    provider_ref: str = ""
    provider_type: str = ""
    error: str = ""


class ComposeAnalyzeResponse(BaseModel):
    ok: bool = True
    model: str = VISION_ANALYZE_MODEL
    assets: list[ComposeAssetAnalysis]
    questions: list[ComposeQuestion]
    summary: str = ""
    warnings: list[str] = []


class ComposeAnswer(BaseModel):
    question_id: str
    answer: str


class ComposeVideoParams(BaseModel):
    platform: str = "douyin_xhs"
    scenario: str = "product_seed"
    duration: int = 15
    size: str = "1080p"
    ratio: str = "9:16"
    native_audio: bool = True
    count: int = 1
    user_instruction: str = ""
    model: str = DEFAULT_COMPOSE_VIDEO_MODEL


class ComposePrepareRequest(BaseModel):
    analysis: ComposeAnalyzeResponse
    answers: list[ComposeAnswer] = []
    params: ComposeVideoParams = ComposeVideoParams()


class ComposePrepareResponse(BaseModel):
    ok: bool = True
    storyboard: list[dict[str, Any]]
    final_prompt: str
    used_assets: list[ComposeAssetAnalysis]
    unsupported_features: list[str] = []
    warnings: list[str] = []
    summary: str = ""


class ComposeCreateRequest(BaseModel):
    prepared: ComposePrepareResponse
    params: ComposeVideoParams = ComposeVideoParams()


class OptimizePromptRequest(BaseModel):
    prompt: str
    duration: int = 6
    ratio: str = "9:16"
    native_audio: bool = False
    model: str = DEFAULT_VIDEO_MODEL
    style: str = ""


class OptimizePromptResponse(BaseModel):
    final_prompt: str
    negative_prompt: str = ""
    audio_prompt: str = ""
    summary: str = ""
    optimized_by: str = "template"


class StoryboardRequest(BaseModel):
    prompt: str
    duration: int = 15
    ratio: str = "9:16"
    native_audio: bool = False
    model: str = DEFAULT_VIDEO_MODEL
    shot_count: int = 0


class StoryboardShot(BaseModel):
    id: str
    title: str
    duration: int
    scene: str
    camera: str
    shot_size: str
    narration: str = ""
    audio: str = ""
    prompt: str


class StoryboardCharacterLock(BaseModel):
    enabled: bool = False
    character_name: str = ""
    identity: str = ""
    age_range: str = ""
    gender: str = ""
    appearance: str = ""
    hairstyle: str = ""
    outfit: str = ""
    temperament: str = ""
    consistency_prompt: str = ""


class StoryboardResponse(BaseModel):
    character_lock: list[StoryboardCharacterLock] = []
    shots: list[StoryboardShot]
    final_prompt: str
    summary: str = ""
    generated_by: str = "template"


def _video_profile(model: str) -> dict:
    return _configured_video_profiles().get(model) or {
        "model": model,
        "label": model,
        "sizes": {"720p", "1080p"},
        "min_duration": 3,
        "max_duration": 15,
        "native_audio": False,
    }


def _validate_video_params(duration: int, size: str, ratio: str, count: int, model: str = DEFAULT_VIDEO_MODEL, native_audio: bool = False):
    profile = _video_profile(model)
    if duration not in ALLOWED_DURATIONS:
        raise HTTPException(400, "时长仅支持 3-30 秒")
    if duration < profile["min_duration"]:
        raise HTTPException(400, f"{profile['label']} 当前最少支持 {profile['min_duration']} 秒")
    if duration > profile["max_duration"]:
        raise HTTPException(400, f"{profile['label']} 当前最多支持 {profile['max_duration']} 秒")
    if size not in ALLOWED_SIZES:
        raise HTTPException(400, "分辨率仅支持 720p、1080p 或 4K")
    if size not in profile["sizes"]:
        raise HTTPException(400, f"{profile['label']} 当前不支持 {size}，请切换 Seedance 2.5 商业大片模式")
    if ratio not in ALLOWED_RATIOS:
        raise HTTPException(400, "视频比例仅支持 16:9、1:1 或 9:16")
    if count < 1 or count > MAX_OUTPUTS:
        raise HTTPException(400, "生成数量仅支持 1-4 个")
    if native_audio and not profile["native_audio"]:
        raise HTTPException(400, f"{profile['label']} 当前不支持原生声音，请关闭后重试")


@router.get("/config")
async def video_config():
    defaults = _configured_video_defaults()
    profiles = _configured_video_profiles()
    return {
        "ok": True,
        "default_model": defaults["model"],
        "compose_default_model": defaults["compose_model"],
        "defaults": {
            "duration": defaults["duration"],
            "size": defaults["size"],
            "ratio": defaults["ratio"],
            "native_audio": defaults["native_audio"],
            "count": defaults["count"],
        },
        "models": [
            {
                "id": model_id,
                "provider_model": profile["model"],
                "label": profile["label"],
                "sizes": sorted(profile["sizes"]),
                "min_duration": profile["min_duration"],
                "max_duration": profile["max_duration"],
                "native_audio": profile["native_audio"],
            }
            for model_id, profile in profiles.items()
        ],
    }


def _dump_model(value: BaseModel) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value.dict()


def _register_generated_video_material(path: str, task_id: str = "") -> dict[str, Any] | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return None
    try:
        materials = json.loads(MATERIALS_FILE.read_text(encoding="utf-8")) if MATERIALS_FILE.exists() else []
    except Exception:
        materials = []
    resolved = str(file_path.resolve())
    existing = next((item for item in materials if str(item.get("path") or "") == resolved), None)
    item = {
        "id": existing.get("id") if existing else f"video:{str(uuid.uuid4())[:8]}",
        "name": file_path.name,
        "type": "video",
        "tags": ["一键成片", "AI生成"],
        "platform": "all",
        "url": media_url_for_path(file_path),
        "path": resolved,
        "size": file_path.stat().st_size,
        "created_at": existing.get("created_at") if existing else datetime.now().isoformat(),
        "source": "one_click_video",
        "task_id": task_id,
    }
    next_materials = [entry for entry in materials if str(entry.get("path") or "") != resolved]
    next_materials.append(item)
    MATERIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    MATERIALS_FILE.write_text(json.dumps(next_materials, ensure_ascii=False, indent=2), encoding="utf-8")
    return item


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None


def _check_compose_assets(assets: list[ComposeAssetRef]) -> None:
    if not assets:
        raise HTTPException(400, "请至少选择 1 个素材")
    if len(assets) > MAX_COMPOSE_ASSETS:
        raise HTTPException(400, f"一键成片最多支持 {MAX_COMPOSE_ASSETS} 个素材")


def _infer_asset_type(asset: ComposeAssetRef, path: Path | None = None) -> str:
    value = (asset.type or "").lower().strip()
    if value in {"image", "video", "audio", "text"}:
        return value
    name = (path.name if path else asset.name or asset.path or asset.url).lower()
    if name.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")):
        return "image"
    if name.endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
        return "video"
    if name.endswith((".mp3", ".wav", ".m4a", ".aac", ".flac")):
        return "audio"
    return "text"


def _resolve_compose_path(asset: ComposeAssetRef) -> Path | None:
    value = asset.path or asset.url
    if not value:
        return None
    try:
        return resolve_managed_media_path(value)
    except ValueError:
        pass
    try:
        path = Path(value).expanduser().resolve()
        return path if path.exists() else None
    except OSError:
        return None


def _file_to_data_url(path: Path, max_side: int = 768, max_bytes: int = 180_000) -> str:
    try:
        from PIL import Image

        with Image.open(path) as image:
            image.thumbnail((max_side, max_side))
            if image.mode in {"RGBA", "LA", "P"}:
                background = Image.new("RGB", image.size, (255, 255, 255))
                if image.mode == "P":
                    image = image.convert("RGBA")
                background.paste(image, mask=image.split()[-1] if image.mode in {"RGBA", "LA"} else None)
                image = background
            else:
                image = image.convert("RGB")

            for side, quality in ((max_side, 78), (640, 72), (512, 68), (384, 64)):
                candidate = image.copy()
                candidate.thumbnail((side, side))
                buffer = io.BytesIO()
                candidate.save(buffer, format="JPEG", quality=quality, optimize=True)
                data = buffer.getvalue()
                if len(data) <= max_bytes or side == 384:
                    encoded = base64.b64encode(data).decode("ascii")
                    return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        raw = path.read_bytes()
        if len(raw) > max_bytes:
            raise RuntimeError("图片过大且压缩失败，无法提交给视觉模型")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(raw).decode("ascii")
        return f"data:{mime};base64,{encoded}"


def _extract_video_frames(path: Path, limit: int = 3) -> list[Path]:
    temp_dir = Path(tempfile.mkdtemp(prefix="szyg_video_frames_"))
    pattern = str(temp_dir / "frame_%02d.jpg")
    commands = [
        ["ffmpeg", "-y", "-i", str(path), "-vf", f"fps=1/{max(1, limit)}", "-frames:v", str(limit), pattern],
        ["ffmpeg", "-y", "-i", str(path), "-vf", f"select=not(mod(n\\,{max(30, limit * 30)}))", "-frames:v", str(limit), pattern],
    ]
    last_error = ""
    for command in commands:
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                frames = sorted(temp_dir.glob("frame_*.jpg"))
                if frames:
                    return frames[:limit]
            last_error = (result.stderr or result.stdout or "")[-300:]
        except (OSError, subprocess.TimeoutExpired) as exc:
            last_error = str(exc)
    raise RuntimeError(last_error or "视频关键帧抽取失败")


def _normalize_questions(items: Any) -> list[ComposeQuestion]:
    questions: list[ComposeQuestion] = []
    if not isinstance(items, list):
        return questions
    for index, item in enumerate(items[:3]):
        if not isinstance(item, dict):
            continue
        raw_options = item.get("options") if isinstance(item.get("options"), list) else []
        options = []
        for opt in raw_options[:4]:
            if isinstance(opt, dict):
                label = str(opt.get("label") or opt.get("value") or "").strip()
                value = str(opt.get("value") or label).strip()
            else:
                label = str(opt).strip()
                value = label
            if label and value:
                options.append(ComposeQuestionOption(label=label, value=value))
        question = str(item.get("question") or "").strip()
        if not question:
            continue
        questions.append(ComposeQuestion(
            id=str(item.get("id") or f"q{index + 1}"),
            question=question,
            type=str(item.get("type") or "single"),
            options=options,
            recommended=str(item.get("recommended") or (options[0].value if options else "")).strip(),
        ))
    return questions


def _normalize_asset_analysis(items: Any, source_assets: list[ComposeAssetRef]) -> list[ComposeAssetAnalysis]:
    by_id = {asset.id or asset.name or str(i): asset for i, asset in enumerate(source_assets)}
    normalized: list[ComposeAssetAnalysis] = []
    if isinstance(items, list):
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            fallback = source_assets[min(index, len(source_assets) - 1)]
            asset_id = str(item.get("id") or fallback.id or fallback.name or f"asset_{index + 1}")
            source = by_id.get(asset_id, fallback)
            normalized.append(ComposeAssetAnalysis(
                id=asset_id,
                name=str(item.get("name") or source.name or Path(source.path or source.url or asset_id).name),
                type=str(item.get("type") or source.type or "text"),
                role=str(item.get("role") or "素材参考"),
                summary=str(item.get("summary") or "").strip(),
                status=str(item.get("status") or "success"),
                error=str(item.get("error") or "").strip(),
            ))
    return normalized


async def _analyze_assets_with_vision(req: ComposeAnalyzeRequest) -> ComposeAnalyzeResponse:
    from szyg.integrations.volcengine_client import VolcEngineClient

    model = _configured_compose_model("compose_vision_model", VISION_ANALYZE_MODEL)
    source_assets = req.assets
    visual_content: list[dict[str, Any]] = []
    text_notes: list[str] = []
    prepared: list[ComposeAssetAnalysis] = []
    warnings: list[str] = []

    for index, asset in enumerate(source_assets, start=1):
        path = _resolve_compose_path(asset)
        asset_type = _infer_asset_type(asset, path)
        asset_id = asset.id or f"asset_{index}"
        name = asset.name or (path.name if path else asset_id)
        if path is None or not path.exists():
            prepared.append(ComposeAssetAnalysis(id=asset_id, name=name, type=asset_type, status="failed", error="素材文件不存在"))
            continue
        try:
            if asset_type == "image":
                data_url = _file_to_data_url(path)
                visual_content.append({"type": "image_url", "image_url": {"url": data_url}})
                prepared.append(ComposeAssetAnalysis(id=asset_id, name=name, type="image", status="pending", provider_ref=data_url, provider_type="image_url"))
            elif asset_type == "video":
                frames = _extract_video_frames(path, limit=3)
                if not frames:
                    raise RuntimeError("未抽取到关键帧")
                first_ref = ""
                for frame in frames:
                    data_url = _file_to_data_url(frame)
                    first_ref = first_ref or data_url
                    visual_content.append({"type": "image_url", "image_url": {"url": data_url}})
                prepared.append(ComposeAssetAnalysis(id=asset_id, name=name, type="video", status="pending", provider_ref=first_ref, provider_type="image_url"))
            elif asset_type == "text":
                content = path.read_text(encoding="utf-8", errors="ignore")[:5000]
                text_notes.append(f"[{asset_id}] 文案素材 {name}:\n{content}")
                prepared.append(ComposeAssetAnalysis(
                    id=asset_id,
                    name=name,
                    type="text",
                    status="pending",
                    provider_ref=content,
                    provider_type="text",
                ))
            elif asset_type == "audio":
                warnings.append(f"{name} 是音频素材，v1 仅作为音频参考信息记录，暂不做深度音频理解。")
                prepared.append(ComposeAssetAnalysis(id=asset_id, name=name, type="audio", role="音频参考", summary="音频素材，建议作为配音、背景音乐或氛围参考。", status="success"))
            else:
                prepared.append(ComposeAssetAnalysis(id=asset_id, name=name, type=asset_type, status="failed", error="不支持的素材类型"))
        except Exception as exc:
            prepared.append(ComposeAssetAnalysis(id=asset_id, name=name, type=asset_type, status="failed", error=str(exc)[:200]))

    if not visual_content and not text_notes:
        raise HTTPException(400, "没有可用于视觉/文案理解的素材")

    system = (
        "你是企业短视频素材导演。必须真实基于输入图片、视频关键帧和文案内容做判断。"
        "输出严格 JSON，不要解释。"
    )
    user = {
        "task": "分析素材并生成一键成片的动态确认问题",
        "requirements": [
            "逐个素材判断角色：主商品、人物参考、场景参考、风格参考、脚本/卖点、音频参考",
            "提取适合企业营销视频的核心卖点和画面方向",
            "生成 1-3 个对成片效果影响最大的确认问题，每题最多 4 个选项",
            "不要编造看不到的信息",
        ],
        "assets": [_dump_model(item) for item in prepared],
        "text_notes": text_notes,
        "output_schema": {
            "summary": "整体素材理解摘要",
            "assets": [{"id": "素材ID", "name": "文件名", "type": "image|video|text|audio", "role": "素材用途", "summary": "素材内容摘要", "status": "success"}],
            "questions": [{"id": "q1", "question": "问题", "type": "single", "options": [{"label": "选项", "value": "值"}], "recommended": "推荐值"}],
            "warnings": ["注意事项"],
        },
    }
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": [{"type": "text", "text": json.dumps(user, ensure_ascii=False)}, *visual_content]},
    ]
    client = VolcEngineClient(timeout=120)
    try:
        result = await client.chat(messages=messages, model=model, temperature=0.2, max_tokens=3000)
        raw = result.get("message", {}).get("content", "")
    except IntegrationError as exc:
        raise HTTPException(502, f"视觉模型不可用，无法理解素材：{str(exc)[:300]}")
    finally:
        await client.close()
    data = _extract_json_object(raw)
    if not data:
        raise HTTPException(502, "视觉模型返回内容无法解析")

    model_assets = _normalize_asset_analysis(data.get("assets"), source_assets)
    by_id = {item.id: item for item in prepared}
    merged: list[ComposeAssetAnalysis] = []
    for item in model_assets or prepared:
        original = by_id.get(item.id)
        merged.append(ComposeAssetAnalysis(
            id=item.id,
            name=item.name or (original.name if original else ""),
            type=item.type or (original.type if original else ""),
            role=item.role or (original.role if original else ""),
            summary=item.summary or (original.summary if original else ""),
            status="success" if item.status == "pending" else item.status,
            provider_ref=original.provider_ref if original else item.provider_ref,
            provider_type=original.provider_type if original else item.provider_type,
            error=item.error or (original.error if original else ""),
        ))
    questions = _normalize_questions(data.get("questions"))
    if not questions:
        raise HTTPException(502, "视觉模型未生成确认问题")
    extra_warnings = data.get("warnings") if isinstance(data.get("warnings"), list) else []
    warnings.extend(str(item) for item in extra_warnings if item)
    return ComposeAnalyzeResponse(
        model=model,
        assets=merged,
        questions=questions[:3],
        summary=str(data.get("summary") or "").strip(),
        warnings=warnings,
    )


async def _prepare_compose_with_remote_model(req: ComposePrepareRequest) -> ComposePrepareResponse:
    from szyg.integrations.volcengine_client import VolcEngineClient

    model = _configured_compose_model("compose_planner_model", COMPOSE_PLANNER_MODEL)
    _validate_video_params(req.params.duration, req.params.size, req.params.ratio, req.params.count, req.params.model, req.params.native_audio)
    system = (
        "你是企业短视频分镜导演。基于视觉模型已经给出的素材理解结果和用户回答，"
        "整理为可执行分镜和 Seedance 2.5 最终提示词。"
        "不要调用外部工具，不要输出解释文字，只输出严格 JSON。"
    )
    user = {
        "analysis": _dump_model(req.analysis),
        "answers": [_dump_model(answer) for answer in req.answers],
        "params": _dump_model(req.params),
        "requirements": [
            "分镜数量 4-6 个，总时长接近目标时长",
            "final_prompt 必须包含商品/人物/场景一致性约束",
            "明确哪些素材被用于主商品、人物、场景、风格、脚本或音频参考",
            "适合中小企业短视频获客和发布",
            "如果 params.user_instruction 包含用户修改后的最终提示词或补充意见，必须在保留素材理解和用户回答上下文的基础上吸收这些修改，而不是从零重写",
        ],
        "output_schema": {
            "summary": "成片方案摘要",
            "storyboard": [{"id": "shot_1", "title": "镜头标题", "duration": 3, "scene": "画面", "camera": "运镜", "shot_size": "景别", "narration": "旁白", "audio": "声音", "prompt": "单镜头提示词"}],
            "final_prompt": "最终视频提示词",
            "warnings": ["注意事项"],
        },
    }
    client = VolcEngineClient(timeout=90)
    try:
        result = await client.chat([
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ], model=model, temperature=0.2, max_tokens=3500)
        raw = result.get("message", {}).get("content", "")
        data = _extract_json_object(raw)
    except IntegrationError as exc:
        raise HTTPException(502, f"远程轻量模型不可用，无法整理成片方案：{str(exc)[:300]}")
    except Exception as exc:
        raise HTTPException(502, f"远程轻量模型分镜整理失败：{str(exc)[:300]}")
    finally:
        await client.close()
    if not data:
        raise HTTPException(502, "远程轻量模型返回内容无法解析")

    storyboard = data.get("storyboard") if isinstance(data.get("storyboard"), list) else []
    if not storyboard:
        raise HTTPException(502, "远程轻量模型未生成分镜")
    used_assets = [asset for asset in req.analysis.assets if asset.status == "success"]
    warnings = [str(item) for item in data.get("warnings", [])] if isinstance(data.get("warnings"), list) else []
    return ComposePrepareResponse(
        storyboard=storyboard[:6],
        final_prompt=str(data.get("final_prompt") or "").strip(),
        used_assets=used_assets,
        unsupported_features=[],
        warnings=[*req.analysis.warnings, *warnings],
        summary=str(data.get("summary") or "").strip(),
    )


def _ratio_hint(ratio: str) -> str:
    return {
        "16:9": "横屏 16:9 构图，适合品牌片、产品展示和横版素材",
        "1:1": "方形 1:1 构图，主体居中，适合信息流素材",
        "9:16": "竖屏 9:16 构图，适合抖音、小红书和短视频投放",
    }.get(ratio, "清晰构图")


def _template_optimize_prompt(req: OptimizePromptRequest) -> OptimizePromptResponse:
    audio_prompt = ""
    if req.native_audio:
        audio_prompt = "生成与画面同步的环境声、轻微动作声和自然氛围音，避免突兀音乐和机械旁白。"
    final_prompt = (
        f"{req.prompt.strip()}。"
        f"生成一段 {req.duration} 秒短视频，{_ratio_hint(req.ratio)}。"
        "画面需要主体明确、动作连续、镜头运动自然、光线真实、细节清晰，"
        "适合企业营销获客场景，避免文字乱码、肢体变形、跳帧和过度夸张特效。"
    )
    if req.style:
        final_prompt += f"整体风格：{req.style}。"
    if audio_prompt:
        final_prompt += f"声音要求：{audio_prompt}"
    return OptimizePromptResponse(
        final_prompt=final_prompt,
        negative_prompt="低清晰度、模糊、畸形、文字乱码、跳帧、过度闪烁、主体漂移、无关水印",
        audio_prompt=audio_prompt,
        summary="已补充视频时长、画幅、镜头、光线、动作连续性和营销场景约束。",
        optimized_by="template",
    )


def _clamp_shot_count(count: int) -> int:
    return max(1, min(8, count))


def _distribute_duration(total: int, count: int) -> list[int]:
    total = max(count, total)
    base = total // count
    rest = total % count
    return [base + (1 if i < rest else 0) for i in range(count)]


def _normalize_shot_durations(shots: list[StoryboardShot], total_duration: int) -> list[StoryboardShot]:
    if not shots:
        return shots
    total_duration = max(1, int(total_duration or 1))
    if len(shots) > total_duration:
        shots = shots[:total_duration]
    durations = [max(1, int(shot.duration or 1)) for shot in shots]
    current_total = sum(durations)
    if current_total != total_duration:
        durations = _distribute_duration(total_duration, len(shots))
    normalized: list[StoryboardShot] = []
    for shot, duration in zip(shots, durations):
        if hasattr(shot, "model_copy"):
            normalized.append(shot.model_copy(update={"duration": duration}))
        else:
            normalized.append(shot.copy(update={"duration": duration}))
    return normalized


ROLE_KEYWORDS = (
    "人物", "角色", "真人", "人像", "主角", "老板", "员工", "顾客", "客户", "主播", "创始人",
    "老师", "医生", "店长", "店员", "销售员", "讲师", "模特", "男生", "女生", "男人", "女人",
    "男性", "女性", "小哥", "小姐姐", "大叔", "阿姨", "孩子", "儿童",
)


def _needs_character_lock(prompt: str) -> bool:
    return any(keyword in prompt for keyword in ROLE_KEYWORDS)


def _default_character_lock(prompt: str) -> StoryboardCharacterLock:
    identity = "企业营销短视频主角"
    if "老板" in prompt:
        identity = "本地小店老板"
    elif "员工" in prompt:
        identity = "企业员工"
    elif "顾客" in prompt or "客户" in prompt:
        identity = "目标顾客"
    elif "主播" in prompt:
        identity = "短视频主播"
    elif "老师" in prompt:
        identity = "专业老师"
    elif "医生" in prompt:
        identity = "专业医生"
    consistency_prompt = (
        f"主角始终为同一位30岁左右的{identity}，自然真实的东亚面孔，五官端正，"
        "黑色自然发型，穿简洁商务休闲服装，亲和自信。"
        "所有镜头保持同一人物的脸型、发型、服装、年龄和气质一致，不改变五官，不更换服装。"
    )
    return StoryboardCharacterLock(
        enabled=True,
        character_name="主角",
        identity=identity,
        age_range="30岁左右",
        gender="未指定",
        appearance="自然真实的东亚面孔，五官端正",
        hairstyle="黑色自然发型",
        outfit="简洁商务休闲服装",
        temperament="亲和、自信、适合企业营销",
        consistency_prompt=consistency_prompt,
    )


def _normalize_character_locks(raw: object, prompt: str) -> list[StoryboardCharacterLock]:
    needs_lock = _needs_character_lock(prompt)
    if not needs_lock:
        return []
    items: list[object]
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = [raw]
    else:
        items = []
    locks: list[StoryboardCharacterLock] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        enabled = bool(item.get("enabled", True))
        consistency_prompt = str(item.get("consistency_prompt") or "").strip()
        if enabled and not consistency_prompt:
            name = str(item.get("character_name") or f"角色{index + 1}").strip()
            identity = str(item.get("identity") or "企业营销短视频角色").strip()
            age_range = str(item.get("age_range") or "30岁左右").strip()
            gender = str(item.get("gender") or "未指定").strip()
            appearance = str(item.get("appearance") or "自然真实，五官端正").strip()
            hairstyle = str(item.get("hairstyle") or "发型保持一致").strip()
            outfit = str(item.get("outfit") or "服装保持一致").strip()
            temperament = str(item.get("temperament") or "自然、可信").strip()
            consistency_prompt = (
                f"{name}始终为同一位{age_range}{gender}{identity}，{appearance}，{hairstyle}，{outfit}，"
                f"{temperament}。所有镜头保持同一人物的脸型、发型、服装、年龄和气质一致，不改变五官，不更换服装。"
            )
        locks.append(StoryboardCharacterLock(
            enabled=enabled,
            character_name=str(item.get("character_name") or f"角色{index + 1}").strip(),
            identity=str(item.get("identity") or "").strip(),
            age_range=str(item.get("age_range") or "").strip(),
            gender=str(item.get("gender") or "").strip(),
            appearance=str(item.get("appearance") or "").strip(),
            hairstyle=str(item.get("hairstyle") or "").strip(),
            outfit=str(item.get("outfit") or "").strip(),
            temperament=str(item.get("temperament") or "").strip(),
            consistency_prompt=consistency_prompt,
        ))
    active_locks = [lock for lock in locks if lock.enabled and lock.consistency_prompt]
    if not active_locks and needs_lock:
        active_locks = [_default_character_lock(prompt)]
    return active_locks


def _apply_character_lock_to_shots(shots: list[StoryboardShot], locks: list[StoryboardCharacterLock]) -> list[StoryboardShot]:
    prompts = [lock.consistency_prompt for lock in locks if lock.enabled and lock.consistency_prompt]
    if not prompts:
        return shots
    consistency_text = " ".join(prompts)
    normalized: list[StoryboardShot] = []
    for shot in shots:
        prompt = shot.prompt.strip() or shot.scene.strip()
        if consistency_text not in prompt:
            prompt = f"{consistency_text} {prompt}"
        if hasattr(shot, "model_copy"):
            normalized.append(shot.model_copy(update={"prompt": prompt}))
        else:
            normalized.append(shot.copy(update={"prompt": prompt}))
    return normalized


def _compose_storyboard_prompt(shots: list[StoryboardShot], ratio: str, native_audio: bool, character_locks: list[StoryboardCharacterLock] | None = None) -> str:
    lines: list[str] = []
    active_locks = [lock for lock in (character_locks or []) if lock.enabled and lock.consistency_prompt]
    if active_locks:
        lines.append("角色一致性要求：")
        for lock in active_locks:
            lines.append(lock.consistency_prompt)
        lines.append("")
    lines.append(f"按照以下分镜生成一段连贯短视频，{_ratio_hint(ratio)}，镜头之间自然衔接。")
    for index, shot in enumerate(shots, start=1):
        lines.append(
            f"镜头{index}（{shot.duration}秒，{shot.title}）：{shot.scene}；"
            f"景别：{shot.shot_size}；镜头运动：{shot.camera}；"
            f"旁白：{shot.narration or '无'}；声音：{shot.audio or ('自然环境声' if native_audio else '无特殊声音要求')}；"
            f"单镜头提示词：{shot.prompt}。"
        )
    return "\n".join(lines)


def _template_storyboard(req: StoryboardRequest) -> StoryboardResponse:
    count = _clamp_shot_count(req.shot_count or min(5, max(1, req.duration)))
    durations = _distribute_duration(req.duration, count)
    character_locks = [_default_character_lock(req.prompt)] if _needs_character_lock(req.prompt) else []
    titles = ["开场吸引注意", "场景建立", "核心卖点", "使用体验", "信任强化", "行动号召", "细节补充", "品牌收束"]
    cameras = ["快速推进", "稳定跟拍", "缓慢推近", "横向移动", "特写停留", "轻微拉远", "环绕展示", "定格收尾"]
    shot_sizes = ["中景", "远景", "近景", "特写", "中近景", "近景", "特写", "中景"]
    shots: list[StoryboardShot] = []
    for index in range(count):
        title = titles[index]
        camera = cameras[index]
        shot_size = shot_sizes[index]
        scene = f"围绕“{req.prompt.strip()}”呈现{title}，画面主体明确，节奏适合企业营销短视频。"
        narration = "用一句简短、有行动指向的话强化用户收益。" if index in (0, count - 1) else "用自然口吻补充产品价值或场景信息。"
        audio = "保留与画面动作同步的环境声和轻微氛围音。" if req.native_audio else ""
        shot_prompt = (
            f"{scene} {shot_size}，{camera}，{_ratio_hint(req.ratio)}，"
            "光线真实，动作连续，避免文字乱码、跳帧和主体漂移。"
        )
        shots.append(StoryboardShot(
            id=f"shot_{index + 1}",
            title=title,
            duration=durations[index],
            scene=scene,
            camera=camera,
            shot_size=shot_size,
            narration=narration,
            audio=audio,
            prompt=shot_prompt,
        ))
    shots = _normalize_shot_durations(_apply_character_lock_to_shots(shots, character_locks), req.duration)
    return StoryboardResponse(
        character_lock=character_locks,
        shots=shots,
        final_prompt=_compose_storyboard_prompt(shots, req.ratio, req.native_audio, character_locks),
        summary=f"已拆分为 {count} 个镜头，总时长约 {sum(durations)} 秒。",
        generated_by="template",
    )


def _parse_storyboard_json(raw: str, ratio: str, native_audio: bool, generated_by: str, original_prompt: str, total_duration: int) -> StoryboardResponse | None:
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    data = json.loads(raw[start:end + 1])
    raw_shots = data.get("shots") or []
    if not isinstance(raw_shots, list) or not raw_shots:
        return None
    shots: list[StoryboardShot] = []
    for index, item in enumerate(raw_shots[:8]):
        if not isinstance(item, dict):
            continue
        shots.append(StoryboardShot(
            id=f"shot_{index + 1}",
            title=str(item.get("title") or f"镜头 {index + 1}").strip(),
            duration=max(1, int(item.get("duration") or 3)),
            scene=str(item.get("scene") or "").strip(),
            camera=str(item.get("camera") or "稳定镜头").strip(),
            shot_size=str(item.get("shot_size") or "中景").strip(),
            narration=str(item.get("narration") or "").strip(),
            audio=str(item.get("audio") or "").strip(),
            prompt=str(item.get("prompt") or item.get("scene") or "").strip(),
        ))
    if len(shots) < 1:
        return None
    character_locks = _normalize_character_locks(data.get("character_lock") or data.get("character_locks"), original_prompt)
    shots = _normalize_shot_durations(_apply_character_lock_to_shots(shots, character_locks), total_duration)
    return StoryboardResponse(
        character_lock=character_locks,
        shots=shots,
        final_prompt=_compose_storyboard_prompt(shots, ratio, native_audio, character_locks),
        summary=str(data.get("summary") or f"已拆分为 {len(shots)} 个镜头。").strip(),
        generated_by=generated_by,
    )


async def _try_storyboard_with_lite_model(req: StoryboardRequest) -> StoryboardResponse | None:
    try:
        from szyg.integrations.volcengine_client import VolcEngineClient
        model = _configured_storyboard_remote_model()
        system = (
            "你是企业短视频分镜导演。你的任务不是自由创作，而是把用户需求整理成可执行分镜。"
            "只有当用户明确描述人物、真人、主角、老板、员工、顾客、主播、创始人、老师、医生等角色时，才抽取统一角色设定。"
            "如果用户只描述物体、产品、饮品、食物、空间、自然景观、抽象意象或空镜头，character_lock 必须为空数组，不得补充人物。"
            "只输出 JSON，不要输出 Markdown。JSON 字段必须包含 character_lock, shots, summary。"
            "character_lock 可以是对象或数组，每个角色包含 enabled, character_name, identity, age_range, gender, appearance, hairstyle, outfit, temperament, consistency_prompt。"
            "shots 是数组，每项必须包含 title, duration, scene, camera, shot_size, narration, audio, prompt。"
            "要求：1. 如果 character_lock.enabled=true，每个 shot.prompt 都必须显式包含 consistency_prompt。"
            "2. 不允许在不同镜头中改变人物年龄、发型、服装、身份。"
            "3. 只有用户明确要求人物但没有给出人物细节时，才补充一个保守、稳定、适合企业营销的角色设定。"
            "4. 如果用户要求多人物，必须分别建立 character_lock 列表。"
            "5. 不要为了企业营销感强行加入办公室、商务男性、员工或主播；必须尊重用户原始画面主体。"
            "6. 分镜数量和每个镜头停留时间由内容节奏决定，不要固定为每秒一个镜头；所有镜头 duration 之和必须严格等于用户给定总时长。"
            "7. 分镜要适合 TikTok、抖音、小红书广告素材，镜头描述具体、可执行、可直接用于视频生成。"
        )
        user = {
            "prompt": req.prompt.strip(),
            "duration": req.duration,
            "ratio": req.ratio,
            "native_audio": req.native_audio,
            "shot_count": req.shot_count if req.shot_count > 0 else None,
            "requirements": [
                f"总视频时长必须严格等于 {req.duration} 秒，所有镜头 duration 相加必须等于 {req.duration}",
                "分镜数量由你根据内容节奏自行决定，允许 1-8 个镜头，不要固定为 1 秒一个分镜",
                "scene 只描述画面",
                "camera 描述镜头运动",
                "prompt 是单镜头视频生成提示词",
                "如果原始需求没有人物，不要输出任何人物、角色、办公室员工或商务装描述",
                "如果存在明确人物，每个 prompt 必须复用同一段 consistency_prompt",
                "不要输出解释文字",
            ],
        }
        client = VolcEngineClient()
        try:
            result = await client.responses_text(
                input_items=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": f"{system}\n\n任务参数：\n{json.dumps(user, ensure_ascii=False)}"},
                        ],
                    },
                ],
                model=model,
                max_output_tokens=1800,
            )
            content = result.get("message", {}).get("content", "")
            return _parse_storyboard_json(content, req.ratio, req.native_audio, model, req.prompt, req.duration)
        finally:
            await client.close()
    except Exception:
        return None


async def _try_storyboard_with_small_model(req: StoryboardRequest) -> StoryboardResponse | None:
    try:
        from szyg.integrations.local_llama_runtime import get_local_llama_runtime
        from szyg.integrations.local_small_model_client import LocalSmallModelClient
        system = (
            "你是企业短视频分镜导演。你的任务不是自由创作，而是把用户需求整理成可执行分镜。"
            "只有当用户明确描述人物、真人、主角、老板、员工、顾客、主播、创始人、老师、医生等角色时，才抽取统一角色设定。"
            "如果用户只描述物体、产品、饮品、食物、空间、自然景观、抽象意象或空镜头，character_lock 必须为空数组，不得补充人物。"
            "只输出 JSON，不要输出 Markdown。JSON 字段必须包含 character_lock, shots, summary。"
            "character_lock 可以是对象或数组，每个角色包含 enabled, character_name, identity, age_range, gender, appearance, hairstyle, outfit, temperament, consistency_prompt。"
            "shots 是数组，每项包含 title, duration, scene, camera, shot_size, narration, audio, prompt。"
            "如果 character_lock.enabled=true，每个 shot.prompt 都必须显式包含 consistency_prompt。"
            "不允许在不同镜头中改变人物年龄、发型、服装、身份。"
            "只有用户明确要求人物但没有给出人物细节时，才补充一个保守、稳定、适合企业营销的角色设定。"
            "如果用户要求多人物，必须分别建立 character_lock 列表。"
            "不要为了企业营销感强行加入办公室、商务男性、员工或主播；必须尊重用户原始画面主体。"
            "分镜数量和每个镜头停留时间由内容节奏决定，不要固定为每秒一个镜头；所有镜头 duration 之和必须严格等于用户给定总时长。"
        )
        user = {
            "prompt": req.prompt.strip(),
            "duration": req.duration,
            "ratio": req.ratio,
            "native_audio": req.native_audio,
            "shot_count": req.shot_count if req.shot_count > 0 else None,
            "requirements": [
                f"总视频时长必须严格等于 {req.duration} 秒，所有镜头 duration 相加必须等于 {req.duration}",
                "分镜数量由你根据内容节奏自行决定，允许 1-8 个镜头，不要固定为 1 秒一个分镜",
            ],
        }
        runtime = get_local_llama_runtime()
        state = await runtime.status()
        if not state.get("runtime_ready"):
            started = await runtime.start("qwen3-4b")
            if not started.get("success"):
                return None
        client = LocalSmallModelClient(default_model="qwen3-4b", timeout=45)
        try:
            result = await client.chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
                ],
                max_tokens=1800,
                temperature=0.35,
            )
            raw = result.get("message", {}).get("content", "")
            return _parse_storyboard_json(raw, req.ratio, req.native_audio, "qwen3-4b-local", req.prompt, req.duration)
        finally:
            await client.close()
    except Exception:
        return None


async def _try_optimize_with_small_model(req: OptimizePromptRequest) -> OptimizePromptResponse | None:
    try:
        from szyg.integrations.local_llama_runtime import get_local_llama_runtime
        from szyg.integrations.local_small_model_client import LocalSmallModelClient
        system = (
            "你是短视频生成提示词优化器。只输出 JSON，不要输出 Markdown。"
            "JSON 字段必须包含 final_prompt, negative_prompt, audio_prompt, summary。"
            "final_prompt 用中文，结构包含主体、动作、场景、镜头、光线、风格。"
        )
        user = {
            "prompt": req.prompt.strip(),
            "duration": req.duration,
            "ratio": req.ratio,
            "native_audio": req.native_audio,
            "style": req.style,
        }
        runtime = get_local_llama_runtime()
        state = await runtime.status()
        if not state.get("runtime_ready"):
            started = await runtime.start("qwen3-4b")
            if not started.get("success"):
                return None
        client = LocalSmallModelClient(default_model="qwen3-4b", timeout=45)
        try:
            result = await client.chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
                ],
                max_tokens=1000,
                temperature=0.35,
            )
            raw = result.get("message", {}).get("content", "")
        finally:
            await client.close()
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        data = json.loads(raw[start:end + 1])
        final_prompt = str(data.get("final_prompt", "")).strip()
        if not final_prompt:
            return None
        return OptimizePromptResponse(
            final_prompt=final_prompt,
            negative_prompt=str(data.get("negative_prompt", "")).strip(),
            audio_prompt=str(data.get("audio_prompt", "")).strip(),
            summary=str(data.get("summary", "")).strip(),
            optimized_by="qwen3-4b-local",
        )
    except Exception:
        return None


def _parse_optimize_json(raw: str, model: str) -> OptimizePromptResponse | None:
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    data = json.loads(raw[start:end + 1])
    final_prompt = str(data.get("final_prompt", "")).strip()
    if not final_prompt:
        return None
    return OptimizePromptResponse(
        final_prompt=final_prompt,
        negative_prompt=str(data.get("negative_prompt", "")).strip(),
        audio_prompt=str(data.get("audio_prompt", "")).strip(),
        summary=str(data.get("summary", "")).strip(),
        optimized_by=model,
    )


async def _try_optimize_with_remote_model(req: OptimizePromptRequest) -> OptimizePromptResponse | None:
    try:
        from szyg.integrations.volcengine_client import VolcEngineClient

        model = _configured_prompt_optimize_model()
        system = (
            "你是专业的视频生成提示词优化器，服务于 Seedance / Kling / Veo 类视频模型。"
            "你的任务是把用户原始视频描述改写成更适合视频模型执行的最终提示词。"
            "必须严格尊重用户原始描述，不得改变核心事件、主体、开始画面和禁止项。"
            "如果用户明确说“一开始就是某画面”“不要某画面”，必须在 final_prompt 中保留并强化。"
            "不要强行加入人物、办公室、企业代表、主播或营销话术，除非用户明确要求。"
            "可以补充镜头语言、运动节奏、材质细节、光线、风格、物理变化过程和声音氛围。"
            "只输出 JSON，不要输出 Markdown。JSON 字段必须包含 final_prompt, negative_prompt, audio_prompt, summary。"
        )
        user = {
            "prompt": req.prompt.strip(),
            "duration": req.duration,
            "ratio": req.ratio,
            "native_audio": req.native_audio,
            "style": req.style,
            "requirements": [
                "final_prompt 必须比原始 prompt 更具体、更可执行，不能只是原文复述",
                "保留用户写出的关键否定约束和起始画面约束",
                "强化镜头从第一帧开始的画面状态、主体动作、变化过程、结尾画面",
                "如有超现实转换，描述转换机制和视觉连续性",
                "negative_prompt 写出需要避免的错误画面",
                "audio_prompt 根据 native_audio 给出声音氛围，未开启原生声音也可提供参考",
            ],
        }
        client = VolcEngineClient()
        try:
            result = await client.responses_text(
                input_items=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": f"{system}\n\n任务参数：\n{json.dumps(user, ensure_ascii=False)}"},
                        ],
                    },
                ],
                model=model,
                max_output_tokens=1800,
            )
            content = result.get("message", {}).get("content", "")
            return _parse_optimize_json(content, model)
        finally:
            await client.close()
    except Exception:
        return None


@router.post("/optimize-prompt", response_model=OptimizePromptResponse)
async def optimize_prompt(req: OptimizePromptRequest):
    """使用远程轻量模型优化视频提示词。"""
    if not req.prompt.strip():
        raise HTTPException(400, "视频描述不能为空")
    _validate_video_params(req.duration, "720p", req.ratio, 1, req.model, req.native_audio)
    optimized = await _try_optimize_with_remote_model(req)
    if optimized:
        return optimized
    if os.environ.get("SZYG_VIDEO_API_OPTIMIZE_LOCAL_FALLBACK", "").strip() == "1":
        optimized = await _try_optimize_with_small_model(req)
        if optimized:
            return optimized
    if os.environ.get("SZYG_VIDEO_API_OPTIMIZE_TEMPLATE_FALLBACK", "").strip() == "1":
        return _template_optimize_prompt(req)
    raise HTTPException(502, f"真实提示词优化模型调用失败，请检查火山 {_configured_prompt_optimize_model()} 服务或将其配置为可用的 ep-xxxx 接入点")


@router.post("/storyboard", response_model=StoryboardResponse)
async def create_storyboard(req: StoryboardRequest):
    if not req.prompt.strip():
        raise HTTPException(400, "视频描述不能为空")
    if req.shot_count and (req.shot_count < 1 or req.shot_count > 8):
        raise HTTPException(400, "分镜数量仅支持 1-8 个")
    _validate_video_params(req.duration, "720p", req.ratio, 1, req.model, req.native_audio)
    generated = await _try_storyboard_with_lite_model(req)
    if generated:
        return generated
    if os.environ.get("SZYG_VIDEO_API_STORYBOARD_LOCAL_FALLBACK", "").strip() == "1":
        generated = await _try_storyboard_with_small_model(req)
        if generated:
            return generated
    if os.environ.get("SZYG_VIDEO_API_STORYBOARD_TEMPLATE_FALLBACK", "").strip() == "1":
        return _template_storyboard(req)
    raise HTTPException(502, f"真实分镜模型调用失败，请检查火山 {_configured_storyboard_remote_model()} 服务或将其配置为可用的 ep-xxxx 接入点")


@router.post("/compose/analyze", response_model=ComposeAnalyzeResponse)
async def analyze_composition(req: ComposeAnalyzeRequest):
    _check_compose_assets(req.assets)
    return await _analyze_assets_with_vision(req)


@router.post("/compose/prepare", response_model=ComposePrepareResponse)
async def prepare_composition(req: ComposePrepareRequest):
    if not req.analysis.assets:
        raise HTTPException(400, "缺少素材理解结果")
    return await _prepare_compose_with_remote_model(req)


def _compose_reference_enriched_prompt(prepared: ComposePrepareResponse) -> str:
    prompt = prepared.final_prompt.strip()
    visual_lines = []
    text_blocks = []
    for asset in prepared.used_assets:
        if asset.status != "success":
            continue
        if asset.type in {"image", "video"}:
            visual_lines.append(
                f"- {asset.name or asset.id}：{asset.role or '视觉参考'}。{asset.summary}".strip()
            )
        elif asset.type == "text" and asset.provider_ref.strip():
            content = asset.provider_ref.strip()
            text_blocks.append(
                f"【{asset.name or asset.id}】\n{content[:1800]}"
            )

    sections = [prompt]
    if visual_lines:
        sections.append(
            "必须参考并保持以下素材一致性：\n"
            + "\n".join(visual_lines)
            + "\n画面主体、产品特征、人物形象、场景氛围和风格需要尽量贴合参考素材，不要只按文字自由发挥。"
        )
    if text_blocks:
        sections.append(
            "必须吸收以下文案素材中的卖点、表达重点和产品信息：\n"
            + "\n\n".join(text_blocks)
            + "\n不要遗漏关键卖点，不要编造与文案冲突的产品参数。"
        )
    return "\n\n".join(section for section in sections if section.strip())


@router.post("/compose/create")
async def create_composition(req: ComposeCreateRequest):
    if not req.prepared.final_prompt.strip():
        raise HTTPException(400, "缺少最终视频提示词")
    _validate_video_params(
        req.params.duration,
        req.params.size,
        req.params.ratio,
        req.params.count,
        req.params.model,
        req.params.native_audio,
    )
    reference_assets = []
    unsupported_features = [item for item in req.prepared.unsupported_features if item != "audio_reference_input"]
    for asset in req.prepared.used_assets:
        if asset.provider_ref and asset.provider_type:
            reference_assets.append({
                "type": asset.provider_type,
                "url": asset.provider_ref,
                "role": asset.role or "reference",
                "asset_id": asset.id,
                "name": asset.name,
            })
    if not reference_assets and any(asset.type in {"image", "video"} for asset in req.prepared.used_assets):
        unsupported_features.append("visual_reference_upload")
        raise HTTPException(400, {
            "message": "当前没有可提交给 Seedance 2.5 的视觉参考素材",
            "unsupported_features": sorted(set(unsupported_features)),
        })

    profile = _video_profile(req.params.model)
    enriched_prompt = _compose_reference_enriched_prompt(req.prepared)
    supports_reference_assets = profile["model"] not in {
        "doubao-seedance-1.5-pro",
        "doubao-seedance-1-5-pro",
        "doubao-seedance-1-5-pro-251215",
    }
    submit_reference_assets = reference_assets if supports_reference_assets else []
    if reference_assets and not supports_reference_assets:
        unsupported_features.append("visual_reference_input")
    try:
        from szyg.integrations.volcengine_client import VolcEngineClient
        client = VolcEngineClient(output_dir=str(get_media_output_dir("video")))
        tasks = []
        for _ in range(req.params.count):
            result = await client.generate_video(
                prompt=enriched_prompt,
                reference_assets=submit_reference_assets,
                model=profile["model"],
                duration=req.params.duration,
                size=req.params.size,
                ratio=req.params.ratio,
                native_audio=req.params.native_audio,
            )
            tasks.append({
                "task_id": result["task_id"],
                "status": result["status"],
                "model": profile["model"],
                "model_label": profile["label"],
                "prompt": enriched_prompt,
                "duration": req.params.duration,
                "size": req.params.size,
                "ratio": req.params.ratio,
                "used_assets": [_dump_model(asset) for asset in req.prepared.used_assets],
                "unsupported_features": sorted(set(unsupported_features)),
            })
        await client.close()
        first = tasks[0]
        return {
            "ok": True,
            "task_id": first["task_id"],
            "tasks": tasks,
            "status": first["status"],
            "model": profile["model"],
            "model_label": profile["label"],
            "final_prompt": enriched_prompt,
            "used_assets": [_dump_model(asset) for asset in req.prepared.used_assets],
            "unsupported_features": sorted(set(unsupported_features)),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"一键成片提交失败: {str(exc)[:300]}")


@router.post("/create")
async def create_video(req: CreateRequest):
    """提交 AI 视频生成任务 (文生视频 / 图生视频)。

    火山引擎视频生成是异步任务，返回 task_id，前端轮询 /api/video/task/{task_id}。
    """
    if not req.prompt.strip():
        raise HTTPException(400, "视频描述不能为空")
    _validate_video_params(req.duration, req.size, req.ratio, req.count, req.model, req.native_audio)
    profile = _video_profile(req.model)

    try:
        from szyg.integrations.volcengine_client import VolcEngineClient
        client = VolcEngineClient(output_dir=str(get_media_output_dir("video")))
        prompt = (req.final_prompt or req.prompt).strip()
        tasks = []
        for _ in range(req.count):
            result = await client.generate_video(
                prompt=prompt,
                image_url=req.image_url or None,
                model=profile["model"],
                duration=req.duration,
                size=req.size,
                ratio=req.ratio,
                native_audio=req.native_audio,
            )
            tasks.append({
                "task_id": result["task_id"],
                "status": result["status"],
                "model": profile["model"],
                "model_label": profile["label"],
                "prompt": prompt,
                "duration": req.duration,
                "size": req.size,
                "ratio": req.ratio,
                "native_audio": req.native_audio,
            })
        await client.close()
        first = tasks[0]
        return {
            "ok": True,
            "task_id": first["task_id"],
            "tasks": tasks,
            "status": first["status"],
            "model": profile["model"],
            "model_label": profile["label"],
            "prompt": req.prompt.strip(),
            "final_prompt": prompt,
            "duration": req.duration,
            "size": req.size,
            "ratio": req.ratio,
            "native_audio": req.native_audio,
            "count": req.count,
            "unsupported_features": [],
        }
    except Exception as e:
        raise HTTPException(500, f"视频生成提交失败: {str(e)[:200]}")


@router.get("/task/{task_id}")
async def video_task_status(task_id: str, model: str = DEFAULT_VIDEO_MODEL):
    """查询 AI 视频生成任务状态。

    任务完成时自动下载视频到本地，返回可访问的视频 URL。
    """
    try:
        from szyg.integrations.volcengine_client import VolcEngineClient
        client = VolcEngineClient(output_dir=str(get_media_output_dir("video")))
        result = await client.get_video_task(task_id=task_id, model=model)

        # 如果已完成且有视频URL，下载到本地
        if result.get("status") == "succeeded" and result.get("video_url"):
            safe_task_id = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in task_id)
            output_name = f"ai_video_{safe_task_id}.mp4"
            cached_path = get_media_output_dir("video") / output_name
            if cached_path.exists() and cached_path.stat().st_size > 0:
                local_path = str(cached_path)
            else:
                local_path = await client.download_video(
                    result["video_url"],
                    output_name=output_name,
                )
            result["local_path"] = local_path
            result["video_url"] = media_url_for_path(local_path)
            result["download_url"] = media_url_for_path(local_path)
            result["material"] = _register_generated_video_material(local_path, task_id)

        await client.close()
        return result
    except Exception as e:
        raise HTTPException(500, f"查询视频任务失败: {str(e)[:200]}")


@router.get("/download/{filename}")
async def download_video(filename: str):
    """下载/播放生成的视频文件。"""
    try:
        path, _media_type = resolve_media_file("video", filename)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not path.exists():
        raise HTTPException(404, "视频文件不存在")
    return FileResponse(str(path), media_type="video/mp4", filename=filename)
