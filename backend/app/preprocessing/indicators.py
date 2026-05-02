"""Volatility indicators used in the StructureSummary.

Kept here rather than in `validators.py` because they're descriptive, not
gating. ATR(14) and 20-bar realised volatility are enough — anything more
exotic would drift toward indicator bloat.
"""

from __future__ import annotations

import numpy as np


def atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
    """Wilder's ATR, returning the last value.

    Uses a simple moving average of true range over `period` for the seed,
    then a Wilder smoothing thereafter.
    """
    n = len(highs)
    if n < period + 1:
        # Fall back to plain mean true range over the available bars.
        return float(np.mean(np.maximum(highs - lows, 0))) if n > 0 else 0.0

    tr = np.maximum(
        highs[1:] - lows[1:],
        np.maximum(
            np.abs(highs[1:] - closes[:-1]),
            np.abs(lows[1:] - closes[:-1]),
        ),
    )
    atr_val = float(np.mean(tr[:period]))
    for v in tr[period:]:
        atr_val = (atr_val * (period - 1) + float(v)) / period
    return round(atr_val, 4)


def realized_volatility_pct(closes: np.ndarray, lookback: int = 20) -> float:
    """20-bar realised volatility — std of log-returns × 100, expressed as %."""
    if len(closes) < 2:
        return 0.0
    series = closes[-(lookback + 1):]
    log_rets = np.diff(np.log(series))
    if len(log_rets) == 0:
        return 0.0
    return round(float(np.std(log_rets, ddof=1) * 100), 4)
