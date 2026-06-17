"""
「域灵」AI 短视频创作流水线。

端到端流程: 用户输入主题 → 写脚本 → 生封面 → 配音 → FFmpeg合成 → 输出视频

配置来源: config.yaml (llm.openrouter, image.dashscope, tts.edge_tts, video.*)
环境变量: OPENROUTER_API_KEY, DASHSCOPE_API_KEY

用法:
    python -m yuling.pipelines.video_creator "AI发展趋势" 60
"""

import asyncio
import json
import subprocess
import time
from pathlib import Path

import edge_tts

from yuling.config.loader import load_config
from yuling.integrations.openrouter_client import OpenRouterClient
from yuling.integrations.dashscope_client import DashScopeImageClient


class VideoCreator:
    """AI 短视频创作流水线。读取 config.yaml 获取所有配置。"""

    def __init__(self, config: dict | None = None):
        cfg = config or load_config()

        # LLM
        llm_cfg = cfg.get("llm", {}).get("openrouter", {})
        self.llm = OpenRouterClient(
            api_key=llm_cfg.get("api_key", ""),
            base_url=llm_cfg.get("base_url", "https://openrouter.ai/api/v1"),
            default_model=llm_cfg.get("default_model", "openrouter/free"),
            timeout=llm_cfg.get("timeout", 60),
        )

        # 图像
        img_cfg = cfg.get("image", {}).get("dashscope", {})
        self.image = DashScopeImageClient(
            api_key=img_cfg.get("api_key", ""),
            model=img_cfg.get("model", "qwen-image-plus"),
        )

        # TTS
        tts_cfg = cfg.get("tts", {}).get("edge_tts", {})
        self.voice = tts_cfg.get("voice", "zh-CN-XiaoxiaoNeural")

        # 视频输出
        video_cfg = cfg.get("video", {})
        self.ffmpeg = video_cfg.get("ffmpeg_path", "ffmpeg")
        self.output_dir = Path(video_cfg.get("output_dir", "./data/output"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def create(self, topic: str, duration_seconds: int = 60) -> dict:
        """完整的短视频创作流程。

        Returns:
            dict: {
                "script": str, "cover": str, "audio": str,
                "video": str, "duration": float
            }
        """
        ts = int(time.time())

        # ── Step 1: 生成脚本 ──
        print(f"📝 生成脚本: {topic}")
        script = await self._generate_script(topic, duration_seconds)

        # ── Step 2: 生成封面图 ──
        print("🎨 生成封面图...")
        covers = await self.image.generate(
            prompt=script.get("cover_prompt", f"{topic}, 短视频封面, 高清"),
            size="1024*1024",
            output_dir=str(self.output_dir / "images"),
        )
        cover_path = covers[0] if covers else None
        if cover_path:
            print(f"   封面: {cover_path}")

        # ── Step 3: 生成配音 ──
        print("🎙️ 生成配音...")
        narration = script.get("narration", script.get("script", topic))
        audio_path = str(self.output_dir / f"narration_{ts}.mp3")
        await self._text_to_speech(narration, audio_path)
        print(f"   配音: {audio_path}")

        # ── Step 4: FFmpeg 合成视频 ──
        print("🎬 合成视频...")
        video_path = str(self.output_dir / f"output_{ts}.mp4")
        duration = await self._compose_video(
            cover_path or self._make_solid_color_bg(),
            audio_path,
            video_path,
            script.get("subtitles", ""),
        )
        print(f"   视频: {video_path} ({duration:.1f}s)")

        return {
            "script": script,
            "cover": cover_path,
            "audio": audio_path,
            "video": video_path,
            "duration": duration,
        }

    async def _generate_script(self, topic: str, duration: int) -> dict:
        """用 LLM 生成视频脚本。"""
        prompt = f"""你是一个短视频创作专家。为主题「{topic}」创作一个约{duration}秒的短视频脚本。

请用 JSON 格式返回，包含以下字段：
{{
    "title": "视频标题(吸引眼球,10字以内)",
    "cover_prompt": "封面图描述(英文,给AI绘画用,描述画面元素和风格)",
    "narration": "旁白文本(中文,适合朗读,{duration}秒大约{int(duration*2.5)}字)",
    "subtitles": "字幕文本(和旁白相同)"
}}

只返回 JSON，不要其他内容。"""

        resp = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
        )
        content = resp["message"]["content"]
        # 提取 JSON
        try:
            # 去掉可能的 markdown 代码块包裹
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
        except json.JSONDecodeError:
            return {
                "title": topic,
                "cover_prompt": f"{topic}, video cover, high quality",
                "narration": f"今天我们来聊聊{topic}。这是一个非常有趣的话题。",
                "subtitles": "",
            }

    async def _text_to_speech(self, text: str, output_path: str) -> None:
        """edge-tts 文字转语音。"""
        communicate = edge_tts.Communicate(text, self.VOICE)
        await communicate.save(output_path)

    async def _compose_video(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        subtitles: str = "",
    ) -> float:
        """用 FFmpeg 合成视频: 封面图 + 音频 + 可选字幕。"""
        # 获取音频时长
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", audio_path],
            capture_output=True, text=True,
        )
        duration = float(result.stdout.strip())

        # 构建 FFmpeg 命令
        cmd = [
            self.ffmpeg, "-y",
            "-loop", "1", "-i", image_path,
            "-i", audio_path,
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            "-vf", f"scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
            output_path,
        ]

        # 如果有字幕，添加字幕滤镜
        if subtitles:
            # 写临时字幕文件
            srt_path = output_path.replace(".mp4", ".srt")
            await self._write_srt(subtitles, duration, srt_path)
            cmd.insert(-3, "-vf")
            cmd.insert(-3, f"scale=1920:1080,subtitles={srt_path}:force_style='Fontsize=24,Alignment=2'")

        subprocess.run(cmd, capture_output=True, check=True)
        return duration

    async def _write_srt(self, text: str, duration: float, path: str) -> None:
        """生成简单 SRT 字幕文件。"""
        # 按句号分句
        sentences = [s.strip() for s in text.replace("！", "。").replace("？", "。").split("。") if s.strip()]
        if not sentences:
            sentences = [text]

        chars_per_sec = len(text) / duration if duration > 0 else 5
        srt = ""
        t = 0.0
        for i, s in enumerate(sentences):
            d = max(1.0, len(s) / chars_per_sec)
            srt += f"{i+1}\n"
            srt += f"{self._fmt_time(t)} --> {self._fmt_time(t+d)}\n"
            srt += f"{s}\n\n"
            t += d

        Path(path).write_text(srt, encoding="utf-8")

    def _make_solid_color_bg(self) -> str:
        """没有封面时生成纯色背景。"""
        path = str(self.output_dir / "bg.png")
        subprocess.run([
            self.ffmpeg, "-y", "-f", "lavfi",
            "-i", "color=c=0x1a1a2e:s=1920x1080:d=1",
            "-frames:v", "1", path,
        ], capture_output=True, check=True)
        return path

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    async def close(self):
        await self.llm.close()
        await self.image.close()


# ── CLI 入口 ─────────────────────────────────────────────────────────────────


async def main():
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else "人工智能改变未来"
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    creator = VideoCreator()
    try:
        result = await creator.create(topic, duration)
        print(f"\n✅ 视频创作完成!")
        print(f"   脚本: {result['script'].get('title', topic)}")
        print(f"   封面: {result['cover']}")
        print(f"   配音: {result['audio']}")
        print(f"   视频: {result['video']}  ({result['duration']:.1f}s)")
    finally:
        await creator.close()


if __name__ == "__main__":
    asyncio.run(main())
