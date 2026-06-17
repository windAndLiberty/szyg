from fastapi import APIRouter
from yuling.api.chat import router as chat_router
from yuling.api.models_endpoint import router as models_router
from yuling.api.frontend_routes import router as frontend_router

router = APIRouter()
router.include_router(chat_router)
router.include_router(models_router)
router.include_router(frontend_router)
