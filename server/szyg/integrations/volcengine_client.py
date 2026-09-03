"""
火山引擎方舟(ARK)统一客户端 — 多模态AIGC能力集成

提供统一的OpenAI兼容API入口，一个API Key调用多个模型：
  - 文本对话: Doubao-pro / DeepSeek-R1 / DeepSeek-V3
  - 图像生成: 豆包·文生图 / SDXL / FLUX
  - 视频生成: 豆包·视频生成 / Seaweed
  - 语音合成: 豆包·语音合成 (情感语音)
  - 声音克隆: 豆包·声音克隆
  - 向量嵌入: Doubao-embedding

用法:
    client = VolcEngineClient(api_key="sk-xxx")
    # 文本对话
    resp = await client.chat(messages=[{"role": "user", "content": "Hello"}])
    # 图像生成
    path = await client.generate_image("a golden cat", model="doubao-image")
    # 视频生成
    task_id = await client.generate_video("a cat playing piano")
    # 语音合成
    path = await client.text_to_speech("你好世界", voice_id="zh_female_xiaoyi")
"""

import asyncio
import base64
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator

import httpx
from openai import AsyncOpenAI, RateLimitError

from szyg.integrations.base_llm_client import BaseLLMClient, retry_with_backoff
from szyg.models.common import IntegrationError

logger = logging.getLogger(__name__)


# ── Config helpers (fallback when api_key/endpoints not passed explicitly) ──

def _read_config_key(key: str, default: str = "") -> str:
    """Read a volcengine config value from config.yaml."""
    try:
        from szyg.config.loader import load_config
        cfg = load_config()
        value = cfg.get("llm", {}).get("volcengine", {}).get(key, default)
        if isinstance(value, str):
            return value
        return default
    except Exception:
        pass
    try:
        import yaml
        cfg_path = Path(__file__).parent.parent.parent.parent / "config.yaml"
        if cfg_path.exists():
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
            value = cfg.get("llm", {}).get("volcengine", {}).get(key, default)
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                return default
            return value
    except Exception as e:
        logger.debug("Failed to read volcengine config key %s: %s", key, e)
    return default


def _read_config_section(key: str) -> dict:
    """Read a volcengine config section from config.yaml."""
    try:
        import yaml
        cfg_path = Path(__file__).parent.parent.parent.parent / "config.yaml"
        if cfg_path.exists():
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
            return cfg.get("llm", {}).get("volcengine", {}).get(key, {})
    except Exception as e:
        logger.debug("Failed to read volcengine config section %s: %s", key, e)
    return {}


# ── Default model endpoint IDs (火山方舟推理接入点ID) ───────────────────────
# 用户可在 config.yaml 中覆盖，此处为占位默认值
DEFAULT_ENDPOINTS = {
    # 文本模型
    "doubao-pro-128k": "doubao-pro-128k",
    "doubao-lite": "doubao-lite",
    "doubao-seed-2-0-pro": "doubao-seed-2-0-pro-260215",
    "doubao-seed-2-0-pro-260215": "doubao-seed-2-0-pro-260215",
    "doubao-seed-2-0-lite": "doubao-seed-2-0-lite-260428",
    "doubao-seed-2-0-lite-260428": "doubao-seed-2-0-lite-260428",
    "deepseek-r1": "deepseek-r1",
    "deepseek-v3": "deepseek-v3",
    # 图像模型
    "doubao-image": "doubao-image",
    "sdxl": "sdxl",
    "flux": "flux",
    # 视频模型
    "doubao-video": "doubao-video",
    "doubao-seedance-1.5-pro": "",
    "doubao-seedance-1-5-pro-251215": "doubao-seedance-1-5-pro-251215",
    "doubao-seedance-2.0-fast": "",
    "doubao-seedance-2.0": "",
    "doubao-seedance-2.5": "",
    "seaweed": "seaweed",
    # 语音模型
    "doubao-tts": "doubao-tts",
    "doubao-voice-clone": "doubao-voice-clone",
    # 向量模型
    "doubao-embedding": "doubao-embedding",
}


class VolcEngineClient(BaseLLMClient):
    """火山引擎方舟平台统一客户端。

    使用OpenAI兼容接口，支持:
      - chat(): LLM对话 (流式/非流式 + Function Calling)
      - generate_image(): 文生图
      - generate_video(): 文生视频 / 图生视频 (异步)
      - text_to_speech(): 情感语音合成
      - clone_voice(): 声音克隆 + 语音合成
      - create_embedding(): 向量嵌入 (批量)

    内置功能:
      - 指数退避重试 (限流/故障自动恢复)
      - 熔断器 (连续失败自动切换)
      - 统一错误处理
    """

    def __new__(cls, *args, **kwargs):
        if cls is VolcEngineClient:
            try:
                from szyg.cloud_auth import cloud_auth
                if cloud_auth.config["enabled"]:
                    from szyg.integrations.cloud_inference_client import CloudInferenceClient
                    return CloudInferenceClient(
                        timeout=float(kwargs.get("timeout", 120)),
                        output_dir=kwargs.get("output_dir"),
                    )
            except Exception as exc:
                logger.warning("Cloud inference selection failed: %s", exc)
        return super().__new__(cls)

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
        endpoints: dict | None = None,
        timeout: float = 120.0,
        max_retries: int = 3,
        output_dir: str | None = None,
    ):
        super().__init__(
            base_url=base_url, default_model="doubao-pro-128k", timeout=timeout,
        )
        self.api_key = (
            api_key
            or os.environ.get("VOLCENGINE_API_KEY", "")
            or _read_config_key("api_key")
        )
        self.endpoints = {
            **DEFAULT_ENDPOINTS,
            **(_read_config_section("endpoints") or {}),
            **(endpoints or {}),
        }
        self.timeout = timeout
        self.max_retries = max_retries
        if output_dir is None:
            from szyg.media_storage import get_media_output_dir
            output_dir = str(get_media_output_dir("image"))
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 自动检测默认文本 endpoint（取第一个配置的文本模型 endpoint）
        if not self.DEFAULT_TEXT_ENDPOINT:
            for model, ep in self.endpoints.items():
                if ep and ep.startswith("ep-") and not any(
                    model.startswith(p) for p in ("doubao-image", "doubao-video", "doubao-seedance",
                    "doubao-tts", "doubao-voice", "doubao-embedding",
                    "sdxl", "flux", "seaweed", "wan", "seedream", "seedance")
                ):
                    VolcEngineClient.DEFAULT_TEXT_ENDPOINT = ep
                    break

        self._client: AsyncOpenAI | None = None
        self._httpx: httpx.AsyncClient | None = None

        # 熔断器状态
        self._circuit_state = "CLOSED"  # CLOSED | OPEN | HALF_OPEN
        self._fail_count = 0
        self._circuit_opened_at = 0.0
        self.CIRCUIT_THRESHOLD = 5
        self.CIRCUIT_TIMEOUT = 30

    # ── Internal clients ──────────────────────────────────────────────────

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            if not self.api_key:
                raise IntegrationError("VolcEngine API key not configured — set VOLCENGINE_API_KEY")
            # 创建禁用系统代理的 httpx 客户端 (Windows 上可能残留过期代理配置)
            import httpx as _httpx
            _http_client = _httpx.AsyncClient(
                timeout=_httpx.Timeout(self.timeout),
                trust_env=False,  # 忽略系统代理设置
            )
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=0,  # 我们自己处理重试
                http_client=_http_client,
            )
        return self._client

    @property
    def httpx(self) -> httpx.AsyncClient:
        if self._httpx is None or self._httpx.is_closed:
            self._httpx = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={"Authorization": f"Bearer {self.api_key}"},
                trust_env=False,
            )
        return self._httpx

    # 默认推理接入点 — 当模型未在 endpoints 中配置时使用
    # 火山方舟允许用模型名直接调用（部分模型）或通过共享 endpoint 调用
    DEFAULT_TEXT_ENDPOINT = ""  # 由 config.yaml → endpoints 中任意已配置 endpoint 自动填充

    def _ep(self, model: str) -> str:
        """获取模型对应的推理接入点ID。

        优先级:
          1. endpoints 中精确匹配 (非空)
          2. 模型名本身 (直接调用，支持 deepseek-v4-flash-260425 等)
          3. 默认文本 endpoint (如果配置了)
        """
        if model.startswith("ep-"):
            return model
        if model in self.endpoints and self.endpoints[model]:
            return self.endpoints[model]
        # 如果配置了默认 endpoint 且模型是文本模型，使用默认 endpoint
        if self.DEFAULT_TEXT_ENDPOINT and not any(
            model.startswith(p) for p in ("doubao-image", "doubao-video", "doubao-seedance",
            "doubao-tts", "doubao-voice", "doubao-embedding",
            "sdxl", "flux", "seaweed", "wan", "seedream", "seedance",
            "hitem3d", "hyper3d")
        ):
            return self.DEFAULT_TEXT_ENDPOINT
        return model

    # ── Circuit breaker ───────────────────────────────────────────────────

    def _circuit_check(self) -> bool:
        if self._circuit_state == "CLOSED":
            return True
        if self._circuit_state == "OPEN":
            if time.time() - self._circuit_opened_at > self.CIRCUIT_TIMEOUT:
                self._circuit_state = "HALF_OPEN"
                self._fail_count = 0
                return True
            return False
        # HALF_OPEN
        return True

    def _circuit_success(self):
        self._fail_count = 0
        self._circuit_state = "CLOSED"

    def _circuit_failure(self):
        self._fail_count += 1
        if self._fail_count >= self.CIRCUIT_THRESHOLD:
            self._circuit_state = "OPEN"
            self._circuit_opened_at = time.time()

    # ── Retry wrapper ─────────────────────────────────────────────────────

    async def _retry(self, fn, *args, **kwargs):
        """指数退避重试，支持熔断器。"""
        if not self._circuit_check():
            raise IntegrationError("VolcEngine circuit breaker is OPEN")
        try:
            result = await retry_with_backoff(
                fn, *args, max_retries=self.max_retries,
                on_rate_limit="VolcEngine", **kwargs,
            )
            self._circuit_success()
            return result
        except IntegrationError:
            self._circuit_failure()
            raise
        except Exception:
            self._circuit_failure()
            raise

    # ═══════════════════════════════════════════════════════════════════════
    # 1. 文本对话 (Chat Completions)
    # ═══════════════════════════════════════════════════════════════════════

    async def chat(
        self,
        messages: list[dict],
        model: str = "doubao-pro-128k",
        stream: bool = False,
        tools: list | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> dict:
        """非流式聊天补全。

        Returns:
            {"message": {"role": "assistant", "content": "..."}, "model": "...", "usage": {...}}
        """
        try:
            kwargs = {
                "model": self._ep(model),
                "messages": messages,
                "stream": False,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if tools:
                kwargs["tools"] = tools
                # 火山引擎方舟 API 不支持 tool_choice 参数，省略即可自动使用 tools

            response = await self._retry(self.client.chat.completions.create, **kwargs)

            if response is None or not response.choices:
                raise IntegrationError("VolcEngine returned empty response")

            choice = response.choices[0]
            tool_calls = None
            if choice.message and choice.message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in choice.message.tool_calls
                ]
            usage = None
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            return self.normalize_chat_response(
                role=choice.message.role if choice.message else "assistant",
                content=choice.message.content if choice.message else "",
                model=response.model or model,
                usage=usage,
                tool_calls=tool_calls,
            )
        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(f"VolcEngine chat failed: {e}")

    async def responses_text(
        self,
        input_items: list[dict],
        model: str = "doubao-seed-2-0-lite-260428",
        max_output_tokens: int = 4096,
        reasoning_effort: str | None = None,
    ) -> dict:
        """Call Ark Responses API and return concatenated output_text content."""
        try:
            payload = {
                "model": self._ep(model),
                "input": input_items,
                "max_output_tokens": max_output_tokens,
            }
            if reasoning_effort:
                payload["reasoning"] = {"effort": reasoning_effort}
            async with httpx.AsyncClient(timeout=120, trust_env=False) as c:
                r = await c.post(
                    f"{self.base_url}/responses",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if r.is_error:
                    raise IntegrationError(f"HTTP {r.status_code}: {r.text[:500]}")
                data = r.json()

            parts: list[str] = []
            for output in data.get("output") or []:
                if not isinstance(output, dict):
                    continue
                for content in output.get("content") or []:
                    if isinstance(content, dict) and content.get("type") == "output_text":
                        parts.append(str(content.get("text") or ""))
            return {
                "message": {"role": "assistant", "content": "".join(parts)},
                "model": data.get("model") or model,
                "usage": data.get("usage"),
                "raw": data,
            }
        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(f"VolcEngine responses failed: {e}")

    async def chat_stream(
        self,
        messages: list[dict],
        model: str = "doubao-pro-128k",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncGenerator[dict, None]:
        """流式聊天补全。"""
        try:
            stream = await self.client.chat.completions.create(
                model=self._ep(model),
                messages=messages,
                stream=True,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta
                    content = delta.content or ""
                    if content:
                        yield self.normalize_stream_chunk(content, chunk.model or model)
            yield self.normalize_stream_chunk("", model, done=True)
        except Exception as e:
            raise IntegrationError(f"VolcEngine stream failed: {e}")

    async def list_models(self) -> dict:
        """列出可用模型。"""
        try:
            models = await self.client.models.list()
            return {"models": [{"name": m.id} for m in models.data]}
        except Exception as e:
            raise IntegrationError(f"VolcEngine list_models failed: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # 2. 图像生成 (Image Generations)
    # ═══════════════════════════════════════════════════════════════════════

    STYLE_TO_PROMPT = {
        "realistic": "photorealistic, 8k, highly detailed, professional photography",
        "anime": "anime style, studio ghibli, vibrant colors, cel shading",
        "cyberpunk": "cyberpunk, neon lights, futuristic, blade runner style, synthwave",
        "oil": "oil painting, classical art, textured canvas, museum quality",
        "ink": "chinese ink painting, traditional brushwork, elegant, watercolor",
        "minimal": "minimalist, clean composition, simple, modern design",
        "3d": "3d render, c4d, octane render, ray tracing, blender",
        "pixel": "pixel art, 16-bit, retro game style, dithering",
    }

    async def generate_image(
        self,
        prompt: str,
        style: str | None = None,
        size: str = "1024x1024",
        model: str = "doubao-image",
        output_dir: str | None = None,
        reference_images: list[str] | None = None,
    ) -> str:
        """文生图，返回本地文件路径。

        Args:
            prompt: 图像描述 (支持中文)
            style: 风格标签 (realistic/anime/cyberpunk/oil/ink/minimal/3d/pixel)
            size: 分辨率 (512x512/768x768/1024x1024/1024x768/768x1024)
            model: 模型ID (doubao-image/sdxl/flux)
            output_dir: 输出目录，默认 self.output_dir

        Returns:
            本地文件路径 str
        """
        # 风格增强
        enhanced_prompt = prompt
        if style and style in self.STYLE_TO_PROMPT:
            enhanced_prompt = f"{prompt}, {self.STYLE_TO_PROMPT[style]}"

        # 尺寸映射 — 火山引擎要求 ≥ 3686400 pixels (~3.7MP)
        size_map = {
            "1920x1920": (1920, 1920),     # 1:1 方形 (3.7MP)
            "1920x1080": (1920, 1080),     # 16:9 横版 (2.1MP — 不满足要求，替换为下)
            "1080x1920": (1080, 1920),     # 9:16 竖版
            "2048x2048": (2048, 2048),     # 1:1 大方形 (4.2MP)
            "2304x1728": (2304, 1728),     # 4:3 (4.0MP)
            "2560x1440": (2560, 1440),     # 16:9 横版 (3.7MP)
            "1440x2560": (1440, 2560),     # 9:16 竖版 (3.7MP)
            "3072x1296": (3072, 1296),     # 21:9 超宽 (4.0MP)
        }
        # Support custom WxH format (e.g. "1920x1920")
        if 'x' in size:
            parts = size.split('x')
            try:
                w, h = int(parts[0]), int(parts[1])
                if w * h < 3686400:
                    # Auto-scale up to minimum
                    scale = (3686400 / (w * h)) ** 0.5
                    w, h = int(w * scale), int(h * scale)
            except (ValueError, IndexError):
                w, h = size_map.get(size, (1920, 1920))
        else:
            w, h = size_map.get(size, (1920, 1920))

        try:
            request_kwargs = {
                "model": self._ep(model),
                "prompt": enhanced_prompt,
                "size": f"{w}x{h}",
                "n": 1,
            }
            if reference_images:
                request_kwargs["extra_body"] = {"image": reference_images}
            response = await self._retry(self.client.images.generate, **request_kwargs)

            if not response.data:
                raise IntegrationError("VolcEngine image generation returned no data")

            image_url = response.data[0].url
            if not image_url:
                raise IntegrationError("VolcEngine image generation returned empty URL")

            # 下载图像
            async with httpx.AsyncClient(timeout=60, trust_env=False) as c:
                img_resp = await c.get(image_url)
                img_resp.raise_for_status()

            out = Path(output_dir) if output_dir else self.output_dir
            out.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            content_type = img_resp.headers.get("content-type", "").lower()
            if "jpeg" in content_type or "jpg" in content_type:
                suffix = ".jpg"
            elif "webp" in content_type:
                suffix = ".webp"
            else:
                suffix = ".png"
            path = out / f"volc_image_{model.replace('-', '_')}_{ts}_{uuid.uuid4().hex[:6]}{suffix}"
            path.write_bytes(img_resp.content)
            return str(path)

        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(f"VolcEngine image generation failed: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # 3. 视频生成 (Video Generations) — 异步任务
    # ═══════════════════════════════════════════════════════════════════════

    async def generate_video(
        self,
        prompt: str,
        image_url: str | None = None,
        reference_assets: list[dict] | None = None,
        model: str = "doubao-seedance-2.0-fast",
        duration: int = 5,
        size: str = "720p",
        ratio: str = "9:16",
        native_audio: bool = False,
    ) -> dict:
        """提交视频生成任务 (文生视频 / 图生视频)。

        火山引擎视频生成是异步任务，此接口返回 task_id，需要轮询 get_video_task 获取结果。
        API: POST /api/v3/contents/generations/tasks

        Args:
            prompt: 视频内容描述
            image_url: 参考图片URL (图生视频时提供)
            reference_assets: 多模态参考素材，元素格式为 {"type": "image_url"|"video_url", "url": "..."}
            model: 模型 (doubao-seedance-2.0-fast / doubao-seedance-2.0 / doubao-seedance-2.5)
            duration: 时长秒数
            size: 分辨率 (720p | 1080p)
            ratio: 视频比例 (16:9 | 1:1 | 9:16)

        Returns:
            {"task_id": "cgt-...", "status": "queued", "model": "..."}
        """
        try:
            # 火山方舟视频生成 API — 使用 contents/generations/tasks 端点
            resolved_model = self._ep(model)
            if model == "doubao-seedance-1.5-pro":
                resolved_model = self._ep("doubao-seedance-1-5-pro-251215")
            if (
                model in {"doubao-seedance-2.0-fast"}
                and not resolved_model.startswith("ep-")
                and self.endpoints.get("doubao-video", "").startswith("ep-")
            ):
                resolved_model = self.endpoints["doubao-video"]
            image_item = None
            if image_url:
                image_item = {
                    "type": "image_url",
                    "image_url": {"url": image_url},
                    "role": "reference_image",
                }
            reference_items = []
            text_reference_lines = []
            for item in reference_assets or []:
                item_type = str(item.get("type") or "").strip()
                url = str(item.get("url") or item.get("provider_ref") or "").strip()
                role = str(item.get("role") or "reference").strip()
                if item_type == "image_url" and url:
                    ref = {
                        "type": "image_url",
                        "image_url": {"url": url},
                        "role": role if role.startswith("reference_") else "reference_image",
                    }
                    reference_items.append(ref)
                elif item_type == "video_url" and url:
                    ref = {
                        "type": "video_url",
                        "video_url": {"url": url},
                        "role": role if role.startswith("reference_") else "reference_video",
                    }
                    reference_items.append(ref)
                elif item_type == "audio_url" and url:
                    ref = {
                        "type": "audio_url",
                        "audio_url": {"url": url},
                        "role": role if role.startswith("reference_") else "reference_audio",
                    }
                    reference_items.append(ref)
                elif item_type == "text" and url:
                    name = str(item.get("name") or item.get("asset_id") or "text_reference").strip()
                    text_reference_lines.append(f"[{name} / {role}]\n{url[:1800]}")
            if image_item and not reference_items:
                reference_items.append(image_item)
            if text_reference_lines:
                prompt = (
                    f"{prompt}\n\n参考文案素材如下，必须吸收其中的产品信息、卖点和表达重点：\n"
                    + "\n\n".join(text_reference_lines)
                )

            if resolved_model.startswith("doubao-seedance-1-5-"):
                audio_hint = (
                    "开启原生声音：同步生成与画面高度匹配的人声对白、环境音效、动作声音和背景氛围音乐。"
                    if native_audio
                    else "关闭原生声音：生成无对白、无环境声、无背景音乐的静音视频。"
                )
                prompt_text = (
                    f"{prompt} {audio_hint} --duration {duration} --resolution {size} "
                    f"--ratio {ratio} --camerafixed false --watermark true"
                )
                payload = {
                    "model": resolved_model,
                    "content": [{"type": "text", "text": prompt_text}, *reference_items],
                    "generate_audio": native_audio,
                }
            else:
                payload = {
                    "model": resolved_model,
                    "content": [{"type": "text", "text": prompt}, *reference_items],
                    "resolution": size,
                    "ratio": ratio,
                    "duration": duration,
                    "generate_audio": native_audio,
                    "watermark": False,
                }

            async with httpx.AsyncClient(timeout=60, trust_env=False) as c:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                r = await c.post(
                    f"{self.base_url}/contents/generations/tasks",
                    headers=headers,
                    json=payload,
                )
                if r.is_error:
                    raise IntegrationError(
                        f"HTTP {r.status_code}: {r.text[:500]}"
                    )
                r.raise_for_status()
                data = r.json()
                return {
                    "task_id": data.get("id", ""),
                    "status": "queued",
                    "model": model,
                    "prompt": prompt,
                }
        except Exception as e:
            raise IntegrationError(f"VolcEngine video generation submit failed: {e}")

    async def get_video_task(self, task_id: str, model: str = "doubao-seedance-2.0-fast") -> dict:
        """查询视频生成任务状态。

        API: GET /api/v3/contents/generations/tasks/{task_id}

        Returns:
            {"task_id": "...", "status": "queued|running|succeeded|failed",
             "video_url": "...", "progress": 0-100, "error": "..."}
        """
        try:
            async with httpx.AsyncClient(timeout=30, trust_env=False) as c:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                r = await c.get(
                    f"{self.base_url}/contents/generations/tasks/{task_id}",
                    headers=headers,
                )
                r.raise_for_status()
                data = r.json()
                return {
                    "task_id": task_id,
                    "status": data.get("status", "unknown"),
                    "video_url": data.get("content", {}).get("video_url", ""),
                    "progress": 50 if data.get("status") == "running" else (100 if data.get("status") == "succeeded" else 0),
                    "error": data.get("error", ""),
                }
        except Exception as e:
            raise IntegrationError(f"VolcEngine video task query failed: {e}")

    async def download_video(self, video_url: str, output_name: str = "", output_dir: str | None = None) -> str:
        """下载已完成的视频到本地。"""
        try:
            async with httpx.AsyncClient(timeout=120, trust_env=False) as c:
                r = await c.get(video_url)
                r.raise_for_status()

            if not output_name:
                ts = int(time.time())
                output_name = f"volc_video_{ts}_{uuid.uuid4().hex[:6]}.mp4"
            if output_dir is None:
                from szyg.media_storage import get_media_output_dir
                output_path = get_media_output_dir("video")
            else:
                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)
            path = output_path / output_name
            path.write_bytes(r.content)
            return str(path)
        except Exception as e:
            raise IntegrationError(f"VolcEngine video download failed: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # 4. 语音合成 (TTS)
    # ═══════════════════════════════════════════════════════════════════════

    # 豆包语音合成声音ID映射
    VOICE_IDS = {
        "zh_female_xiaoyi": "zh_female_xiaoyi",
        "zh_female_shuangjia": "zh_female_shuangjia",
        "zh_male_sichuan": "zh_male_sichuan",
        "zh_female_linjianvjin": "zh_female_linjianvjin",
        "zh_male_yuanfeng": "zh_male_yuanfeng",
        "en_female_sarah": "en_female_sarah",
        "en_male_george": "en_male_george",
    }

    EMOTION_TO_SPEED = {
        "neutral": (1.0, 0),
        "happy": (1.1, 50),
        "sad": (0.9, -50),
        "excited": (1.2, 80),
        "calm": (0.95, -30),
        "angry": (1.05, 30),
    }

    async def text_to_speech(
        self,
        text: str,
        voice_id: str = "zh_female_xiaoyi",
        emotion: str = "neutral",
        speed: float = 1.0,
        pitch: int = 0,
        output_name: str = "",
        output_dir: str | None = None,
    ) -> str:
        """情感语音合成，返回本地音频文件路径。

        Args:
            text: 要合成的文本 (中文/英文)
            voice_id: 声音ID
            emotion: 情感 (neutral/happy/sad/excited/calm/angry)
            speed: 语速倍率 (0.5-2.0)
            pitch: 音调调整 (-100 ~ +100)
            output_name: 输出文件名

        Returns:
            本地音频文件路径 (.mp3)
        """
        # 情感映射到速度和音调
        if emotion in self.EMOTION_TO_SPEED:
            em_speed, em_pitch = self.EMOTION_TO_SPEED[emotion]
            speed = speed * em_speed
            pitch = pitch + em_pitch

        # 限制范围
        speed = max(0.5, min(2.0, speed))
        pitch = max(-100, min(100, pitch))

        try:
            # 火山引擎TTS使用OpenAI TTS兼容接口
            response = await self._retry(
                self.client.audio.speech.create,
                model=self._ep("doubao-tts"),
                voice=self.VOICE_IDS.get(voice_id, voice_id),
                input=text,
                speed=speed,
                response_format="mp3",
            )

            if not output_name:
                ts = int(time.time())
                output_name = f"volc_tts_{emotion}_{ts}_{uuid.uuid4().hex[:6]}.mp3"
            if output_dir is None:
                from szyg.media_storage import get_media_output_dir
                output_path = get_media_output_dir("audio")
            else:
                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)
            path = output_path / output_name
            path.write_bytes(response.content)
            return str(path)

        except Exception as e:
            raise IntegrationError(f"VolcEngine TTS failed: {e}")

    async def seed_audio_text_to_speech(
        self,
        text: str,
        voice_id: str = "zh_female_xiaoyi",
        voice_prompt: str = "",
        speed: float = 1.0,
        pitch: int = 0,
        output_name: str = "",
        output_dir: str | None = None,
        response_format: str = "mp3",
    ) -> tuple[str, float]:
        """Generate speech through VolcEngine OpenSpeech seed-audio-1.0 HTTP API."""
        speech_api_key = (
            os.environ.get("VOLCENGINE_SPEECH_API_KEY", "")
            or os.environ.get("VOLCENGINE_TTS_API_KEY", "")
            or _read_config_key("speech_api_key")
        )
        if not speech_api_key:
            raise IntegrationError("VolcEngine Speech API key not configured — set VOLCENGINE_SPEECH_API_KEY")

        text_prompt = text.strip()
        if voice_prompt.strip():
            text_prompt = f"{voice_prompt.strip()}\n{text_prompt}"

        speech_rate = int(round((max(0.5, min(2.0, speed)) - 1.0) * 100))
        pitch_rate = int(round(max(-100, min(100, pitch)) / 100 * 12))
        references = []
        provider_voice = self.VOICE_IDS.get(voice_id, voice_id)
        # seed-audio-1.0 speaker ids are not the same as legacy Ark TTS voices
        # such as zh_female_xiaoyi. Only pass explicit Seed Audio speakers.
        if provider_voice and not provider_voice.startswith(("zh_", "en_")):
            references.append({"speaker": provider_voice})

        payload = {
            "model": "seed-audio-1.0",
            "text_prompt": text_prompt,
            "references": references,
            "audio_config": {
                "format": response_format,
                "sample_rate": 24000,
                "speech_rate": max(-50, min(100, speech_rate)),
                "pitch_rate": max(-12, min(12, pitch_rate)),
            },
        }

        try:
            async with httpx.AsyncClient(timeout=120, trust_env=False) as c:
                response = await c.post(
                    "https://openspeech.bytedance.com/api/v3/tts/create",
                    headers={
                        "X-Api-Key": speech_api_key,
                        "X-Api-Request-Id": str(uuid.uuid4()),
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            if response.status_code >= 400:
                raise IntegrationError(f"HTTP {response.status_code}: {response.text[:500]}")
            data = response.json()
            if int(data.get("code", 0) or 0) != 0:
                raise IntegrationError(f"{data.get('code')}: {data.get('message') or 'speech synthesis failed'}")

            audio = data.get("audio") or ""
            if not audio:
                raise IntegrationError("speech synthesis returned no audio data")

            if not output_name:
                ts = int(time.time())
                output_name = f"seed_audio_{ts}_{uuid.uuid4().hex[:6]}.{response_format}"
            if output_dir is None:
                from szyg.media_storage import get_media_output_dir
                output_path = get_media_output_dir("audio")
            else:
                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)
            path = output_path / output_name
            path.write_bytes(base64.b64decode(audio))
            return str(path), float(data.get("duration") or 0)
        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(f"VolcEngine seed-audio TTS failed: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # 5. 声音克隆 (Voice Clone)
    # ═══════════════════════════════════════════════════════════════════════

    async def clone_voice(
        self,
        audio_sample_path: str,
        text: str,
        emotion: str = "neutral",
        output_name: str = "",
        output_dir: str | None = None,
    ) -> str:
        """声音克隆 + 语音合成。

        上传声音样本，克隆后用于合成指定文本。

        Args:
            audio_sample_path: 声音样本文件路径 (.wav/.mp3, 10s-30s)
            text: 要合成的文本
            emotion: 情感
            output_name: 输出文件名

        Returns:
            本地音频文件路径
        """
        sample_path = Path(audio_sample_path)
        if not sample_path.exists():
            raise IntegrationError(f"Voice sample not found: {audio_sample_path}")

        try:
            # 火山引擎声音克隆使用 multipart/form-data 上传
            async with httpx.AsyncClient(timeout=120, trust_env=False) as c:
                headers = {"Authorization": f"Bearer {self.api_key}"}

                # Step 1: 上传声音样本获取 voice_id
                with open(sample_path, "rb") as f:
                    files = {"file": (sample_path.name, f, "audio/mpeg")}
                    data = {"model": self._ep("doubao-voice-clone")}
                    upload_r = await c.post(
                        f"{self.base_url}/audio/voice-clone",
                        headers=headers,
                        data=data,
                        files=files,
                    )
                    upload_r.raise_for_status()
                    voice_id = upload_r.json().get("voice_id", "")

                if not voice_id:
                    raise IntegrationError("Voice clone upload failed: no voice_id returned")

                # Step 2: 使用克隆的声音合成
                tts_payload = {
                    "model": self._ep("doubao-tts"),
                    "voice": voice_id,
                    "input": text,
                    "response_format": "mp3",
                }
                tts_r = await c.post(
                    f"{self.base_url}/audio/speech",
                    headers={**headers, "Content-Type": "application/json"},
                    json=tts_payload,
                )
                tts_r.raise_for_status()

            if not output_name:
                ts = int(time.time())
                output_name = f"volc_clone_{emotion}_{ts}_{uuid.uuid4().hex[:6]}.mp3"
            if output_dir is None:
                from szyg.media_storage import get_media_output_dir
                output_path = get_media_output_dir("audio")
            else:
                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)
            path = output_path / output_name
            path.write_bytes(tts_r.content)
            return str(path)

        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(f"VolcEngine voice clone failed: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # 6. 向量嵌入 (Embedding)
    # ═══════════════════════════════════════════════════════════════════════

    async def create_embedding(
        self,
        texts: list[str] | str,
        model: str = "doubao-embedding",
    ) -> dict:
        """批量文本向量嵌入。

        Args:
            texts: 文本或文本列表
            model: 嵌入模型

        Returns:
            {"embeddings": [[0.1, 0.2, ...], ...], "model": "...", "usage": {...}}
        """
        if isinstance(texts, str):
            texts = [texts]

        try:
            response = await self._retry(
                self.client.embeddings.create,
                model=self._ep(model),
                input=texts,
            )

            embeddings = [item.embedding for item in response.data]
            return {
                "embeddings": embeddings,
                "model": response.model or model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
            }
        except Exception as e:
            raise IntegrationError(f"VolcEngine embedding failed: {e}")

    # ── Cleanup ───────────────────────────────────────────────────────────

    async def close(self):
        if self._client is not None:
            try:
                await self._client.close()
            except RuntimeError:
                pass
            self._client = None
        if self._httpx is not None and not self._httpx.is_closed:
            await self._httpx.aclose()
            self._httpx = None
