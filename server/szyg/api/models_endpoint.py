"""
AI 模型列表 API — 从已配置的后端动态获取可用模型。

支持后端:
  - 火山引擎方舟 (VolcEngine ARK)
  - 本地 Ollama
  - LiteLLM

用法: GET /api/models → 返回所有后端的可用模型列表
"""
import logging
from fastapi import APIRouter

from szyg.agent_core.model_router import ModelRouter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/models", tags=["models"])
async def list_models():
    """获取所有已配置后端的可用模型列表。

    调用 ModelRouter 的 get_available_models() 动态查询各后端。
    """
    try:
        router_instance = ModelRouter()
        models = await router_instance.get_available_models()

        if not models:
            # 如果没有后端在线，返回离线可用列表
            return {
                "object": "list",
                "source": "static_fallback",
                "data": [
                    {"id": "doubao-pro-128k", "object": "model", "backend": "volcengine", "available": False},
                    {"id": "deepseek-r1", "object": "model", "backend": "volcengine", "available": False},
                    {"id": "deepseek-v3", "object": "model", "backend": "volcengine", "available": False},
                ],
            }

        return {
            "object": "list",
            "source": "dynamic",
            "backends": list(router_instance.get_backends().keys()),
            "data": [{"id": m, "object": "model"} for m in models],
        }
    except Exception as e:
        logger.warning(f"列出模型失败: {e}")
        return {
            "object": "list",
            "source": "error_fallback",
            "error": str(e)[:200],
            "data": [
                {"id": "qwen2.5", "object": "model", "backend": "ollama"},
                {"id": "doubao-pro-128k", "object": "model", "backend": "volcengine"},
                {"id": "deepseek-r1", "object": "model", "backend": "volcengine"},
            ],
        }
