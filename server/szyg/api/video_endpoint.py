"""AI 视频生成 API — 火山引擎 doubao-video 直连。"""

import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from szyg.media_storage import get_media_output_dir, media_url_for_path, resolve_media_file

router = APIRouter(prefix="/api/video", tags=["video"])


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
        client = VolcEngineClient(output_dir=str(get_media_output_dir("video")))
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
        client = VolcEngineClient(output_dir=str(get_media_output_dir("video")))
        result = await client.get_video_task(task_id=task_id, model=model)

        # 如果已完成且有视频URL，下载到本地
        if result.get("status") == "succeeded" and result.get("video_url"):
            local_path = await client.download_video(
                result["video_url"],
                output_name=f"ai_video_{task_id[:8]}_{uuid.uuid4().hex[:6]}.mp4"
            )
            result["local_path"] = local_path
            result["video_url"] = media_url_for_path(local_path)
            result["download_url"] = media_url_for_path(local_path)

        await client.close()
        return result
    except Exception as e:
        raise HTTPException(500, f"查询视频任务失败: {str(e)[:200]}")


@router.get("/download/{filename}")
async def download_video(filename: str):
    """下载/播放生成的视频文件。"""
    try:
        path, _media_type = resolve_media_file("video", filename)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not path.exists():
        raise HTTPException(404, "视频文件不存在")
    return FileResponse(str(path), media_type="video/mp4", filename=filename)
