"""Tests for the NEOWave rule validators."""

from __future__ import annotations

from app.rules.neowave_rules import evaluate_count
from app.schemas.waves import NeowaveCount, WaveSegment

from tests.rules.conftest import make_pivot


def _result(compliance, rule_id: str):
    matching = [r for r in compliance.rule_results if r.rule_id == rule_id]
    assert matching, f"Expected a result for {rule_id}; got {[r.rule_id for r in compliance.rule_results]}"
    return matching[0]


def test_nw_h_1_passes_balanced_corrective() -> None:
    """Five mono-waves of similar size should pass the Similarity & Balance rule."""
    # Triangle with a..e at 10, 8, 6, 7, 5 — spread max/min = 10/5 = 2.0× < 3.0× tolerance
    pivots = [
        make_pivot(0, 100.0, "H"),
        make_pivot(10, 90.0, "L"),
        make_pivot(20, 98.0, "H"),
        make_pivot(30, 92.0, "L"),
        make_pivot(40, 99.0, "H"),
        make_pivot(50, 94.0, "L"),
    ]
    count = NeowaveCount(
        pattern="triangle_contracting",
        mono_waves=[
            WaveSegment(label="a", start_pivot_idx=0, end_pivot_idx=10),
            WaveSegment(label="b", start_pivot_idx=10, end_pivot_idx=20),
            WaveSegment(label="c", start_pivot_idx=20, end_pivot_idx=30),
            WaveSegment(label="d", start_pivot_idx=30, end_pivot_idx=40),
            WaveSegment(label="e", start_pivot_idx=40, end_pivot_idx=50),
        ],
        current_position="in e",
        rationale="Balanced triangle.",
    )
    res = _result(evaluate_count(count, pivots), "NW-H-1")
    assert res.passed


def test_nw_h_1_rejects_unbalanced_corrective() -> None:
    """One mono-wave 10× the others should fail Similarity & Balance."""
    pivots = [
        make_pivot(0, 100.0, "H"),
        make_pivot(10, 99.0, "L"),
        make_pivot(20, 100.5, "H"),
        make_pivot(30, 60.0, "L"),  # massive 40-point leg vs other ~1-point legs
        make_pivot(40, 99.5, "H"),
        make_pivot(50, 99.0, "L"),
    ]
    count = NeowaveCount(
        pattern="triangle_contracting",
        mono_waves=[
            WaveSegment(label="a", start_pivot_idx=0, end_pivot_idx=10),
            WaveSegment(label="b", start_pivot_idx=10, end_pivot_idx=20),
            WaveSegment(label="c", start_pivot_idx=20, end_pivot_idx=30),
            WaveSegment(label="d", start_pivot_idx=30, end_pivot_idx=40),
            WaveSegment(label="e", start_pivot_idx=40, end_pivot_idx=50),
        ],
        current_position="in e",
        rationale="Unbalanced triangle.",
    )
    res = _result(evaluate_count(count, pivots), "NW-H-1")
    assert not res.passed
    assert "Similarity" in res.name


def test_nw_h_2_rejects_monotony() -> None:
    """Three motive waves of equal size violate monotony."""
    pivots = [
        make_pivot(0, 100.0, "L"),
        make_pivot(10, 110.0, "H"),  # m1 = 10
        make_pivot(20, 105.0, "L"),
        make_pivot(30, 115.0, "H"),  # m3 = 10
        make_pivot(40, 110.0, "L"),
        make_pivot(50, 120.0, "H"),  # m5 = 10
    ]
    count = NeowaveCount(
        pattern="impulse",
        mono_waves=[
            WaveSegment(label="m1", start_pivot_idx=0, end_pivot_idx=10),
            WaveSegment(label="m2", start_pivot_idx=10, end_pivot_idx=20),
            WaveSegment(label="m3", start_pivot_idx=20, end_pivot_idx=30),
            WaveSegment(label="m4", start_pivot_idx=30, end_pivot_idx=40),
            WaveSegment(label="m5", start_pivot_idx=40, end_pivot_idx=50),
        ],
        current_position="in m5",
        rationale="All three motive waves identical.",
    )
    res = _result(evaluate_count(count, pivots), "NW-H-2")
    assert not res.passed
    assert "monotony" in res.message.lower()


def test_nw_h_2_passes_extended_third() -> None:
    pivots = [
        make_pivot(0, 100.0, "L"),
        make_pivot(10, 110.0, "H"),  # m1 = 10
        make_pivot(20, 105.0, "L"),
        make_pivot(30, 130.0, "H"),  # m3 = 25 (extended)
        make_pivot(40, 125.0, "L"),
        make_pivot(50, 135.0, "H"),  # m5 = 10
    ]
    count = NeowaveCount(
        pattern="impulse",
        mono_waves=[
            WaveSegment(label="m1", start_pivot_idx=0, end_pivot_idx=10),
            WaveSegment(label="m2", start_pivot_idx=10, end_pivot_idx=20),
            WaveSegment(label="m3", start_pivot_idx=20, end_pivot_idx=30),
            WaveSegment(label="m4", start_pivot_idx=30, end_pivot_idx=40),
            WaveSegment(label="m5", start_pivot_idx=40, end_pivot_idx=50),
        ],
        current_position="in m5",
        rationale="Wave 3 extended.",
    )
    res = _result(evaluate_count(count, pivots), "NW-H-2")
    assert res.passed


def test_nw_h_4_passes_correction_in_time_band() -> None:
    """Correction time = 1.2× impulse time — within the 1.0–1.618 band."""
    # Impulse: 0 → 30 (30 bars). Correction: 30 → 66 (36 bars). Ratio = 36/30 = 1.2 ✓
    pivots = [
        make_pivot(0, 100.0, "L"),
        make_pivot(30, 130.0, "H"),
        make_pivot(50, 115.0, "L"),
        make_pivot(66, 125.0, "H"),
    ]
    count = NeowaveCount(
        pattern="zigzag",
        mono_waves=[
            WaveSegment(label="impulse", start_pivot_idx=0, end_pivot_idx=30),
            WaveSegment(label="A", start_pivot_idx=30, end_pivot_idx=50),
            WaveSegment(label="B", start_pivot_idx=50, end_pivot_idx=66),
        ],
        current_position="end of zigzag",
        rationale="Time ratio in band.",
    )
    res = _result(evaluate_count(count, pivots), "NW-H-4")
    assert res.passed


def test_nw_h_4_rejects_correction_too_short() -> None:
    """Correction time = 0.5× impulse time — below 1.0× floor."""
    pivots = [
        make_pivot(0, 100.0, "L"),
        make_pivot(40, 130.0, "H"),  # impulse = 40 bars
        make_pivot(50, 115.0, "L"),
        make_pivot(60, 125.0, "H"),  # correction = 20 bars (0.5×)
    ]
    count = NeowaveCount(
        pattern="zigzag",
        mono_waves=[
            WaveSegment(label="impulse", start_pivot_idx=0, end_pivot_idx=40),
            WaveSegment(label="A", start_pivot_idx=40, end_pivot_idx=50),
            WaveSegment(label="B", start_pivot_idx=50, end_pivot_idx=60),
        ],
        current_position="end of zigzag",
        rationale="Correction is too brief vs impulse.",
    )
    res = _result(evaluate_count(count, pivots), "NW-H-4")
    assert not res.passed
