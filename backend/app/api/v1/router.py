"""API v1 routers."""

from fastapi import APIRouter

from app.api.v1.chat import router as chat_router
from app.api.v1.documents import router as documents_router
from app.api.v1.embeddings import router as embeddings_router
from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.search import router as search_router
from app.api.v1.sources import router as sources_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(sources_router)
api_router.include_router(documents_router)
api_router.include_router(embeddings_router)
api_router.include_router(search_router)
api_router.include_router(chat_router)
api_router.include_router(jobs_router)
