"""social-auto-upload API routes — exposes SAU adapter to the frontend."""

import asyncio
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/sau", tags=["social-auto-upload"])


class SAUUploadVideo(BaseModel):
    platform: str
    file_path: str
    title: str
    desc: str = ""
    tags: list[str] = []
    thumbnail_path: Optional[str] = None
    schedule: Optional[str] = None
    headless: bool = True
    account_id: Optional[str] = None
    target_account_ids: list[str] = []
    profile_id: Optional[str] = None


class SAUUploadNote(BaseModel):
    platform: str
    image_paths: list[str]
    title: str
    note: str = ""
    tags: list[str] = []
    schedule: Optional[str] = None
    headless: bool = True
    account_id: Optional[str] = None
    target_account_ids: list[str] = []
    profile_id: Optional[str] = None


class PublishTitleRequest(BaseModel):
    platform: str
    kind: str = "note"
    content: str = ""
    current_title: str = ""
    tags: list[str] = []


class PublishCopyRequest(BaseModel):
    platform: str
    kind: str = "note"
    assets: list[dict] = []
    content: str = ""
    current_title: str = ""
    current_body: str = ""
    tags: list[str] = []


def _publishing_config() -> dict:
    try:
        from szyg.config.loader import load_config

        return load_config().get("publishing", {}) or {}
    except Exception:
        return {}


def _publish_title_limit(platform: str, kind: str) -> int:
    cfg = _publishing_config()
    limits = cfg.get("title_limits") if isinstance(cfg.get("title_limits"), dict) else {}
    value = ((limits.get(platform) or {}) if isinstance(limits.get(platform), dict) else {}).get(kind)
    if value:
        return int(value)
    if platform in {"douyin", "xhs"} and kind == "note":
        return 20
    return 100


def _validate_publish_payload(platform: str, kind: str, title: str) -> None:
    limit = _publish_title_limit(platform, kind)
    if limit > 0 and len(title or "") > limit:
        platform_label = {"douyin": "抖音", "xhs": "小红书"}.get(platform, platform)
        kind_label = "图文" if kind == "note" else "视频"
        raise HTTPException(400, f"{platform_label}{kind_label}标题不能超过{limit}字符，当前{len(title or '')}字符")


def _ensure_not_desktop_assist_platform(platform: str) -> None:
    if (platform or "").strip().lower() == "tencent":
        raise HTTPException(400, "视频号当前采用桌面辅助接管发布，请从素材管理与发布中选择视频号账号。")


def _ensure_supported_publish_platform(platform: str, kind: str) -> None:
    platform = (platform or "").strip().lower()
    supported = {
        "video": {"douyin", "xhs", "kuaishou", "bilibili", "tencent", "youtube", "weibo"},
        "note": {"douyin", "xhs", "kuaishou", "tencent", "weibo"},
    }
    labels = {
        "douyin": "抖音",
        "xhs": "小红书",
        "kuaishou": "快手",
        "bilibili": "B站",
        "tencent": "视频号",
        "youtube": "YouTube",
        "weibo": "微博",
    }
    allowed = supported.get(kind, set())
    if platform in allowed:
        return
    kind_label = "图文" if kind == "note" else "视频"
    platform_label = labels.get(platform, platform or "未知平台")
    allowed_labels = "、".join(labels.get(item, item) for item in sorted(allowed))
    raise HTTPException(400, f"{platform_label}{kind_label}发布暂未接入，当前支持：{allowed_labels}")


async def _create_weibo_desktop_runs(body: SAUUploadVideo | SAUUploadNote, kind: str) -> dict:
    from szyg.channel_accounts import resolve_publish_targets
    from szyg.execution_kernel import get_execution_kernel
    from szyg.platforms.weibo_desktop import WeiboPublishPayload, get_weibo_desktop_publisher

    material_paths = getattr(body, "image_paths", []) if kind == "note" else [getattr(body, "file_path", "")]
    missing = [str(item) for item in material_paths if item and not Path(str(item)).expanduser().exists()]
    if kind == "note" and not material_paths:
        missing.append("图片素材为空")
    if kind == "video" and not getattr(body, "file_path", ""):
        missing.append("视频文件路径为空")
    if missing:
        kernel = get_execution_kernel()
        payload = {
            "platform": "weibo",
            "title": body.title,
            "desc": getattr(body, "desc", "") or getattr(body, "note", ""),
            "tags": body.tags,
            "file_path": getattr(body, "file_path", ""),
            "image_paths": getattr(body, "image_paths", []),
            "mode": kind,
        }
        run = kernel.create_run(
            "publish_video" if kind == "video" else "publish_note",
            "weibo",
            "desktop",
            payload,
            title=body.title or "微博桌面发布",
            source_task_id="desktop:weibo:material",
        )
        message = "File not found: " + ", ".join(missing)
        step = kernel.start_step(run["id"], "validate_material", "Validate Weibo material", "desktop", "validate_material")
        kernel.add_observation(run["id"], step["id"], "text", message)
        kernel.finish_step(step, "failed", message, error_code="material_missing")
        run = kernel.complete_run(run["id"], "failed", error_code="material_missing", error_message=message)
        return {"ok": True, "task_id": run["id"], "execution_id": run["id"], "task": run, "run": run}

    try:
        targets = resolve_publish_targets(
            "weibo",
            account_id=body.account_id or "",
            target_account_ids=body.target_account_ids,
            profile_id=body.profile_id or "",
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    publisher = get_weibo_desktop_publisher()
    runs = []
    for account in targets:
        payload = WeiboPublishPayload(
            title=body.title,
            desc=getattr(body, "desc", "") or getattr(body, "note", ""),
            tags=body.tags,
            file_path=getattr(body, "file_path", ""),
            asset_paths=getattr(body, "image_paths", []) or ([getattr(body, "file_path", "")] if getattr(body, "file_path", "") else []),
            mode=kind,
            auto_publish=True,
        )
        result = await publisher.publish(account, payload)
        runs.append(result.get("run") or {})
    if len(runs) == 1:
        run = runs[0]
        return {"ok": True, "task_id": run.get("id", ""), "execution_id": run.get("id", ""), "task": run, "run": run}
    batch_id = f"batch_{uuid.uuid4().hex[:8]}"
    return {
        "ok": True,
        "batch_id": batch_id,
        "task_id": runs[0].get("id", "") if runs else "",
        "execution_id": runs[0].get("id", "") if runs else "",
        "execution_ids": [run.get("id", "") for run in runs if run.get("id")],
        "tasks": runs,
        "runs": runs,
        "run": runs[0] if runs else None,
    }


def _clean_title(value: str, limit: int) -> str:
    title = (value or "").strip()
    title = re.sub(r"^[#\s\"'“”《》]+|[#\s\"'“”《》]+$", "", title)
    title = re.sub(r"\s+", "", title)
    title = re.sub(r"[#《》\"'“”]", "", title)
    return title[:limit] if limit > 0 else title


def _parse_title_response(raw: str, limit: int) -> tuple[str, list[str], str]:
    text = (raw or "").strip()
    data = None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                data = None
    if isinstance(data, dict):
        title = _clean_title(str(data.get("title") or ""), limit)
        candidates = [_clean_title(str(item), limit) for item in data.get("candidates") or [] if str(item).strip()]
        reason = str(data.get("reason") or "")
        if title:
            deduped = list(dict.fromkeys([item for item in [title, *candidates] if item]))
            return title, deduped[:3], reason
    lines = [line.strip(" -0123456789.、") for line in text.splitlines() if line.strip()]
    candidates = [_clean_title(line, limit) for line in lines if _clean_title(line, limit)]
    candidates = list(dict.fromkeys(candidates))
    title = candidates[0] if candidates else ""
    return title, candidates[:3], ""


def _clean_tags(items: list | str) -> list[str]:
    if isinstance(items, str):
        parts = re.split(r"[,，#\s]+", items)
    else:
        parts = [str(item) for item in items or []]
    tags = []
    for item in parts:
        tag = re.sub(r"^[#\s]+|[#\s]+$", "", str(item)).strip()
        if tag and tag not in tags:
            tags.append(tag[:20])
    return tags[:8]


def _clean_image_anchors(items: list | None) -> list[dict]:
    anchors: list[dict] = []
    if not isinstance(items, list):
        return anchors
    for item in items[:8]:
        if not isinstance(item, dict):
            continue
        asset_id = str(item.get("asset_id") or item.get("id") or "").strip()
        if not asset_id:
            continue
        try:
            anchor_after = int(item.get("anchor_after_paragraph") or item.get("after") or 1)
        except Exception:
            anchor_after = 1
        anchors.append({
            "asset_id": asset_id,
            "anchor_after_paragraph": max(1, min(anchor_after, 20)),
            "caption": str(item.get("caption") or "").strip()[:80],
        })
    return anchors


def _parse_publish_copy_response(raw: str, limit: int) -> tuple[str, list[str], str, list[str], list[dict], str]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    data = None
    try:
        data = json.loads(text)
    except Exception:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                data = None
    if not isinstance(data, dict):
        title, candidates, reason = _parse_title_response(text, limit)
        return title, candidates, "", [], [], reason
    title = _clean_title(str(data.get("title") or ""), limit)
    candidates = [_clean_title(str(item), limit) for item in data.get("candidates") or [] if str(item).strip()]
    body = str(data.get("body") or data.get("description") or "").strip()
    tags = _clean_tags(data.get("tags") or [])
    image_anchors = _clean_image_anchors(data.get("image_anchors"))
    reason = str(data.get("reason") or "")
    deduped = list(dict.fromkeys([item for item in [title, *candidates] if item]))
    return title, deduped[:3], body, tags, image_anchors, reason


def _clip_publish_assets(raw_assets: list[dict]) -> list[dict]:
    """Keep all text assets and a small visual set for model cost and stability."""
    clipped: list[dict] = []
    visual_count = 0
    for asset in raw_assets or []:
        asset_type = str(asset.get("type") or "").lower()
        if asset_type in {"image", "video"}:
            if visual_count >= 5:
                continue
            visual_count += 1
        clipped.append(asset)
    return clipped[:12]


@router.get("/platforms")
async def list_platforms():
    """列出 sau 支持的所有平台及登录状态。"""
    from szyg.integrations.social_auto_upload_adapter import get_sau_adapter
    adapter = get_sau_adapter()
    return {"platforms": adapter.list_platforms()}


@router.post("/generate-title")
async def generate_publish_title(body: PublishTitleRequest):
    """Generate a platform-compliant publish title from current content."""
    limit = _publish_title_limit(body.platform, body.kind)
    if not (body.content or body.current_title or body.tags):
        raise HTTPException(400, "缺少可用于生成标题的内容")
    platform_label = {"douyin": "抖音", "xhs": "小红书"}.get(body.platform, body.platform)
    kind_label = "图文" if body.kind == "note" else "视频"
    cfg = _publishing_config()
    model = str(cfg.get("title_model") or "doubao-seed-2-0-lite-260428")
    prompt = (
        "你是企业新媒体发布标题助手。请基于内容生成适合平台的一句话标题。\n"
        f"平台：{platform_label}\n"
        f"内容类型：{kind_label}\n"
        f"标题硬性上限：{limit}个中文字符，必须包含标点和数字一起计数，不能超过。\n"
        "要求：标题自然、具体、有点击欲，但不要夸张、不要引号、不要话题符号、不要换行。\n"
        "只输出 JSON：{\"title\":\"...\",\"candidates\":[\"...\",\"...\",\"...\"],\"reason\":\"...\"}\n\n"
        f"当前标题：{body.current_title}\n"
        f"标签：{' '.join(body.tags or [])}\n"
        f"正文/描述：{body.content[:2500]}"
    )
    try:
        from szyg.integrations.volcengine_client import VolcEngineClient

        client = VolcEngineClient()
        response = await client.chat(
            [
                {
                    "role": "system",
                    "content": "你是严格的发布标题生成器，只输出 JSON，不输出解释和思考过程。",
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=model,
            max_tokens=512,
            temperature=0.7,
        )
        raw = ((response.get("message") or {}).get("content") or "").strip()
        title, candidates, reason = _parse_title_response(raw, limit)
        if not title:
            raise ValueError("模型未返回可用标题")
        return {
            "ok": True,
            "title": title,
            "candidates": candidates,
            "limit": limit,
            "platform": body.platform,
            "kind": body.kind,
            "model": response.get("model") or model,
            "reason": reason,
        }
    except Exception as exc:
        raise HTTPException(502, f"标题生成失败：{exc}")


@router.post("/generate-publish-copy")
async def generate_publish_copy(body: PublishCopyRequest):
    """Generate publish title/body/tags from selected media and text assets."""
    limit = _publish_title_limit(body.platform, body.kind)
    if not (body.assets or body.content or body.current_title or body.current_body):
        raise HTTPException(400, "缺少可用于生成发布内容的素材")

    platform_label = {"douyin": "抖音", "xhs": "小红书", "kuaishou": "快手"}.get(body.platform, body.platform)
    kind_label = "图文" if body.kind == "note" else "视频"
    cfg = _publishing_config()
    text_model = str(cfg.get("title_model") or "doubao-seed-2-0-lite-260428")
    visual_model = ""
    visual_summary = ""
    text_notes: list[str] = []
    asset_summaries: list[dict] = []

    raw_assets = _clip_publish_assets(body.assets)
    if raw_assets:
        try:
            from szyg.api.content_graphic_routes import _graphic_model, _prepare_graphic_asset_inputs, _responses_content
            from szyg.api.video_endpoint import ComposeAssetRef, _dump_model, _extract_json_object
            from szyg.integrations.volcengine_client import VolcEngineClient

            refs = [ComposeAssetRef(**asset) for asset in raw_assets]
            prepared, visual_content, text_notes, warnings = _prepare_graphic_asset_inputs(refs)
            visual_model = _graphic_model()
            if visual_content:
                system = (
                    "你是企业内容发布素材理解助手。请真实读取图片和视频关键帧，"
                    "把素材转换成可用于社媒发布文案的文字信息。不要输出消极替换建议，"
                    "优先提炼主体、场景、情绪、风格、可用卖点、儿童化或生活化表达线索。只输出 JSON。"
                )
                user = {
                    "task": "理解发布前选中的素材",
                    "platform": platform_label,
                    "kind": kind_label,
                    "assets": [_dump_model(item) for item in prepared],
                    "text_notes": text_notes,
                    "output_schema": {
                        "summary": "整体素材摘要",
                        "assets": [{"id": "素材ID", "summary": "可用于发布文案的素材描述", "role": "用途"}],
                    },
                }
                client = VolcEngineClient(timeout=120)
                try:
                    response = await client.responses_text(
                        [
                            {
                                "role": "user",
                                "content": _responses_content(f"{system}\n\n{json.dumps(user, ensure_ascii=False)}", visual_content),
                            }
                        ],
                        model=visual_model,
                        max_output_tokens=2200,
                    )
                    raw = ((response.get("message") or {}).get("content") or "").strip()
                    data = _extract_json_object(raw) or {}
                    visual_summary = str(data.get("summary") or "").strip()
                    if isinstance(data.get("assets"), list):
                        asset_summaries = data.get("assets")[:8]
                finally:
                    await client.close()
            else:
                visual_summary = "本次未包含图片或视频素材。"
            if warnings:
                text_notes.extend([f"素材提示：{item}" for item in warnings])
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(502, f"视觉素材理解失败：{str(exc)[:300]}")

    content_parts = [
        f"视觉理解摘要：{visual_summary}" if visual_summary else "",
        "单素材摘要：" + json.dumps(asset_summaries, ensure_ascii=False) if asset_summaries else "",
        "\n\n".join(text_notes),
        body.content,
        body.current_body,
    ]
    combined_content = "\n\n".join([part for part in content_parts if part and part.strip()]).strip()
    if not combined_content and body.current_title:
        combined_content = body.current_title
    if not combined_content:
        raise HTTPException(400, "没有可用于生成发布内容的素材文字")

    prompt = (
        "你是企业新媒体发布文案助手。请基于视觉理解结果、已有文案和用户当前编辑内容，"
        "生成可直接填写到发布抽屉里的标题、正文和标签。\n"
        f"平台：{platform_label}\n"
        f"内容类型：{kind_label}\n"
        f"标题硬性上限：{limit}个中文字符，包含标点和数字一起计数，必须不超过。\n"
        "要求：\n"
        "1. 标题只是一句短语，不要换行、不要话题符号、不要引号。\n"
        "2. 正文要自然、有温度，适合真实用户发布，不要出现“需求：”“文案素材：”等内部字样。\n"
        "3. 如果用户要求儿童化、亲子化、宝妈口吻，要明显更软萌、更生活化。\n"
        "4. 标签输出 3-6 个，不带 #。\n"
        "5. 如果是图文发布，请根据正文段落决定图片展示锚点。image_anchors 中 asset_id 必须来自输入素材 ID，anchor_after_paragraph 表示插入到第几段之后。\n"
        "6. 不要编造价格、品牌授权、医学或绝对化效果。\n"
        "只输出 JSON：{\"title\":\"...\",\"candidates\":[\"...\",\"...\",\"...\"],\"body\":\"...\",\"tags\":[\"...\"],\"image_anchors\":[{\"asset_id\":\"...\",\"anchor_after_paragraph\":1,\"caption\":\"...\"}],\"reason\":\"...\"}\n\n"
        f"当前标题：{body.current_title}\n"
        f"当前标签：{' '.join(body.tags or [])}\n"
        f"素材与上下文：{combined_content[:4500]}"
    )
    try:
        from szyg.integrations.volcengine_client import VolcEngineClient

        client = VolcEngineClient()
        try:
            response = await client.chat(
                [
                    {"role": "system", "content": "你是严格的发布内容生成器，只输出 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                model=text_model,
                max_tokens=1200,
                temperature=0.55,
            )
        finally:
            await client.close()
        raw = ((response.get("message") or {}).get("content") or "").strip()
        title, candidates, next_body, next_tags, image_anchors, reason = _parse_publish_copy_response(raw, limit)
        if not title:
            raise ValueError("模型未返回可用标题")
        return {
            "ok": True,
            "title": title,
            "candidates": candidates,
            "body": next_body or body.current_body or body.content,
            "tags": next_tags or _clean_tags(body.tags),
            "image_anchors": image_anchors,
            "limit": limit,
            "platform": body.platform,
            "kind": body.kind,
            "model": response.get("model") or text_model,
            "visual_model": visual_model,
            "visual_summary": visual_summary,
            "asset_summaries": asset_summaries,
            "reason": reason,
        }
    except Exception as exc:
        raise HTTPException(502, f"发布内容生成失败：{exc}")


@router.post("/upload-video")
async def upload_video(body: SAUUploadVideo):
    """上传视频到指定平台。"""
    from szyg.integrations.social_auto_upload_adapter import get_sau_adapter
    _ensure_supported_publish_platform(body.platform, "video")
    if (body.platform or "").strip().lower() == "weibo":
        raise HTTPException(400, "微博视频发布使用桌面辅助异步执行，请调用异步发布入口。")
    _ensure_not_desktop_assist_platform(body.platform)
    adapter = get_sau_adapter()
    sched = datetime.strptime(body.schedule, "%Y-%m-%d %H:%M") if body.schedule else None
    result = await adapter.upload_video(
        platform=body.platform,
        file_path=body.file_path,
        title=body.title,
        desc=body.desc,
        tags=body.tags,
        thumbnail_path=body.thumbnail_path,
        schedule=sched,
        account_id=body.account_id,
        headless=body.headless,
    )
    return result


@router.post("/upload-video-async")
async def upload_video_async(body: SAUUploadVideo):
    """Create an observable ExecutionRun for a background video upload."""
    from szyg.execution_kernel import get_execution_kernel
    from szyg.channel_accounts import resolve_publish_targets

    _ensure_supported_publish_platform(body.platform, "video")
    if (body.platform or "").strip().lower() == "weibo":
        return await _create_weibo_desktop_runs(body, "video")
    _ensure_not_desktop_assist_platform(body.platform)
    try:
        targets = resolve_publish_targets(
            body.platform,
            account_id=body.account_id or "",
            target_account_ids=body.target_account_ids,
            profile_id=body.profile_id or "",
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    kernel = get_execution_kernel()
    batch_id = f"batch_{uuid.uuid4().hex[:8]}" if len(targets) > 1 or body.profile_id or body.target_account_ids else ""
    runs = []
    for account in targets:
        payload = {
            "platform": body.platform,
            "file_path": body.file_path,
            "title": body.title,
            "desc": body.desc,
            "tags": body.tags,
            "thumbnail_path": body.thumbnail_path,
            "schedule": body.schedule,
            "headless": body.headless,
            "account_id": account.get("id", ""),
            "account_label": account.get("label", ""),
            "account_file": account.get("session_path", ""),
            "account_name": account.get("sau_account_name", ""),
            "profile_id": body.profile_id or "",
            "batch_id": batch_id,
        }
        runs.append(kernel.create_sau_upload_video_run(payload))
    if len(runs) == 1 and not batch_id:
        task = kernel.sau_compatible_task(runs[0])
        return {"ok": True, "task_id": runs[0]["id"], "execution_id": runs[0]["id"], "task": task, "run": runs[0]}
    tasks = [kernel.sau_compatible_task(run) for run in runs]
    return {
        "ok": True,
        "batch_id": batch_id,
        "task_id": runs[0]["id"] if runs else "",
        "execution_id": runs[0]["id"] if runs else "",
        "execution_ids": [run["id"] for run in runs],
        "tasks": tasks,
        "task": tasks[0] if tasks else None,
        "run": runs[0] if runs else None,
        "runs": runs,
    }


@router.post("/upload-note")
async def upload_note(body: SAUUploadNote):
    """上传图文到指定平台。"""
    from szyg.integrations.social_auto_upload_adapter import get_sau_adapter
    _ensure_supported_publish_platform(body.platform, "note")
    if (body.platform or "").strip().lower() == "weibo":
        raise HTTPException(400, "微博图文发布使用桌面辅助异步执行，请调用异步发布入口。")
    _ensure_not_desktop_assist_platform(body.platform)
    _validate_publish_payload(body.platform, "note", body.title)
    adapter = get_sau_adapter()
    sched = datetime.strptime(body.schedule, "%Y-%m-%d %H:%M") if body.schedule else None
    result = await adapter.upload_note(
        platform=body.platform,
        image_paths=body.image_paths,
        title=body.title,
        note=body.note,
        tags=body.tags,
        schedule=sched,
        account_id=body.account_id,
        headless=body.headless,
    )
    return result


@router.post("/upload-note-async")
async def upload_note_async(body: SAUUploadNote):
    """Create an observable ExecutionRun for a background note upload."""
    from szyg.execution_kernel import get_execution_kernel
    from szyg.channel_accounts import resolve_publish_targets

    _ensure_supported_publish_platform(body.platform, "note")
    if (body.platform or "").strip().lower() == "weibo":
        return await _create_weibo_desktop_runs(body, "note")
    _ensure_not_desktop_assist_platform(body.platform)
    _validate_publish_payload(body.platform, "note", body.title)
    try:
        targets = resolve_publish_targets(
            body.platform,
            account_id=body.account_id or "",
            target_account_ids=body.target_account_ids,
            profile_id=body.profile_id or "",
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    kernel = get_execution_kernel()
    batch_id = f"batch_{uuid.uuid4().hex[:8]}" if len(targets) > 1 or body.profile_id or body.target_account_ids else ""
    runs = []
    for account in targets:
        payload = {
            "platform": body.platform,
            "image_paths": body.image_paths,
            "title": body.title,
            "note": body.note,
            "tags": body.tags,
            "schedule": body.schedule,
            "headless": body.headless,
            "account_id": account.get("id", ""),
            "account_label": account.get("label", ""),
            "account_file": account.get("session_path", ""),
            "account_name": account.get("sau_account_name", ""),
            "profile_id": body.profile_id or "",
            "batch_id": batch_id,
        }
        runs.append(kernel.create_sau_upload_note_run(payload))
    if len(runs) == 1 and not batch_id:
        task = kernel.sau_compatible_task(runs[0])
        return {"ok": True, "task_id": runs[0]["id"], "execution_id": runs[0]["id"], "task": task, "run": runs[0]}
    tasks = [kernel.sau_compatible_task(run) for run in runs]
    return {
        "ok": True,
        "batch_id": batch_id,
        "task_id": runs[0]["id"] if runs else "",
        "execution_id": runs[0]["id"] if runs else "",
        "execution_ids": [run["id"] for run in runs],
        "tasks": tasks,
        "task": tasks[0] if tasks else None,
        "run": runs[0] if runs else None,
        "runs": runs,
    }


@router.get("/tasks")
async def list_sau_tasks(limit: int = Query(50, ge=1, le=200)):
    """List recent social-auto-upload compatible background tasks."""
    from szyg.execution_kernel import get_execution_kernel

    tasks = get_execution_kernel().sau_compatible_tasks(limit=limit)
    try:
        from szyg.integrations.sau_task_manager import get_sau_task_manager
        seen = {task.get("id") for task in tasks}
        for item in get_sau_task_manager().list_tasks(limit=limit):
            if item.get("id") not in seen:
                tasks.append(item)
    except Exception:
        pass
    return {"tasks": tasks[:limit]}


@router.get("/tasks/{task_id}")
async def get_sau_task(task_id: str):
    """Get one social-auto-upload background task."""
    from szyg.execution_kernel import get_execution_kernel

    kernel = get_execution_kernel()
    task = next((item for item in kernel.sau_compatible_tasks(limit=200) if item.get("id") == task_id), None)
    if not task:
        try:
            from szyg.integrations.sau_task_manager import get_sau_task_manager
            task = get_sau_task_manager().get_task(task_id)
        except Exception:
            task = None
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.get("/check-login/{platform}")
async def check_login(platform: str, account_id: str = Query("")):
    """检查平台登录状态。"""
    from szyg.integrations.social_auto_upload_adapter import get_sau_adapter
    adapter = get_sau_adapter()
    return await adapter.check_login(platform, account_id=account_id or None)


@router.post("/login/{platform}")
async def login(platform: str, headless: bool = Query(False), account_id: str = Query("")):
    """触发平台扫码登录。"""
    from szyg.integrations.social_auto_upload_adapter import get_sau_adapter
    adapter = get_sau_adapter()
    return await adapter.login(platform, headless=headless, account_id=account_id or None)
