"""One-click graphic post generation from selected media assets."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from szyg.config.loader import load_config
from szyg.data_path import DATA_DIR
from szyg.integrations.volcengine_client import VolcEngineClient
from szyg.media_storage import get_media_output_dir, media_url_for_path
from szyg.models.common import IntegrationError
from szyg.api.video_endpoint import (
    ComposeAssetAnalysis,
    ComposeAssetRef,
    ComposeQuestion,
    _check_compose_assets,
    _dump_model,
    _extract_json_object,
    _extract_video_frames,
    _file_to_data_url,
    _infer_asset_type,
    _normalize_asset_analysis,
    _normalize_questions,
    _resolve_compose_path,
)

router = APIRouter(prefix="/api/content/graphic", tags=["content-graphic"])

DEFAULT_GRAPHIC_MODEL = "ep-20260714133840-lckqb"
_MATERIALS_FILE = DATA_DIR / "materials.json"


def _load_materials() -> list[dict]:
    if _MATERIALS_FILE.exists():
        return json.loads(_MATERIALS_FILE.read_text(encoding="utf-8"))
    return []


def _save_materials(data: list[dict]):
    _MATERIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _MATERIALS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class GraphicAnalyzeRequest(BaseModel):
    assets: list[ComposeAssetRef]
    user_instruction: str = ""


class GraphicAnalyzeResponse(BaseModel):
    ok: bool = True
    model: str = DEFAULT_GRAPHIC_MODEL
    assets: list[ComposeAssetAnalysis]
    questions: list[ComposeQuestion]
    summary: str = ""
    warnings: list[str] = []


class GraphicAnswer(BaseModel):
    question_id: str
    answer: str


class GraphicDraft(BaseModel):
    title: str = ""
    body: str = ""
    tags: list[str] = []
    platform_suggestion: list[str] = []
    image_order: list[str] = []
    image_anchors: list[dict[str, Any]] = []
    material_summary: str = ""
    publish_notes: str = ""


class GraphicPrepareRequest(BaseModel):
    analysis: GraphicAnalyzeResponse
    answers: list[GraphicAnswer] = []
    user_instruction: str = ""


class GraphicPrepareResponse(BaseModel):
    ok: bool = True
    draft: GraphicDraft
    used_assets: list[ComposeAssetAnalysis]
    warnings: list[str] = []
    summary: str = ""


class GraphicSaveRequest(BaseModel):
    draft: GraphicDraft
    used_assets: list[ComposeAssetAnalysis] = []
    filename: str = ""


def _graphic_model() -> str:
    try:
        cfg = load_config()
        content_cfg = cfg.get("content", {}) if isinstance(cfg.get("content"), dict) else {}
        graphic_cfg = content_cfg.get("graphic", {}) if isinstance(content_cfg.get("graphic"), dict) else {}
        return str(graphic_cfg.get("multimodal_model") or DEFAULT_GRAPHIC_MODEL)
    except Exception:
        return DEFAULT_GRAPHIC_MODEL


def _safe_filename(value: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|\r\n]+", "_", value).strip(" ._")
    return name[:60] or "一键图文草稿"


def _prepare_graphic_asset_inputs(assets: list[ComposeAssetRef]) -> tuple[list[ComposeAssetAnalysis], list[dict[str, Any]], list[str], list[str]]:
    prepared: list[ComposeAssetAnalysis] = []
    visual_content: list[dict[str, Any]] = []
    text_notes: list[str] = []
    warnings: list[str] = []

    for index, asset in enumerate(assets, start=1):
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
                first_ref = ""
                for frame in frames:
                    data_url = _file_to_data_url(frame)
                    first_ref = first_ref or data_url
                    visual_content.append({"type": "image_url", "image_url": {"url": data_url}})
                prepared.append(ComposeAssetAnalysis(id=asset_id, name=name, type="video", status="pending", provider_ref=first_ref, provider_type="image_url"))
            elif asset_type == "text":
                content = path.read_text(encoding="utf-8", errors="ignore")[:5000]
                text_notes.append(f"[{asset_id}] 文案素材 {name}:\n{content}")
                prepared.append(ComposeAssetAnalysis(id=asset_id, name=name, type="text", status="pending", provider_ref=content, provider_type="text"))
            elif asset_type == "audio":
                warnings.append(f"{name} 是音频素材，v1 仅作为配音或氛围参考。")
                prepared.append(ComposeAssetAnalysis(id=asset_id, name=name, type="audio", role="音频参考", summary="音频素材，建议作为配音、背景音乐或氛围参考。", status="success"))
            else:
                prepared.append(ComposeAssetAnalysis(id=asset_id, name=name, type=asset_type, status="failed", error="不支持的素材类型"))
        except Exception as exc:
            prepared.append(ComposeAssetAnalysis(id=asset_id, name=name, type=asset_type, status="failed", error=str(exc)[:200]))

    if not visual_content and not text_notes:
        raise HTTPException(400, "没有可用于 AI 理解的图片、视频或文案素材")
    return prepared, visual_content, text_notes, warnings


def _responses_content(text: str, visual_content: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "input_text", "text": text}]
    for item in visual_content or []:
        if item.get("type") == "image_url":
            url = ((item.get("image_url") or {}).get("url") or "").strip()
            if url:
                content.append({"type": "input_image", "image_url": url})
    return content


def _positive_graphic_role(value: str) -> str:
    text = (value or "").strip()
    negative_markers = ("无适配", "无关联", "不相关", "不适用", "无法匹配")
    if not text or any(marker in text for marker in negative_markers):
        return "创意视觉参考"
    return text


@router.post("/analyze", response_model=GraphicAnalyzeResponse)
async def analyze_graphic(req: GraphicAnalyzeRequest):
    _check_compose_assets(req.assets)
    model = _graphic_model()
    prepared, visual_content, text_notes, warnings = _prepare_graphic_asset_inputs(req.assets)
    system = (
        "你是企业图文内容策划。必须真实基于输入图片、视频关键帧和文案内容做判断。"
        "你要有营销创意发散能力：即使图片和产品不是直接同物，也要优先寻找隐喻、情绪、场景、视觉钩子、背景风格、对比叙事等可用方式。"
        "不要把素材简单判定为无关、无适配用途或需要替换。只有素材损坏或完全不可读时才标记失败。"
        "输出严格 JSON，不要解释。"
    )
    user = {
        "task": "分析素材并生成一键图文的动态确认问题",
        "user_instruction": req.user_instruction.strip(),
        "requirements": [
            "逐个素材判断用途：主图、产品图、场景图、人物图、风格参考、卖点文案、音频参考、创意隐喻、视觉钩子、背景氛围",
            "提取适合小红书、朋友圈、公众号、抖音图文的核心卖点和表达方向",
            "生成 1-3 个对图文成稿影响最大的确认问题，每题最多 4 个选项",
            "不要编造看不到的信息",
            "不要输出“现有图片无关、建议补充或替换素材”这类消极结论；如果素材不直连产品，请说明它可如何作为视觉隐喻或风格参考",
            "summary 只输出积极可执行的内容策略，不输出素材不足提醒",
            "如果 user_instruction 不为空，必须优先围绕用户补充要求重新发散素材用途、内容角度和确认问题",
        ],
        "assets": [_dump_model(item) for item in prepared],
        "text_notes": text_notes,
        "output_schema": {
            "summary": "整体素材理解摘要",
            "assets": [{"id": "素材ID", "name": "文件名", "type": "image|video|text|audio", "role": "素材用途", "summary": "素材内容摘要", "status": "success"}],
            "questions": [{"id": "q1", "question": "问题", "type": "single", "options": [{"label": "选项", "value": "值"}], "recommended": "推荐值"}],
            "warnings": [],
        },
    }
    client = VolcEngineClient(timeout=120)
    try:
        result = await client.responses_text(
            [
                {
                    "role": "user",
                    "content": _responses_content(f"{system}\n\n{json.dumps(user, ensure_ascii=False)}", visual_content),
                }
            ],
            model=model,
            max_output_tokens=3000,
        )
        raw = result.get("message", {}).get("content", "")
    except IntegrationError as exc:
        raise HTTPException(502, f"远程多模态模型不可用，无法理解素材：{str(exc)[:300]}")
    finally:
        await client.close()

    data = _extract_json_object(raw)
    if not data:
        raise HTTPException(502, "远程多模态模型返回内容无法解析")
    model_assets = _normalize_asset_analysis(data.get("assets"), req.assets)
    by_id = {item.id: item for item in prepared}
    merged: list[ComposeAssetAnalysis] = []
    for item in model_assets or prepared:
        original = by_id.get(item.id)
        merged.append(ComposeAssetAnalysis(
            id=item.id,
            name=item.name or (original.name if original else ""),
            type=item.type or (original.type if original else ""),
            role=_positive_graphic_role(item.role or (original.role if original else "")),
            summary=item.summary or (original.summary if original else ""),
            status="success" if item.status == "pending" else item.status,
            provider_ref=original.provider_ref if original else item.provider_ref,
            provider_type=original.provider_type if original else item.provider_type,
            error=item.error or (original.error if original else ""),
        ))
    questions = _normalize_questions(data.get("questions"))
    if not questions:
        raise HTTPException(502, "远程多模态模型未生成确认问题")
    return GraphicAnalyzeResponse(
        model=model,
        assets=merged,
        questions=questions[:3],
        summary=str(data.get("summary") or "").strip(),
        warnings=warnings,
    )


@router.post("/prepare", response_model=GraphicPrepareResponse)
async def prepare_graphic(req: GraphicPrepareRequest):
    if not req.analysis.assets:
        raise HTTPException(400, "缺少素材理解结果")
    model = _graphic_model()
    used_assets = [asset for asset in req.analysis.assets if asset.status == "success"]
    system = (
        "你是企业图文内容主编。基于素材理解结果和用户确认，生成可直接发布的图文草稿包。"
        "你要把所有可读素材转化为可执行内容资产：产品文案用于卖点，非产品图可用于隐喻、情绪、视觉钩子、对比或背景风格。"
        "不要在正文、summary、publish_notes 或 warnings 中输出“素材无关、无法匹配、建议补充或替换素材”这类消极提醒。"
        "不要调用外部工具，不要输出解释文字，只输出严格 JSON。"
    )
    user = {
        "analysis": _dump_model(req.analysis),
        "answers": [_dump_model(answer) for answer in req.answers],
        "user_instruction": req.user_instruction,
        "requirements": [
            "标题要适合中小企业获客，清晰、有具体利益点",
            "正文要自然中文，可直接发布，不要暴露模型或技术细节",
            "标签 3-8 个，去掉 # 号",
            "image_order 使用素材 id，说明推荐配图顺序",
            "image_anchors 必须说明每张图插入到正文第几个段落之后，字段为 asset_id、anchor_after_paragraph、caption；anchor_after_paragraph 为 0 表示标题后正文前，1 表示第 1 段后",
            "平台建议从 小红书、朋友圈、公众号、抖音图文、微博 中选择",
            "如果图片和产品不是直接同物，也要给出创意使用方式，不要排除图片",
            "publish_notes 只写发布操作建议、平台表达建议或配图使用建议，不写素材不足提醒",
        ],
        "output_schema": {
            "summary": "图文方案摘要",
            "draft": {
                "title": "标题",
                "body": "正文",
                "tags": ["标签"],
                "platform_suggestion": ["小红书"],
                "image_order": ["asset_id"],
                "image_anchors": [{"asset_id": "asset_id", "anchor_after_paragraph": 1, "caption": "配图说明"}],
                "material_summary": "素材理解摘要",
                "publish_notes": "发布建议",
            },
            "warnings": [],
        },
    }
    client = VolcEngineClient(timeout=90)
    try:
        result = await client.responses_text([
            {
                "role": "user",
                "content": _responses_content(f"{system}\n\n{json.dumps(user, ensure_ascii=False)}"),
            }
        ], model=model, max_output_tokens=3500)
        raw = result.get("message", {}).get("content", "")
    except IntegrationError as exc:
        raise HTTPException(502, f"远程多模态模型不可用，无法生成图文草稿：{str(exc)[:300]}")
    finally:
        await client.close()

    data = _extract_json_object(raw)
    if not data or not isinstance(data.get("draft"), dict):
        raise HTTPException(502, "远程多模态模型返回图文草稿无法解析")
    draft_data = data["draft"]
    draft = GraphicDraft(
        title=str(draft_data.get("title") or "").strip(),
        body=str(draft_data.get("body") or "").strip(),
        tags=[str(item).strip().lstrip("#") for item in draft_data.get("tags", []) if str(item).strip()][:8] if isinstance(draft_data.get("tags"), list) else [],
        platform_suggestion=[str(item).strip() for item in draft_data.get("platform_suggestion", []) if str(item).strip()][:5] if isinstance(draft_data.get("platform_suggestion"), list) else [],
        image_order=[str(item).strip() for item in draft_data.get("image_order", []) if str(item).strip()] if isinstance(draft_data.get("image_order"), list) else [],
        image_anchors=_normalize_image_anchors(draft_data.get("image_anchors"), used_assets),
        material_summary=str(draft_data.get("material_summary") or req.analysis.summary or "").strip(),
        publish_notes=str(draft_data.get("publish_notes") or "").strip(),
    )
    if not draft.title or not draft.body:
        raise HTTPException(502, "远程多模态模型未生成完整标题和正文")
    warnings = [str(item) for item in data.get("warnings", [])] if isinstance(data.get("warnings"), list) else []
    return GraphicPrepareResponse(
        draft=draft,
        used_assets=used_assets,
        warnings=[*req.analysis.warnings, *warnings],
        summary=str(data.get("summary") or "").strip(),
    )


def _normalize_image_anchors(value: Any, assets: list[ComposeAssetAnalysis]) -> list[dict[str, Any]]:
    visual_ids = [asset.id for asset in assets if asset.type in {"image", "video"} and asset.id]
    if not visual_ids:
        return []
    anchors: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            asset_id = str(item.get("asset_id") or item.get("id") or "").strip()
            if asset_id not in visual_ids:
                continue
            try:
                paragraph = int(item.get("anchor_after_paragraph", 1))
            except Exception:
                paragraph = 1
            anchors.append({
                "asset_id": asset_id,
                "anchor_after_paragraph": max(0, paragraph),
                "caption": str(item.get("caption") or "").strip(),
            })
    anchored = {item["asset_id"] for item in anchors}
    for index, asset_id in enumerate(visual_ids):
        if asset_id in anchored:
            continue
        anchors.append({
            "asset_id": asset_id,
            "anchor_after_paragraph": index + 1,
            "caption": "",
        })
    return anchors


@router.post("/save")
async def save_graphic(req: GraphicSaveRequest):
    if not req.draft.title.strip() or not req.draft.body.strip():
        raise HTTPException(400, "图文标题和正文不能为空")
    output_dir = get_media_output_dir("document")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = _safe_filename(req.filename or req.draft.title)
    path = output_dir / f"{filename}_{stamp}.md"
    lines = [
        f"# {req.draft.title.strip()}",
        "",
        req.draft.body.strip(),
        "",
        "## 标签",
        " ".join(f"#{tag}" for tag in req.draft.tags),
        "",
        "## 平台建议",
        "、".join(req.draft.platform_suggestion) or "未指定",
        "",
        "## 配图顺序",
        "\n".join(f"{index + 1}. {asset_id}" for index, asset_id in enumerate(req.draft.image_order)) or "未指定",
        "",
        "## 配图锚点",
        "\n".join(
            f"- {item.get('asset_id', '')}: 第 {item.get('anchor_after_paragraph', 1)} 段后"
            + (f"｜{item.get('caption')}" if item.get("caption") else "")
            for item in req.draft.image_anchors
        ) or "未指定",
        "",
        "## 素材理解",
        req.draft.material_summary or "无",
        "",
        "## 发布建议",
        req.draft.publish_notes or "无",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    item = {
        "ok": True,
        "id": f"graphic:{str(uuid.uuid4())[:8]}",
        "name": path.name,
        "type": "text",
        "tags": ["一键图文", "AI生成"],
        "platform": "all",
        "url": media_url_for_path(path),
        "path": str(path.resolve()),
        "size": path.stat().st_size,
        "created_at": datetime.now().isoformat(),
        "source": "one_click_graphic",
        "image_order": req.draft.image_order,
        "image_anchors": req.draft.image_anchors,
        "used_asset_ids": [asset.id for asset in req.used_assets],
    }
    materials = [entry for entry in _load_materials() if str(entry.get("path") or "") != item["path"]]
    materials.append({key: value for key, value in item.items() if key != "ok"})
    _save_materials(materials)
    return item
