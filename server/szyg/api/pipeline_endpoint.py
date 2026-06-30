"""Pipeline API — 多模型AIGC流水线编排REST端点。

利用火山引擎"一个API调用多个模型"的能力，提供:
  - 流水线模板查询
  - 流水线执行
  - 执行状态查询
  - 执行历史
"""

import json, logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from szyg.pipeline_engine import PipelineRegistry, PipelineExecutor, get_pipeline_registry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

# ── Models ──────────────────────────────────────────────────────────────

class PipelineListRequest(BaseModel):
    pass

class PipelineExecuteRequest(BaseModel):
    name: str
    inputs: dict = Field(default_factory=dict)
    model: str = "doubao-pro-128k"  # 默认使用火山引擎

class PipelineStatusRequest(BaseModel):
    pipeline_id: str

# ── Routes ──────────────────────────────────────────────────────────────

@router.get("/templates")
async def list_templates():
    """列出所有预定义的流水线模板。"""
    registry = get_pipeline_registry()
    return {"templates": registry.list(), "total": len(registry._pipelines)}


@router.get("/templates/{name}")
async def get_template(name: str):
    """获取单个流水线模板的详细信息。"""
    registry = get_pipeline_registry()
    pipeline = registry.get(name)
    if not pipeline:
        raise HTTPException(404, f"流水线模板不存在: {name}")
    return {
        "name": pipeline.name,
        "description": pipeline.description,
        "nodes": [{"id": n.id, "type": n.type.value, "name": n.name, "model": n.model} for n in pipeline.nodes],
        "inputs_schema": pipeline.inputs_schema,
        "outputs_schema": pipeline.outputs_schema,
    }


@router.post("/execute")
async def execute_pipeline(req: PipelineExecuteRequest):
    """执行流水线（同步返回结果）。"""
    registry = get_pipeline_registry()
    pipeline = registry.get(req.name)
    if not pipeline:
        raise HTTPException(404, f"流水线模板不存在: {name}")

    try:
        from szyg.integrations.volcengine_client import VolcEngineClient
        client = VolcEngineClient()
        executor = PipelineExecutor(client)
        ctx = await executor.run(pipeline, inputs=req.inputs)
        await client.close()

        return {
            "ok": True,
            "pipeline_id": ctx.pipeline_id,
            "pipeline_name": pipeline.name,
            "status": "completed" if not ctx.errors else "partial",
            "outputs": ctx.outputs,
            "artifacts": ctx.artifacts,
            "node_status": ctx.status,
            "errors": ctx.errors,
            "duration_ms": _calc_duration(ctx.start_time, ctx.end_time),
        }
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        raise HTTPException(500, f"流水线执行失败: {str(e)[:200]}")


@router.post("/execute/stream")
async def execute_pipeline_stream(req: PipelineExecuteRequest):
    """执行流水线（SSE流式返回进度）。

    实时推送每个节点的执行状态:
      - type: "node_status" → 状态更新
      - type: "done" → 流水线完成
      - type: "error" → 执行失败
    """
    import asyncio as _asyncio

    registry = get_pipeline_registry()
    pipeline = registry.get(req.name)
    if not pipeline:
        raise HTTPException(404, f"流水线模板不存在: {req.name}")

    async def event_stream():
        from szyg.integrations.volcengine_client import VolcEngineClient
        client = VolcEngineClient()
        executor = PipelineExecutor(client)

        # Queue bridges sync callback → async SSE generator
        queue: _asyncio.Queue = _asyncio.Queue()

        def progress_callback(node_id: str, status: str, message: str):
            """Called synchronously within PipelineExecutor.run() (same event loop)."""
            event = json.dumps({
                "type": "node_status",
                "node_id": node_id,
                "status": status,
                "message": message,
                "timestamp": datetime.now().isoformat(),
            }, ensure_ascii=False)
            queue.put_nowait(event)

        async def run_pipeline():
            """Background task: execute pipeline, push results to queue."""
            try:
                ctx = await executor.run(
                    pipeline,
                    inputs=req.inputs,
                    progress_callback=progress_callback,
                )
                await client.close()
                done_event = json.dumps({
                    "type": "done",
                    "pipeline_id": ctx.pipeline_id,
                    "outputs": ctx.outputs,
                    "artifacts": ctx.artifacts,
                    "status": ctx.status,
                    "errors": ctx.errors,
                }, ensure_ascii=False)
                queue.put_nowait(done_event)
            except Exception as e:
                await client.close()
                error_event = json.dumps({
                    "type": "error",
                    "message": str(e)[:200],
                }, ensure_ascii=False)
                queue.put_nowait(error_event)

        # Run pipeline as a concurrent task
        bg_task = _asyncio.create_task(run_pipeline())

        # Stream events from queue
        while True:
            data = await queue.get()
            yield f"data: {data}\n\n"
            parsed = json.loads(data)
            if parsed.get("type") in ("done", "error"):
                break

        await bg_task  # Propagate exceptions if any

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/execute/video")
async def execute_video_pipeline(topic: str, duration: int = 30):
    """快捷执行AI短视频流水线。"""
    registry = get_pipeline_registry()
    pipeline = registry.get("ai_short_video")
    if not pipeline:
        raise HTTPException(500, "AI短视频流水线未注册")

    try:
        from szyg.integrations.volcengine_client import VolcEngineClient
        client = VolcEngineClient()
        executor = PipelineExecutor(client)
        ctx = await executor.run(pipeline, inputs={"topic": topic, "duration": duration})
        await client.close()

        return {
            "ok": True,
            "pipeline_id": ctx.pipeline_id,
            "topic": topic,
            "script": ctx.outputs.get("script", {}),
            "artifacts": ctx.artifacts,
            "status": ctx.status,
            "errors": ctx.errors,
        }
    except Exception as e:
        raise HTTPException(500, f"AI视频流水线失败: {str(e)[:200]}")


def _calc_duration(start: str, end: str) -> int:
    """计算执行耗时(ms)。"""
    try:
        from datetime import datetime
        s = datetime.fromisoformat(start)
        e = datetime.fromisoformat(end) if end else datetime.now()
        return int((e - s).total_seconds() * 1000)
    except Exception:
        return 0
