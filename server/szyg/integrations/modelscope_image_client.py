"""
[DEPRECATED] ModelScope 图像生成客户端 — 已于 2026-06-27 废弃。

Z-Image-Turbo 已不可用 — API Key 过期。
图像生成已全面迁移至:
  - 本地 ComfyUI (SD 2.1) — 免费无限
  - 火山引擎方舟 Seedream — 云端降级

如需重新启用，请提供有效的 ModelScope API Key。
"""
raise ImportError(
    "ModelScope Image client has been deprecated (2026-06-27). "
    "Use ComfyUIClient (comfyui_client.py) or VolcEngineClient.generate_image() instead. "
    "To re-enable ModelScope, provide a valid API key in config.yaml."
)
