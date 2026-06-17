"""AI Tools Hub API — curated AI tool directory"""
import json, os
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/hub", tags=["hub"])

from szyg.data_path import DATA_DIR
HUB_FILE = DATA_DIR / "hub_tools.json"


class HubTool(BaseModel):
    id: str
    name: str
    url: str
    desc: str = ""
    icon: str = "🔗"
    category: str = "other"
    tags: list[str] = []
    is_free: bool = True
    is_hot: bool = False
    is_new: bool = False


def _read() -> list[dict]:
    if HUB_FILE.exists():
        return json.loads(HUB_FILE.read_text(encoding='utf-8'))
    return []


@router.get("/list", response_model=list[HubTool])
async def list_tools(category: str | None = None, search: str | None = None, hot: bool = False, new_only: bool = False):
    tools = _read()
    if category:
        tools = [t for t in tools if t.get("category") == category]
    if search:
        q = search.lower()
        tools = [t for t in tools if q in t.get("name","").lower() or q in t.get("desc","").lower()]
    if hot:
        tools = [t for t in tools if t.get("is_hot")]
    if new_only:
        tools = [t for t in tools if t.get("is_new")]
    return [HubTool(**t) for t in tools]


@router.get("/categories")
async def categories():
    tools = _read()
    cats = {}
    for t in tools:
        c = t.get("category", "other")
        if c not in cats:
            cats[c] = 0
        cats[c] += 1
    return [{"key": k, "label": _cat_label(k), "count": v} for k, v in sorted(cats.items())]


def _cat_label(key: str) -> str:
    labels = {
        "llm": "🤖 大语言模型", "image": "🎨 AI绘图", "video": "🎬 AI视频",
        "audio": "🎵 AI音频", "code": "💻 AI编程", "writing": "✍️ AI写作",
        "search": "🔍 AI搜索", "office": "📊 AI办公", "other": "📦 其他工具",
    }
    return labels.get(key, key)
