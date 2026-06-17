"""
火山引擎语音合成客户端 — 大模型语音合成。

调用火山引擎语音合成 API，支持多种音色和情感控制。
API 文档: https://www.volcengine.com/docs/6561/1257584

用法:
    client = VolcanoEngineTTSClient(app_id="xxx", access_token="yyy")
    path = await client.synthesize("你好，这是测试语音", output_path="./output.mp3")
"""

import os
import uuid
from pathlib import Path

import httpx

from szyg.models.common import IntegrationError


class VolcanoEngineTTSClient:
    """火山引擎语音合成客户端。

    使用火山引擎 openspeech API 进行文本到语音转换。
    支持音色选择、语速调节、情感控制等参数。
    """

    DEFAULT_BASE_URL = "https://openspeech.bytedance.com/api/v1/tts"

    def __init__(
        self,
        app_id: str | None = None,
        access_token: str | None = None,
        base_url: str | None = None,
        voice_type: str = "zh_female_qingxinnvsheng_mars_bigtts",
        encoding: str = "mp3",
        speed_ratio: float = 1.0,
        volume_ratio: float = 1.0,
        timeout: float = 60.0,
    ):
        self.app_id = app_id or os.environ.get("VOLCANO_SPEECH_APP_ID", "")
        self.access_token = access_token or os.environ.get("VOLCANO_SPEECH_TOKEN", "")
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.voice_type = voice_type
        self.encoding = encoding
        self.speed_ratio = max(0.2, min(3.0, speed_ratio))
        self.volume_ratio = max(0.1, min(3.0, volume_ratio))
        self.timeout = timeout

    async def synthesize(
        self,
        text: str,
        output_path: str | None = None,
        voice_type: str | None = None,
        encoding: str | None = None,
        speed_ratio: float | None = None,
    ) -> str:
        """将文本合成为语音，保存到本地文件。

        Args:
            text: 要合成的文本（UTF-8）
            output_path: 输出文件路径，默认 ./data/volcano_output/tts_{uuid}.mp3
            voice_type: 临时指定音色，默认使用初始化时的音色
            encoding: 音频编码格式: mp3 / wav / pcm / ogg_opus
            speed_ratio: 语速倍率，默认 1.0

        Returns:
            str: 保存的本地音频文件路径
        """
        if not self.app_id or not self.access_token:
            raise IntegrationError(
                "VolcanoEngine TTS requires app_id and access_token. "
                "Set VOLCANO_SPEECH_APP_ID and VOLCANO_SPEECH_TOKEN env vars."
            )

        if not text or not text.strip():
            raise IntegrationError("Text cannot be empty for TTS synthesis")

        # 默认输出路径
        if output_path is None:
            out_dir = Path("./data/volcano_output")
            out_dir.mkdir(parents=True, exist_ok=True)
            ext = (encoding or self.encoding).lower()
            if ext == "ogg_opus":
                ext = "ogg"
            output_path = str(out_dir / f"tts_{uuid.uuid4().hex[:8]}.{ext}")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer; {self.access_token}",
        }

        payload = {
            "app": {
                "appid": self.app_id,
                "token": self.access_token,
                "cluster": "volcano_tts",
            },
            "user": {
                "uid": "szyg_user_001",
            },
            "audio": {
                "voice_type": voice_type or self.voice_type,
                "encoding": encoding or self.encoding,
                "speed_ratio": speed_ratio or self.speed_ratio,
            },
            "request": {
                "reqid": str(uuid.uuid4()),
                "text": text,
                "operation": "query",
            },
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

                # 解析返回的音频数据（base64 编码）
                audio_data = data.get("data", "")
                if not audio_data:
                    raise IntegrationError(
                        f"VolcanoEngine TTS returned empty audio data: {data}"
                    )

                import base64
                audio_bytes = base64.b64decode(audio_data)
                Path(output_path).write_bytes(audio_bytes)
                return output_path

        except httpx.HTTPStatusError as e:
            raise IntegrationError(
                f"VolcanoEngine TTS HTTP error: {e.response.status_code} - {e.response.text}"
            )
        except Exception as e:
            raise IntegrationError(f"VolcanoEngine TTS synthesis failed: {e}")

    async def close(self):
        pass
