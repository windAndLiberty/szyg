"""AI Agent Marketplace API — system prompt tiered agents"""
import json, os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/agents", tags=["agents"])

from szyg.data_path import DATA_DIR
AGENTS_FILE = DATA_DIR / "agents.json"

PROMPT_TIERS = ["base", "domain", "task"]
PROMPT_TIER_LABELS = {
    "base": "基础层 — 通用对话与推理",
    "domain": "领域层 — 垂直行业专家",
    "task": "任务层 — 特定场景执行",
}


class AgentInfo(BaseModel):
    id: str
    name: str
    avatar: str = "🤖"
    description: str = ""
    system_prompt: str = ""
    tier: str = "base"  # base | domain | task
    category: str = "general"
    model_preference: str = ""
    temperature: float = 0.7
    tags: list[str] = []
    usage_count: int = 0
    rating: float = 4.0
    created_by: str = "system"


def _read_agents() -> list[dict]:
    if AGENTS_FILE.exists():
        return json.loads(AGENTS_FILE.read_text(encoding='utf-8'))
    return []


def _write_agents(data: list[dict]):
    AGENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    AGENTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("/list", response_model=list[AgentInfo])
async def list_agents(tier: str | None = None, category: str | None = None, search: str | None = None):
    agents = _read_agents()
    if tier and tier in PROMPT_TIERS:
        agents = [a for a in agents if a.get("tier") == tier]
    if category:
        agents = [a for a in agents if a.get("category") == category]
    if search:
        q = search.lower()
        agents = [a for a in agents if q in a.get("name","").lower() or q in a.get("description","").lower() or any(q in t.lower() for t in a.get("tags",[]))]
    # Sort: highest rating first
    agents.sort(key=lambda a: (a.get("rating",0), a.get("usage_count",0)), reverse=True)
    return [AgentInfo(**a) for a in agents]


@router.get("/tiers")
async def list_tiers():
    return [{"key": k, "label": v} for k, v in PROMPT_TIER_LABELS.items()]


@router.get("/categories")
async def agent_categories():
    agents = _read_agents()
    return list(set(a.get("category", "general") for a in agents))


@router.get("/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: str):
    agents = _read_agents()
    for a in agents:
        if a.get("id") == agent_id:
            # Increment usage
            a["usage_count"] = a.get("usage_count", 0) + 1
            _write_agents(agents)
            return AgentInfo(**a)
    raise HTTPException(404, "智能体不存在")
