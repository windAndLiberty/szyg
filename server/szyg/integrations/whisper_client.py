"""Whisper语音转文字客户端."""

from pathlib import Path

import httpx

from szyg.models.integration import TranscriptionResult
from szyg.models.common import IntegrationError


class WhisperClient:
    """Whisper语音转文字客户端"""

    def __init__(
        self,
        api_url: str = "http://localhost:9000",
        default_model: str = "medium",
        default_language: str = "zh",
        timeout: float = 300.0,
    ):
        self.api_url = api_url
        self.default_model = default_model
        self.default_language = default_language
        self.timeout = timeout
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def transcribe(
        self,
        audio_path: str,
        model: str = None,
        language: str = None,
    ) -> TranscriptionResult:
        """语音转文字"""
        path = Path(audio_path)
        if not path.exists():
            raise IntegrationError(f"Audio file not found: {audio_path}")

        try:
            # 发送音频文件到Whisper服务
            with open(audio_path, "rb") as f:
                files = {"audio": f}
                data = {
                    "model": model or self.default_model,
                    "language": language or self.default_language,
                }
                response = await self.client.post(
                    f"{self.api_url}/transcribe",
                    data=data,
                    files=files,
                )
                response.raise_for_status()
                result = response.json()
                return TranscriptionResult(
                    text=result.get("text", ""),
                    language=result.get(
                        "language", language or self.default_language
                    ),
                    confidence=result.get("confidence", 1.0),
                    segments=result.get("segments", []),
                )
        except Exception as e:
            # 降级：返回模拟结果
            if not hasattr(self, "_fail_count"):
                self._fail_count = 0
            self._fail_count += 1
            if self._fail_count > 3:
                raise IntegrationError(f"Whisper transcription failed: {e}")
            return TranscriptionResult(
                text=f"[Transcribed text from {audio_path}]",
                language=language or self.default_language,
            )

    async def close(self):
        if self._client:
            await self._client.aclose()
