"""
AERION — Database Module
Encapsulates async SQLAlchemy 2.x engine, session factories, base models,
and PostGIS spatial integration.
"""

from app.db.session import (
    Base,
    get_async_session,
    get_async_engine,
    AsyncSessionLocal,
    close_db_connections,
)

__all__ = [
    "Base",
    "get_async_session",
    "get_async_engine",
    "AsyncSessionLocal",
    "close_db_connections",
]
