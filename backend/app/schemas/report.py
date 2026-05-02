"""Final analysis report — what the orchestrator returns and what `/runs/{id}` serves."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.responses import _BaseResponse
from app.schemas.structure import StructureSummary
from app.schemas.synthesis import SynthesisReport
from app.schemas.validated import ValidationOutcome


RunStatus = Literal["pending", "running", "completed", "failed", "rejected_cost_cap"]


class CostBreakdown(BaseModel):
    """Per-agent cost summary for one run."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    agent_name: str
    model: str
    is_test: bool
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cache_hit: bool
    timeframe: str | None = None


class TimeframeReport(BaseModel):
    """All deterministic + interpretive output for one timeframe."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    timeframe: str
    structure: StructureSummary
    validation: ValidationOutcome


class AnalysisReport(_BaseResponse):
    """Top-level report. Carries the disclaimer in `disclaimer` (via `_BaseResponse`)."""

    run_id: str
    instrument_name: str
    status: RunStatus
    started_at: datetime
    completed_at: datetime | None
    timeframes: list[TimeframeReport]
    synthesis: SynthesisReport | None
    cost_breakdown: list[CostBreakdown] = Field(default_factory=list)
    total_cost_usd: float = 0.0
    error: str | None = None
