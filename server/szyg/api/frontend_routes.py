"""前端 Web UI 所需的后端 API 路由。"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from szyg.config.loader import load_config
from szyg.agent_core.sop_manager import SOPManager
from szyg.knowledge_service import get_knowledge_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["frontend"])

# 懒加载单例
_sop: SOPManager | None = None


def get_sop() -> SOPManager:
    global _sop
    if _sop is None:
        _sop = SOPManager()
    return _sop


# ── 配置 ──────────────────────────────────────────────────────────────────────


def _redact_config(obj, _key: str = ""):
    """Recursively redact values whose key contains 'key', 'secret', 'token', or 'password'."""
    sensitive = ("api_key", "secret", "token", "password", "credential")
    if isinstance(obj, dict):
        return {
            k: _redact_config(v, k) for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact_config(v, _key) for v in obj]
    if isinstance(obj, str) and any(s in _key.lower() for s in sensitive) and obj:
        return "***"
    return obj


@router.get("/config")
async def get_config():
    """读取当前配置（API key 已脱敏）。"""
    try:
        cfg = load_config()
        return _redact_config(cfg)
    except Exception as e:
        raise HTTPException(500, str(e))


# ── 知识库 ────────────────────────────────────────────────────────────────────


class IngestRequest(BaseModel):
    text: str
    source: str = "web_upload"


@router.post("/knowledge/ingest")
async def knowledge_ingest(req: IngestRequest):
    """摄入文本到知识库。"""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="文本内容为空")
    service = get_knowledge_service()
    filename = Path(req.source or "web_upload").name
    if Path(filename).suffix.lower() not in {".txt", ".md"}:
        filename += ".md"
    try:
        document = service.create_document(filename, req.text.encode("utf-8"))
        if not document.get("duplicate"):
            service.start_processing(document["id"])
        return {"document": document, "taskId": document.get("job_id"), "source": req.source}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/knowledge/search")
async def knowledge_search(q: str = "", top_k: int = 5, collection: str = ""):
    """检索知识库。"""
    if not q:
        return {"results": []}
    results = await get_knowledge_service().search(q, limit=top_k, collection=collection)
    return {"results": results}


# ── 知识库文档管理（源文件 + Markdown 规范化 + RAG 索引）──────────────────────


@router.post("/knowledge/documents")
async def upload_document(file: UploadFile = File(...), collection: str = Form("企业资料")):
    """上传文件并摄入到知识库。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件内容为空")
    try:
        service = get_knowledge_service()
        document = service.create_document(file.filename, content, collection=collection.strip() or "企业资料")
        if not document.get("duplicate"):
            service.start_processing(document["id"])
        return {**document, "taskId": document.get("job_id")}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("knowledge upload failed")
        raise HTTPException(status_code=500, detail=f"知识文件保存失败：{exc}") from exc


@router.get("/knowledge/documents")
async def list_documents(q: str = "", collection: str = "", status: str = ""):
    """列出知识库中所有已摄入的文档。"""
    service = get_knowledge_service()
    service.resume_pending()
    return {"items": service.list_documents(query=q, collection=collection, status=status)}


@router.get("/knowledge/documents/{doc_id}")
async def get_document(doc_id: str):
    document = get_knowledge_service().get_document(doc_id, include_markdown=True)
    if not document:
        raise HTTPException(status_code=404, detail="知识文件不存在")
    return document


@router.get("/knowledge/documents/{doc_id}/source")
async def open_document_source(doc_id: str):
    document = get_knowledge_service().get_document(doc_id)
    if not document or not document.get("source_available"):
        raise HTTPException(status_code=404, detail="源文件已不存在")
    return FileResponse(document["original_path"], filename=document["filename"], media_type=document.get("mime_type"))


@router.delete("/knowledge/documents/{doc_id}")
async def delete_document(doc_id: str):
    """删除指定文档及其所有分块。"""
    if not get_knowledge_service().delete_document(doc_id):
        raise HTTPException(status_code=404, detail="知识文件不存在")
    return {"ok": True, "deleted": doc_id}


@router.post("/knowledge/documents/{doc_id}/reparse")
async def reparse_document(doc_id: str):
    service = get_knowledge_service()
    try:
        document = service.reparse(doc_id)
        service.start_processing(doc_id)
        return {**document, "taskId": document.get("job_id")}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="知识文件不存在") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/knowledge/tasks/{task_id}")
async def get_task(task_id: str):
    """查询摄入任务状态。"""
    task = get_knowledge_service().get_job(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="解析任务不存在")
    return task


@router.get("/knowledge/stats")
async def knowledge_stats():
    """获取知识库统计信息。"""
    stats = get_knowledge_service().stats()
    return {
        **stats,
        "totalDocs": stats["total_docs"],
        "totalChunks": stats["total_chunks"],
        "lastUpdate": stats["last_update"] or "—",
    }


@router.get("/knowledge/collections")
async def knowledge_collections():
    return {"items": get_knowledge_service().collections()}


class RetrievalTestRequest(BaseModel):
    query: str
    top_k: int = 5
    collection: str = ""


@router.post("/knowledge/retrieval/test")
async def test_knowledge_retrieval(req: RetrievalTestRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="请输入检索问题")
    results = await get_knowledge_service().search(req.query, limit=req.top_k, collection=req.collection)
    return {"query": req.query, "results": results}


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
    for sop in sop_mgr.list_sops():
        if sop.id == sop_id:
            sop_mgr.delete(sop.name)
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
                from szyg.agent_core.sop_manager import SOPStep
                s.steps = [step if isinstance(step, SOPStep) else SOPStep.from_dict(step) for step in body["steps"]]
            if "enabled" in body:
                s.enabled = body["enabled"]
            sop_mgr.save(s)
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
