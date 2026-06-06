"""AI 视频创作 API — 本地 FFmpeg 视频生成。"""

import os
import subprocess
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/video", tags=["video"])

FFMPEG = os.environ.get("FFMPEG_PATH", r"D:\tools\ffmpeg\bin\ffmpeg.exe")
OUTPUT_DIR = Path(os.environ.get("SZYG_DATA_DIR", "data")) / "video_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class CreateRequest(BaseModel):
    theme: str
    duration: int = 10
    width: int = 1280
    height: int = 720
    bg_color: str = "#1a1f25"
    text_color: str = "white"
    font_size: int = 48


@router.post("/create")
async def create_video(req: CreateRequest):
    """使用 FFmpeg 生成带文字叠加的视频。"""
    if not req.theme.strip():
        raise HTTPException(400, "主题不能为空")
    if req.duration < 3 or req.duration > 120:
        raise HTTPException(400, "时长需在 3-120 秒之间")

    output_name = f"video_{uuid.uuid4().hex[:8]}.mp4"
    output_path = str(OUTPUT_DIR / output_name)

    # Build text: join all lines with newlines
    lines = [l.strip() for l in req.theme.replace("；", ";").replace("。", ";").split(";") if l.strip()]
    if not lines:
        lines = [req.theme]

    # Build multi-line drawtext filter
    total_lines = len(lines)
    line_height = req.font_size + 16
    start_y = (req.height - total_lines * line_height) // 2

    draw_filters = []
    for i, line in enumerate(lines):
        safe = line.replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")
        y = start_y + i * line_height
        draw_filters.append(
            f"drawtext=text='{safe}':"
            f"fontsize={req.font_size}:fontcolor={req.text_color}:"
            f"x=(w-text_w)/2:y={y}:"
            f"box=1:boxcolor=black@0.5:boxborderw=12"
        )

    vf = ",".join(draw_filters)

    bg_hex = req.bg_color.replace("#", "0x")

    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi",
        "-i", f"color=c={bg_hex}:s={req.width}x{req.height}:d={req.duration}:r=25",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, timeout=120, text=True)
    if result.returncode != 0:
        raise HTTPException(500, f"FFmpeg 渲染失败: {result.stderr[-300:]}")

    return {
        "ok": True,
        "filename": output_name,
        "url": f"/api/video/download/{output_name}",
        "duration": req.duration,
        "theme": req.theme,
        "slides": len(lines),
    }


@router.get("/download/{filename}")
async def download_video(filename: str):
    """下载生成的视频文件。"""
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "视频文件不存在")
    return FileResponse(str(path), media_type="video/mp4", filename=filename)
