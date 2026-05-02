"""Tests for the Elliott rule validators.

Each test exercises one rule on a count that is intentionally either compliant
or non-compliant. The test asserts the rule's specific result by `rule_id`.
"""

from __future__ import annotations

from app.rules.elliott_rules import evaluate_count
from app.schemas.waves import ElliottCount, WaveSegment

from tests.rules.conftest import impulse_up_count, impulse_up_pivots, make_pivot


def _result(compliance, rule_id: str):
    matching = [r for r in compliance.rule_results if r.rule_id == rule_id]
    assert matching, f"Expected a result for {rule_id}; got {[r.rule_id for r in compliance.rule_results]}"
    return matching[0]


def test_clean_impulse_passes_all_hard_rules() -> None:
    compliance = evaluate_count(impulse_up_count(), impulse_up_pivots())
    assert compliance.is_valid, [r.message for r in compliance.hard_failures]
    # Soft heuristics may or may not all pass on synthetic numbers — but score is computable.
    assert 0.0 <= compliance.score <= 1.0


def test_ew_h_1_rejects_wave_2_beyond_wave_1_start() -> None:
    pivots = [
        make_pivot(0, 100.0, "L"),
        make_pivot(10, 120.0, "H"),
        make_pivot(20, 95.0, "L"),  # below wave 1 start (100) — invalid
    ]
    count = ElliottCount(
        pattern="impulse",
        degree="Minor",
        waves=[
            WaveSegment(label="1", start_pivot_idx=0, end_pivot_idx=10),
            WaveSegment(label="2", start_pivot_idx=10, end_pivot_idx=20),
        ],
        current_wave="2",
        rationale="Wave 2 retraces past wave 1 start — should be rejected.",
    )
    res = _result(evaluate_count(count, pivots), "EW-H-1")
    assert not res.passed
    assert "100% retracement" in res.message


def test_ew_h_2_rejects_wave_3_being_shortest() -> None:
    pivots = [
        make_pivot(0, 100.0, "L"),
        make_pivot(10, 130.0, "H"),  # wave 1: +30
        make_pivot(20, 120.0, "L"),
        make_pivot(30, 125.0, "H"),  # wave 3: +5  ← shortest
        make_pivot(40, 122.0, "L"),
        make_pivot(50, 145.0, "H"),  # wave 5: +23 (longer than 3)
    ]
    count = ElliottCount(
        pattern="impulse",
        degree="Minor",
        waves=[
            WaveSegment(label="1", start_pivot_idx=0, end_pivot_idx=10),
            WaveSegment(label="2", start_pivot_idx=10, end_pivot_idx=20),
            WaveSegment(label="3", start_pivot_idx=20, end_pivot_idx=30),
            WaveSegment(label="4", start_pivot_idx=30, end_pivot_idx=40),
            WaveSegment(label="5", start_pivot_idx=40, end_pivot_idx=50),
        ],
        current_wave="5",
        rationale="Wave 3 is the shortest of (1, 3, 5) — should be rejected.",
    )
    res = _result(evaluate_count(count, pivots), "EW-H-2")
    assert not res.passed
    assert "shortest" in res.message.lower()


def test_ew_h_3_rejects_wave_4_overlap_with_wave_1() -> None:
    pivots = [
        make_pivot(0, 100.0, "L"),
        make_pivot(10, 120.0, "H"),  # wave 1 top = 120
        make_pivot(20, 110.0, "L"),
        make_pivot(30, 150.0, "H"),
        make_pivot(40, 115.0, "L"),  # wave 4 enters wave 1 territory (115 < 120)
        make_pivot(50, 160.0, "H"),
    ]
    count = ElliottCount(
        pattern="impulse",
        degree="Minor",
        waves=[
            WaveSegment(label="1", start_pivot_idx=0, end_pivot_idx=10),
            WaveSegment(label="2", start_pivot_idx=10, end_pivot_idx=20),
            WaveSegment(label="3", start_pivot_idx=20, end_pivot_idx=30),
            WaveSegment(label="4", start_pivot_idx=30, end_pivot_idx=40),
            WaveSegment(label="5", start_pivot_idx=40, end_pivot_idx=50),
        ],
        current_wave="5",
        rationale="Wave 4 enters wave 1 price territory — should be rejected for non-diagonal impulse.",
    )
    res = _result(evaluate_count(count, pivots), "EW-H-3")
    assert not res.passed
    assert "wave 1 territory" in res.message


def test_ew_h_3_allows_overlap_for_diagonals() -> None:
    """Diagonals are exempt from the wave-4 overlap rule."""
    pivots = [
        make_pivot(0, 100.0, "L"),
        make_pivot(10, 120.0, "H"),
        make_pivot(20, 110.0, "L"),
        make_pivot(30, 130.0, "H"),
        make_pivot(40, 115.0, "L"),  # overlap allowed for diagonal
        make_pivot(50, 140.0, "H"),
    ]
    count = ElliottCount(
        pattern="ending_diagonal",
        degree="Minor",
        waves=[
            WaveSegment(label="1", start_pivot_idx=0, end_pivot_idx=10),
            WaveSegment(label="2", start_pivot_idx=10, end_pivot_idx=20),
            WaveSegment(label="3", start_pivot_idx=20, end_pivot_idx=30),
            WaveSegment(label="4", start_pivot_idx=30, end_pivot_idx=40),
            WaveSegment(label="5", start_pivot_idx=40, end_pivot_idx=50),
        ],
        current_wave="5",
        rationale="Diagonal — wave 4 may overlap wave 1.",
    )
    compliance = evaluate_count(count, pivots)
    # EW-H-3 should be skipped (returns None) for diagonals.
    assert all(r.rule_id != "EW-H-3" for r in compliance.rule_results)


def test_ew_h_4_rejects_wrong_directional_motive() -> None:
    """Wave 3 in an upward impulse cannot end below its start."""
    pivots = [
        make_pivot(0, 100.0, "L"),
        make_pivot(10, 120.0, "H"),
        make_pivot(20, 110.0, "L"),
        make_pivot(30, 105.0, "L"),  # wave 3 went DOWN — invalid for an upward impulse
    ]
    count = ElliottCount(
        pattern="impulse",
        degree="Minor",
        waves=[
            WaveSegment(label="1", start_pivot_idx=0, end_pivot_idx=10),
            WaveSegment(label="2", start_pivot_idx=10, end_pivot_idx=20),
            WaveSegment(label="3", start_pivot_idx=20, end_pivot_idx=30),
        ],
        current_wave="3",
        rationale="Wave 3 moves opposite the trend — should be rejected.",
    )
    res = _result(evaluate_count(count, pivots), "EW-H-4")
    assert not res.passed
    assert "opposite" in res.message.lower()


def test_ew_h_5_rejects_zigzag_wave_b_too_deep() -> None:
    pivots = [
        make_pivot(0, 100.0, "H"),
        make_pivot(10, 80.0, "L"),    # wave A: -20
        make_pivot(20, 105.0, "H"),   # wave B exceeds A's start (100) — invalid
    ]
    count = ElliottCount(
        pattern="zigzag",
        degree="Minor",
        waves=[
            WaveSegment(label="A", start_pivot_idx=0, end_pivot_idx=10),
            WaveSegment(label="B", start_pivot_idx=10, end_pivot_idx=20),
        ],
        current_wave="B",
        rationale="Wave B retraces past wave A start — should be rejected for a zigzag.",
    )
    res = _result(evaluate_count(count, pivots), "EW-H-5")
    assert not res.passed


def test_ew_h_6_rejects_shallow_flat_wave_b() -> None:
    pivots = [
        make_pivot(0, 100.0, "H"),
        make_pivot(10, 80.0, "L"),    # wave A: -20
        make_pivot(20, 85.0, "H"),    # wave B: +5 (only 25% of A) — too shallow for a flat
    ]
    count = ElliottCount(
        pattern="flat",
        degree="Minor",
        waves=[
            WaveSegment(label="A", start_pivot_idx=0, end_pivot_idx=10),
            WaveSegment(label="B", start_pivot_idx=10, end_pivot_idx=20),
        ],
        current_wave="B",
        rationale="Wave B is shallow — should fail the flat threshold.",
    )
    res = _result(evaluate_count(count, pivots), "EW-H-6")
    assert not res.passed
    assert "below the 90%" in res.message


def test_ew_h_7_rejects_non_contracting_triangle() -> None:
    pivots = [
        make_pivot(0, 100.0, "H"),
        make_pivot(10, 90.0, "L"),    # a: 10
        make_pivot(20, 98.0, "H"),    # b: 8
        make_pivot(30, 92.0, "L"),    # c: 6 (smaller than a — OK for contracting)
        make_pivot(40, 100.0, "H"),   # d: 8 (LARGER than b — not contracting!)
        make_pivot(50, 95.0, "L"),    # e: 5
    ]
    count = ElliottCount(
        pattern="triangle_contracting",
        degree="Minor",
        waves=[
            WaveSegment(label="a", start_pivot_idx=0, end_pivot_idx=10),
            WaveSegment(label="b", start_pivot_idx=10, end_pivot_idx=20),
            WaveSegment(label="c", start_pivot_idx=20, end_pivot_idx=30),
            WaveSegment(label="d", start_pivot_idx=30, end_pivot_idx=40),
            WaveSegment(label="e", start_pivot_idx=40, end_pivot_idx=50),
        ],
        current_wave="e",
        rationale="d is larger than b — does not contract.",
    )
    res = _result(evaluate_count(count, pivots), "EW-H-7")
    assert not res.passed


def test_score_reflects_soft_rule_compliance() -> None:
    compliance = evaluate_count(impulse_up_count(), impulse_up_pivots())
    # The textbook impulse should hit at least one heuristic
    soft = [r for r in compliance.rule_results if r.severity == "soft"]
    assert soft, "expected at least one soft rule to be evaluated"
    assert 0.0 <= compliance.score <= 1.0
