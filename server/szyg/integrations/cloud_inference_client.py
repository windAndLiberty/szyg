"""Compatibility client for the SZYG cloud inference gateway."""

from __future__ import annotations

import base64
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator

import httpx

from szyg.cloud_auth import CloudAuthError, cloud_auth
from szyg.models.common import IntegrationError


class CloudInferenceClient:
    def __init__(self, *, timeout: float = 120, output_dir: str | None = None, **_: object) -> None:
        self.timeout = timeout
        if output_dir is None:
            from szyg.media_storage import get_media_output_dir
            output_dir = str(get_media_output_dir("image"))
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        cfg = cloud_auth.config
        try:
            token = cloud_auth.access_token()
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.request(
                    method,
                    cfg["control_url"] + path,
                    headers={"Authorization": f"Bearer {token}"},
                    json=payload,
                )
        except (CloudAuthError, httpx.HTTPError) as exc:
            raise IntegrationError("智能服务暂时不可用") from exc
        if response.is_error:
            try:
                detail = response.json().get("detail", {})
                request_id = detail.get("request_id", "") if isinstance(detail, dict) else ""
            except Exception:
                request_id = ""
            suffix = f"（请求编号：{request_id}）" if request_id else ""
            raise IntegrationError(f"智能服务暂时不可用{suffix}")
        return response.json()

    def _body(self, capability: str, payload: dict) -> dict:
        return {
            "capability": capability,
            "payload": payload,
            "idempotency_key": str(uuid.uuid4()),
            "app_version": cloud_auth.config["app_version"],
        }

    async def chat(self, messages: list[dict], model: str = "", stream: bool = False, tools: list | None = None, max_tokens: int = 4096, temperature: float = 0.7) -> dict:
        del model, stream
        payload = {"messages": messages, "stream": False, "max_tokens": max_tokens, "temperature": temperature}
        if tools:
            payload["tools"] = tools
        result = await self._request("POST", "/api/v1/inference/chat", self._body("text.fast", payload))
        data = result.get("data") or {}
        choice = (data.get("choices") or [{}])[0]
        return {"message": choice.get("message") or {"role": "assistant", "content": ""}, "model": "text.fast", "usage": data.get("usage")}

    async def responses_text(self, input_items: list[dict], model: str = "", max_output_tokens: int = 4096, reasoning_effort: str | None = None) -> dict:
        del model
        payload = {"input": input_items, "max_output_tokens": max_output_tokens}
        if reasoning_effort:
            payload["reasoning"] = {"effort": reasoning_effort}
        result = await self._request("POST", "/api/v1/inference/vision", self._body("text.vision", payload))
        data = result.get("data") or {}
        parts = []
        for output in data.get("output") or []:
            for content in output.get("content") or []:
                if content.get("type") == "output_text":
                    parts.append(str(content.get("text") or ""))
        return {"message": {"role": "assistant", "content": "".join(parts)}, "model": "text.vision", "usage": data.get("usage"), "raw": data}

    async def chat_stream(self, messages: list[dict], model: str = "", max_tokens: int = 4096, temperature: float = 0.7) -> AsyncGenerator[dict, None]:
        data = await self.chat(messages, model=model, max_tokens=max_tokens, temperature=temperature)
        yield {"message": {"role": "assistant", "content": data["message"].get("content", "")}, "model": "text.fast", "done": False}
        yield {"message": {"role": "assistant", "content": ""}, "model": "text.fast", "done": True}

    async def generate_image(self, prompt: str, style: str | None = None, size: str = "1024x1024", model: str = "", output_dir: str | None = None) -> str:
        del model
        if style:
            prompt = f"{prompt}, {style}"
        result = await self._request("POST", "/api/v1/inference/image", self._body("image.standard", {"prompt": prompt, "size": size, "n": 1}))
        item = ((result.get("data") or {}).get("data") or [{}])[0]
        url = str(item.get("url") or "")
        encoded = str(item.get("b64_json") or "")
        if not url and not encoded:
            raise IntegrationError("图像生成未返回结果")
        if encoded:
            content, suffix = base64.b64decode(encoded), ".png"
        else:
            async with httpx.AsyncClient(timeout=90, trust_env=False) as client:
                response = await client.get(url)
                response.raise_for_status()
                content = response.content
                suffix = ".jpg" if "jpeg" in response.headers.get("content-type", "") else ".png"
        out = Path(output_dir) if output_dir else self.output_dir
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"szyg_image_{int(time.time())}_{uuid.uuid4().hex[:6]}{suffix}"
        path.write_bytes(content)
        return str(path)

    async def generate_video(self, prompt: str, image_url: str | None = None, reference_assets: list[dict] | None = None, model: str = "", duration: int = 5, size: str = "720p", ratio: str = "9:16", native_audio: bool = False) -> dict:
        del model
        content: list[dict] = [{"type": "text", "text": prompt}]
        if image_url:
            content.append({"type": "image_url", "image_url": {"url": image_url}, "role": "reference_image"})
        for item in reference_assets or []:
            kind, url = str(item.get("type") or ""), str(item.get("url") or item.get("provider_ref") or "")
            if kind in {"image_url", "video_url", "audio_url"} and url:
                content.append({"type": kind, kind: {"url": url}, "role": item.get("role") or f"reference_{kind.split('_')[0]}"})
            elif kind == "text" and url:
                content[0]["text"] += f"\n\n参考内容：{url[:1800]}"
        payload = {"content": content, "resolution": size, "ratio": ratio, "duration": duration, "generate_audio": native_audio, "watermark": False}
        result = await self._request("POST", "/api/v1/inference/video/tasks", self._body("video.standard", payload))
        return {"task_id": result.get("task_id", ""), "status": result.get("status", "queued"), "model": "video.standard", "prompt": prompt}

    async def get_video_task(self, task_id: str, model: str = "") -> dict:
        del model
        data = await self._request("GET", f"/api/v1/inference/video/tasks/{task_id}")
        status = data.get("status", "unknown")
        return {"task_id": task_id, "status": status, "video_url": (data.get("content") or {}).get("video_url", ""), "progress": 100 if status == "succeeded" else (50 if status in {"running", "processing"} else 0), "error": data.get("error", "")}

    async def download_video(self, video_url: str, output_name: str = "", output_dir: str | None = None) -> str:
        async with httpx.AsyncClient(timeout=180, trust_env=False) as client:
            response = await client.get(video_url)
            response.raise_for_status()
        if output_dir is None:
            from szyg.media_storage import get_media_output_dir
            out = get_media_output_dir("video")
        else:
            out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
        path = out / (output_name or f"szyg_video_{int(time.time())}_{uuid.uuid4().hex[:6]}.mp4")
        path.write_bytes(response.content)
        return str(path)

    async def text_to_speech(self, text: str, voice_id: str = "zh_female_xiaoyi", emotion: str = "neutral", speed: float = 1.0, pitch: int = 0, output_name: str = "", output_dir: str | None = None) -> str:
        del emotion, pitch
        result = await self._request("POST", "/api/v1/inference/tts", self._body("speech.tts", {"input": text, "voice": voice_id, "speed": speed, "response_format": "mp3"}))
        audio = base64.b64decode((result.get("data") or {}).get("audio_base64", ""))
        if not audio:
            raise IntegrationError("语音生成未返回结果")
        if output_dir is None:
            from szyg.media_storage import get_media_output_dir
            out = get_media_output_dir("audio")
        else:
            out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
        path = out / (output_name or f"szyg_voice_{int(time.time())}_{uuid.uuid4().hex[:6]}.mp3")
        path.write_bytes(audio)
        return str(path)

    async def seed_audio_text_to_speech(self, text: str, voice_id: str = "zh_female_xiaoyi", emotion: str = "neutral", speed: float = 1.0, pitch: int = 0, output_name: str = "", output_dir: str | None = None, **_: object) -> tuple[str, float]:
        path = await self.text_to_speech(text, voice_id, emotion, speed, pitch, output_name, output_dir)
        return path, max(1.0, len(text) / 4.2)

    async def create_embedding(self, texts: list[str] | str, model: str = "") -> dict:
        del model
        values = [texts] if isinstance(texts, str) else texts
        result = await self._request("POST", "/api/v1/inference/embeddings", self._body("embedding.standard", {"input": values}))
        data = result.get("data") or {}
        return {"embeddings": [item.get("embedding", []) for item in data.get("data") or []], "model": "embedding.standard", "usage": data.get("usage") or {}}

    async def close(self) -> None:
        return None
