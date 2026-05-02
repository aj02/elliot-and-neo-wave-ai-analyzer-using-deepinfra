"""Deterministic price-level schemas surfaced in reports.

These are produced by Python (`app.services.validator`), NOT by an LLM.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InvalidationLevel(BaseModel):
    """Price level whose violation falsifies a count.

    `direction="below"` means the count is invalidated if price moves below
    `price`; `direction="above"` is the opposite.

    `reason` references the specific Elliott/NEOWave rule and pivot that
    determines this level — so a user reading the report can audit the basis
    without trusting the LLM.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    price: float
    direction: Literal["above", "below"]
    reason: str = Field(
        description=(
            "Human-readable explanation referencing the rule and pivot index "
            "(e.g. 'Wave 4 cannot enter wave 1 territory (pivot #80 = 165.00).')"
        )
    )
