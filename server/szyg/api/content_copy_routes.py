"""Content copy generation endpoints."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


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


def _load_volcengine_api_key() -> str:
    key = os.environ.get("VOLCENGINE_API_KEY", "").strip()
    if key:
        return key
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith("VOLCENGINE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


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
    api_key = _load_volcengine_api_key()
    if not api_key:
        raise HTTPException(500, "火山引擎 API Key 未配置")

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
    payload = {
        "model": "deepseek-v4-flash-260425",
        "stream": True,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system_text}]},
            {"role": "user", "content": [{"type": "input_text", "text": user_text}]},
        ],
    }
    if enable_web_search:
        payload["tools"] = [{"type": "web_search", "max_keyword": 3}]

    chunks: list[str] = []
    completed_text = ""
    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        async with client.stream(
            "POST",
            "https://ark.cn-beijing.volces.com/api/v3/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        ) as response:
            if response.is_error:
                raise HTTPException(500, f"文案生成提交失败: HTTP {response.status_code}: {(await response.aread()).decode('utf-8', errors='replace')[:300]}")
            async for line in response.aiter_lines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                raw = line.removeprefix("data:").strip()
                if not raw or raw == "[DONE]":
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                event_type = event.get("type")
                if event_type == "error":
                    if event.get("code") == "ToolNotOpen":
                        raise _ArkToolNotOpen(str(event.get("message") or "web_search not activated"))
                    raise HTTPException(500, f"文案生成失败: {str(event.get('message') or event)[:300]}")
                if event_type == "response.failed":
                    err = (event.get("response") or {}).get("error") or {}
                    if err.get("code") == "ToolNotOpen":
                        raise _ArkToolNotOpen(str(err.get("message") or "web_search not activated"))
                    raise HTTPException(500, f"文案生成失败: {str(err.get('message') or event)[:300]}")
                if event_type == "response.output_text.delta" and isinstance(event.get("delta"), str):
                    chunks.append(event["delta"])
                elif event_type == "response.completed":
                    completed_text = _extract_text_from_obj(event.get("response"))

    text = "".join(chunks).strip() or completed_text.strip()
    if not text:
        raise HTTPException(500, "文案生成失败：模型未返回内容")
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
