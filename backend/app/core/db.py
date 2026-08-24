"""SQLAlchemy engines and session factories.

FastAPI uses the async engine. Alembic and Celery use the sync engine.
Tables are never created with create_all on startup; schema changes go
through Alembic migrations only.
"""

from collections.abc import AsyncGenerator, Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import Settings, get_settings

_async_engine: AsyncEngine | None = None
_sync_engine: Engine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None
_sync_session_factory: sessionmaker[Session] | None = None


def get_async_engine(settings: Settings | None = None) -> AsyncEngine:
    global _async_engine
    if _async_engine is None:
        cfg = settings or get_settings()
        _async_engine = create_async_engine(
            cfg.async_database_url,
            pool_pre_ping=True,
            pool_size=cfg.postgres_pool_size,
            max_overflow=cfg.postgres_max_overflow,
        )
    return _async_engine


def get_sync_engine(settings: Settings | None = None) -> Engine:
    global _sync_engine
    if _sync_engine is None:
        cfg = settings or get_settings()
        _sync_engine = create_engine(
            cfg.sync_database_url,
            pool_pre_ping=True,
            pool_size=cfg.postgres_pool_size,
            max_overflow=cfg.postgres_max_overflow,
        )
    return _sync_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_async_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _async_session_factory


def get_sync_session_factory() -> sessionmaker[Session]:
    global _sync_session_factory
    if _sync_session_factory is None:
        _sync_session_factory = sessionmaker(
            get_sync_engine(),
            expire_on_commit=False,
            class_=Session,
        )
    return _sync_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    factory = get_async_session_factory()
    async with factory() as session:
        yield session


def get_sync_db() -> Generator[Session, None, None]:
    factory = get_sync_session_factory()
    with factory() as session:
        yield session


def create_null_pool_sync_engine(url: str) -> Engine:
    """Alembic uses a NullPool so migrations do not hold connections."""
    return create_engine(url, poolclass=NullPool, pool_pre_ping=True)


async def dispose_engines() -> None:
    global _async_engine, _sync_engine, _async_session_factory, _sync_session_factory
    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None
    if _sync_engine is not None:
        _sync_engine.dispose()
        _sync_engine = None
    _async_session_factory = None
    _sync_session_factory = None
