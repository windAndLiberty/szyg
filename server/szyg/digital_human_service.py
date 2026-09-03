"""Local-first digital presenter projects and segmented render orchestration."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from szyg.cloud_auth import cloud_auth
from szyg.data_path import DATA_DIR
from szyg.integrations.cloud_inference_client import CloudInferenceClient
from szyg.integrations.public_media_resolver import download_public_media, resolve_public_media
from szyg.media_storage import get_media_output_dir, media_url_for_path
from szyg.video_cut_engine import concat_videos_normalized


ROOT = DATA_DIR / "digital_human"
ASSET_DIR = ROOT / "assets"
RENDER_DIR = ROOT / "renders"
FILES = {
    "assets": ROOT / "assets.json",
    "profiles": ROOT / "profiles.json",
    "inspirations": ROOT / "inspirations.json",
    "projects": ROOT / "projects.json",
    "renders": ROOT / "render_jobs.json",
}
LOCK = threading.RLock()

ASSET_ROLES = {
    "avatar_reference",
    "product_reference",
    "background_reference",
    "motion_reference",
    "voice_reference",
    "brand_asset",
    "inspiration_reference",
    "scene_reference",
}
ROLE_PREFIX = {
    "avatar_reference": "人物",
    "product_reference": "产品",
    "background_reference": "背景",
    "motion_reference": "动作",
    "voice_reference": "声音",
    "brand_asset": "品牌",
    "inspiration_reference": "灵感",
    "scene_reference": "背景",
}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_SUFFIXES = {".mp4", ".mov"}
AUDIO_SUFFIXES = {".mp3", ".wav"}
KIND_LIMITS = {"image": 30, "video": 200, "audio": 15}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _owner() -> str:
    try:
        cached = cloud_auth._cached_profile() or {}  # local encrypted session cache
        return str((cached.get("user") or {}).get("id") or "local")
    except Exception:
        return "local"


def _read(name: str) -> list[dict[str, Any]]:
    path = FILES[name]
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write(name: str, items: list[dict[str, Any]]) -> None:
    path = FILES[name]
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _owned(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    owner = _owner()
    return [item for item in items if str(item.get("owner_id") or owner) == owner]


def _upsert(name: str, item: dict[str, Any]) -> dict[str, Any]:
    with LOCK:
        items = _read(name)
        items = [row for row in items if row.get("id") != item.get("id")]
        items.append(item)
        _write(name, items)
    return item


def _remove(name: str, item_id: str) -> dict[str, Any] | None:
    with LOCK:
        items = _read(name)
        found = next((row for row in items if row.get("id") == item_id and row in _owned(items)), None)
        if found:
            _write(name, [row for row in items if row.get("id") != item_id])
        return found


def public_config() -> dict[str, Any]:
    session = cloud_auth.session()
    return {
        "ok": True,
        "configured": bool(session.get("authenticated")),
        "configuration_message": "数字人创作可用" if session.get("authenticated") else "登录后使用数字人创作",
        "duration": {"min": 4, "max": 60, "segment_max": 30},
        "sizes": ["480p", "720p"],
        "ratios": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"],
        "max_references": 50,
        "supported_profile_types": ["virtual"],
    }


def _kind(filename: str, content_type: str = "") -> str:
    suffix = Path(filename).suffix.lower()
    mime = content_type or mimetypes.guess_type(filename)[0] or ""
    if suffix in IMAGE_SUFFIXES or mime.startswith("image/"):
        return "image"
    if suffix in VIDEO_SUFFIXES or mime.startswith("video/"):
        return "video"
    if suffix in AUDIO_SUFFIXES or mime.startswith("audio/"):
        return "audio"
    raise ValueError("仅支持 JPG、PNG、WEBP、MP4、MOV、MP3 和 WAV 素材")


def save_asset(
    filename: str,
    content_type: str,
    content: bytes,
    role: str,
    *,
    profile_id: str = "",
    project_id: str = "",
    source: str = "upload",
) -> dict[str, Any]:
    if role not in ASSET_ROLES:
        raise ValueError("不支持的素材用途")
    kind = _kind(filename, content_type)
    if not content:
        raise ValueError("素材文件为空")
    limit = KIND_LIMITS[kind]
    if len(content) > limit * 1024 * 1024:
        raise ValueError(f"{kind} 素材不能超过 {limit}MB")
    asset_id = _id("dha")
    safe_name = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", Path(filename).name, flags=re.UNICODE)[:100]
    stored_name = f"{asset_id}_{safe_name or ('asset' + Path(filename).suffix.lower())}"
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    path = (ASSET_DIR / stored_name).resolve()
    path.write_bytes(content)
    item = {
        "id": asset_id,
        "owner_id": _owner(),
        "name": Path(filename).name,
        "role": role,
        "kind": kind,
        "content_type": content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
        "size": len(content),
        "path": str(path),
        "url": f"/api/digital-human/assets/{asset_id}",
        "profile_id": profile_id,
        "project_id": project_id,
        "source": source,
        "created_at": _now(),
    }
    return _upsert("assets", item)


def save_asset_file(
    source_path: str | Path,
    filename: str,
    content_type: str,
    role: str,
    *,
    profile_id: str = "",
    project_id: str = "",
    source: str = "import",
) -> dict[str, Any]:
    """Register a bounded local file without loading the whole video into memory."""
    source_file = Path(source_path).resolve()
    if role not in ASSET_ROLES:
        raise ValueError("不支持的素材用途")
    if not source_file.is_file():
        raise ValueError("素材文件不存在")
    kind = _kind(filename, content_type)
    size = source_file.stat().st_size
    if size <= 0:
        raise ValueError("素材文件为空")
    limit = KIND_LIMITS[kind]
    if size > limit * 1024 * 1024:
        raise ValueError(f"{kind} 素材不能超过 {limit}MB")
    asset_id = _id("dha")
    safe_name = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", Path(filename).name, flags=re.UNICODE)[:100]
    stored_name = f"{asset_id}_{safe_name or ('asset' + Path(filename).suffix.lower())}"
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    path = (ASSET_DIR / stored_name).resolve()
    shutil.move(str(source_file), str(path))
    item = {
        "id": asset_id,
        "owner_id": _owner(),
        "name": Path(filename).name,
        "role": role,
        "kind": kind,
        "content_type": content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
        "size": size,
        "path": str(path),
        "url": f"/api/digital-human/assets/{asset_id}",
        "profile_id": profile_id,
        "project_id": project_id,
        "source": source,
        "created_at": _now(),
    }
    return _upsert("assets", item)


def list_assets(*, profile_id: str = "", project_id: str = "") -> list[dict[str, Any]]:
    items = _owned(_read("assets"))
    if profile_id:
        items = [item for item in items if item.get("profile_id") == profile_id]
    if project_id:
        items = [item for item in items if item.get("project_id") == project_id]
    return sorted(items, key=lambda row: str(row.get("created_at") or ""), reverse=True)


def get_asset(asset_id: str) -> dict[str, Any] | None:
    item = next((row for row in _owned(_read("assets")) if row.get("id") == asset_id), None)
    return item if item and Path(str(item.get("path") or "")).is_file() else None


def delete_asset(asset_id: str) -> bool:
    item = _remove("assets", asset_id)
    if not item:
        return False
    Path(str(item.get("path") or "")).unlink(missing_ok=True)
    return True


def list_profiles() -> list[dict[str, Any]]:
    return sorted(_owned(_read("profiles")), key=lambda row: str(row.get("updated_at") or ""), reverse=True)


def get_profile(profile_id: str) -> dict[str, Any] | None:
    return next((row for row in list_profiles() if row.get("id") == profile_id), None)


def save_profile(payload: dict[str, Any], profile_id: str = "") -> dict[str, Any]:
    existing = get_profile(profile_id) if profile_id else None
    now = _now()
    profile = {
        **(existing or {}),
        "id": profile_id or _id("dhp"),
        "owner_id": _owner(),
        "name": str(payload.get("name") or "未命名数字人").strip()[:80],
        "profile_type": str(payload.get("profile_type") or "virtual"),
        "avatar_asset_ids": [str(value) for value in payload.get("avatar_asset_ids") or []],
        "voice_asset_id": str(payload.get("voice_asset_id") or ""),
        "cover_asset_id": str(payload.get("cover_asset_id") or ""),
        "default_style": str(payload.get("default_style") or "自然、可信的商业口播"),
        "outfit": str(payload.get("outfit") or ""),
        "notes": str(payload.get("notes") or ""),
        "created_at": (existing or {}).get("created_at") or now,
        "updated_at": now,
    }
    if profile["profile_type"] not in {"virtual", "real"}:
        raise ValueError("不支持的形象类型")
    if not profile["avatar_asset_ids"]:
        raise ValueError("请至少添加一项人物参考素材")
    for asset_id in [*profile["avatar_asset_ids"], profile["voice_asset_id"]]:
        if asset_id and not get_asset(asset_id):
            raise ValueError("形象引用的素材已不存在")
    return _upsert("profiles", profile)


def delete_profile(profile_id: str) -> bool:
    return bool(_remove("profiles", profile_id))


def list_inspirations() -> list[dict[str, Any]]:
    return sorted(_owned(_read("inspirations")), key=lambda row: str(row.get("updated_at") or ""), reverse=True)


def save_inspiration(payload: dict[str, Any]) -> dict[str, Any]:
    asset_id = str(payload.get("asset_id") or "")
    source_url = str(payload.get("source_url") or "").strip()
    if not asset_id and not source_url:
        raise ValueError("请上传灵感素材或填写公开链接")
    if source_url and not source_url.lower().startswith(("https://", "http://")):
        raise ValueError("请输入可公开访问的 HTTP 或 HTTPS 链接")
    if asset_id and not get_asset(asset_id):
        raise ValueError("灵感素材不存在")
    item = {
        "id": _id("dhi"),
        "owner_id": _owner(),
        "name": str(payload.get("name") or (get_asset(asset_id) or {}).get("name") or "灵感视频素材")[:100],
        "asset_id": asset_id,
        "source_url": source_url,
        "status": "ready",
        "analysis": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    return _upsert("inspirations", item)


def delete_inspiration(inspiration_id: str) -> bool:
    return bool(_remove("inspirations", inspiration_id))


def _json_object(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I | re.S)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not match:
            raise ValueError("素材分析结果格式异常，请重新分析")
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("素材分析结果格式异常，请重新分析")
    return value


async def analyze_inspiration(inspiration_id: str) -> dict[str, Any]:
    item = next((row for row in list_inspirations() if row.get("id") == inspiration_id), None)
    if not item:
        raise ValueError("灵感素材不存在")
    client = CloudInferenceClient(timeout=240)
    content: list[dict[str, Any]] = []
    asset = get_asset(str(item.get("asset_id") or "")) if item.get("asset_id") else None
    if asset:
        url = await client.upload_reference(str(asset["path"]))
        input_type = "input_image" if asset.get("kind") == "image" else "input_video"
        content.append({"type": input_type, f"{asset.get('kind')}_url": url})
    elif item.get("source_url"):
        resolved = await resolve_public_media(str(item["source_url"]))
        temp_path, filename, content_type = await download_public_media(
            resolved,
            ROOT / "imports",
            max_bytes=KIND_LIMITS["video"] * 1024 * 1024,
        )
        try:
            asset = save_asset_file(
                temp_path,
                filename,
                content_type,
                "inspiration_reference",
                source="public_link",
            )
        finally:
            temp_path.unlink(missing_ok=True)
        if resolved.title and item.get("name") == "灵感视频素材":
            item["name"] = resolved.title[:100]
        item["asset_id"] = asset["id"]
        item["resolved_media_url"] = resolved.url
        item["updated_at"] = _now()
        _upsert("inspirations", item)
        url = await client.upload_reference(str(asset["path"]))
        input_type = "input_image" if asset.get("kind") == "image" else "input_video"
        content.append({"type": input_type, f"{asset.get('kind')}_url": url})
    prompt = (
        "你是商业短视频策划。仅分析素材内容，不识别人名，不提取人物身份或声纹。"
        "请返回严格 JSON：transcript 完整文案；hook 开场钩子；selling_points 字符串数组；"
        "visual_structure 画面结构；shot_rhythm 镜头节奏；actions 人物动作数组；subtitles 字幕特征；"
        "cta 行动引导；segments 数组，每项含 start、end、spoken_text、visual_prompt、duration、visual_mode；"
        "reusable_scenes 字符串数组。不要输出 Markdown。"
    )
    content.append({"type": "input_text", "text": prompt})
    result = await client.responses_text([{"role": "user", "content": content}], max_output_tokens=6000, reasoning_effort="medium")
    analysis = _json_object(str((result.get("message") or {}).get("content") or ""))
    item.update({"analysis": analysis, "status": "analyzed", "updated_at": _now()})
    _upsert("inspirations", item)
    return item


def _new_scene(index: int, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return {
        "id": str(payload.get("id") or _id("scene")),
        "order": index,
        "spoken_text": str(payload.get("spoken_text") or ""),
        "visual_prompt": str(payload.get("visual_prompt") or ""),
        "duration": max(1, min(30, int(payload.get("duration") or 5))),
        "presenter_mode": str(payload.get("presenter_mode") or "full"),
        "visual_mode": str(payload.get("visual_mode") or "presenter"),
        "reference_asset_ids": [str(value) for value in payload.get("reference_asset_ids") or []],
        "transition": str(payload.get("transition") or "自然衔接"),
        "subtitle": bool(payload.get("subtitle", True)),
        "sound_prompt": str(payload.get("sound_prompt") or "保留清晰自然的人声"),
    }


def list_projects() -> list[dict[str, Any]]:
    return sorted(_owned(_read("projects")), key=lambda row: str(row.get("updated_at") or ""), reverse=True)


def get_project(project_id: str) -> dict[str, Any] | None:
    return next((row for row in list_projects() if row.get("id") == project_id), None)


def save_project(payload: dict[str, Any], project_id: str = "") -> dict[str, Any]:
    existing = get_project(project_id) if project_id else None
    scenes = [_new_scene(index + 1, row) for index, row in enumerate(payload.get("scenes") or (existing or {}).get("scenes") or [_new_scene(1)])]
    project = {
        **(existing or {}),
        "id": project_id or _id("project"),
        "owner_id": _owner(),
        "name": str(payload.get("name") or (existing or {}).get("name") or "未命名数字人作品")[:100],
        "profile_id": str(payload.get("profile_id") if "profile_id" in payload else (existing or {}).get("profile_id") or ""),
        "inspiration_ids": [str(value) for value in payload.get("inspiration_ids", (existing or {}).get("inspiration_ids") or [])],
        "scenes": scenes,
        "ratio": str(payload.get("ratio") or (existing or {}).get("ratio") or "9:16"),
        "size": str(payload.get("size") or (existing or {}).get("size") or "720p"),
        "visual_style": str(payload.get("visual_style") or (existing or {}).get("visual_style") or "现代、自然、可信"),
        "subtitle_enabled": bool(payload.get("subtitle_enabled", (existing or {}).get("subtitle_enabled", True))),
        "subtitle_style": str(payload.get("subtitle_style") or (existing or {}).get("subtitle_style") or "清晰简洁"),
        "version": int((existing or {}).get("version") or 0) + 1,
        "created_at": (existing or {}).get("created_at") or _now(),
        "updated_at": _now(),
    }
    total = sum(scene["duration"] for scene in scenes)
    if total > 60:
        raise ValueError("成片总时长不能超过 60 秒")
    return _upsert("projects", project)


def delete_project(project_id: str) -> bool:
    return bool(_remove("projects", project_id))


async def plan_project(project_id: str, instruction: str = "") -> dict[str, Any]:
    project = get_project(project_id)
    if not project:
        raise ValueError("项目不存在")
    inspirations = [row for row in list_inspirations() if row.get("id") in project.get("inspiration_ids", [])]
    context = [row.get("analysis") for row in inspirations if row.get("analysis")]
    current = project.get("scenes") or []
    prompt = (
        "你是数字人口播导演。根据灵感分析、当前场景和用户要求，返回严格 JSON，格式为 "
        "{\"scenes\":[{\"spoken_text\":\"\",\"visual_prompt\":\"\",\"duration\":5,"
        "\"presenter_mode\":\"full\",\"visual_mode\":\"presenter\",\"transition\":\"自然衔接\","
        "\"subtitle\":true,\"sound_prompt\":\"清晰自然的人声\"}]}。"
        "总时长 4 到 60 秒，单场景 1 到 30 秒。允许插入插画、产品特写、画中画和创意转场。"
        f"\n灵感分析：{json.dumps(context, ensure_ascii=False)}"
        f"\n当前场景：{json.dumps(current, ensure_ascii=False)}"
        f"\n用户要求：{instruction or '提炼为自然可信、具有商业转化力的口播'}"
    )
    client = CloudInferenceClient(timeout=120)
    result = await client.chat([{"role": "user", "content": prompt}], max_tokens=5000, temperature=0.5)
    planned = _json_object(str((result.get("message") or {}).get("content") or ""))
    scenes = [_new_scene(index + 1, row) for index, row in enumerate(planned.get("scenes") or [])]
    if not scenes:
        raise ValueError("没有生成可用的场景，请调整要求后重试")
    return {"scenes": scenes, "total_duration": sum(row["duration"] for row in scenes)}


async def generate_scene_image(project_id: str, scene_id: str, prompt: str) -> dict[str, Any]:
    project = get_project(project_id)
    if not project or not any(row.get("id") == scene_id for row in project.get("scenes") or []):
        raise ValueError("场景不存在")
    client = CloudInferenceClient(output_dir=str(ASSET_DIR), timeout=180)
    path = await client.generate_image(prompt, style=project.get("visual_style"), size="1440x2560" if project.get("ratio") == "9:16" else "2560x1440")
    source = Path(path)
    item = save_asset(source.name, mimetypes.guess_type(source.name)[0] or "image/png", source.read_bytes(), "scene_reference", project_id=project_id, source="generated")
    if source.resolve() != Path(item["path"]).resolve():
        source.unlink(missing_ok=True)
    return item


def _scene_hash(scene: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(scene, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _segment_scenes(scenes: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    duration = 0
    for scene in scenes:
        value = int(scene.get("duration") or 0)
        if current and duration + value > 30:
            groups.append(current)
            current, duration = [], 0
        current.append(scene)
        duration += value
    if current:
        groups.append(current)
    if len(groups) > 1 and sum(int(row.get("duration") or 0) for row in groups[-1]) < 4:
        tail = groups.pop()
        if sum(int(row.get("duration") or 0) for row in groups[-1] + tail) <= 30:
            groups[-1].extend(tail)
        else:
            tail[-1]["duration"] += 4 - sum(int(row.get("duration") or 0) for row in tail)
            groups.append(tail)
    return groups


def _asset_aliases(assets: list[dict[str, Any]]) -> dict[str, str]:
    counts: dict[str, int] = {}
    aliases: dict[str, str] = {}
    for asset in assets:
        prefix = ROLE_PREFIX.get(str(asset.get("role") or ""), "素材")
        counts[prefix] = counts.get(prefix, 0) + 1
        aliases[str(asset["id"])] = f"{prefix}{counts[prefix]}"
    return aliases


def _compile_prompt(project: dict[str, Any], profile: dict[str, Any], scenes: list[dict[str, Any]], assets: list[dict[str, Any]]) -> str:
    aliases = _asset_aliases(assets)
    lines = [
        "生成一段商用级虚拟数字人口播视频。全程保持同一虚拟人物的外貌、服装、声音和气质一致，中文口型准确。",
        f"整体视觉风格：{project.get('visual_style')}；数字人设定：{profile.get('default_style')}；服装：{profile.get('outfit') or '保持参考素材一致'}。",
    ]
    cursor = 0
    for index, scene in enumerate(scenes, 1):
        duration = int(scene.get("duration") or 0)
        refs = "、".join(f"@{aliases[value]}" for value in scene.get("reference_asset_ids") or [] if value in aliases)
        spoken = str(scene.get("spoken_text") or "").strip()
        lines.append(
            f"{cursor}-{cursor + duration}秒，场景{index}：{scene.get('visual_prompt') or '自然口播画面'}；"
            f"构图方式：{scene.get('visual_mode')}，数字人：{scene.get('presenter_mode')}；"
            f"对白：{{{spoken}}}；声音：<{scene.get('sound_prompt') or '清晰自然的人声'}>；"
            f"字幕：【{spoken}】；转场：{scene.get('transition') or '自然衔接'}"
            + (f"；使用{refs}" if refs else "")
        )
        cursor += duration
    lines.append("参考素材职责：")
    for asset in assets:
        lines.append(f"@{aliases[str(asset['id'])]} 用于{ROLE_PREFIX.get(str(asset.get('role') or ''), '画面')}一致性，不朗读素材名称。")
    lines.append("禁止出现多余人物、面部闪烁、畸形手指、品牌文字重绘、产品外观漂移或无关旁白。")
    return "\n".join(lines)


def _render_assets(project: dict[str, Any], profile: dict[str, Any], scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = [*profile.get("avatar_asset_ids", []), profile.get("voice_asset_id", "")]
    for scene in scenes:
        ids.extend(scene.get("reference_asset_ids") or [])
    unique = list(dict.fromkeys(str(value) for value in ids if value))
    if len(unique) > 50:
        raise ValueError("单次生成最多使用 50 个参考素材")
    assets = []
    for asset_id in unique:
        asset = get_asset(asset_id)
        if not asset:
            raise ValueError("项目引用的素材已不存在")
        assets.append(asset)
    counts = {"image": 0, "video": 0, "audio": 0}
    for asset in assets:
        kind = str(asset.get("kind") or "")
        if kind in counts:
            counts[kind] += 1
    if counts["image"] > 30:
        raise ValueError("单次生成最多使用 30 个图片参考")
    if counts["video"] > 10:
        raise ValueError("单次生成最多使用 10 个视频参考")
    if counts["audio"] > 10:
        raise ValueError("单次生成最多使用 10 个声音参考")
    return assets


async def _provider_references(
    client: CloudInferenceClient,
    assets: list[dict[str, Any]],
    url_cache: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    url_cache = url_cache if url_cache is not None else {}
    result = []
    for asset in assets:
        kind = str(asset.get("kind") or "")
        asset_id = str(asset.get("id") or "")
        if asset_id not in url_cache:
            url_cache[asset_id] = await client.upload_reference(str(asset["path"]))
        result.append({
            "type": f"{kind}_url",
            "url": url_cache[asset_id],
            "role": "reference_audio" if asset.get("role") == "voice_reference" and kind == "audio" else f"reference_{kind}",
        })
    return result


def list_renders(project_id: str = "") -> list[dict[str, Any]]:
    items = _owned(_read("renders"))
    if project_id:
        items = [item for item in items if item.get("project_id") == project_id]
    return sorted(items, key=lambda row: str(row.get("created_at") or ""), reverse=True)


def get_render(render_id: str) -> dict[str, Any] | None:
    return next((row for row in list_renders() if row.get("id") == render_id), None)


async def create_render(project_id: str) -> dict[str, Any]:
    project = get_project(project_id)
    if not project:
        raise ValueError("项目不存在")
    profile = get_profile(str(project.get("profile_id") or ""))
    if not profile:
        raise ValueError("请选择数字人形象")
    if profile.get("profile_type") != "virtual":
        raise ValueError("当前版本仅支持虚拟人物生成，真人形象将在授权能力开放后支持")
    if not profile.get("voice_asset_id") or not get_asset(str(profile.get("voice_asset_id"))):
        raise ValueError("当前数字人没有可用声音，请先绑定音频或有声视频")
    scenes = project.get("scenes") or []
    total_duration = sum(int(row.get("duration") or 0) for row in scenes)
    if total_duration < 4 or total_duration > 60:
        raise ValueError("成片总时长需要在 4 到 60 秒之间")
    groups = _segment_scenes(scenes)
    client = CloudInferenceClient(output_dir=str(RENDER_DIR), timeout=240)
    segments = []
    for index, group in enumerate(groups, 1):
        assets = _render_assets(project, profile, group)
        prompt = _compile_prompt(project, profile, group, assets)
        duration = max(4, sum(int(row.get("duration") or 0) for row in group))
        segments.append({
            "id": _id("segment"), "index": index, "scene_ids": [row["id"] for row in group],
            "scene_hashes": [_scene_hash(row) for row in group], "duration": duration,
            "prompt": prompt, "asset_ids": [row["id"] for row in assets],
            "task_id": "", "status": "pending", "video_path": "", "error": "",
        })
    job = {
        "id": _id("render"), "owner_id": _owner(), "project_id": project_id,
        "project_version": project.get("version"), "status": "processing", "progress": 5,
        "segments": segments, "output_path": "", "output_url": "", "material": None,
        "created_at": _now(), "updated_at": _now(),
    }
    _upsert("renders", job)
    reference_urls: dict[str, str] = {}
    for segment in job["segments"]:
        assets = [get_asset(value) for value in segment["asset_ids"]]
        resolved = [value for value in assets if value]
        try:
            task = await client.generate_presenter_video(
                segment["prompt"], await _provider_references(client, resolved, reference_urls),
                duration=segment["duration"], size=project.get("size") or "720p",
                ratio=project.get("ratio") or "9:16",
                idempotency_key=f"{project_id}:{project.get('version')}:{segment['index']}:{hashlib.sha256(segment['prompt'].encode()).hexdigest()[:12]}",
            )
            segment.update({"task_id": task["task_id"], "status": task["status"]})
        except Exception as exc:
            segment.update({"status": "failed", "error": str(exc) or "生成任务提交失败"})
            job["status"] = "failed"
        job["updated_at"] = _now()
        _upsert("renders", job)
    return job


def _register_material(path: Path, project: dict[str, Any], render_id: str) -> dict[str, Any]:
    materials_path = DATA_DIR / "materials.json"
    try:
        items = json.loads(materials_path.read_text(encoding="utf-8")) if materials_path.exists() else []
        if not isinstance(items, list):
            items = []
    except (OSError, json.JSONDecodeError):
        items = []
    item = {
        "id": f"digital-human:{render_id}", "name": f"{project.get('name') or '数字人口播'}.mp4",
        "type": "video", "tags": ["数字人创作"], "platform": "all", "source": "digital_human",
        "url": media_url_for_path(path), "path": str(path.resolve()), "size": path.stat().st_size,
        "created_at": _now(),
    }
    items = [row for row in items if row.get("id") != item["id"]]
    items.append(item)
    materials_path.parent.mkdir(parents=True, exist_ok=True)
    temp = materials_path.with_suffix(".tmp")
    temp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(materials_path)
    return item


async def refresh_render(render_id: str) -> dict[str, Any]:
    job = get_render(render_id)
    if not job:
        raise ValueError("生成任务不存在")
    if job.get("status") in {"succeeded", "failed"}:
        return job
    client = CloudInferenceClient(output_dir=str(RENDER_DIR), timeout=240)
    for segment in job.get("segments") or []:
        if segment.get("status") == "succeeded" and segment.get("video_path"):
            continue
        result = await client.get_video_task(str(segment.get("task_id") or ""))
        segment["status"] = result.get("status") or "processing"
        segment["error"] = result.get("error") or ""
        if segment["status"] == "succeeded" and result.get("video_url"):
            segment["video_path"] = await client.download_video(
                str(result["video_url"]), f"{render_id}_{segment['index']:02d}.mp4", str(RENDER_DIR / render_id)
            )
    statuses = [row.get("status") for row in job.get("segments") or []]
    completed = sum(status == "succeeded" for status in statuses)
    job["progress"] = min(95, int(completed / max(1, len(statuses)) * 90) + 5)
    if any(status == "failed" for status in statuses):
        job["status"] = "failed"
    elif statuses and all(status == "succeeded" for status in statuses):
        project = get_project(str(job.get("project_id") or "")) or {}
        output_dir = get_media_output_dir("video")
        output = output_dir / f"digital_human_{render_id}.mp4"
        paths = [str(row["video_path"]) for row in job["segments"]]
        if len(paths) == 1:
            shutil.copy2(paths[0], output)
        else:
            concat_videos_normalized(paths, str(output), ratio=project.get("ratio") or "9:16")
        job.update({
            "status": "succeeded", "progress": 100, "output_path": str(output),
            "output_url": media_url_for_path(output), "material": _register_material(output, project, render_id),
        })
    else:
        job["status"] = "processing"
    job["updated_at"] = _now()
    return _upsert("renders", job)


async def retry_segment(render_id: str, segment_id: str) -> dict[str, Any]:
    job = get_render(render_id)
    if not job:
        raise ValueError("生成任务不存在")
    segment = next((row for row in job.get("segments") or [] if row.get("id") == segment_id), None)
    if not segment:
        raise ValueError("生成片段不存在")
    project = get_project(str(job.get("project_id") or "")) or {}
    client = CloudInferenceClient(timeout=240)
    assets = [get_asset(value) for value in segment.get("asset_ids") or []]
    resolved = [value for value in assets if value]
    task = await client.generate_presenter_video(
        str(segment.get("prompt") or ""), await _provider_references(client, resolved),
        duration=int(segment.get("duration") or 4), size=project.get("size") or "720p",
        ratio=project.get("ratio") or "9:16", idempotency_key=f"{render_id}:{segment_id}:{uuid.uuid4().hex}",
    )
    segment.update({"task_id": task["task_id"], "status": task["status"], "video_path": "", "error": ""})
    job.update({"status": "processing", "progress": 5, "updated_at": _now()})
    return _upsert("renders", job)


__all__ = [
    "ASSET_ROLES", "public_config", "save_asset", "list_assets", "get_asset", "delete_asset",
    "list_profiles", "get_profile", "save_profile", "delete_profile",
    "list_inspirations", "save_inspiration", "analyze_inspiration", "delete_inspiration",
    "list_projects", "get_project", "save_project", "delete_project", "plan_project", "generate_scene_image",
    "list_renders", "get_render", "create_render", "refresh_render", "retry_segment",
]
