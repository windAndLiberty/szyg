"""Conversation persistence API — 超级员工对话历史存储

Stores conversations as JSON files under data/conversations/.
"""
import json, logging, os, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

from szyg.data_path import DATA_DIR
CONV_DIR = DATA_DIR / "conversations"
CONV_DIR.mkdir(parents=True, exist_ok=True)
MAX_CONVERSATIONS = 50


class ConversationMessage(BaseModel):
    role: str
    content: str = ""
    type: str = "text"  # text / tool_call / tool_result / thinking / error
    timestamp: Optional[float] = None


class ConversationCreate(BaseModel):
    title: str = ""
    messages: list[ConversationMessage] = Field(default_factory=list)
    agent_id: str = ""
    model: str = ""


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    messages: Optional[list[ConversationMessage]] = None
    pinned: Optional[bool] = None
    archived: Optional[bool] = None


def _conv_path(conv_id: str) -> Path:
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', conv_id):
        from fastapi import HTTPException
        raise HTTPException(400, "非法会话ID")
    return CONV_DIR / f"{conv_id}.json"


def _load_conv(conv_id: str) -> dict | None:
    path = _conv_path(conv_id)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _save_conv(conv_id: str, data: dict):
    _conv_path(conv_id).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _list_convs() -> list[dict]:
    convs = []
    for f in sorted(CONV_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            convs.append({
                "id": f.stem,
                "title": data.get("title", ""),
                "message_count": len(data.get("messages", [])),
                "agent_id": data.get("agent_id", ""),
                "model": data.get("model", ""),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "pinned": data.get("pinned", False),
                "archived": data.get("archived", False),
            })
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Skipping corrupt conversation file %s: %s", f.name, e)
    return convs


def _sort_convs(convs: list[dict]) -> list[dict]:
    return sorted(
        convs,
        key=lambda c: (
            c.get("pinned", False),
            c.get("updated_at", ""),
        ),
        reverse=True,
    )


def _prune_conversations(max_count: int = MAX_CONVERSATIONS):
    convs = _sort_convs(_list_convs())
    for conv in convs[max_count:]:
        try:
            _conv_path(conv["id"]).unlink(missing_ok=True)
        except OSError as e:
            logger.warning("Failed to prune old conversation %s: %s", conv.get("id"), e)


@router.get("")
async def list_conversations(
    limit: int = Query(default=MAX_CONVERSATIONS, ge=1, le=MAX_CONVERSATIONS),
    include_archived: bool = Query(default=False),
):
    """列出所有会话（置顶在前，其余按更新时间倒序）"""
    _prune_conversations()
    convs = _sort_convs(_list_convs())
    if not include_archived:
        convs = [conv for conv in convs if not conv.get("archived", False)]
    return {"conversations": convs[:limit]}


@router.get("/{conv_id}")
async def get_conversation(conv_id: str):
    """获取单个会话完整内容"""
    conv = _load_conv(conv_id)
    if not conv:
        raise HTTPException(404, f"会话不存在: {conv_id}")
    return conv


@router.post("")
async def create_conversation(body: ConversationCreate):
    """创建新会话"""
    conv_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "id": conv_id,
        "title": body.title or "新对话",
        "messages": [m.model_dump() for m in body.messages],
        "agent_id": body.agent_id,
        "model": body.model,
        "pinned": False,
        "archived": False,
        "created_at": now,
        "updated_at": now,
    }
    _save_conv(conv_id, data)
    _prune_conversations()
    return data


@router.put("/{conv_id}")
async def update_conversation(conv_id: str, body: ConversationUpdate):
    """更新会话（追加消息或修改标题）"""
    conv = _load_conv(conv_id)
    if not conv:
        raise HTTPException(404, f"会话不存在: {conv_id}")

    if body.title is not None:
        conv["title"] = body.title
    if body.messages is not None:
        conv["messages"] = [m.model_dump() for m in body.messages]
    if body.pinned is not None:
        conv["pinned"] = body.pinned
    if body.archived is not None:
        conv["archived"] = body.archived

    conv["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_conv(conv_id, conv)
    _prune_conversations()
    return conv


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str):
    """删除会话"""
    path = _conv_path(conv_id)
    if not path.exists():
        raise HTTPException(404, f"会话不存在: {conv_id}")
    path.unlink()
    return {"ok": True}
