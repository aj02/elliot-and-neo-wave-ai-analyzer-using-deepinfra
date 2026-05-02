"""Redis-backed UploadSession store.

Sessions are ephemeral handles between `POST /upload` (stages files + validates
them) and `POST /analyze` (kicks off the run). 24-hour TTL keeps Redis tidy.
The persistent record is the `Run` (lands in Step 10), not the session.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from app.schemas.input import UploadedTimeframe

if TYPE_CHECKING:
    from redis.asyncio import Redis


SESSION_KEY_PREFIX = "wave-agent:session:"
SESSION_TTL_SECONDS = 24 * 60 * 60


class UploadSession(BaseModel):
    """Persisted session metadata. Lives in Redis between upload and analyze."""

    model_config = ConfigDict(extra="forbid")

    id: str
    instrument_name: str
    created_at: datetime
    timeframes: list[UploadedTimeframe]


def new_session_id() -> str:
    """24-char URL-safe id. ~140 bits of entropy — collision-free for our use."""
    return secrets.token_urlsafe(18)


def _key(session_id: str) -> str:
    return f"{SESSION_KEY_PREFIX}{session_id}"


class SessionStore:
    """Async Redis adapter for UploadSession."""

    def __init__(self, redis: "Redis") -> None:
        self._redis = redis

    async def create(
        self, *, instrument_name: str, timeframes: list[UploadedTimeframe]
    ) -> UploadSession:
        session = UploadSession(
            id=new_session_id(),
            instrument_name=instrument_name,
            created_at=datetime.now(UTC),
            timeframes=timeframes,
        )
        await self._redis.set(
            _key(session.id),
            session.model_dump_json(),
            ex=SESSION_TTL_SECONDS,
        )
        return session

    async def get(self, session_id: str) -> UploadSession | None:
        raw = await self._redis.get(_key(session_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        return UploadSession.model_validate_json(raw)

    async def delete(self, session_id: str) -> None:
        await self._redis.delete(_key(session_id))
