#!/usr/bin/env python3
"""MCP Server: Video Cut Engine — 视频剪辑引擎"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from szyg.mcp_server import MCPServer

server = MCPServer("szyg-video", "Video cutting, editing, and template rendering engine")


@server.tool("video_info", "获取视频元信息 (时长/分辨率/编码)")
def video_info(file_path: str):
    from szyg.video_cut_engine import get_video_info
    try:
        return get_video_info(file_path)
    except Exception as e:
        return {"error": str(e)}


@server.tool("video_cut", "裁剪视频片段 (start=开始秒数, duration=时长秒数)")
def video_cut(file_path: str, start: float, duration: float, output: str = ""):
    from szyg.video_cut_engine import cut_video
    import tempfile
    if not output:
        output = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    try:
        result = cut_video(file_path, start, duration, output)
        return {"output": result, "start": start, "duration": duration}
    except Exception as e:
        return {"error": str(e)}


@server.tool("video_concat", "拼接多个视频文件 (逗号分隔路径)")
def video_concat(files: str, output: str = ""):
    from szyg.video_cut_engine import concat_videos
    import tempfile
    file_list = [f.strip() for f in files.split(",") if f.strip()]
    if len(file_list) < 2:
        return {"error": "至少需要2个文件"}
    if not output:
        output = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    try:
        result = concat_videos(file_list, output)
        return {"output": result, "segments": len(file_list)}
    except Exception as e:
        return {"error": str(e)}


@server.tool("video_speed", "视频变速 (0.5=慢放一半, 2.0=快进一倍)")
def video_speed(file_path: str, speed: float, output: str = ""):
    from szyg.video_cut_engine import change_speed
    import tempfile
    if not output:
        output = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    try:
        result = change_speed(file_path, speed, output)
        return {"output": result, "speed": speed}
    except Exception as e:
        return {"error": str(e)}


@server.tool("video_add_title", "在视频上叠加文字标题")
def video_add_title(file_path: str, text: str, output: str = "",
                    font_size: int = 48, font_color: str = "white",
                    x: str = "(w-text_w)/2", y: str = "h/3"):
    from szyg.video_cut_engine import add_text_overlay
    import tempfile
    if not output:
        output = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    try:
        result = add_text_overlay(file_path, output, text, x=x, y=y, font_size=font_size, font_color=font_color)
        return {"output": result, "text": text}
    except Exception as e:
        return {"error": str(e)}


@server.tool("video_replace_audio", "替换视频的音频轨道")
def video_replace_audio(video_path: str, audio_path: str, output: str = ""):
    from szyg.video_cut_engine import replace_audio
    import tempfile
    if not output:
        output = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    try:
        result = replace_audio(video_path, audio_path, output)
        return {"output": result}
    except Exception as e:
        return {"error": str(e)}


@server.tool("video_mix_audio", "混合视频原声和背景音乐")
def video_mix_audio(video_path: str, bgm_path: str, output: str = "",
                    video_volume: float = 0.3, bgm_volume: float = 1.0):
    from szyg.video_cut_engine import mix_audio
    import tempfile
    if not output:
        output = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    try:
        result = mix_audio(video_path, bgm_path, output, video_vol=video_volume, audio_vol=bgm_volume)
        return {"output": result}
    except Exception as e:
        return {"error": str(e)}


@server.tool("video_extract_frame", "从视频中提取一帧作为封面图片")
def video_extract_frame(file_path: str, time_sec: float, output: str = "",
                         width: int = 0, height: int = 0):
    from szyg.video_cut_engine import extract_frame
    import tempfile
    if not output:
        output = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    try:
        result = extract_frame(file_path, time_sec, output, width, height)
        return {"output": result, "time": time_sec}
    except Exception as e:
        return {"error": str(e)}


@server.tool("video_templates", "列出可用的视频模板")
def video_templates():
    from szyg.video_cut_engine import list_templates
    templates = list_templates()
    return {"templates": templates, "count": len(templates)}


@server.tool("video_fonts", "列出可用的视频标题字体")
def video_fonts():
    from szyg.video_cut_engine import list_fonts
    fonts = list_fonts()
    return {"fonts": fonts, "count": len(fonts)}


@server.tool("video_render", "使用模板渲染视频 (加标题+字幕)")
def video_render(template_id: str, media_files: str, title: str,
                 subtitle: str = "", font_name: str = "", output: str = ""):
    from szyg.video_cut_engine import render_template
    import tempfile
    files = [f.strip() for f in media_files.split(",") if f.strip()]
    if not output:
        output = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    try:
        result = render_template(template_id, files, title, subtitle, output, font_name)
        return {"output": result, "template": template_id, "title": title}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    server.run()
