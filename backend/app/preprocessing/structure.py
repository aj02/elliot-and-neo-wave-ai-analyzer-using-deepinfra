"""StructureSummary builder.

Composes the deterministic preprocessing primitives into one `StructureSummary`
ready for the LLM agents (and for the chart renderer).
"""

from __future__ import annotations

import pandas as pd

from app.preprocessing.channels import fit_channel
from app.preprocessing.fibonacci import (
    extension_levels,
    retracement_levels,
)
from app.preprocessing.indicators import atr, realized_volatility_pct
from app.preprocessing.pivots import auto_threshold_pct, find_pivots
from app.preprocessing.swings import label_pivots
from app.schemas.structure import (
    ChannelLine,
    ChannelLines,
    FibZones,
    Pivot,
    StructureSummary,
)
from app.schemas.timeframe import Timeframe


# Constants
RECENT_PIVOTS_WINDOW = 13
NEAR_CHANNEL_PCT = 1.5  # within ±1.5% counts as "near"


def build(
    df: pd.DataFrame,
    *,
    instrument: str,
    timeframe: Timeframe,
    threshold_pct: float | None = None,
) -> StructureSummary:
    """Build a `StructureSummary` from a cleaned OHLCV DataFrame.

    Args:
        df: cleaned canonical DataFrame (datetime, open, high, low, close, volume).
        instrument: human-readable instrument label, e.g. "NIFTY 50".
        timeframe: enum tag.
        threshold_pct: ZigZag threshold; if `None`, auto-tuned to ~30 pivots.
    """
    if df.empty:
        raise ValueError("Cannot build StructureSummary from an empty DataFrame.")

    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)

    chosen_threshold = threshold_pct if threshold_pct is not None else auto_threshold_pct(closes)

    raw_pivots = find_pivots(highs, lows, threshold_pct=chosen_threshold)
    pivots = label_pivots(raw_pivots, df["datetime"])

    if not pivots:
        raise ValueError(
            "No pivots found — series may be too short or volatility too low for the "
            f"chosen threshold ({chosen_threshold}%)."
        )

    recent = pivots[-RECENT_PIVOTS_WINDOW:]
    current_price = float(closes[-1])

    # Price position within the recent_pivots envelope.
    recent_high = max(p.price for p in recent)
    recent_low = min(p.price for p in recent)
    if recent_high == recent_low:
        price_position_pct = 0.5
    else:
        price_position_pct = round(
            (current_price - recent_low) / (recent_high - recent_low), 4
        )
    price_position_pct = max(0.0, min(1.0, price_position_pct))

    channel = fit_channel(raw_pivots, lookback=7) or _fallback_channel(df, current_price)

    fib_zones = _compute_fib_zones(pivots)
    hints = _structural_hints(pivots, channel, current_price)

    atr14 = atr(highs, lows, closes, period=14)
    rv20 = realized_volatility_pct(closes, lookback=20)

    return StructureSummary(
        instrument=instrument,
        timeframe=timeframe,
        date_range=(df["datetime"].iloc[0].to_pydatetime(), df["datetime"].iloc[-1].to_pydatetime()),
        bar_count=len(df),
        pivots=pivots,
        recent_pivots=recent,
        current_price=current_price,
        price_position_pct=price_position_pct,
        channel_lines=channel,
        atr_14=atr14,
        realized_vol_20_pct=rv20,
        structural_phase_hints=hints,
        fibonacci_zones=fib_zones,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fallback_channel(df: pd.DataFrame, current_price: float) -> ChannelLines:
    """If we can't fit a real channel (too few pivots), produce a flat one.

    Width = ATR-derived. The intercept is the current price; slope is zero.
    """
    flat = ChannelLine(slope=0.0, intercept=current_price)
    return ChannelLines(
        upper=flat,
        lower=flat,
        slope_angle_deg=0.0,
        fit_pivot_indices=[],
    )


def _compute_fib_zones(pivots: list[Pivot]) -> FibZones:
    """Identify the most recent confirmed impulse and correction legs and compute
    Fibonacci retracements / extensions for them.

    Heuristic for impulse vs correction: of the last two confirmed legs, the
    one with the larger absolute swing is the impulse and the smaller is the
    correction. If only one confirmed leg is available, use it as the impulse.
    """
    confirmed = [p for p in pivots if p.confirmed]
    if len(confirmed) < 2:
        return FibZones()

    legs: list[tuple[Pivot, Pivot, float]] = []
    for i in range(1, len(confirmed)):
        start, end = confirmed[i - 1], confirmed[i]
        legs.append((start, end, abs(end.swing_pct)))
    if not legs:
        return FibZones()

    last_two = legs[-2:]
    if len(last_two) == 2:
        impulse_leg, correction_leg = sorted(last_two, key=lambda x: -x[2])
    else:
        impulse_leg, correction_leg = last_two[0], None

    impulse_retr = retracement_levels(impulse_leg[0].price, impulse_leg[1].price)
    impulse_ext = extension_levels(impulse_leg[0].price, impulse_leg[1].price)

    if correction_leg is not None:
        corr_retr = retracement_levels(correction_leg[0].price, correction_leg[1].price)
    else:
        corr_retr = []

    return FibZones(
        last_impulse_retracements=impulse_retr,
        last_impulse_extensions=impulse_ext,
        last_correction_retracements=corr_retr,
    )


def _structural_hints(
    pivots: list[Pivot], channel: ChannelLines, current_price: float
) -> list[str]:
    """Produce deterministic geometric observations.

    These are NOT wave counts. They are observations the LLM can reference but
    that the LLM did not generate.
    """
    hints: list[str] = []
    confirmed = [p for p in pivots if p.confirmed]
    if len(confirmed) >= 4:
        last4 = confirmed[-4:]
        labels = [p.label for p in last4]
        if labels.count("HH") + labels.count("HL") >= 3:
            hints.append("uptrend(HH/HL)")
        elif labels.count("LH") + labels.count("LL") >= 3:
            hints.append("downtrend(LH/LL)")
        else:
            hints.append("range")

    if pivots and not pivots[-1].confirmed:
        ongoing = pivots[-1]
        hints.append(f"in-progress {ongoing.type}-swing pct={ongoing.swing_pct:+.1f}")
    elif len(confirmed) >= 2:
        last_leg_dir = "up" if confirmed[-1].price > confirmed[-2].price else "down"
        hints.append(f"last-completed-leg={last_leg_dir}")

    # Channel position
    if channel.fit_pivot_indices:
        last_idx = max(p.idx for p in pivots) if pivots else 0
        upper_at = channel.upper.slope * last_idx + channel.upper.intercept
        lower_at = channel.lower.slope * last_idx + channel.lower.intercept
        if current_price > upper_at:
            hints.append("price>upper-channel")
        elif current_price < lower_at:
            hints.append("price<lower-channel")
        elif upper_at > 0 and (upper_at - current_price) / current_price * 100 < NEAR_CHANNEL_PCT:
            hints.append("near-upper-channel")
        elif lower_at > 0 and (current_price - lower_at) / current_price * 100 < NEAR_CHANNEL_PCT:
            hints.append("near-lower-channel")
        else:
            hints.append("inside-channel")

    # Wave-3-extended candidate: largest confirmed swing (last 7) >= 1.618× the median.
    recent_swings = [abs(p.swing_pct) for p in confirmed[-7:] if p.swing_pct]
    if len(recent_swings) >= 4:
        sorted_sw = sorted(recent_swings)
        median_sw = sorted_sw[len(sorted_sw) // 2]
        if median_sw > 0 and max(recent_swings) >= 1.618 * median_sw:
            hints.append("extended-leg-present")

    return hints
