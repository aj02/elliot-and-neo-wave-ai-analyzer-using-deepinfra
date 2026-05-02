"""Supported timeframe labels.

Timeframes are user-tagged on upload, never auto-detected — auto-detection is
brittle around weekends and holidays.
"""

from __future__ import annotations

from enum import StrEnum


class Timeframe(StrEnum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1D"
    W1 = "1W"
    MO1 = "1M"

    @property
    def expected_bars_per_year(self) -> int:
        """Approximate bar count per calendar year — used only for gap heuristics."""
        return {
            Timeframe.M1: 252 * 6 * 60,
            Timeframe.M5: 252 * 6 * 12,
            Timeframe.M15: 252 * 6 * 4,
            Timeframe.H1: 252 * 6,
            Timeframe.H4: 252 * 2,
            Timeframe.D1: 252,
            Timeframe.W1: 52,
            Timeframe.MO1: 12,
        }[self]
