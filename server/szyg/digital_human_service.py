"""Seedance-backed digital presenter asset and render service."""

from __future__ import annotations

import base64
import json
import mimetypes
import re
import threading
import uuid
from pathlib import Path
from typing import Any

from szyg.config.loader import load_config
from szyg.data_path import DATA_DIR
from szyg.integrations.volcengine_client import VolcEngineClient
from szyg.media_storage import get_media_output_dir


ASSET_ROLES = {
    "avatar_reference",
    "product_reference",
    "background_reference",
    "motion_reference",
    "voice_reference",
    "brand_asset",
}
ASSET_ROLE_LABELS = {
    "avatar_reference": "人物",
    "product_reference": "产品",
    "background_reference": "背景",
    "motion_reference": "动作",
    "voice_reference": "声音",
    "brand_asset": "品牌",
}
STYLE_LABELS = {
    "professional": "专业商务",
    "lifestyle": "生活方式",
    "ecommerce": "电商口播",
    "education": "知识讲解",
    "technology": "科技品牌",
}
_ASSET_DIR = DATA_DIR / "digital_human" / "assets"
_ASSET_INDEX = DATA_DIR / "digital_human" / "assets.json"
_LOCK = threading.Lock()


def _config() -> dict[str, Any]:
    try:
        value = load_config().get("digital_human", {})
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def public_config() -> dict[str, Any]:
    cfg = _config()
    endpoint = str(cfg.get("endpoint") or "").strip()
    require_endpoint = bool(cfg.get("require_endpoint", True))
    configured = bool(endpoint) if require_endpoint else bool(endpoint or cfg.get("model"))
    return {
        "ok": True,
        "provider": "volcengine",
        "model_label": str(cfg.get("model_label") or "专业口播"),
        "configured": configured,
        "configuration_message": "数字人口播服务暂未开放" if not configured else "数字人口播服务可用",
        "durations": list(range(4, int(cfg.get("max_duration") or 30) + 1)),
        "sizes": list(cfg.get("sizes") or ["720p", "1080p", "4K"]),
        "ratios": ["9:16", "16:9", "1:1"],
        "max_assets": int(cfg.get("max_assets") or 50),
        "max_inline_asset_mb": int(cfg.get("max_inline_asset_mb") or 12),
        "native_audio": True,
    }


def _read_assets_unlocked() -> list[dict[str, Any]]:
    if not _ASSET_INDEX.exists():
        return []
    try:
        raw = json.loads(_ASSET_INDEX.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write_assets_unlocked(items: list[dict[str, Any]]) -> None:
    _ASSET_INDEX.parent.mkdir(parents=True, exist_ok=True)
    tmp = _ASSET_INDEX.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_ASSET_INDEX)


def _kind_for_file(filename: str, content_type: str = "") -> str:
    mime = content_type or mimetypes.guess_type(filename)[0] or ""
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    raise ValueError("仅支持图片、视频和音频素材")


def save_asset(filename: str, content_type: str, content: bytes, role: str) -> dict[str, Any]:
    if role not in ASSET_ROLES:
        raise ValueError("不支持的素材用途")
    kind = _kind_for_file(filename, content_type)
    if not content:
        raise ValueError("素材文件为空")
    max_upload_mb = int(_config().get("max_upload_mb") or 80)
    if len(content) > max_upload_mb * 1024 * 1024:
        raise ValueError(f"单个素材不能超过 {max_upload_mb}MB")

    suffix = Path(filename).suffix.lower()
    safe_stem = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", Path(filename).stem, flags=re.UNICODE).strip("_")[:48]
    asset_id = f"dha_{uuid.uuid4().hex[:12]}"
    stored_name = f"{asset_id}_{safe_stem or 'asset'}{suffix}"
    _ASSET_DIR.mkdir(parents=True, exist_ok=True)
    path = (_ASSET_DIR / stored_name).resolve()
    path.write_bytes(content)
    item = {
        "id": asset_id,
        "name": Path(filename).name,
        "role": role,
        "kind": kind,
        "content_type": content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
        "size": len(content),
        "path": str(path),
        "url": f"/api/digital-human/assets/{asset_id}",
    }
    with _LOCK:
        items = [entry for entry in _read_assets_unlocked() if entry.get("id") != asset_id]
        items.append(item)
        _write_assets_unlocked(items)
    return item


def get_asset(asset_id: str) -> dict[str, Any] | None:
    with _LOCK:
        item = next((entry for entry in _read_assets_unlocked() if entry.get("id") == asset_id), None)
    if not item:
        return None
    path = Path(str(item.get("path") or ""))
    return item if path.exists() and path.is_file() else None


def delete_asset(asset_id: str) -> bool:
    with _LOCK:
        items = _read_assets_unlocked()
        item = next((entry for entry in items if entry.get("id") == asset_id), None)
        _write_assets_unlocked([entry for entry in items if entry.get("id") != asset_id])
    if item:
        path = Path(str(item.get("path") or ""))
        if path.exists() and path.is_file():
            path.unlink(missing_ok=True)
        return True
    return False


def _provider_reference(item: dict[str, Any]) -> dict[str, str]:
    path = Path(str(item.get("path") or ""))
    if not path.exists() or not path.is_file():
        raise ValueError(f"素材不存在：{item.get('name') or item.get('id')}")
    max_inline = int(_config().get("max_inline_asset_mb") or 12) * 1024 * 1024
    if path.stat().st_size > max_inline:
        raise ValueError(f"素材 {item.get('name') or path.name} 过大，请压缩后重新上传")
    mime = str(item.get("content_type") or mimetypes.guess_type(path.name)[0] or "application/octet-stream")
    data_url = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
    kind = str(item.get("kind") or "")
    provider_type = {"image": "image_url", "video": "video_url", "audio": "audio_url"}.get(kind)
    if not provider_type:
        raise ValueError("不支持的素材类型")
    provider_role = {"motion_reference": "reference_video", "voice_reference": "reference_audio"}.get(
        str(item.get("role") or ""), "reference_image" if kind == "image" else f"reference_{kind}"
    )
    return {"type": provider_type, "url": data_url, "role": provider_role, "name": str(item.get("name") or "")}


def _render_prompt(payload: dict[str, Any], assets: list[dict[str, Any]]) -> str:
    layout = {"center": "人物居中半身", "left": "人物位于画面左侧", "right": "人物位于画面右侧", "full": "人物全身展示"}.get(
        str(payload.get("avatar_position") or "center"), "人物居中半身"
    )
    aliases = payload.get("asset_aliases") if isinstance(payload.get("asset_aliases"), dict) else {}
    role_counts: dict[str, int] = {}
    asset_lines = []
    for item in assets:
        role = str(item.get("role") or "")
        role_counts[role] = role_counts.get(role, 0) + 1
        fallback_alias = f"{ASSET_ROLE_LABELS.get(role, '素材')}{role_counts[role]}"
        raw_alias = str(aliases.get(str(item.get("id") or "")) or fallback_alias).strip().lstrip("@")
        alias = re.sub(r"[^\w\u4e00-\u9fff-]", "", raw_alias, flags=re.UNICODE)[:24] or fallback_alias
        asset_lines.append(f"- @{alias} = {item.get('name')}（{ASSET_ROLE_LABELS.get(role, '参考素材')}）")
    raw_style = str(payload.get("style") or "professional").strip()
    resolved_style = STYLE_LABELS.get(raw_style, raw_style)
    return (
        "生成一支商用级单人虚拟数字人口播视频。全片始终保持同一位人物的脸型、五官、发型、服装、年龄和气质一致，"
        "中文口型与台词精确同步，动作自然克制，不出现多余人物、畸形手指、面部闪烁或产品外观漂移。\n"
        "用户内容中的 @人物1、@产品1 等标记均指向下方同名参考素材，只用于控制画面，不属于口播台词，禁止朗读这些标记。\n"
        f"口播内容与画面要求：{str(payload.get('script') or '').strip()}\n"
        f"画面布局：{layout}；视觉风格：{resolved_style}；"
        f"背景要求：{str(payload.get('background_prompt') or '简洁、可信的商业场景')}。\n"
        "产品图片、品牌标识和人物参考必须保持原始视觉特征；不要重绘品牌文字，不要虚构产品参数。"
        + ("\n参考素材：\n" + "\n".join(asset_lines) if asset_lines else "")
    )


async def create_render(payload: dict[str, Any]) -> dict[str, Any]:
    cfg = _config()
    endpoint = str(cfg.get("endpoint") or "").strip()
    model = str(cfg.get("model") or "doubao-seedance-2.5").strip()
    if bool(cfg.get("require_endpoint", True)) and not endpoint:
        raise RuntimeError("数字人口播服务暂未开放")
    resolved_model = endpoint or model
    asset_ids = [str(value) for value in payload.get("asset_ids") or []]
    if not asset_ids:
        raise ValueError("请至少上传一张数字人参考图片")
    assets = []
    for asset_id in asset_ids:
        item = get_asset(asset_id)
        if not item:
            raise ValueError(f"素材不存在或已被移除：{asset_id}")
        assets.append(item)
    if not any(item.get("role") == "avatar_reference" for item in assets):
        raise ValueError("请上传人物参考图片")

    references = [_provider_reference(item) for item in assets]
    prompt = _render_prompt(payload, assets)
    client = VolcEngineClient(output_dir=str(get_media_output_dir("video")))
    try:
        result = await client.generate_video(
            prompt=prompt,
            reference_assets=references,
            model=resolved_model,
            duration=int(payload.get("duration") or 15),
            size=str(payload.get("size") or "1080p"),
            ratio=str(payload.get("ratio") or "9:16"),
            native_audio=bool(payload.get("native_audio", True)),
        )
    finally:
        await client.close()
    return {
        "ok": True,
        "task_id": result["task_id"],
        "status": result.get("status", "queued"),
        "model": resolved_model,
        "model_label": str(cfg.get("model_label") or "专业口播"),
        "prompt": prompt,
        "asset_ids": asset_ids,
    }
