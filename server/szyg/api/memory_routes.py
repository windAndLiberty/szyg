"""Memory CRUD API routes — exposes agent_core.memory.Memory to the frontend."""

import json
import os
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/memory", tags=["memory"])

_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data",
    "memory.db",
)


def _get_memory():
    from szyg.agent_core.memory import Memory
    return Memory(db_path=_DB_PATH)


class MemoryCreate(BaseModel):
    content: str
    metadata: Optional[dict] = None
    type: Optional[str] = None


class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    metadata: Optional[dict] = None


@router.get("/list")
async def list_memories(
    type: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    """List memory entries with optional type filter."""
    mem = _get_memory()
    try:
        conn = mem._get_connection()
        if type:
            pattern = f'%"type": "{type}"%'
            rows = conn.execute(
                "SELECT id, content, metadata, created_at, updated_at "
                "FROM memories WHERE metadata LIKE ? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (pattern, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, content, metadata, created_at, updated_at "
                "FROM memories ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()

        items = []
        for r in rows:
            meta = json.loads(r[2]) if isinstance(r[2], str) else (r[2] or {})
            items.append({
                "id": r[0],
                "content": r[1],
                "type": meta.get("type", "unknown"),
                "metadata": meta,
                "createdAt": str(r[3]),
                "updatedAt": str(r[4]),
            })

        # Stats
        total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        stats = {"total": total, "conversation": 0, "customer": 0, "task": 0, "knowledge": 0}
        for t in ["conversation", "customer", "task", "knowledge"]:
            pat = f'%"type": "{t}"%'
            stats[t] = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE metadata LIKE ?", (pat,)
            ).fetchone()[0]

        return {"items": items, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_memories(q: str = Query(..., min_length=1), limit: int = Query(20, le=100)):
    """Search memory entries via FTS5."""
    mem = _get_memory()
    try:
        results = mem.search(q, limit=limit)
        items = []
        for r in results:
            items.append({
                "id": r.id,
                "content": r.content,
                "type": r.metadata.get("type", "unknown") if r.metadata else "unknown",
                "metadata": r.metadata or {},
                "createdAt": str(r.created_at),
                "relevanceScore": getattr(r, "relevance_score", None),
            })
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_memory(body: MemoryCreate):
    """Create a new memory entry."""
    mem = _get_memory()
    try:
        metadata = body.metadata or {}
        if body.type:
            metadata["type"] = body.type
        entry = mem.store(body.content, metadata)
        return {
            "id": entry.id,
            "content": entry.content,
            "metadata": entry.metadata,
            "createdAt": str(entry.created_at),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{entry_id}")
async def update_memory(entry_id: int, body: MemoryUpdate):
    """Update a memory entry."""
    mem = _get_memory()
    try:
        entry = mem.update(entry_id, content=body.content, metadata=body.metadata)
        if entry is None:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        return {
            "id": entry.id,
            "content": entry.content,
            "metadata": entry.metadata,
            "updatedAt": str(entry.updated_at),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{entry_id}")
async def delete_memory(entry_id: int):
    """Delete a memory entry."""
    mem = _get_memory()
    try:
        deleted = mem.delete(entry_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        return {"ok": True, "deleted": entry_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
