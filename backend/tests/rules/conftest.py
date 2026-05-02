"""Helpers for building synthetic Pivot lists + counts in rule tests."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.schemas.structure import Pivot
from app.schemas.waves import ElliottCount, NeowaveCount, WaveSegment


_BASE_DT = datetime(2024, 1, 1)


def make_pivot(idx: int, price: float, ptype: str = "H") -> Pivot:
    return Pivot(
        idx=idx,
        datetime=_BASE_DT + timedelta(days=idx),
        price=price,
        type=ptype,  # type: ignore[arg-type]
        label="?",
        swing_pct=0.0,
        swing_bars=0,
        fib_retrace_of_prior=None,
        confirmed=True,
    )


def impulse_up_pivots() -> list[Pivot]:
    """A textbook 5-wave impulse going up.

    Wave 1: 100 → 120 (+20)
    Wave 2: 120 → 110 (-10, ~50% retrace of W1)
    Wave 3: 110 → 150 (+40, longest)
    Wave 4: 150 → 140 (-10, ~25% retrace of W3, doesn't enter W1 territory at 120)
    Wave 5: 140 → 160 (+20)
    """
    return [
        make_pivot(0, 100.0, "L"),
        make_pivot(20, 120.0, "H"),
        make_pivot(35, 110.0, "L"),
        make_pivot(80, 150.0, "H"),
        make_pivot(95, 140.0, "L"),
        make_pivot(130, 160.0, "H"),
    ]


def impulse_up_count() -> ElliottCount:
    """Matching wave count for `impulse_up_pivots()`."""
    return ElliottCount(
        pattern="impulse",
        degree="Minor",
        waves=[
            WaveSegment(label="1", start_pivot_idx=0, end_pivot_idx=20),
            WaveSegment(label="2", start_pivot_idx=20, end_pivot_idx=35),
            WaveSegment(label="3", start_pivot_idx=35, end_pivot_idx=80),
            WaveSegment(label="4", start_pivot_idx=80, end_pivot_idx=95),
            WaveSegment(label="5", start_pivot_idx=95, end_pivot_idx=130),
        ],
        current_wave="5",
        rationale="Synthetic impulse — wave 3 longest, wave 4 holds above wave 1 top.",
    )
