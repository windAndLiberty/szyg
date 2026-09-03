from __future__ import annotations

import uuid
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
        data["provider_model"] = str(data.get("model") or model)
        data["model"] = "text.fast"
        return data, request_id

    async def vision(self, model: str, payload: dict) -> tuple[dict, str]:
        body = dict(payload)
        body["model"] = model
        data, request_id = await self._request("POST", "responses", payload=body)
        data["provider_model"] = str(data.get("model") or model)
        data["model"] = "text.vision"
        return data, request_id

    @staticmethod
    def _dedupe_citations(items: list[dict[str, Any]]) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        seen: set[str] = set()
        for raw in items:
            url = str(raw.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            result.append({
                "url": url,
                "title": str(raw.get("title") or "").strip(),
                "snippet": str(raw.get("snippet") or "").strip(),
                "cited_text": str(raw.get("cited_text") or "").strip(),
            })
        return result

    @classmethod
    def _parse_responses_search(cls, data: dict) -> dict:
        text_parts: list[str] = []
        citations: list[dict[str, Any]] = []
        search_queries: list[str] = []
        for output in data.get("output") or []:
            if not isinstance(output, dict):
                continue
            if output.get("type") == "web_search_call":
                action = output.get("action") or {}
                query = str(action.get("query") or "").strip()
                if query:
                    search_queries.append(query)
            for content in output.get("content") or []:
                if not isinstance(content, dict) or content.get("type") != "output_text":
                    continue
                text_parts.append(str(content.get("text") or ""))
                for annotation in content.get("annotations") or []:
                    if not isinstance(annotation, dict):
                        continue
                    url_data = annotation.get("url_citation") or annotation
                    citations.append({
                        "url": url_data.get("url") or "",
                        "title": url_data.get("title") or "",
                        "snippet": url_data.get("snippet") or "",
                        "cited_text": url_data.get("text") or "",
                    })
        return {
            "answer": "".join(text_parts).strip(),
            "citations": cls._dedupe_citations(citations),
            "search_queries": list(dict.fromkeys(search_queries)),
            "usage": data.get("usage") or {},
        }

    async def _geo_http(self, method: str, url: str, *, headers: dict[str, str], payload: dict) -> tuple[dict, str]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120), trust_env=False) as client:
            response = await client.request(method, url, headers=headers, json=payload)
        request_id = response.headers.get("x-request-id", "") or response.headers.get("request-id", "")
        if response.is_error:
            try:
                body = response.json()
                error = body.get("error") or body
                code = str(error.get("code") or f"provider_{response.status_code}") if isinstance(error, dict) else f"provider_{response.status_code}"
            except Exception:
                code = f"provider_{response.status_code}"
            raise ProviderError(response.status_code, code, "GEO检测服务暂时不可用", request_id)
        try:
            return response.json(), request_id
        except ValueError as exc:
            raise ProviderError(502, "invalid_provider_response", "GEO检测服务返回异常", request_id) from exc

    async def geo_search(self, provider: str, model: str, payload: dict) -> tuple[dict, str]:
        query = str(payload.get("query") or "").strip()
        if not query or len(query) > 2000:
            raise ProviderError(400, "invalid_query", "客户问题无效")
        language = str(payload.get("language") or "zh-CN")[:20]
        region = str(payload.get("region") or "")[:80]
        context = f"请使用公开网络信息回答。回答语言：{language}。"
        if region:
            context += f"用户所在地区：{region}。"
        prompt = f"{context}\n\n客户问题：{query}"

        if provider in {"doubao", "openai"}:
            if provider == "doubao":
                api_key = self.settings.provider_api_key
                base_url = self.settings.provider_base_url
            else:
                api_key = self.settings.geo_openai_api_key
                base_url = self.settings.geo_openai_base_url
            if not api_key:
                raise ProviderError(503, "provider_not_configured", "检测平台尚未配置")
            data, request_id = await self._geo_http(
                "POST",
                f"{base_url.rstrip('/')}/responses",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                payload={
                    "model": model,
                    "input": prompt,
                    "tools": [{"type": "web_search"}],
                    "max_output_tokens": int(payload.get("max_output_tokens") or 1800),
                },
            )
            parsed = self._parse_responses_search(data)
        elif provider == "perplexity":
            if not self.settings.geo_perplexity_api_key:
                raise ProviderError(503, "provider_not_configured", "检测平台尚未配置")
            data, request_id = await self._geo_http(
                "POST",
                f"{self.settings.geo_perplexity_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.geo_perplexity_api_key}", "Content-Type": "application/json"},
                payload={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1},
            )
            answer = str((((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""))
            sources = data.get("search_results") or []
            citations = [
                {"url": item.get("url") or "", "title": item.get("title") or "", "snippet": item.get("snippet") or ""}
                for item in sources if isinstance(item, dict)
            ]
            for url in data.get("citations") or []:
                citations.append({"url": url})
            parsed = {
                "answer": answer.strip(),
                "citations": self._dedupe_citations(citations),
                "search_queries": list(data.get("search_queries") or []),
                "usage": data.get("usage") or {},
            }
        elif provider == "gemini":
            if not self.settings.geo_gemini_api_key:
                raise ProviderError(503, "provider_not_configured", "检测平台尚未配置")
            data, request_id = await self._geo_http(
                "POST",
                f"{self.settings.geo_gemini_base_url.rstrip('/')}/models/{model}:generateContent?key={self.settings.geo_gemini_api_key}",
                headers={"Content-Type": "application/json"},
                payload={"contents": [{"parts": [{"text": prompt}]}], "tools": [{"google_search": {}}]},
            )
            candidate = (data.get("candidates") or [{}])[0]
            answer = "".join(str(part.get("text") or "") for part in ((candidate.get("content") or {}).get("parts") or []) if isinstance(part, dict))
            grounding = candidate.get("groundingMetadata") or candidate.get("grounding_metadata") or {}
            citations = []
            for chunk in grounding.get("groundingChunks") or grounding.get("grounding_chunks") or []:
                web = (chunk or {}).get("web") or {}
                citations.append({"url": web.get("uri") or "", "title": web.get("title") or ""})
            usage_meta = data.get("usageMetadata") or {}
            parsed = {
                "answer": answer.strip(),
                "citations": self._dedupe_citations(citations),
                "search_queries": list(grounding.get("webSearchQueries") or grounding.get("web_search_queries") or []),
                "usage": {
                    "input_tokens": usage_meta.get("promptTokenCount") or 0,
                    "output_tokens": usage_meta.get("candidatesTokenCount") or 0,
                    "total_tokens": usage_meta.get("totalTokenCount") or 0,
                },
            }
        else:
            raise ProviderError(400, "unsupported_provider", "不支持的检测平台")

        if not parsed.get("answer"):
            raise ProviderError(502, "empty_provider_response", "检测平台未返回可用回答", request_id)
        parsed.update({
            "provider_model": model,
            "model": f"geo.search.{provider}",
            "fidelity": "official_search_api",
        })
        return parsed, request_id

    async def image(self, model: str, payload: dict) -> tuple[dict, str]:
        body = dict(payload)
        body["model"] = model
        data, request_id = await self._request("POST", "images/generations", payload=body)
        data["provider_model"] = str(data.get("model") or model)
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
        data["provider_model"] = str(data.get("model") or model)
        data["model"] = "embedding.standard"
        return data, request_id

    async def tts(self, model: str, payload: dict) -> tuple[dict, str]:
        if not self.settings.provider_speech_api_key:
            raise ProviderError(503, "speech_key_missing", "豆包语音 API Key 未配置")

        request_id = str(uuid.uuid4())
        voice = str(payload.get("voice") or "")
        references = []
        # Seed Audio speaker IDs are different from legacy zh_*/en_* voice IDs.
        if voice and not voice.startswith(("zh_", "en_")):
            references.append({"speaker": voice})
        speed = max(0.5, min(2.0, float(payload.get("speed") or 1.0)))
        pitch = max(-100, min(100, int(payload.get("pitch") or 0)))
        response_format = str(payload.get("response_format") or "mp3")
        body = {
            "model": model or "seed-audio-1.0",
            "text_prompt": str(payload.get("input") or payload.get("text") or ""),
            "references": references,
            "audio_config": {
                "format": response_format,
                "sample_rate": 24000,
                "speech_rate": max(-50, min(100, int(round((speed - 1.0) * 100)))),
                "pitch_rate": max(-12, min(12, int(round(pitch / 100 * 12)))),
            },
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(180), trust_env=False) as client:
            response = await client.post(
                self.settings.provider_speech_base_url,
                headers={
                    "X-Api-Key": self.settings.provider_speech_api_key,
                    "X-Api-Request-Id": request_id,
                    "Content-Type": "application/json",
                },
                json=body,
            )
        request_id = response.headers.get("x-request-id", "") or response.headers.get("x-api-request-id", "") or request_id
        if response.is_error:
            try:
                error = response.json()
                code = str(error.get("code") or f"speech_{response.status_code}")
                message = str(error.get("message") or "语音生成服务暂时不可用")
            except Exception:
                code, message = f"speech_{response.status_code}", "语音生成服务暂时不可用"
            raise ProviderError(response.status_code, code, message, request_id)
        result = response.json()
        if int(result.get("code", 0) or 0) != 0:
            raise ProviderError(502, str(result.get("code") or "speech_failed"), str(result.get("message") or "语音生成失败"), request_id)
        audio = str(result.get("audio") or "")
        if not audio:
            raise ProviderError(502, "speech_empty", "语音生成未返回音频", request_id)
        return {
            "audio_base64": audio,
            "format": response_format,
            "model": "speech.tts",
            "provider_model": model or "seed-audio-1.0",
            "duration": result.get("duration") or 0,
        }, request_id
