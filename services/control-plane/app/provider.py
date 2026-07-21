from __future__ import annotations

import base64
from typing import Any

import httpx

from .config import get_settings


class ProviderError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str, request_id: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.request_id = request_id


class ProviderGateway:
    def __init__(self):
        self.settings = get_settings()

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.provider_api_key}",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, *, payload: dict | None = None) -> tuple[dict, str]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(180), trust_env=False) as client:
            response = await client.request(
                method,
                f"{self.settings.provider_base_url.rstrip('/')}/{path.lstrip('/')}",
                headers=self.headers,
                json=payload,
            )
        request_id = response.headers.get("x-request-id", "")
        if response.is_error:
            try:
                body = response.json()
                error = body.get("error") or {}
                code = str(error.get("code") or f"provider_{response.status_code}")
                message = str(error.get("message") or "智能服务请求失败")
            except Exception:
                code, message = f"provider_{response.status_code}", "智能服务请求失败"
            raise ProviderError(response.status_code, code, message, request_id)
        return response.json(), request_id

    async def chat(self, model: str, payload: dict) -> tuple[dict, str]:
        body = dict(payload)
        body["model"] = model
        body.setdefault("stream", False)
        data, request_id = await self._request("POST", "chat/completions", payload=body)
        data["model"] = "text.fast"
        return data, request_id

    async def vision(self, model: str, payload: dict) -> tuple[dict, str]:
        body = dict(payload)
        body["model"] = model
        data, request_id = await self._request("POST", "responses", payload=body)
        data["model"] = "text.vision"
        return data, request_id

    async def image(self, model: str, payload: dict) -> tuple[dict, str]:
        body = dict(payload)
        body["model"] = model
        data, request_id = await self._request("POST", "images/generations", payload=body)
        data["model"] = "image.standard"
        return data, request_id

    async def create_video(self, model: str, payload: dict) -> tuple[dict, str]:
        body = dict(payload)
        body["model"] = model
        return await self._request("POST", "contents/generations/tasks", payload=body)

    async def get_video(self, provider_task_id: str) -> tuple[dict, str]:
        return await self._request("GET", f"contents/generations/tasks/{provider_task_id}")

    async def embeddings(self, model: str, payload: dict) -> tuple[dict, str]:
        body = dict(payload)
        body["model"] = model
        data, request_id = await self._request("POST", "embeddings", payload=body)
        data["model"] = "embedding.standard"
        return data, request_id

    async def tts(self, model: str, payload: dict) -> tuple[dict, str]:
        body = dict(payload)
        body["model"] = model
        async with httpx.AsyncClient(timeout=httpx.Timeout(180), trust_env=False) as client:
            response = await client.post(
                f"{self.settings.provider_base_url.rstrip('/')}/audio/speech",
                headers=self.headers,
                json=body,
            )
        request_id = response.headers.get("x-request-id", "")
        if response.is_error:
            raise ProviderError(response.status_code, "speech_failed", "语音生成服务暂时不可用", request_id)
        return {
            "audio_base64": base64.b64encode(response.content).decode("ascii"),
            "format": str(payload.get("response_format") or "mp3"),
            "model": "speech.tts",
        }, request_id
