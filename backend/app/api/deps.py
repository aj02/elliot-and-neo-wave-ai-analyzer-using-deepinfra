"""FastAPI dependency providers — Redis client, storage, session store."""

from __future__ import annotations

from typing import Annotated, AsyncIterator

from fastapi import Depends
from redis.asyncio import Redis, from_url

from app.core.config import get_settings
from app.upload.sessions import SessionStore
from app.upload.storage import FileSystemStorage


_redis_singleton: Redis | None = None


async def get_redis() -> AsyncIterator[Redis]:
    """Process-wide Redis pool, lazily created."""
    global _redis_singleton
    if _redis_singleton is None:
        _redis_singleton = from_url(get_settings().redis_url, decode_responses=False)
    yield _redis_singleton


async def get_session_store(redis: Annotated[Redis, Depends(get_redis)]) -> SessionStore:
    return SessionStore(redis)


def get_storage() -> FileSystemStorage:
    return FileSystemStorage()


RedisDep = Annotated[Redis, Depends(get_redis)]
SessionStoreDep = Annotated[SessionStore, Depends(get_session_store)]
StorageDep = Annotated[FileSystemStorage, Depends(get_storage)]
