"""Async readiness probes for Postgres and Redis."""

from __future__ import annotations

import time
from typing import Tuple

import redis.asyncio as redis_async
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.schemas.responses import CheckDetail


async def check_postgres() -> Tuple[bool, CheckDetail]:
    """Round-trip a `SELECT 1` to confirm Postgres connectivity."""
    settings = get_settings()
    started = time.perf_counter()
    # SQLAlchemy 2.0 + psycopg v3 share the `postgresql+psycopg://` scheme
    # for both sync and async engines.
    engine = create_async_engine(settings.database_url, pool_pre_ping=True, future=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency_ms = (time.perf_counter() - started) * 1000
        return True, CheckDetail(ok=True, latency_ms=round(latency_ms, 2))
    except Exception as exc:  # noqa: BLE001 — health-probe surface
        return False, CheckDetail(ok=False, detail=type(exc).__name__)
    finally:
        await engine.dispose()


async def check_redis() -> Tuple[bool, CheckDetail]:
    """PING Redis."""
    settings = get_settings()
    started = time.perf_counter()
    client: redis_async.Redis = redis_async.from_url(settings.redis_url)
    try:
        pong = await client.ping()
        latency_ms = (time.perf_counter() - started) * 1000
        return bool(pong), CheckDetail(ok=bool(pong), latency_ms=round(latency_ms, 2))
    except Exception as exc:  # noqa: BLE001 — health-probe surface
        return False, CheckDetail(ok=False, detail=type(exc).__name__)
    finally:
        await client.aclose()
