"""FastAPI application factory.

The ASGI app is assembled here. Domain logic lives in dedicated packages;
this module only wires transport, middleware, and lifecycle.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.health import liveness_payload
from app.api.v1.router import api_router
from app.core.bootstrap import ensure_dev_tenant
from app.core.config import get_settings
from app.core.db import dispose_engines, get_sync_session_factory
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestIdMiddleware
from app.core.qdrant import close_qdrant
from app.core.redis import close_redis

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)
    logger.info(
        "api.startup",
        env=settings.app_env,
        version=__version__,
    )
    if settings.app_env == "development":
        factory = get_sync_session_factory()
        with factory() as session:
            ensure_dev_tenant(session)
            session.commit()
    yield
    await close_redis()
    close_qdrant()
    await dispose_engines()
    logger.info("api.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="CorpusForge API",
        description=(
            "Production-oriented multi-source RAG platform. "
            "Control plane for ingestion, retrieval, evaluation, and operations."
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    application.add_middleware(RequestIdMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix=settings.api_v1_prefix)

    @application.get("/health", tags=["health"], summary="Process liveness")
    async def liveness() -> dict[str, str]:
        return liveness_payload()

    return application


app = create_app()
