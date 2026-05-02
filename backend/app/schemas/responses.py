"""Generic API response envelopes.

Every API response carries the disclaimer field. This is enforced at the schema
level so it cannot be omitted by accident.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _BaseResponse(BaseModel):
    """Base for all responses. Every response carries the disclaimer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    disclaimer: str = Field(
        ...,
        description=(
            "wave-agent does not give investment advice. The disclaimer is included "
            "on every response so consumers cannot strip it inadvertently."
        ),
    )


class RootResponse(_BaseResponse):
    name: Literal["wave-agent"] = "wave-agent"
    version: str


class HealthResponse(_BaseResponse):
    status: Literal["ok"] = "ok"
    version: str


class CheckDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    ok: bool
    detail: str | None = None
    latency_ms: float | None = None


class ReadyResponse(_BaseResponse):
    status: Literal["ok", "degraded"]
    checks: dict[str, CheckDetail]
