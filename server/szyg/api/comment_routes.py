"""
智能评论状态机 API

提供 CommentTask 的 CRUD + 状态控制 + 执行记录查询 + 引擎 tick

底层数据库由 szyg.comment_db 管理，状态流转由 szyg.comment_engine 驱动。
"""

import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from szyg.comment_db import (
    init_db,
    create_task as db_create_task,
    get_task as db_get_task,
    list_tasks as db_list_tasks,
    update_task as db_update_task,
    delete_task as db_delete_task,
    transition as db_transition,
    get_records as db_get_records,
    get_transitions as db_get_transitions,
    get_dashboard as db_get_dashboard,
)
from szyg.comment_engine import CommentEngine
from szyg.models.comment_state_machine import (
    CommentTask,
    CommentTaskCreate,
    CommentTaskUpdate,
    CommentTaskStatus,
)

router = APIRouter(prefix="/api/comment", tags=["smart-comment"])
init_db()


# ── CRUD ───────────────────────────────────────────────────────────


@router.post("/tasks", response_model=CommentTask)
async def create_task(payload: CommentTaskCreate):
    task = CommentTask(**payload.model_dump())
    db_create_task(task.model_dump())
    return task


@router.get("/tasks", response_model=List[dict])
async def list_tasks(
    status: Optional[str] = Query(None, description="按状态筛选"),
    platform: Optional[str] = Query(None, description="按平台筛选"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return db_list_tasks(status=status, platform=platform, limit=limit, offset=offset)


@router.get("/tasks/{task_id}", response_model=dict)
async def get_task(task_id: str):
    task = db_get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/tasks/{task_id}", response_model=dict)
async def update_task(task_id: str, payload: CommentTaskUpdate):
    task = db_get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    updates = {}
    for k, v in payload.model_dump(exclude_unset=True).items():
        if v is not None:
            updates[k] = v

    # 状态变更时记录转移日志
    if "status" in updates and updates["status"] != task["status"]:
        db_transition(task_id, updates["status"], "用户手动更新状态", event="api_update")
        del updates["status"]  # transition 已更新状态

    result = db_update_task(task_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    if not db_get_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    db_delete_task(task_id)
    return {"deleted": task_id}


# ── 状态控制 ───────────────────────────────────────────────────────


class StatusActionRequest(BaseModel):
    reason: Optional[str] = None


@router.post("/tasks/{task_id}/pause")
async def pause_task(task_id: str, req: Optional[StatusActionRequest] = None):
    if not db_get_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return db_transition(task_id, CommentTaskStatus.PAUSED.value, req.reason if req else "用户暂停", event="api_action")


@router.post("/tasks/{task_id}/resume")
async def resume_task(task_id: str, req: Optional[StatusActionRequest] = None):
    if not db_get_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return db_transition(task_id, CommentTaskStatus.MONITORING.value, req.reason if req else "用户恢复", event="api_action")


@router.post("/tasks/{task_id}/approve")
async def approve_task(task_id: str):
    """人工审核通过：reviewing -> queued"""
    if not db_get_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return db_transition(task_id, CommentTaskStatus.QUEUED.value, "人工审核通过", event="api_action")


@router.post("/tasks/{task_id}/reject")
async def reject_task(task_id: str, req: Optional[StatusActionRequest] = None):
    """人工审核驳回：reviewing -> generating（重新生成）"""
    if not db_get_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return db_transition(task_id, CommentTaskStatus.GENERATING.value, req.reason if req else "人工审核驳回，重新生成", event="api_action")


# ── 记录查询 ───────────────────────────────────────────────────────


@router.get("/tasks/{task_id}/records")
async def get_records(task_id: str, limit: int = Query(50, ge=1, le=200)):
    return db_get_records(task_id, limit)


@router.get("/tasks/{task_id}/transitions")
async def get_transitions(task_id: str, limit: int = Query(100, ge=1, le=500)):
    return db_get_transitions(task_id, limit)


# ── 仪表盘 ─────────────────────────────────────────────────────────


@router.get("/dashboard")
async def dashboard():
    return db_get_dashboard()


# ── 引擎控制 ───────────────────────────────────────────────────────


@router.post("/tick")
async def tick_engine():
    """手动触发状态机引擎执行一次 tick（用于测试或即时执行）"""
    engine = CommentEngine()
    try:
        stats = await engine.tick()
        return {"success": True, **stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await engine.close()


# ── 意向识别 + 自动线索创建 ──────────────────────────────────────


class IntentCheckRequest(BaseModel):
    platform: str
    reply_content: str
    task_context: str = ""


@router.post("/check-intent")
async def check_intent(req: IntentCheckRequest):
    """对用户评论/回复进行意向评分。

    高意向内容自动创建线索到线索管家（Lead Manager）。
    对标: 销氪AIsales 意向识别 / 探迹AI评分

    用法: 在 smart-comment 引擎执行后，对用户回复调用此接口
    """
    engine = CommentEngine()
    try:
        result = await engine.score_reply_intent(
            platform=req.platform,
            reply_content=req.reply_content,
            task_context=req.task_context,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await engine.close()
