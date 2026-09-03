"""Compatibility client for the SZYG cloud inference gateway."""

from __future__ import annotations

import base64
import logging
import mimetypes
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator

import httpx

from szyg.cloud_auth import CloudAuthError, cloud_auth
from szyg.models.common import IntegrationError


logger = logging.getLogger(__name__)

# The cloud gateway validates image dimensions at generation time and rejects
# undersized requests with HTTP 502. Supported sizes mirror the doubao-image
# contract (>= 3,686,400 pixels). Always map unspecified/unsupported sizes to a
# supported one so a conversation turn never fails with a hard 502.
SUPPORTED_IMAGE_SIZES = {
    "1920x1920", "2560x1440", "1440x2560",
    "2048x2048", "2304x1728", "3072x1296",
}
DEFAULT_IMAGE_SIZE = "1920x1920"


class CloudInferenceError(IntegrationError):
    """User-safe cloud failure with an HTTP status for local API routes."""

    def __init__(self, message: str, *, status_code: int = 503, request_id: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id


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

        async def send(token: str) -> httpx.Response:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                return await client.request(
                    method,
                    cfg["control_url"] + path,
                    headers={"Authorization": f"Bearer {token}"},
                    json=payload,
                )

        try:
            token = cloud_auth.access_token()
            response = await send(token)
            if response.status_code == 401:
                token = cloud_auth.access_token(force_refresh=True)
                response = await send(token)
        except CloudAuthError as exc:
            message = str(exc)
            if any(marker in message for marker in ("请先登录", "登录状态", "令牌", "设备已被移除", "设备不存在")):
                raise CloudInferenceError("登录状态已失效，请重新登录", status_code=401) from None
            raise CloudInferenceError("账户服务暂时不可用，请稍后重试", status_code=503) from None
        except httpx.HTTPError as exc:
            raise CloudInferenceError("智能服务暂时不可用，请稍后重试", status_code=503) from exc
        if response.is_error:
            detail: object = ""
            try:
                detail = response.json().get("detail", "")
                request_id = str(detail.get("request_id") or "") if isinstance(detail, dict) else ""
                detail_message = str(detail.get("message") or "") if isinstance(detail, dict) else str(detail)
            except Exception:
                request_id, detail_message = "", ""
            logger.warning(
                "Cloud inference request failed: status=%s path=%s request_id=%s",
                response.status_code,
                path,
                request_id or "-",
            )
            suffix = f"（请求编号：{request_id}）" if request_id else ""
            if response.status_code == 401:
                raise CloudInferenceError("登录状态已失效，请重新登录", status_code=401, request_id=request_id)
            if response.status_code == 403:
                message = "服务授权已到期，请联系管理员" if "到期" in detail_message else "当前账户暂时无法使用此能力，请联系管理员"
                raise CloudInferenceError(message, status_code=403, request_id=request_id)
            if response.status_code == 429:
                message = "Credits 余额不足，请联系管理员" if any(word in detail_message.lower() for word in ("credit", "余额", "额度")) else "请求较多，请稍后重试"
                raise CloudInferenceError(message, status_code=429, request_id=request_id)
            raise CloudInferenceError(f"智能服务暂时不可用{suffix}", status_code=503, request_id=request_id)
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

    async def geo_search(
        self,
        provider: str,
        query: str,
        *,
        language: str = "zh-CN",
        region: str = "",
        idempotency_key: str = "",
    ) -> dict:
        provider = provider.strip().lower()
        if provider not in {"doubao", "openai", "perplexity", "gemini"}:
            raise CloudInferenceError("当前AI检测平台暂不可用", status_code=400)
        body = self._body(f"geo.search.{provider}", {
            "query": query,
            "language": language,
            "region": region,
            "max_output_tokens": 1800,
        })
        if idempotency_key:
            body["idempotency_key"] = idempotency_key
        result = await self._request("POST", "/api/v1/inference/geo/search", body)
        data = result.get("data") or {}
        return {
            "answer": str(data.get("answer") or ""),
            "citations": list(data.get("citations") or []),
            "search_queries": list(data.get("search_queries") or []),
            "provider_model": str(data.get("provider_model") or ""),
            "fidelity": str(data.get("fidelity") or "official_search_api"),
            "request_id": str(result.get("request_id") or ""),
            "usage": data.get("usage") or {},
        }

    async def geo_provider_status(self) -> list[dict]:
        result = await self._request("GET", "/api/v1/models/capabilities")
        states = {str(item.get("alias") or ""): bool(item.get("available")) for item in result.get("items") or []}
        labels = {"doubao": "豆包", "openai": "ChatGPT", "perplexity": "Perplexity", "gemini": "Google AI"}
        return [
            {"id": provider, "label": label, "configured": states.get(f"geo.search.{provider}", False), "mode": "official_search_api"}
            for provider, label in labels.items()
        ]

    async def chat_stream(self, messages: list[dict], model: str = "", max_tokens: int = 4096, temperature: float = 0.7) -> AsyncGenerator[dict, None]:
        data = await self.chat(messages, model=model, max_tokens=max_tokens, temperature=temperature)
        yield {"message": {"role": "assistant", "content": data["message"].get("content", "")}, "model": "text.fast", "done": False}
        yield {"message": {"role": "assistant", "content": ""}, "model": "text.fast", "done": True}

    async def generate_image(
        self,
        prompt: str,
        style: str | None = None,
        size: str = DEFAULT_IMAGE_SIZE,
        model: str = "",
        output_dir: str | None = None,
        reference_images: list[str] | None = None,
    ) -> str:
        del model
        if style:
            prompt = f"{prompt}, {style}"
        if size not in SUPPORTED_IMAGE_SIZES:
            logger.warning("Image generation requested unsupported size %r, using %s", size, DEFAULT_IMAGE_SIZE)
            size = DEFAULT_IMAGE_SIZE
        payload: dict = {"prompt": prompt, "size": size, "n": 1}
        if reference_images:
            payload["image"] = reference_images
        result = await self._request("POST", "/api/v1/inference/image", self._body("image.standard", payload))
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

    async def upload_reference(self, path: str) -> str:
        """Upload a local reference through the authenticated, short-lived gateway."""
        source = Path(path)
        if not source.exists() or not source.is_file():
            raise CloudInferenceError("参考素材不存在", status_code=400)
        cfg = cloud_auth.config

        async def send(token: str) -> httpx.Response:
            async with httpx.AsyncClient(timeout=max(self.timeout, 180), trust_env=False) as client:
                with source.open("rb") as handle:
                    return await client.post(
                        cfg["control_url"] + "/api/v1/inference/references",
                        headers={"Authorization": f"Bearer {token}"},
                        files={"file": (source.name, handle, mimetypes.guess_type(source.name)[0] or "application/octet-stream")},
                    )

        try:
            response = await send(cloud_auth.access_token())
            if response.status_code == 401:
                response = await send(cloud_auth.access_token(force_refresh=True))
        except (CloudAuthError, httpx.HTTPError) as exc:
            raise CloudInferenceError("参考素材上传失败，请稍后重试") from exc
        if response.is_error:
            try:
                detail = response.json().get("detail") or "参考素材上传失败"
            except Exception:
                detail = "参考素材上传失败"
            raise CloudInferenceError(str(detail), status_code=response.status_code)
        url = str(response.json().get("url") or "")
        if not url:
            raise CloudInferenceError("参考素材上传失败，请稍后重试")
        return url

    async def generate_presenter_video(
        self,
        prompt: str,
        reference_assets: list[dict],
        *,
        duration: int,
        size: str = "720p",
        ratio: str = "9:16",
        output_format: str = "mp4",
        return_last_frame: bool = True,
        idempotency_key: str = "",
    ) -> dict:
        content: list[dict] = [{"type": "text", "text": prompt}]
        for item in reference_assets:
            kind = str(item.get("type") or "")
            url = str(item.get("url") or "")
            if kind not in {"image_url", "video_url", "audio_url"} or not url:
                continue
            content.append({
                "type": kind,
                kind: {"url": url},
                "role": str(item.get("role") or f"reference_{kind.split('_')[0]}"),
            })
        payload = {
            "content": content,
            "resolution": size,
            "ratio": ratio,
            "duration": duration,
            "generate_audio": True,
            "watermark": False,
            "omni_reference_task_type": "auto",
            "return_last_frame": return_last_frame,
            "output_format": output_format,
        }
        body = self._body("video.presenter", payload)
        if idempotency_key:
            body["idempotency_key"] = idempotency_key
        result = await self._request("POST", "/api/v1/inference/video/tasks", body)
        return {
            "task_id": str(result.get("task_id") or ""),
            "status": str(result.get("status") or "queued"),
            "model": "video.presenter",
            "prompt": prompt,
        }

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
