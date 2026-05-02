"""Parallel channel fitting through pivot sequences.

Approach: regression of (idx, price) over the most recent N pivots gives a
trendline. The "upper" and "lower" channel lines are parallel translations of
that trendline that touch the highest and lowest pivots, respectively.

This is intentionally simple — Elliott channeling has many flavours
(0–2/1–3/2–4 lines, Schiff median lines, etc.). Those are computed as needed
in the Validator stage. The structural summary just needs a one-shot picture
of the recent trend's slope and corridor.
"""

from __future__ import annotations

import math

import numpy as np

from app.preprocessing.pivots import RawPivot
from app.schemas.structure import ChannelLine, ChannelLines


def fit_channel(pivots: list[RawPivot], lookback: int = 7) -> ChannelLines | None:
    """Fit a parallel channel through the last `lookback` pivots.

    Returns `None` if there are fewer than 3 pivots — channel fitting needs at
    least 3 points to be meaningful.
    """
    confirmed = [p for p in pivots if p.confirmed]
    if len(confirmed) < 3:
        return None
    series = confirmed[-lookback:]
    xs = np.array([p.idx for p in series], dtype=float)
    ys = np.array([p.price for p in series], dtype=float)

    # OLS regression line through pivots: y = slope * x + intercept.
    slope, intercept = np.polyfit(xs, ys, 1)

    # Translate parallel lines to touch the highest and lowest pivots.
    residuals = ys - (slope * xs + intercept)
    upper_offset = float(residuals.max())
    lower_offset = float(residuals.min())

    upper = ChannelLine(slope=float(slope), intercept=float(intercept) + upper_offset)
    lower = ChannelLine(slope=float(slope), intercept=float(intercept) + lower_offset)

    # Slope angle in degrees. Use the *typical* pivot price as the y-scale so
    # the angle is dimensionally meaningful.
    typical_price = float(ys.mean())
    typical_bars = float(xs.max() - xs.min()) or 1.0
    # Normalize: percent-rise per bar across the visible window.
    pct_per_bar = (slope * typical_bars / typical_price) if typical_price > 0 else 0.0
    angle_deg = math.degrees(math.atan(pct_per_bar))

    return ChannelLines(
        upper=upper,
        lower=lower,
        slope_angle_deg=round(angle_deg, 2),
        fit_pivot_indices=[p.idx for p in series],
    )
