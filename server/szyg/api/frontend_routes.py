"""前端 Web UI 所需的后端 API 路由。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from szyg.config.loader import load_config
from szyg.agent_core.knowledge import KnowledgeBase
from szyg.agent_core.sop_manager import SOPManager

router = APIRouter(prefix="/api", tags=["frontend"])

# 懒加载单例
_kb: KnowledgeBase | None = None
_sop: SOPManager | None = None


def get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb


def get_sop() -> SOPManager:
    global _sop
    if _sop is None:
        _sop = SOPManager()
    return _sop


# ── 配置 ──────────────────────────────────────────────────────────────────────


@router.get("/config")
async def get_config():
    """读取当前配置（API key 已脱敏）。"""
    try:
        cfg = load_config()
        return cfg
    except Exception as e:
        raise HTTPException(500, str(e))


# ── 知识库 ────────────────────────────────────────────────────────────────────


class IngestRequest(BaseModel):
    text: str
    source: str = "web_upload"


@router.post("/knowledge/ingest")
async def knowledge_ingest(req: IngestRequest):
    """摄入文本到知识库。"""
    kb = get_kb()
    count = kb.ingest_text(req.text, source=req.source)
    return {"chunks": count, "source": req.source}


@router.get("/knowledge/search")
async def knowledge_search(q: str = "", top_k: int = 5):
    """检索知识库。"""
    if not q:
        return {"results": []}
    kb = get_kb()
    results = kb.query(q, top_k=top_k)
    return {"results": results}


# ── SOP ───────────────────────────────────────────────────────────────────────


class SOPDefineRequest(BaseModel):
    name: str
    description: str = ""
    steps: list[dict]


@router.post("/sop/define")
async def sop_define(req: SOPDefineRequest):
    """定义新 SOP。"""
    sop_mgr = get_sop()
    try:
        sop = sop_mgr.define(req.name, req.description, req.steps)
        return {"id": sop.id, "name": sop.name, "steps": len(sop.steps)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/sop/list")
async def sop_list():
    """列出所有 SOP。"""
    sop_mgr = get_sop()
    return {"sops": [s.to_dict() for s in sop_mgr.list_sops()]}
