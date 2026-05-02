"""Synthesis output schemas — what the cross-timeframe Sonnet agent emits.

The agent identifies which already-validated counts compose each scenario via
`CountRef`s. It does NOT invent counts. The orchestrator hydrates each
scenario with the deterministic invalidation levels of its supporting counts
after the agent runs (so the prices in the final report are always Python's,
not the LLM's).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.levels import InvalidationLevel


class CountRef(BaseModel):
    """Reference to a surviving count by (timeframe, framework, index in the surviving list)."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    timeframe: str = Field(description="Timeframe label, e.g. '1D', '1W'.")
    framework: Literal["elliott", "neowave"]
    count_idx: int = Field(ge=0, le=2, description="0-based index into the surviving list (max 3).")


class SynthesisScenario(BaseModel):
    """One ranked scenario in the cross-timeframe synthesis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rank: Literal[1, 2, 3]
    label: Literal["Primary", "Alternate", "Counter"]
    summary: str = Field(
        max_length=480,
        description=(
            "Structural summary; must reference at least one pivot index. "
            "Forbidden words: buy/sell/long/short/target/predict/forecast/recommend."
        ),
    )
    cross_timeframe_alignment: str = Field(max_length=320)
    cross_framework_agreement: str = Field(max_length=320)
    supporting: list[CountRef] = Field(
        default_factory=list,
        description="Surviving counts that compose this scenario.",
    )
    # Hydrated by the orchestrator from the supporting counts' invalidation levels.
    invalidation_levels: list[InvalidationLevel] = Field(default_factory=list)


class SynthesisReport(BaseModel):
    """Top-level synthesis output. 1–3 scenarios."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    scenarios: list[SynthesisScenario] = Field(default_factory=list, max_length=3)
    methodology_note: str = Field(
        default="",
        max_length=320,
        description="Short note (≤320 chars) on how the ranking was decided.",
    )
