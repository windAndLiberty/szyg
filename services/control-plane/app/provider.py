from __future__ import annotations

import json
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


def _v4_sign(method: str, host: str, path: str, query: dict[str, str], body: str, *, ak: str, sk: str, service: str, region: str) -> dict[str, str]:
    """构造火山引擎 V4 鉴权 Header。延迟导入避免未装 volcengine 时启动失败。"""
    from volcengine.Credentials import Credentials
    from volcengine.auth.SignerV4 import SignerV4
    from volcengine.base.Request import Request

    request = Request()
    request.host = host
    request.method = method
    request.path = path
    request.query = dict(query)
    request.headers = {"Host": host, "Content-Type": "application/json"}
    request.body = body
    credentials = Credentials(ak, sk, service, region)
    SignerV4.sign(request, credentials)
    return dict(request.headers)


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
        reference_audio_url = str(payload.get("reference_audio_url") or "").strip()
        text_prompt = str(payload.get("input") or payload.get("text") or "")
        if reference_audio_url:
            from urllib.parse import urlsplit

            reference_url = urlsplit(reference_audio_url)
            if reference_url.scheme not in {"http", "https"} or not reference_url.hostname or reference_url.username or reference_url.password:
                raise ProviderError(400, "invalid_voice_reference", "声音参考必须是有效的音频链接")
            references.append({"audio_url": reference_audio_url})
            text_prompt = (
                "请以@音频1中的人声为声音参考，保持相近的音色、口音和说话风格，"
                "自然清晰地朗读以下台词。只生成一位说话人的干净人声，不添加音乐、"
                "环境音或额外台词，不复述参考音频的内容。\n台词：\n" + text_prompt
            )
        # Seed Audio speaker IDs are different from legacy zh_*/en_* voice IDs.
        elif voice and not voice.startswith(("zh_", "en_")):
            references.append({"speaker": voice})
        if len(text_prompt) > 3000:
            raise ProviderError(400, "speech_text_too_long", "语音生成内容过长，请缩短台词")
        speed = max(0.5, min(2.0, float(payload.get("speed") or 1.0)))
        pitch = max(-100, min(100, int(payload.get("pitch") or 0)))
        response_format = str(payload.get("response_format") or "mp3")
        body = {
            "model": model or "seed-audio-1.0",
            "text_prompt": text_prompt,
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
            "original_duration": result.get("original_duration") or result.get("duration") or 0,
        }, request_id

    # ═══════════════════════════════════════════════════════════════════════
    # 火山视觉 CV 平台（V4 鉴权，Region=cn-north-1，Service=cv）
    # 用于 OmniHuman1.5、主体检测、其它视觉类能力。
    # ═══════════════════════════════════════════════════════════════════════

    async def _visual_request(
        self,
        action: str,
        body: dict,
        *,
        version: str = "2022-08-31",
    ) -> tuple[dict, str]:
        """通用 CV 平台调用。自动 V4 签名。"""
        settings = self.settings
        if not settings.provider_cv_access_key or not settings.provider_cv_secret_key:
            raise ProviderError(503, "cv_credentials_missing", "火山视觉 CV 鉴权未配置")
        host = settings.provider_cv_base_url.replace("https://", "").replace("http://", "").rstrip("/")
        path = "/"
        query = {"Action": action, "Version": version}
        body_text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        headers = _v4_sign(
            "POST",
            host,
            path,
            query,
            body_text,
            ak=settings.provider_cv_access_key,
            sk=settings.provider_cv_secret_key,
            service="cv",
            region=settings.provider_cv_region,
        )
        url = f"https://{host}{path}?Action={action}&Version={version}"
        async with httpx.AsyncClient(timeout=httpx.Timeout(180), trust_env=False) as client:
            response = await client.post(url, headers=headers, content=body_text)
        request_id = response.headers.get("x-request-id", "") or response.headers.get("X-Tt-Logid", "")
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderError(502, "invalid_cv_response", "视觉平台返回非 JSON", request_id) from exc
        code = int(data.get("code") or 0)
        if code != 0 and code != 10000:
            message = str(data.get("message") or "视觉平台业务错误")
            raise ProviderError(400, f"cv_biz_{code}", message, request_id)
        if response.is_error:
            raise ProviderError(response.status_code, f"cv_{response.status_code}",
                                f"视觉平台调用失败：HTTP {response.status_code}", request_id)
        return data, request_id

    async def omni_human_submit(
        self,
        model: str,
        payload: dict,
    ) -> tuple[dict, str]:
        """提交 OmniHuman1.5 任务。req_key 固定为 model (jimeng_realman_avatar_picture_omni_v15)。"""
        # payload 由调用方按 OmniHuman schema 构造：image_url/audio_url/(mask_url[])/prompt/output_resolution/pe_fast_mode/seed
        body = {"req_key": model, **payload}
        data, request_id = await self._visual_request("CVSubmitTask", body)
        result = data.get("data") or {}
        task_id = str(result.get("task_id") or "")
        if not task_id:
            raise ProviderError(502, "omni_no_task_id", "OmniHuman 未返回 task_id", request_id)
        return {"task_id": task_id, "model": model, "request_id": str(data.get("request_id") or request_id)}, request_id

    async def omni_human_get(self, provider_task_id: str, *, model: str = "jimeng_realman_avatar_picture_omni_v15") -> tuple[dict, str]:
        """查询 OmniHuman1.5 任务状态。"""
        try:
            data, request_id = await self._visual_request(
                "CVGetResult",
                {"req_key": model, "task_id": provider_task_id},
            )
        except ProviderError as exc:
            if exc.code == "cv_biz_50215":
                return {"task_id": provider_task_id, "status": "failed", "video_url": ""}, exc.request_id
            raise
        result = data.get("data") or {}
        return {
            "task_id": provider_task_id,
            "status": str(result.get("status") or "unknown"),
            "video_url": str(result.get("video_url") or ""),
            "aigc_meta_tagged": bool(result.get("aigc_meta_tagged", False)),
            "request_id": str(data.get("request_id") or request_id),
        }, request_id

    async def subject_detection(
        self,
        model: str,
        image_url: str,
    ) -> tuple[dict, str]:
        """主体检测（同步 CVProcess）：返回主体 mask_url 列表。"""
        data, request_id = await self._visual_request(
            "CVProcess",
            {"req_key": model, "image_url": image_url},
        )
        result = data.get("data") or {}
        resp_data_raw = str(result.get("resp_data") or "{}")
        try:
            resp_data = json.loads(resp_data_raw)
        except ValueError:
            resp_data = {}
        object_detection = resp_data.get("object_detection_result") or {}
        mask = object_detection.get("mask") or {}
        mask_urls = [str(u) for u in (mask.get("url") or []) if u]
        return {
            "status": int(resp_data.get("status") or 0),
            "mask_urls": mask_urls,
            "request_id": str(data.get("request_id") or request_id),
        }, request_id

    # ═══════════════════════════════════════════════════════════════════════
    # 火山大模型录音文件识别（X-Api-Key + X-Api-Resource-Id 鉴权，非 V4）
    # ═══════════════════════════════════════════════════════════════════════

    async def asr_transcribe(
        self,
        model: str,
        payload: dict,
        *,
        max_poll_seconds: int = 240,
        poll_interval: float = 1.5,
    ) -> tuple[dict, str]:
        """大模型录音文件识别：提交 + 轮询，返回转写文本。

        payload 字段：
          audio_url: 必填，音频 URL
          format: 必填，raw/wav/mp3/ogg
          language: 可选，如 zh-CN
          enable_itn / enable_punc / enable_ddc / show_utterances: 可选 bool
        """
        import asyncio

        settings = self.settings
        if not settings.provider_asr_app_key:
            raise ProviderError(503, "asr_credentials_missing", "大模型录音文件识别 APP Key 未配置")

        audio_url = str(payload.get("audio_url") or "").strip()
        if not audio_url:
            raise ProviderError(400, "invalid_audio_url", "audio_url 必填")
        audio_format = str(payload.get("format") or "mp3").strip().lower()
        if audio_format not in {"raw", "wav", "mp3", "ogg"}:
            raise ProviderError(400, "invalid_audio_format", f"不支持的音频格式：{audio_format}")

        request_id = str(uuid.uuid4())
        body = {
            "user": {"uid": str(payload.get("uid") or "szyg")},
            "audio": {
                "url": audio_url,
                "format": audio_format,
                "rate": int(payload.get("rate") or 16000),
                "bits": int(payload.get("bits") or 16),
                "channel": int(payload.get("channel") or 1),
            },
            "request": {
                "model_name": str(payload.get("model_name") or "bigmodel"),
                "enable_itn": bool(payload.get("enable_itn", True)),
                "enable_punc": bool(payload.get("enable_punc", True)),
                "enable_ddc": bool(payload.get("enable_ddc", False)),
                "show_utterances": bool(payload.get("show_utterances", True)),
            },
        }
        language = str(payload.get("language") or "").strip()
        if language:
            body["audio"]["language"] = language

        headers = {
            "X-Api-Key": settings.provider_asr_app_key,
            "X-Api-Resource-Id": model or settings.provider_asr_resource_id,
            "X-Api-Request-Id": request_id,
            "X-Api-Sequence": "-1",
            "Content-Type": "application/json",
        }
        submit_url = f"{settings.provider_asr_base_url.rstrip('/')}/api/v3/auc/bigmodel/submit"
        query_url = f"{settings.provider_asr_base_url.rstrip('/')}/api/v3/auc/bigmodel/query"

        async with httpx.AsyncClient(timeout=httpx.Timeout(60), trust_env=False) as client:
            response = await client.post(submit_url, headers=headers, json=body)
        if response.is_error:
            raise ProviderError(response.status_code, f"asr_submit_{response.status_code}",
                                "录音文件识别提交失败", request_id)
        status_code = response.headers.get("X-Api-Status-Code", "")
        if status_code and status_code not in {"20000000"}:
            message = response.headers.get("X-Api-Message", "录音文件识别提交失败")
            raise ProviderError(400, f"asr_submit_{status_code}", message, request_id)

        # 轮询结果
        import time
        started = time.perf_counter()
        query_headers = dict(headers)
        last_text = ""
        last_utterances: list[dict] = []
        last_duration_ms = 0
        while time.perf_counter() - started < max_poll_seconds:
            await asyncio.sleep(poll_interval)
            query_headers["X-Api-Request-Id"] = request_id
            async with httpx.AsyncClient(timeout=httpx.Timeout(60), trust_env=False) as client:
                poll_response = await client.post(query_url, headers=query_headers, content=b"{}")
            if poll_response.is_error:
                raise ProviderError(poll_response.status_code, f"asr_query_{poll_response.status_code}",
                                    "录音文件识别查询失败", request_id)
            poll_status = poll_response.headers.get("X-Api-Status-Code", "")
            if poll_status == "20000000":
                try:
                    poll_data = poll_response.json()
                except ValueError:
                    continue
                result = poll_data.get("result") or {}
                audio_info = poll_data.get("audio_info") or {}
                last_text = str(result.get("text") or "")
                last_utterances = list(result.get("utterances") or [])
                last_duration_ms = int(audio_info.get("duration") or 0)
                return {
                    "text": last_text,
                    "utterances": last_utterances,
                    "duration_ms": last_duration_ms,
                    "model": model or settings.provider_asr_resource_id,
                }, request_id
            if poll_status == "20000001":
                continue  # 处理中
            if poll_status == "20000002":
                continue  # 队列中
            if poll_status == "20000003":
                raise ProviderError(400, "asr_silent_audio", "未检测到人声", request_id)
            if poll_status and poll_status.startswith("45"):
                # 参数/限制类错误
                message = poll_response.headers.get("X-Api-Message", "ASR 请求无效")
                raise ProviderError(400, f"asr_invalid_{poll_status}", message, request_id)
            if poll_status and poll_status.startswith("55"):
                # 服务端错误
                raise ProviderError(503, f"asr_server_{poll_status}", "ASR 服务暂时不可用", request_id)
        raise ProviderError(504, "asr_timeout", "录音文件识别超时", request_id)
