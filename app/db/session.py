"""
AERION — Async Database Session & Engine Factory
SQLAlchemy 2.x async session dependency and engine management.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger("aerion.db")


class Base(DeclarativeBase):
    """Declarative Base class for all AERION relational and spatial models."""
    pass


_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_async_engine() -> AsyncEngine:
    """
    Returns the singleton AsyncEngine instance configured with connection pool parameters.
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        db_url = settings.async_database_url
        
        # Determine connect_args depending on driver
        connect_args = {}
        if "postgresql+asyncpg" in db_url:
            # Pass timeout or custom asyncpg args
            connect_args = {"server_settings": {"application_name": "aerion_api"}}

        _engine = create_async_engine(
            db_url,
            echo=settings.DATABASE_ECHO,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_timeout=settings.DATABASE_POOL_TIMEOUT,
            pool_recycle=settings.DATABASE_POOL_RECYCLE,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        logger.info(f"Initialized AERION AsyncEngine for {settings.POSTGRES_DB} on {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Returns the singleton async sessionmaker instance.
    """
    global _session_factory
    if _session_factory is None:
        engine = get_async_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


async def AsyncSessionLocal() -> AsyncSession:
    """Create a new AsyncSession."""
    factory = get_session_factory()
    return factory()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding an async database session with automatic transaction management.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db_connections() -> None:
    """Closes all active engine connections on application shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("AERION AsyncEngine connection pool disposed.")
