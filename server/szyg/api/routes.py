from fastapi import APIRouter
from szyg.api.chat import router as chat_router
from szyg.api.models_endpoint import router as models_router

router = APIRouter()
router.include_router(chat_router)
router.include_router(models_router)

# frontend_routes included separately in app.py via _try_include
