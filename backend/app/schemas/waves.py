"""Wave-count schemas — what an LLM agent emits.

`WaveSegment`s reference pivots by index (`start_pivot_idx`, `end_pivot_idx`).
Prices are looked up from the underlying pivot list at validation time, so the
agent never has to repeat numeric data the system already knows.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# Elliott degree labels in increasing-magnitude order. Used for sanity checks
# (e.g. cross-timeframe degree alignment in synthesis).
ELLIOTT_DEGREES = (
    "Subminuette",
    "Minuette",
    "Minute",
    "Minor",
    "Intermediate",
    "Primary",
    "Cycle",
    "Supercycle",
    "GrandSupercycle",
)

ElliottWaveLabel = Literal[
    "1", "2", "3", "4", "5",  # impulse / diagonal
    "A", "B", "C",            # zigzag / flat
    "a", "b", "c", "d", "e",  # triangle
    "W", "X", "Y", "Z",       # combinations
]

ElliottPattern = Literal[
    "impulse",
    "leading_diagonal",
    "ending_diagonal",
    "zigzag",
    "flat",
    "expanded_flat",
    "running_flat",
    "triangle_contracting",
    "triangle_expanding",
    "double_three",
    "triple_three",
]

NeowavePattern = Literal[
    "impulse",
    "zigzag",
    "flat",
    "triangle_contracting",
    "triangle_expanding",
    "diametric",
    "symmetrical",
    "double_combination",
    "triple_combination",
]


class WaveSegment(BaseModel):
    """A labelled segment between two pivots (inclusive)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(description="e.g. '1', '3', 'a', 'X'.")
    start_pivot_idx: int = Field(ge=0, description="`Pivot.idx` of the segment's start.")
    end_pivot_idx: int = Field(ge=0, description="`Pivot.idx` of the segment's end.")


class ElliottCount(BaseModel):
    """One candidate Elliott Wave count proposed by the Elliott agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pattern: ElliottPattern
    degree: str = Field(description="One of ELLIOTT_DEGREES.")
    waves: list[WaveSegment]
    current_wave: str = Field(description="Label of the wave currently in progress.")
    rationale: str = Field(
        max_length=600,
        description=(
            "Structural rationale. The LLM is prompted to keep this ≤ 320 chars; "
            "the post-processing decorator then expands `#<idx>` references into "
            "`<price> (<date>)` (each replacement adds ~12-22 chars), which can "
            "push the stored value past 320. The 600 cap is the runaway-output "
            "guard, not the typical-case limit. Never make a buy/sell statement, "
            "never quote 'targets'."
        ),
    )


class NeowaveCount(BaseModel):
    """One candidate NEOWave structural identification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pattern: NeowavePattern
    mono_waves: list[WaveSegment] = Field(
        description="The mono-wave segmentation (smallest unbroken moves)."
    )
    current_position: str = Field(
        description="Where the present moment falls within the pattern (e.g. 'in m5')."
    )
    rationale: str = Field(max_length=600)  # see ElliottCount.rationale for sizing rationale


class CandidateCounts(BaseModel):
    """Container for the (≤3) ranked candidates a per-timeframe agent produces."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    timeframe: str
    elliott: list[ElliottCount] = Field(default_factory=list, max_length=3)
    neowave: list[NeowaveCount] = Field(default_factory=list, max_length=3)
