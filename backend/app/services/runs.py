"""In-process run registry + Redis-backed report persistence.

For this single-instance demo the live run state lives in a process-local
dict. Completed reports are persisted to Redis with a 24h TTL so a
`GET /runs/{id}` after the WebSocket has closed still works.

Run state uses a single events list as the source of truth and an
`asyncio.Condition` for change notification. WebSocket subscribers wait on
the condition with an index cursor — this lets late subscribers catch up by
replaying the buffer without races, and supports more than one subscriber
per run (e.g. the analyze page tab and a re-loaded report tab).

A multi-instance deployment would back this with Redis pub/sub or a message
broker; the interface here is small enough to swap out later without
disturbing the API layer.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from app.core.logging import get_logger
from app.schemas.report import AnalysisReport


log = get_logger("services.runs")


if TYPE_CHECKING:
    from redis.asyncio import Redis


REPORT_KEY_PREFIX = "wave-agent:run:report:"
CHART_PATHS_KEY_PREFIX = "wave-agent:run:chart-paths:"
REPORT_TTL_SECONDS = 24 * 60 * 60


RunPhase = Literal["pending", "running", "completed", "failed", "rejected_cost_cap"]


@dataclass
class RunState:
    """Live in-process state for one analysis run."""

    run_id: str
    instrument_name: str
    phase: RunPhase = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    events: list[dict] = field(default_factory=list)
    report: AnalysisReport | None = None
    _condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    _closed: bool = False

    async def emit(self, evt: dict) -> None:
        """Append an event and wake all WebSocket subscribers."""
        async with self._condition:
            self.events.append(evt)
            self._condition.notify_all()

    async def close(self) -> None:
        """Mark the stream as ended; wake all subscribers so they can exit."""
        async with self._condition:
            self._closed = True
            self._condition.notify_all()

    async def wait_for_events_after(self, since_idx: int) -> tuple[list[dict], bool]:
        """Block until events beyond `since_idx` appear OR the run closes.

        Returns `(new_events, is_closed)`. Multiple subscribers each maintain
        their own cursor; the events list never gets consumed.
        """
        async with self._condition:
            while len(self.events) <= since_idx and not self._closed:
                await self._condition.wait()
            return list(self.events[since_idx:]), self._closed


class RunRegistry:
    """Process-local registry. One per FastAPI app."""

    def __init__(self) -> None:
        self._runs: dict[str, RunState] = {}

    def create(self, run_id: str, instrument_name: str) -> RunState:
        state = RunState(run_id=run_id, instrument_name=instrument_name)
        self._runs[run_id] = state
        return state

    def get(self, run_id: str) -> RunState | None:
        return self._runs.get(run_id)

    def drop(self, run_id: str) -> None:
        self._runs.pop(run_id, None)


# Singleton — bound at module import time. The dependency provider returns this.
_REGISTRY = RunRegistry()


def get_registry() -> RunRegistry:
    return _REGISTRY


# ---------------------------------------------------------------------------
# Redis-backed report persistence
# ---------------------------------------------------------------------------


def _report_key(run_id: str) -> str:
    return f"{REPORT_KEY_PREFIX}{run_id}"


async def persist_report(redis: "Redis", report: AnalysisReport) -> None:
    """Save the final report to Redis (24h TTL)."""
    await redis.set(
        _report_key(report.run_id),
        report.model_dump_json(),
        ex=REPORT_TTL_SECONDS,
    )


async def fetch_report(redis: "Redis", run_id: str) -> AnalysisReport | None:
    raw = await redis.get(_report_key(run_id))
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return AnalysisReport.model_validate_json(raw)


# ---------------------------------------------------------------------------
# Per-run chart-data path mapping. Keeps server-internal storage paths out of
# the AnalysisReport JSON while still letting the chart-data endpoint find the
# right CSV at request time.
# ---------------------------------------------------------------------------


def _chart_paths_key(run_id: str) -> str:
    return f"{CHART_PATHS_KEY_PREFIX}{run_id}"


async def persist_chart_paths(redis: "Redis", run_id: str, paths: dict[str, str]) -> None:
    import json as _json

    await redis.set(_chart_paths_key(run_id), _json.dumps(paths), ex=REPORT_TTL_SECONDS)


async def fetch_chart_paths(redis: "Redis", run_id: str) -> dict[str, str] | None:
    raw = await redis.get(_chart_paths_key(run_id))
    if raw is None:
        return None
    import json as _json

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return _json.loads(raw)
