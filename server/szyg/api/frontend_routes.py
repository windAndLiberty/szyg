"""前端 Web UI 所需的后端 API 路由。"""

import json
import logging
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from szyg.config.loader import load_config
from szyg.agent_core.knowledge import KnowledgeBase
from szyg.agent_core.sop_manager import SOPManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["frontend"])

# 懒加载单例
_kb: KnowledgeBase | None = None
_sop: SOPManager | None = None

# 知识库任务与文档元数据缓存（内存级，重启后从数据库重建）
_tasks: dict[str, dict] = {}
_documents: dict[str, dict] = {}


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


# ── 知识库文档管理（真实文件上传 + 列表 + 删除 + 统计）──────────────────────────


def _get_doc_id(source: str) -> str:
    """根据 source 名称生成稳定的文档 ID。"""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, source))


def _scan_documents() -> dict[str, dict]:
    """从 knowledge 数据库中扫描所有已摄入的文档并统计分块数。"""
    kb = get_kb()
    docs: dict[str, dict] = {}
    try:
        conn = kb.memory._get_connection()
        rows = conn.execute(
            "SELECT metadata, created_at FROM memories WHERE metadata LIKE ?",
            ('%"type": "knowledge"%',),
        ).fetchall()
        for row in rows:
            meta = json.loads(row[0]) if isinstance(row[0], str) else (row[0] or {})
            source = meta.get("source", "unknown")
            if source not in docs:
                docs[source] = {"count": 0, "first_at": row[1], "last_at": row[1]}
            docs[source]["count"] += 1
            if row[1] < docs[source]["first_at"]:
                docs[source]["first_at"] = row[1]
            if row[1] > docs[source]["last_at"]:
                docs[source]["last_at"] = row[1]
    except Exception as e:
        logger.warning(f"Failed to scan knowledge documents: {e}")
    return docs


def _doc_response(source: str, info: dict, meta: dict | None = None) -> dict:
    doc_id = _get_doc_id(source)
    return {
        "id": doc_id,
        "filename": source,
        "source": (meta or {}).get("source", "upload"),
        "chunks": info["count"],
        "status": "ready",
        "ingestedAt": (meta or {}).get("ingestedAt", info["first_at"]),
    }


@router.post("/knowledge/documents")
async def upload_document(file: UploadFile = File(...)):
    """上传文件并摄入到知识库。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    suffix = Path(file.filename).suffix
    allowed = {".txt", ".md", ".json", ".pdf", ".docx"}
    if suffix.lower() not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        kb = get_kb()
        count = kb.ingest_file(tmp_path, source_name=file.filename)
        doc_id = _get_doc_id(file.filename)
        ingested_at = datetime.now().isoformat()
        _documents[doc_id] = {
            "id": doc_id,
            "filename": file.filename,
            "source": "upload",
            "chunks": count,
            "status": "ready",
            "ingestedAt": ingested_at,
        }
        task_id = str(uuid.uuid4())
        _tasks[task_id] = {
            "status": "ready",
            "progress": 100,
            "documentId": doc_id,
        }
        return {
            "id": doc_id,
            "filename": file.filename,
            "source": "upload",
            "chunks": count,
            "status": "ready",
            "ingestedAt": ingested_at,
            "taskId": task_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest document: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@router.get("/knowledge/documents")
async def list_documents():
    """列出知识库中所有已摄入的文档。"""
    docs = _scan_documents()
    items = []
    for source, info in docs.items():
        doc_id = _get_doc_id(source)
        meta = _documents.get(doc_id)
        items.append(_doc_response(source, info, meta))
    return {"items": items}


@router.delete("/knowledge/documents/{doc_id}")
async def delete_document(doc_id: str):
    """删除指定文档及其所有分块。"""
    target_source = None
    meta = _documents.get(doc_id)
    if meta:
        target_source = meta["filename"]
    else:
        for source in _scan_documents():
            if _get_doc_id(source) == doc_id:
                target_source = source
                break

    if not target_source:
        raise HTTPException(status_code=404, detail="Document not found")

    kb = get_kb()
    try:
        conn = kb.memory._get_connection()
        rows = conn.execute("SELECT id, metadata FROM memories").fetchall()
        to_delete = []
        for row in rows:
            meta = json.loads(row[1]) if isinstance(row[1], str) else (row[1] or {})
            if meta.get("source") == target_source:
                to_delete.append(row[0])
        for entry_id in to_delete:
            conn.execute("DELETE FROM memories WHERE id = ?", (entry_id,))
        conn.commit()
        _documents.pop(doc_id, None)
        return {"ok": True, "deleted": doc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {e}")


@router.get("/knowledge/tasks/{task_id}")
async def get_task(task_id: str):
    """查询摄入任务状态。"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"id": task_id, "status": task["status"], "progress": task["progress"]}


@router.get("/knowledge/stats")
async def knowledge_stats():
    """获取知识库统计信息。"""
    docs = _scan_documents()
    total_docs = len(docs)
    total_chunks = sum(info["count"] for info in docs.values())
    last_update = max((info["last_at"] for info in docs.values()), default=None)
    return {
        "totalDocs": total_docs,
        "totalChunks": total_chunks,
        "lastUpdate": last_update or "—",
    }


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


@router.delete("/sop/{sop_id}")
async def sop_delete(sop_id: str):
    """删除 SOP。"""
    sop_mgr = get_sop()
    sops = sop_mgr.list_sops()
    for s in sops:
        if s.id == sop_id:
            sops.remove(s)
            sop_mgr._sops = sops
            if hasattr(sop_mgr, '_save'):
                sop_mgr._save()
            return {"ok": True}
    raise HTTPException(404, "SOP 不存在")


@router.put("/sop/{sop_id}")
async def sop_update(sop_id: str, body: dict):
    """更新 SOP。"""
    sop_mgr = get_sop()
    sops = sop_mgr.list_sops()
    for s in sops:
        if s.id == sop_id:
            if "name" in body:
                s.name = body["name"]
            if "description" in body:
                s.description = body["description"]
            if "steps" in body:
                s.steps = body["steps"]
            if "enabled" in body:
                s.enabled = body["enabled"]
            if hasattr(sop_mgr, '_save'):
                sop_mgr._save()
            return {"ok": True, "sop": s.to_dict()}
    raise HTTPException(404, "SOP 不存在")


@router.get("/sop/executions")
async def sop_executions():
    """SOP 执行记录列表。"""
    import json
    from pathlib import Path
    from szyg.data_path import DATA_DIR
    exec_file = DATA_DIR / "sop_executions.json"
    if exec_file.exists():
        items = json.loads(exec_file.read_text(encoding="utf-8"))
    else:
        items = []
    return {"executions": items, "total": len(items)}
