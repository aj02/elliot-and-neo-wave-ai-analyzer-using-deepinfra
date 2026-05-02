"""ZigZag pivot detection (custom implementation, no TA-Lib).

A pivot is a confirmed local extremum that is at least `threshold_pct` away
from the prior pivot. Direction switches when the opposite-extreme of a bar
exceeds the candidate by `threshold_pct`. The final tentative candidate is
emitted as an "unconfirmed" pivot at the right edge so downstream code can
reason about the in-progress swing.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class RawPivot:
    """A pivot in array-index land, before datetime/label enrichment."""

    idx: int
    price: float
    type: str  # "H" or "L"
    confirmed: bool


def find_pivots(
    highs: np.ndarray,
    lows: np.ndarray,
    threshold_pct: float = 3.0,
) -> list[RawPivot]:
    """Identify ZigZag pivots.

    Args:
        highs: high prices, length n.
        lows: low prices, length n.
        threshold_pct: minimum % swing between consecutive pivots, e.g. 3.0.

    Returns:
        Pivots in chronological order. The last pivot is marked
        `confirmed=False` if the most recent swing has not yet reached the
        threshold (in-progress).
    """
    n = len(highs)
    if n != len(lows):
        raise ValueError("highs and lows must be the same length")
    if n == 0:
        return []
    if threshold_pct <= 0.0:
        raise ValueError("threshold_pct must be positive")

    th = threshold_pct / 100.0
    pivots: list[RawPivot] = []

    direction = 0  # 0 = unknown, +1 = looking for high, -1 = looking for low
    cand_idx = 0
    cand_price = highs[0]  # placeholder; set on first state transition

    for i in range(n):
        h = float(highs[i])
        l = float(lows[i])
        if direction == 0:
            up_pct = (h - lows[0]) / lows[0]
            down_pct = (l - highs[0]) / highs[0]
            if up_pct >= th:
                # Initial pivot is the low at bar 0; we now track the high.
                pivots.append(RawPivot(idx=0, price=float(lows[0]), type="L", confirmed=True))
                direction = 1
                cand_idx, cand_price = i, h
            elif down_pct <= -th:
                pivots.append(RawPivot(idx=0, price=float(highs[0]), type="H", confirmed=True))
                direction = -1
                cand_idx, cand_price = i, l
        elif direction == 1:
            if h > cand_price:
                cand_idx, cand_price = i, h
            elif (l - cand_price) / cand_price <= -th:
                pivots.append(
                    RawPivot(idx=cand_idx, price=cand_price, type="H", confirmed=True)
                )
                direction = -1
                cand_idx, cand_price = i, l
        else:  # direction == -1
            if l < cand_price:
                cand_idx, cand_price = i, l
            elif (h - cand_price) / cand_price >= th:
                pivots.append(
                    RawPivot(idx=cand_idx, price=cand_price, type="L", confirmed=True)
                )
                direction = 1
                cand_idx, cand_price = i, h

    if direction != 0:
        # Tentative right-edge pivot — useful for "in progress" hints.
        last_type = "H" if direction == 1 else "L"
        pivots.append(RawPivot(idx=cand_idx, price=cand_price, type=last_type, confirmed=False))

    return pivots


def auto_threshold_pct(closes: np.ndarray, target_pivot_count: int = 30) -> float:
    """Choose a ZigZag threshold that yields roughly `target_pivot_count` pivots.

    Binary search over [0.5%, 25%]. Useful when the same code processes
    instruments of very different volatility.
    """
    if len(closes) < 5:
        return 3.0
    highs = closes.copy()
    lows = closes.copy()
    lo, hi = 0.5, 25.0
    for _ in range(20):
        mid = (lo + hi) / 2
        n_piv = len(find_pivots(highs, lows, threshold_pct=mid))
        if n_piv > target_pivot_count:
            lo = mid
        elif n_piv < target_pivot_count:
            hi = mid
        else:
            return round(mid, 2)
    return round((lo + hi) / 2, 2)
