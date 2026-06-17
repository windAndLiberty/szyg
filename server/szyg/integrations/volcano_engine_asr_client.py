"""
火山引擎语音识别客户端 — 豆包语音识别。

调用火山引擎录音文件识别 API，将音频文件转换为文本。
API 文档: https://www.volcengine.com/docs/6561/80818

用法:
    client = VolcanoEngineASRClient(app_id="xxx", access_token="yyy")
    result = await client.transcribe("./audio.mp3")
    print(result.text)
"""

import os
import uuid
from pathlib import Path

import httpx

from szyg.models.common import IntegrationError
from szyg.models.integration import TranscriptionResult


class VolcanoEngineASRClient:
    """火山引擎语音识别客户端。

    使用火山引擎 openspeech API 进行录音文件识别。
    支持多种音频格式（mp3, wav, pcm, m4a, ogg 等）。
    """

    DEFAULT_BASE_URL = "https://openspeech.bytedance.com/api/v1/auc"

    def __init__(
        self,
        app_id: str | None = None,
        access_token: str | None = None,
        base_url: str | None = None,
        default_language: str = "zh-CN",
        timeout: float = 300.0,
    ):
        self.app_id = app_id or os.environ.get("VOLCANO_SPEECH_APP_ID", "")
        self.access_token = access_token or os.environ.get("VOLCANO_SPEECH_TOKEN", "")
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.default_language = default_language
        self.timeout = timeout

    async def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
        enable_punctuation: bool = True,
    ) -> TranscriptionResult:
        """将音频文件识别为文本。

        Args:
            audio_path: 音频文件本地路径
            language: 语言代码，如 zh-CN, en-US, ja-JP
            enable_punctuation: 是否启用智能标点

        Returns:
            TranscriptionResult: 识别结果
        """
        if not self.app_id or not self.access_token:
            raise IntegrationError(
                "VolcanoEngine ASR requires app_id and access_token. "
                "Set VOLCANO_SPEECH_APP_ID and VOLCANO_SPEECH_TOKEN env vars."
            )

        path = Path(audio_path)
        if not path.exists():
            raise IntegrationError(f"Audio file not found: {audio_path}")

        # 读取音频文件
        audio_bytes = path.read_bytes()
        audio_format = self._detect_format(path.suffix)

        headers = {
            "Authorization": f"Bearer; {self.access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "app": {
                "appid": self.app_id,
                "token": self.access_token,
                "cluster": "volcano-asr",
            },
            "user": {
                "uid": f"szyg_user_{uuid.uuid4().hex[:8]}",
            },
            "request": {
                "reqid": str(uuid.uuid4()),
                "show_utterances": True,
                "enable_punctuation": enable_punctuation,
                "operation": "submit",
            },
            "audio": {
                "format": audio_format,
                "codec": "raw",
            },
            "data": audio_bytes.hex(),
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

                # 解析识别结果
                result_data = data.get("result", "")
                if isinstance(result_data, str):
                    text = result_data
                elif isinstance(result_data, dict):
                    text = result_data.get("text", "")
                    # 提取 utterances 作为 segments
                    utterances = result_data.get("utterances", [])
                    segments = [
                        {
                            "text": u.get("text", ""),
                            "start": u.get("start_time", 0),
                            "end": u.get("end_time", 0),
                            "confidence": u.get("confidence", 1.0),
                        }
                        for u in utterances
                    ]
                else:
                    text = ""
                    segments = []

                return TranscriptionResult(
                    text=text,
                    language=language or self.default_language,
                    confidence=1.0,
                    segments=segments,
                )

        except httpx.HTTPStatusError as e:
            raise IntegrationError(
                f"VolcanoEngine ASR HTTP error: {e.response.status_code} - {e.response.text}"
            )
        except Exception as e:
            raise IntegrationError(f"VolcanoEngine ASR transcription failed: {e}")

    @staticmethod
    def _detect_format(suffix: str) -> str:
        """根据文件后缀检测音频格式。"""
        fmt_map = {
            ".mp3": "mp3",
            ".wav": "wav",
            ".pcm": "pcm",
            ".m4a": "m4a",
            ".ogg": "ogg",
            ".opus": "opus",
            ".flac": "flac",
            ".aac": "aac",
        }
        return fmt_map.get(suffix.lower(), "mp3")

    async def close(self):
        pass
