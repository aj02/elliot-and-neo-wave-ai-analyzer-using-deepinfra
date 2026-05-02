"""Swing labelling: HH / HL / LH / LL on a sequence of pivots.

Given a list of `RawPivot`s, produce `Pivot`s with:
  * `label` ∈ {HH, HL, LH, LL, ?}
  * `swing_pct` — signed % move from the *previous* pivot
  * `swing_bars` — bars elapsed since the previous pivot
  * `fib_retrace_of_prior` — for each retracement leg, the fraction of the
    prior leg it has retraced (None for the first two pivots)
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from app.preprocessing.pivots import RawPivot
from app.schemas.structure import Pivot


def label_pivots(raw: list[RawPivot], times: pd.Series) -> list[Pivot]:
    """Promote `RawPivot`s to fully labelled `Pivot`s.

    `times` must be the canonical datetime column from the cleaned DataFrame.
    """
    out: list[Pivot] = []
    if not raw:
        return out

    # Track the previous H and previous L for HH/HL/LH/LL labelling.
    prev_high_price: float | None = None
    prev_low_price: float | None = None

    for i, p in enumerate(raw):
        prior = raw[i - 1] if i > 0 else None

        if prior is not None:
            swing_pct = (p.price - prior.price) / prior.price * 100.0
            swing_bars = p.idx - prior.idx
        else:
            swing_pct = 0.0
            swing_bars = 0

        # Fibonacci retracement of the prior leg (i.e. leg from raw[i-2] -> raw[i-1]).
        fib_retrace: float | None = None
        if i >= 2:
            leg_start = raw[i - 2].price
            leg_end = raw[i - 1].price
            leg_amplitude = abs(leg_end - leg_start)
            if leg_amplitude > 0:
                retrace_amplitude = abs(p.price - leg_end)
                fib_retrace = round(retrace_amplitude / leg_amplitude, 4)

        # Label vs prior same-type pivot.
        if p.type == "H":
            if prev_high_price is None:
                label = "?"
            else:
                label = "HH" if p.price > prev_high_price else "LH"
            prev_high_price = p.price
        else:  # "L"
            if prev_low_price is None:
                label = "?"
            else:
                label = "HL" if p.price > prev_low_price else "LL"
            prev_low_price = p.price

        out.append(
            Pivot(
                idx=p.idx,
                datetime=_as_datetime(times.iloc[p.idx]),
                price=p.price,
                type=p.type,
                label=label,
                swing_pct=round(swing_pct, 3),
                swing_bars=swing_bars,
                fib_retrace_of_prior=fib_retrace,
                confirmed=p.confirmed,
            )
        )
    return out


def _as_datetime(value: object) -> datetime:
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, datetime):
        return value
    return pd.to_datetime(value).to_pydatetime()
