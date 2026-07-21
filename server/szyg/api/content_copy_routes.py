"""Content copy generation endpoints."""

from __future__ import annotations

import json
import re
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from szyg.integrations.volcengine_client import VolcEngineClient


router = APIRouter(prefix="/api/content/copy", tags=["content-copy"])


class CopyGenerateRequest(BaseModel):
    prompt: str
    copy_type: str = "未定义类型"
    count: int = 5
    min_words: int = 80
    max_words: int = 160


class CopyGenerateResponse(BaseModel):
    ok: bool
    copies: list[str]
    char_counts: list[int] = []
    within_range: list[bool] = []
    raw_text: str = ""


def _extract_text_from_obj(obj: Any) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        return "".join(_extract_text_from_obj(item) for item in obj)
    if not isinstance(obj, dict):
        return ""
    if obj.get("type") in {"output_text", "text"} and isinstance(obj.get("text"), str):
        return obj["text"]
    parts: list[str] = []
    for key in ("output", "content", "message", "response"):
        if key in obj:
            parts.append(_extract_text_from_obj(obj[key]))
    return "".join(parts)


def _parse_copies(text: str, count: int) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(text[start : end + 1])
            copies = data.get("copies")
            if isinstance(copies, list):
                return [str(item).strip() for item in copies if str(item).strip()][:count]
    except Exception:
        pass

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned: list[str] = []
    for line in lines:
        line = re.sub(r"^\s*(?:\d+[\.\、\)]|[-*])\s*", "", line).strip()
        if line and line not in cleaned:
            cleaned.append(line)
    return cleaned[:count]


def _copy_char_count(text: str) -> int:
    return len(re.sub(r"[\r\n]+", "", text or ""))


class _ArkToolNotOpen(Exception):
    pass


async def _call_ark_responses(req: CopyGenerateRequest, *, enable_web_search: bool = True) -> str:
    system_text = (
        "你是企业营销文案专家。请结合可用的联网搜索信息，但不要在结果中暴露模型、接口或技术细节。"
        "你的输出必须是严格 JSON，格式只能是 {\"copies\":[\"...\"]}。"
        "copies 数组里的每一项只能放一条可直接复制使用的正文，不要编号、不要标题、不要解释、不要 Markdown。"
        "每条文案都要中文自然、信息具体、能直接发布，避免空泛口号。"
        "篇幅是偏好，不是机械凑字数。优先保证表达自然、卖点准确、节奏顺畅和可发布性。"
    )
    user_text = (
        f"文案需求：{req.prompt.strip()}\n"
        f"文案类型：{req.copy_type}\n"
        f"生成数量：{req.count} 条\n"
        f"篇幅偏好：建议每条约 {req.min_words}-{req.max_words} 个字符，包含标点，不含换行。\n"
        "请让每条文案尽量贴近篇幅偏好，但不要为了凑字数牺牲自然表达。copies 数量必须准确，每条必须是独立完整文案，不要输出任何 JSON 之外的内容。\n"
        "如果需求涉及热点、节日、行业趋势或事实，请先搜索并融入文案；"
        "如果没有必要搜索，则直接生成。"
    )
    input_items = [
            {"role": "system", "content": [{"type": "input_text", "text": system_text}]},
            {"role": "user", "content": [{"type": "input_text", "text": user_text}]},
    ]
    del enable_web_search
    client = VolcEngineClient(timeout=120)
    try:
        response = await client.responses_text(input_items, max_output_tokens=6000)
    finally:
        await client.close()
    text = str((response.get("message") or {}).get("content") or "").strip()
    if not text:
        raise HTTPException(500, "文案生成失败：服务未返回内容，请重试")
    return text


@router.post("/generate", response_model=CopyGenerateResponse)
async def generate_copy(req: CopyGenerateRequest):
    if not req.prompt.strip():
        raise HTTPException(400, "文案需求不能为空")
    if req.count < 1 or req.count > 10:
        raise HTTPException(400, "生成数量仅支持 1-10 条")
    if req.min_words < 10 or req.max_words > 1000 or req.min_words > req.max_words:
        raise HTTPException(400, "大概字数范围需在 10-1000 之间，且最低不能高于最高")

    try:
        raw_text = await _call_ark_responses(req, enable_web_search=True)
    except _ArkToolNotOpen:
        raw_text = await _call_ark_responses(req, enable_web_search=False)
    copies = _parse_copies(raw_text, req.count)
    if not copies:
        raise HTTPException(500, "文案生成失败：无法解析生成内容")
    char_counts = [_copy_char_count(copy) for copy in copies]
    within_range = [req.min_words <= count <= req.max_words for count in char_counts]
    return CopyGenerateResponse(ok=True, copies=copies, char_counts=char_counts, within_range=within_range, raw_text=raw_text)
