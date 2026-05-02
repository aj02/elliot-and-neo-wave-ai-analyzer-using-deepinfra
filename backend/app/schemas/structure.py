"""StructureSummary — the compact, LLM-facing representation of a timeframe.

LLM agents see the `to_llm_text()` rendering of this object, NOT raw OHLCV.
The full structured form is kept for chart rendering and persistence.

Token budget per timeframe: ~80–150 Claude tokens for `to_llm_text()`.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.timeframe import Timeframe


PivotType = Literal["H", "L"]
PivotLabel = Literal["HH", "HL", "LH", "LL", "?"]


class Pivot(BaseModel):
    """A confirmed ZigZag pivot (high or low)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    idx: int = Field(ge=0, description="Bar index in the OHLCV series.")
    datetime: datetime
    price: float
    type: PivotType
    label: PivotLabel = Field(
        default="?",
        description="Pivot label vs. prior same-type pivot. '?' for the first of its type.",
    )
    swing_pct: float = Field(default=0.0, description="Signed % move from prior pivot.")
    swing_bars: int = Field(default=0, description="Bars elapsed since prior pivot.")
    fib_retrace_of_prior: float | None = Field(
        default=None,
        description=(
            "If this pivot retraces the prior leg, what fraction (0.0–1.0). "
            "None for the first two pivots (no prior leg to retrace)."
        ),
    )
    confirmed: bool = Field(
        default=True,
        description=(
            "True if this pivot has been validated by a >= threshold reversal in the "
            "opposite direction. False for the right-edge tentative pivot whose swing "
            "is still in progress."
        ),
    )


class ChannelLine(BaseModel):
    """y = slope * idx + intercept, with idx anchored to the start of the analysed window."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    slope: float = Field(description="Price units per bar.")
    intercept: float = Field(description="Price at the window-relative origin (idx=0).")


class ChannelLines(BaseModel):
    """Parallel channel fitted through the recent pivot sequence."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    upper: ChannelLine
    lower: ChannelLine
    slope_angle_deg: float
    fit_pivot_indices: list[int] = Field(
        description="Indices of the pivots used to fit the channel."
    )


class FibLevel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    ratio: float
    price: float


class FibZones(BaseModel):
    """Fibonacci levels for the most recent completed impulse and correction."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    last_impulse_retracements: list[FibLevel] = Field(default_factory=list)
    last_impulse_extensions: list[FibLevel] = Field(default_factory=list)
    last_correction_retracements: list[FibLevel] = Field(default_factory=list)


class StructureSummary(BaseModel):
    """Deterministic structural snapshot of one timeframe.

    This is the *only* representation an LLM agent sees. Raw OHLCV never leaves
    the preprocessing layer.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    instrument: str
    timeframe: Timeframe
    date_range: tuple[datetime, datetime]
    bar_count: int

    pivots: list[Pivot] = Field(description="All confirmed pivots in the series.")
    recent_pivots: list[Pivot] = Field(
        description=(
            "The last 13 pivots (covers a 5-3-5 + buffer for Elliott). The LLM "
            "operates on these; older pivots are kept only for chart rendering."
        ),
    )

    current_price: float
    price_position_pct: float = Field(
        ge=0.0,
        le=1.0,
        description="Percentile of current price within the recent_pivots range.",
    )

    channel_lines: ChannelLines
    atr_14: float
    realized_vol_20_pct: float

    structural_phase_hints: list[str] = Field(
        description=(
            "Deterministic geometric hints (e.g. 'in retracement of last impulse'). "
            "These are NOT wave counts — they are observations about geometry."
        ),
    )
    fibonacci_zones: FibZones

    # ----- LLM input rendering -------------------------------------------------

    def to_llm_text(self) -> str:
        """Render the compact text representation passed to LLM agents.

        The format is whitespace-significant and intentionally terse. The token
        budget is ~80–150 Claude tokens; verify with `app.preprocessing.tokens`.
        """
        d_from = self.date_range[0].strftime("%Y-%m")
        d_to = self.date_range[1].strftime("%Y-%m")

        # Compact pivot token: "#<idx>:<U|D><swing%>/<bars><label>[r<retrace_pct>]".
        # The bar index is the canonical handle agents reference in WaveSegment.
        def pivot_token(p: Pivot) -> str:
            sign = "U" if p.type == "H" else "D"  # direction TO this pivot
            mag = f"{abs(p.swing_pct):.1f}"
            label = p.label if p.label != "?" else ""
            fib = f"r{int(round(p.fib_retrace_of_prior * 100))}" if p.fib_retrace_of_prior else ""
            tentative = "*" if not p.confirmed else ""
            return f"#{p.idx}:{sign}{mag}/{p.swing_bars}{label}{fib}{tentative}"

        piv_str = " ".join(pivot_token(p) for p in self.recent_pivots)

        chan = self.channel_lines
        # Width of the channel at the most recent index, in % of price
        recent_idx = self.recent_pivots[-1].idx if self.recent_pivots else self.bar_count - 1
        upper_at = chan.upper.slope * recent_idx + chan.upper.intercept
        lower_at = chan.lower.slope * recent_idx + chan.lower.intercept
        chan_width_pct = (
            (upper_at - lower_at) / self.current_price * 100 if self.current_price > 0 else 0.0
        )

        hints = ";".join(self.structural_phase_hints) or "none"

        # Fibonacci block: only 4 retracements + 2 extensions (compactness).
        def fib_inline(levels: list[FibLevel], prefix: str) -> str:
            if not levels:
                return ""
            return " ".join(f"{prefix}{int(round(l.ratio * 100))}={l.price:.0f}" for l in levels)

        retr = fib_inline(self.fibonacci_zones.last_impulse_retracements[:4], "r")
        ext = fib_inline(self.fibonacci_zones.last_impulse_extensions[:2], "e")
        fib_line = " ".join(s for s in (retr, ext) if s)

        return (
            f"{self.instrument} {self.timeframe} {d_from}..{d_to} ({self.bar_count}b)\n"
            f"piv({len(self.recent_pivots)}): {piv_str}\n"
            f"last={self.current_price:.0f} pos={self.price_position_pct:.2f} "
            f"chan_ang={chan.slope_angle_deg:+.0f}deg width={chan_width_pct:.1f}% "
            f"atr14={self.atr_14:.0f} rv20={self.realized_vol_20_pct:.1f}%\n"
            f"phase: {hints}\n"
            f"fib(impulse): {fib_line}"
        )

    @property
    def approx_token_count(self) -> int:
        """Rough Claude token count for the LLM-input text. Char/4 heuristic."""
        return math.ceil(len(self.to_llm_text()) / 4)
