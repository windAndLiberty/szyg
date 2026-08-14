"""
Video Cut Engine — 视频剪辑引擎

对标数创引擎: core/video_cut.pyd + core/video_title.pyd + core/video_templates/

功能:
  - 视频裁剪 / 拼接 / 变速
  - 标题文字叠加 (多字体支持)
  - 音频替换 / 混音
  - 模板化视频生成
  - 封面提取

依赖: FFmpeg (D:\tools\ffmpeg\ffmpeg.exe)
模板: server/szyg/platforms/../video_templates/ (从数创引擎移植)
"""
import json
import logging
import os
import random
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── FFmpeg ────────────────────────────────────────────

FFMPEG_PATHS = [
    os.environ.get("SZYG_FFMPEG_PATH", ""),
    str(Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "third_party" / "ffmpeg" / "ffmpeg.exe"),
    str(Path(sys.executable).parent / "third_party" / "ffmpeg" / "ffmpeg.exe"),
    "ffmpeg",
    r"D:\tools\ffmpeg\bin\ffmpeg.exe",
    r"D:\tools\ffmpeg\ffmpeg.exe",
    r"C:\ffmpeg\bin\ffmpeg.exe",
]
_ffmpeg: str | None = None

def _get_ffmpeg() -> str:
    global _ffmpeg
    if _ffmpeg:
        return _ffmpeg
    for path in FFMPEG_PATHS:
        if path and (Path(path).exists() or _which(path)):
            _ffmpeg = path
            return path
    # Try which
    import shutil as _sh
    found = _sh.which("ffmpeg")
    if found:
        _ffmpeg = found
        return found
    raise FileNotFoundError("FFmpeg not found. Install: winget install ffmpeg")

def _which(cmd: str) -> bool:
    try:
        subprocess.run([cmd, "-version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False

def _ffmpeg_run(args: list, timeout: int = 300) -> subprocess.CompletedProcess:
    ffmpeg = _get_ffmpeg()
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"] + args
    logger.debug(f"ffmpeg: {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


# ── Video Templates ────────────────────────────────────

TEMPLATES_DIR = Path(__file__).parent / "video_templates"
FONTS_DIR = Path(__file__).parent / "fonts"


def list_templates() -> list[dict]:
    """列出所有可用视频模板"""
    if not TEMPLATES_DIR.exists():
        return []
    templates = []
    for tpl_dir in sorted(TEMPLATES_DIR.iterdir()):
        if tpl_dir.is_dir():
            cfg_file = tpl_dir / "config.json"
            preview = tpl_dir / "preview.png"
            info = {"id": tpl_dir.name, "has_config": cfg_file.exists(), "has_preview": preview.exists()}
            if cfg_file.exists():
                try:
                    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
                    info["name"] = cfg.get("name", tpl_dir.name)
                    info["duration"] = cfg.get("duration", 0)
                    info["width"] = cfg.get("width", 1080)
                    info["height"] = cfg.get("height", 1920)
                except Exception:
                    info["name"] = tpl_dir.name
            templates.append(info)
    return templates


# ── Core Operations ────────────────────────────────────

def cut_video(input_path: str, start: float, duration: float, output_path: str) -> str:
    """裁剪视频片段"""
    result = _ffmpeg_run([
        "-ss", str(start), "-i", input_path,
        "-t", str(duration), "-c", "copy", output_path
    ])
    if result.returncode != 0:
        raise RuntimeError(result.stderr[:500])
    return output_path


def concat_videos(input_files: list[str], output_path: str) -> str:
    """拼接多个视频"""
    # Create concat file list
    list_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    for f in input_files:
        list_file.write(f"file '{Path(f).as_posix()}'\n")
    list_file.close()

    result = _ffmpeg_run([
        "-f", "concat", "-safe", "0", "-i", list_file.name,
        "-c", "copy", output_path
    ])
    os.unlink(list_file.name)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[:500])
    return output_path


def concat_videos_normalized(input_files: list[str], output_path: str, ratio: str = "9:16") -> str:
    """Normalize generated clips before concatenation to avoid codec/size drift."""
    if not input_files:
        raise ValueError("No video segments provided")
    dimensions = {
        "9:16": (720, 1280), "16:9": (1280, 720), "1:1": (720, 720),
        "4:3": (960, 720), "3:4": (720, 960), "21:9": (1680, 720),
    }
    width, height = dimensions.get(ratio, dimensions["9:16"])
    work_dir = Path(tempfile.mkdtemp(prefix="szyg-video-normalize-"))
    normalized: list[str] = []
    try:
        for index, input_file in enumerate(input_files):
            target = work_dir / f"segment_{index:03d}.mp4"
            result = _ffmpeg_run([
                "-i", input_file,
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-movflags", "+faststart",
                str(target),
            ], timeout=600)
            if result.returncode != 0:
                raise RuntimeError(result.stderr[:500])
            normalized.append(str(target))
        return concat_videos(normalized, output_path)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def change_speed(input_path: str, speed: float, output_path: str) -> str:
    """视频变速 (0.5=慢放, 2.0=快进)"""
    setpts = 1.0 / speed
    result = _ffmpeg_run([
        "-i", input_path,
        "-filter:v", f"setpts={setpts}*PTS",
        "-filter:a", f"atempo={speed}" if 0.5 <= speed <= 2.0 else "anull",
        output_path
    ])
    if result.returncode != 0:
        raise RuntimeError(result.stderr[:500])
    return output_path


def add_text_overlay(
    input_path: str, output_path: str, text: str,
    x: str = "(w-text_w)/2", y: str = "(h-text_h)/2",
    font_size: int = 48, font_color: str = "white",
    font_file: str = "", duration: float = 0,
) -> str:
    """在视频上叠加文字标题"""
    font_param = f":fontfile='{font_file}'" if font_file and Path(font_file).exists() else ""
    drawtext = (
        f"drawtext=text='{text}':fontsize={font_size}:fontcolor={font_color}"
        f":x={x}:y={y}{font_param}"
    )
    if duration > 0:
        drawtext += f":enable='between(t,0,{duration})'"

    result = _ffmpeg_run([
        "-i", input_path,
        "-vf", drawtext,
        "-codec:a", "copy", output_path
    ])
    if result.returncode != 0:
        raise RuntimeError(result.stderr[:500])
    return output_path


def replace_audio(video_path: str, audio_path: str, output_path: str) -> str:
    """替换视频音频"""
    result = _ffmpeg_run([
        "-i", video_path, "-i", audio_path,
        "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
        "-shortest", output_path
    ])
    if result.returncode != 0:
        raise RuntimeError(result.stderr[:500])
    return output_path


def mix_audio(video_path: str, audio_path: str, output_path: str,
              video_vol: float = 0.3, audio_vol: float = 1.0) -> str:
    """混合视频原声和背景音乐"""
    result = _ffmpeg_run([
        "-i", video_path, "-i", audio_path,
        "-filter_complex",
        f"[0:a]volume={video_vol}[v];[1:a]volume={audio_vol}[b];[v][b]amix=inputs=2:duration=first",
        "-c:v", "copy", output_path
    ])
    if result.returncode != 0:
        raise RuntimeError(result.stderr[:500])
    return output_path


def extract_frame(input_path: str, time_sec: float, output_path: str,
                   width: int = 0, height: int = 0) -> str:
    """提取视频帧为图片 (封面)"""
    scale = f",scale={width}:{height}" if width > 0 and height > 0 else ""
    result = _ffmpeg_run([
        "-ss", str(time_sec), "-i", input_path,
        "-vframes", "1", "-q:v", "2",
        "-vf", f"select=eq(n\\,0){scale}",
        output_path
    ])
    if result.returncode != 0:
        raise RuntimeError(result.stderr[:500])
    return output_path


def get_video_info(input_path: str) -> dict:
    """获取视频元信息 (时长/分辨率/编码)"""
    result = _ffmpeg_run([
        "-i", input_path, "-f", "null", "-"
    ])
    # FFmpeg outputs info to stderr
    output = result.stderr
    info = {"file": input_path, "duration": 0, "width": 0, "height": 0, "codec": ""}
    for line in output.split("\n"):
        if "Duration" in line:
            dur_str = line.split("Duration: ")[1].split(",")[0].strip()
            try:
                parts = dur_str.split(":")
                info["duration"] = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            except (ValueError, IndexError):
                logger.debug("Failed to parse duration from: %s", dur_str)
        if "Stream #0:0" in line and "Video" in line:
            for part in line.split(","):
                part = part.strip()
                if "x" in part and part[0].isdigit():
                    try:
                        w, h = part.split("x")[0], part.split("x")[1].split()[0]
                        info["width"] = int(w)
                        info["height"] = int(h)
                    except (ValueError, IndexError):
                        pass  # dimension parsing is best-effort
                if part in ("h264", "h265", "hevc", "vp8", "vp9", "av1"):
                    info["codec"] = part
    return info


# ── Template Render ────────────────────────────────────

def render_template(
    template_id: str,
    media_files: list[str],
    title: str,
    subtitle: str = "",
    output_path: str = "",
    font_name: str = "",
) -> str:
    """
    使用模板渲染视频。

    template_id: 模板目录名 (如 tpl_1778211185091)
    media_files: 输入媒体文件列表
    title: 视频标题
    subtitle: 副标题
    output_path: 输出路径 (默认自动生成)
    font_name: 字体文件名 (可选, 从 fonts/ 目录选择)
    """
    tpl_dir = TEMPLATES_DIR / template_id
    if not tpl_dir.exists():
        raise ValueError(f"Template not found: {template_id}")

    if not output_path:
        output_path = str(Path(tempfile.gettempdir()) / f"szyg_video_{int(datetime.now().timestamp())}.mp4")

    # 读取模板配置
    cfg = {}
    cfg_file = tpl_dir / "config.json"
    if cfg_file.exists():
        cfg = json.loads(cfg_file.read_text(encoding="utf-8"))

    # 基本渲染: 如果只有一个文件, 直接加标题
    input_file = media_files[0] if media_files else ""

    if not input_file:
        raise ValueError("No media files provided")

    # 找字体
    font_path = ""
    if font_name and FONTS_DIR.exists():
        candidate = FONTS_DIR / font_name
        if candidate.exists():
            font_path = str(candidate)

    # Step 1: 加标题覆盖
    tmp1 = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    duration = cfg.get("duration", 0)
    add_text_overlay(
        input_file, tmp1, title,
        x=cfg.get("title_x", "(w-text_w)/2"),
        y=cfg.get("title_y", "h/3"),
        font_size=cfg.get("title_size", 64),
        font_file=font_path or "",
        duration=duration,
    )

    # Step 2: 加副标题
    tmp2 = output_path
    if subtitle:
        add_text_overlay(
            tmp1, tmp2, subtitle,
            x=cfg.get("subtitle_x", "(w-text_w)/2"),
            y=cfg.get("subtitle_y", "h/3+80"),
            font_size=cfg.get("subtitle_size", 36),
            font_color="white",
            font_file=font_path or "",
        )
    else:
        tmp2 = tmp1

    # 清理临时文件
    if tmp1 != tmp2 and Path(tmp1).exists():
        os.unlink(tmp1)

    return output_path


def list_fonts() -> list[str]:
    """列出可用字体"""
    if not FONTS_DIR.exists():
        return []
    return sorted([f.name for f in FONTS_DIR.glob("*.ttf")] + [f.name for f in FONTS_DIR.glob("*.ttc")] + [f.name for f in FONTS_DIR.glob("*.otf")])


# ── Quick exports ─────────────────────────────────────

__all__ = [
    "cut_video", "concat_videos", "concat_videos_normalized", "change_speed", "add_text_overlay",
    "replace_audio", "mix_audio", "extract_frame", "get_video_info",
    "list_templates", "render_template", "list_fonts",
]
