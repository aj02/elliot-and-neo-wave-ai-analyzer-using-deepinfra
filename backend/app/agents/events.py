"""WebSocket event types for streaming run state to the frontend.

Events are JSON dictionaries with a discriminated `type` field. The frontend
parses them with the matching Zod schema mirror.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


EventType = Literal[
    "preprocessing_started",
    "preprocessing_completed",
    "agent_started",
    "agent_completed",
    "validation_completed",
    "synthesis_started",
    "synthesis_completed",
    "run_completed",
    "error",
]


class _Event(BaseModel):
    """Base event."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    type: EventType
    run_id: str
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data: dict[str, Any] = Field(default_factory=dict)


def event(
    *,
    type: EventType,  # noqa: A002 - matching the field name
    run_id: str,
    **data: Any,
) -> _Event:
    return _Event(type=type, run_id=run_id, data=data)
