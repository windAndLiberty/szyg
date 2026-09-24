"""
[DEPRECATED] ModelScope API 客户端 — 已于 2026-06-27 废弃。

ModelScope API Key 已过期 (401)，且平台已全面迁移至:
  - 火山引擎方舟 (VolcEngine ARK) — 主力 LLM + 图像/视频生成
  - 本地 Ollama — 免费降级

如需重新启用，请提供有效的 ModelScope API Key。
"""
raise ImportError(
    "ModelScope client has been deprecated (2026-06-27). "
    "Use VolcEngineClient (volcengine_client.py) or OllamaClient (ollama_client.py) instead. "
    "To re-enable ModelScope, provide a valid API key in config.yaml."
)
