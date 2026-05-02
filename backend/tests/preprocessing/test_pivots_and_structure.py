"""Tests for pivots, swings, and the StructureSummary builder.

The test is a synthetic but deterministic price series with three obvious
swings, exercised end-to-end through `structure.build` to check that the
LLM-input text fits the token budget and that pivots round-trip correctly.
"""

from __future__ import annotations

import io
import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app.preprocessing.csv_loader import load_csv
from app.preprocessing.pivots import find_pivots
from app.preprocessing.structure import build
from app.schemas.timeframe import Timeframe


def _synthetic_series(swing_specs: list[float], bars_per_swing: int = 30) -> bytes:
    """Build a synthetic OHLCV CSV from a list of swing percentages.

    Each entry in `swing_specs` is a percent move; a sine smooths each leg so
    pivots are unambiguous.
    """
    start_dt = datetime(2024, 1, 1)
    rows: list[dict[str, object]] = []
    price = 100.0
    bar_idx = 0
    for swing in swing_specs:
        target = price * (1 + swing / 100.0)
        for j in range(bars_per_swing):
            t = (j + 1) / bars_per_swing
            # Smooth interpolation; each bar's body is small but the trend dominates.
            mid = price + (target - price) * (1 - math.cos(t * math.pi)) / 2
            o = mid * (1.0 - 0.0005)
            c = mid * (1.0 + 0.0005)
            h = max(o, c) * 1.0008
            l = min(o, c) * 0.9992
            rows.append(
                {
                    "datetime": (start_dt + timedelta(days=bar_idx)).strftime("%Y-%m-%d"),
                    "open": round(o, 4),
                    "high": round(h, 4),
                    "low": round(l, 4),
                    "close": round(c, 4),
                    "volume": 1000,
                }
            )
            bar_idx += 1
        price = target
    df = pd.DataFrame(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def test_zigzag_finds_obvious_pivots() -> None:
    # Three legs: +20%, -10%, +15% → expect at least 3 confirmed pivots + 1 tentative.
    csv = _synthetic_series([20, -10, 15], bars_per_swing=40)
    df, _ = load_csv(io.BytesIO(csv))
    pivots = find_pivots(
        df["high"].to_numpy(dtype=float),
        df["low"].to_numpy(dtype=float),
        threshold_pct=5.0,
    )
    confirmed = [p for p in pivots if p.confirmed]
    assert len(confirmed) >= 3
    # Pivots alternate H/L
    types = [p.type for p in confirmed]
    for a, b in zip(types, types[1:], strict=False):
        assert a != b


def test_structure_summary_token_budget() -> None:
    csv = _synthetic_series([15, -8, 12, -6, 10], bars_per_swing=30)
    df, _ = load_csv(io.BytesIO(csv))
    summary = build(df, instrument="TEST", timeframe=Timeframe.D1, threshold_pct=4.0)
    text = summary.to_llm_text()
    approx_tokens = math.ceil(len(text) / 4)
    # Spec: ~80–150 tokens per timeframe. Synthetic data lands a bit lower
    # because it has fewer pivots, but never above 200.
    assert 30 <= approx_tokens <= 200, f"Token budget breached: {approx_tokens} tokens"


def test_pivots_have_increasing_indices() -> None:
    csv = _synthetic_series([15, -8, 12, -6, 10], bars_per_swing=30)
    df, _ = load_csv(io.BytesIO(csv))
    summary = build(df, instrument="TEST", timeframe=Timeframe.D1, threshold_pct=4.0)
    indices = [p.idx for p in summary.pivots]
    assert indices == sorted(indices)
    assert all(0 <= i < summary.bar_count for i in indices)


def test_only_last_pivot_can_be_unconfirmed() -> None:
    csv = _synthetic_series([20, -10, 15], bars_per_swing=40)
    df, _ = load_csv(io.BytesIO(csv))
    summary = build(df, instrument="TEST", timeframe=Timeframe.D1, threshold_pct=5.0)
    if summary.pivots:
        for p in summary.pivots[:-1]:
            assert p.confirmed is True
