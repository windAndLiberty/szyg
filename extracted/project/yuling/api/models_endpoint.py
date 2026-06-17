from fastapi import APIRouter

router = APIRouter()


@router.get("/models", tags=["models"])
async def list_models():
    """获取可用模型列表"""
    return {
        "object": "list",
        "data": [
            {"id": "qwen2.5", "object": "model", "created": 1677610602},
            {"id": "qwen2.5:14b", "object": "model", "created": 1677610602},
            {"id": "llama3", "object": "model", "created": 1677649963},
            {"id": "gpt-4", "object": "model", "created": 1677610602},
            {"id": "gpt-3.5-turbo", "object": "model", "created": 1677649963},
        ],
    }
