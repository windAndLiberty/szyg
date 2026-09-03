"""FFmpeg视频处理客户端."""

import subprocess
from pathlib import Path
from typing import Tuple

from szyg.models.integration import BatchResult
from szyg.models.common import IntegrationError


class FFmpegClient:
    """FFmpeg视频处理客户端"""

    def __init__(
        self,
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe",
        templates_dir: str = "./data/ffmpeg_templates",
        threads: int = 4,
    ):
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self.templates_dir = templates_dir
        self.threads = threads

    def _run_command(
        self, args: list[str], timeout: float = 300.0
    ) -> Tuple[int, str, str]:
        """运行FFmpeg命令"""
        try:
            result = subprocess.run(
                [self.ffmpeg_path] + args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.returncode, result.stdout, result.stderr
        except FileNotFoundError:
            raise IntegrationError(f"FFmpeg not found at: {self.ffmpeg_path}")
        except subprocess.TimeoutExpired:
            raise IntegrationError(
                f"FFmpeg command timed out after {timeout}s"
            )

    async def batch_edit(
        self, input_dir: str, output_dir: str, template: str
    ) -> BatchResult:
        """批量编辑视频"""
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        video_files = (
            list(input_path.glob("*.mp4"))
            + list(input_path.glob("*.mov"))
            + list(input_path.glob("*.avi"))
        )
        completed = 0
        errors = []
        output_files = []

        for video_file in video_files:
            output_file = output_path / f"{video_file.stem}_edited.mp4"
            try:
                # 应用模板处理
                returncode, stdout, stderr = self._run_command(
                    [
                        "-i",
                        str(video_file),
                        "-c:v",
                        "libx264",
                        "-c:a",
                        "aac",
                        "-threads",
                        str(self.threads),
                        "-y",
                        str(output_file),
                    ]
                )
                if returncode == 0:
                    completed += 1
                    output_files.append(str(output_file))
                else:
                    errors.append(f"{video_file.name}: {stderr}")
            except Exception as e:
                errors.append(f"{video_file.name}: {str(e)}")

        return BatchResult(
            success=completed > 0,
            output_files=output_files,
            errors=errors,
            total=len(video_files),
            completed=completed,
        )

    async def extract_audio(
        self, video_path: str, output_path: str = None
    ) -> str:
        """从视频提取音频"""
        if output_path is None:
            video = Path(video_path)
            output_path = str(video.parent / f"{video.stem}.mp3")

        returncode, stdout, stderr = self._run_command(
            [
                "-i",
                video_path,
                "-vn",
                "-acodec",
                "libmp3lame",
                "-q:a",
                "2",
                "-y",
                output_path,
            ]
        )

        if returncode != 0:
            raise IntegrationError(f"Failed to extract audio: {stderr}")
        return output_path

    async def add_subtitles(
        self,
        video_path: str,
        subtitle_path: str,
        output_path: str = None,
    ) -> str:
        """添加字幕到视频"""
        if output_path is None:
            video = Path(video_path)
            output_path = str(video.parent / f"{video.stem}_subtitled.mp4")

        returncode, stdout, stderr = self._run_command(
            [
                "-i",
                video_path,
                "-vf",
                f"subtitles={subtitle_path}",
                "-c:a",
                "copy",
                "-y",
                output_path,
            ]
        )

        if returncode != 0:
            raise IntegrationError(f"Failed to add subtitles: {stderr}")
        return output_path

    async def run_command(
        self, args: list[str]
    ) -> Tuple[int, str, str]:
        """运行自定义FFmpeg命令"""
        return self._run_command(args)

    async def close(self):
        pass  # 无需关闭
