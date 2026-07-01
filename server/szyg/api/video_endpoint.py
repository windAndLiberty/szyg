"""AI 视频生成 API — 火山引擎 doubao-video 直连。"""

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/video", tags=["video"])

VOLC_OUTPUT = Path("data/volcengine_output")
VOLC_OUTPUT.mkdir(parents=True, exist_ok=True)


class CreateRequest(BaseModel):
    prompt: str
    duration: int = 5
    size: str = "720p"          # 720p | 1080p
    model: str = "doubao-video"
    image_url: str = ""          # 图生视频 (可选)


@router.post("/create")
async def create_video(req: CreateRequest):
    """提交 AI 视频生成任务 (文生视频 / 图生视频)。

    火山引擎视频生成是异步任务，返回 task_id，前端轮询 /api/video/task/{task_id}。
    """
    if not req.prompt.strip():
        raise HTTPException(400, "视频描述不能为空")
    if req.duration not in (5, 10):
        raise HTTPException(400, "时长仅支持 5 秒或 10 秒")
    if req.size not in ("720p", "1080p"):
        raise HTTPException(400, "分辨率仅支持 720p 或 1080p")

    try:
        from szyg.integrations.volcengine_client import VolcEngineClient
        client = VolcEngineClient()
        result = await client.generate_video(
            prompt=req.prompt.strip(),
            image_url=req.image_url or None,
            model=req.model,
            duration=req.duration,
            size=req.size,
        )
        await client.close()
        return {
            "ok": True,
            "task_id": result["task_id"],
            "status": result["status"],
            "model": req.model,
            "prompt": req.prompt.strip(),
        }
    except Exception as e:
        raise HTTPException(500, f"视频生成提交失败: {str(e)[:200]}")


@router.get("/task/{task_id}")
async def video_task_status(task_id: str, model: str = "doubao-video"):
    """查询 AI 视频生成任务状态。

    任务完成时自动下载视频到本地，返回可访问的视频 URL。
    """
    try:
        from szyg.integrations.volcengine_client import VolcEngineClient
        client = VolcEngineClient()
        result = await client.get_video_task(task_id=task_id, model=model)

        # 如果已完成且有视频URL，下载到本地
        if result.get("status") == "succeeded" and result.get("video_url"):
            local_path = await client.download_video(
                result["video_url"],
                output_name=f"ai_video_{task_id[:8]}_{uuid.uuid4().hex[:6]}.mp4"
            )
            filename = Path(local_path).name
            result["local_path"] = local_path
            result["video_url"] = f"/api/files/volcengine_output/{filename}"
            result["download_url"] = f"/api/video/download/{filename}"

        await client.close()
        return result
    except Exception as e:
        raise HTTPException(500, f"查询视频任务失败: {str(e)[:200]}")


@router.get("/download/{filename}")
async def download_video(filename: str):
    """下载/播放生成的视频文件。"""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "非法文件名")
    path = (VOLC_OUTPUT / filename).resolve()
    if not str(path).startswith(str(VOLC_OUTPUT.resolve())):
        raise HTTPException(400, "非法文件路径")
    if not path.exists():
        raise HTTPException(404, "视频文件不存在")
    return FileResponse(str(path), media_type="video/mp4", filename=filename)
