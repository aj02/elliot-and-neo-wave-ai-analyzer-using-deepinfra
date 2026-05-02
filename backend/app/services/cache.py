"""Content-hash-based agent-output caching.

Cache key: `SHA-256(StructureSummary JSON + agent name + model name)`.
Same input + same agent + same model → identical key → cache hit.
TTL defaults to 7 days (structures don't change once data is fixed).

Stored payload: the agent's raw output JSON, ready to be re-validated by the
caller into the appropriate Pydantic model.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

from app.core.config import get_settings

if TYPE_CHECKING:
    from redis.asyncio import Redis


CACHE_KEY_PREFIX = "wave-agent:agent-cache:"


def cache_key(*, summary_json: str, agent_name: str, model_name: str) -> str:
    """Deterministic cache key for an agent run.

    Args:
        summary_json: JSON-serialised StructureSummary (sort keys for stability).
        agent_name: e.g. "elliott", "neowave", "synthesis".
        model_name: the actual model identifier the agent ran on.
    """
    payload = f"{summary_json}|{agent_name}|{model_name}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{CACHE_KEY_PREFIX}{digest}"


class AgentCache:
    """Thin async wrapper over Redis for agent output caching."""

    def __init__(self, redis: "Redis", ttl_seconds: int | None = None) -> None:
        self._redis = redis
        self._ttl = ttl_seconds or get_settings().cache_ttl_seconds

    async def get(self, key: str) -> Any | None:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    async def set(self, key: str, value: Any) -> None:
        await self._redis.set(key, json.dumps(value, default=str), ex=self._ttl)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)
