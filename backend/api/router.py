from fastapi import APIRouter

from api.chat import router as chat_router
from api.complaints import router as complaints_router

api_router = APIRouter()
api_router.include_router(chat_router)
api_router.include_router(complaints_router)
