"""Tests for the Validator service."""

from __future__ import annotations

from app.agents.elliott_agent import ElliottAgentOutput
from app.agents.neowave_agent import NeowaveAgentOutput
from app.services.validator import (
    compute_elliott_invalidation,
    validate_elliott,
    validate_neowave,
    validate_timeframe,
)
from app.schemas.waves import ElliottCount, NeowaveCount, WaveSegment

from tests.rules.conftest import impulse_up_count, impulse_up_pivots, make_pivot


def test_clean_count_survives_validation() -> None:
    output = ElliottAgentOutput(counts=[impulse_up_count()])
    surviving, rejected = validate_elliott(output, impulse_up_pivots(), timeframe="1D")
    assert len(surviving) == 1
    assert len(rejected) == 0
    assert surviving[0].is_valid
    assert surviving[0].invalidation is not None  # current_wave="5" → wave-4-end invalidation


def test_rule_violating_count_is_rejected() -> None:
    """A wave-4-overlap impulse must be rejected and produce no invalidation."""
    pivots = [
        make_pivot(0, 100.0, "L"),
        make_pivot(10, 120.0, "H"),
        make_pivot(20, 110.0, "L"),
        make_pivot(30, 150.0, "H"),
        make_pivot(40, 115.0, "L"),  # wave 4 overlap
        make_pivot(50, 160.0, "H"),
    ]
    bad = ElliottCount(
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
        rationale="Test impulse with wave-4 overlap.",
    )
    output = ElliottAgentOutput(counts=[bad])
    surviving, rejected = validate_elliott(output, pivots, timeframe="1D")
    assert len(surviving) == 0
    assert len(rejected) == 1
    assert rejected[0].invalidation is None
    assert any(r.rule_id == "EW-H-3" for r in rejected[0].compliance.hard_failures)


def test_invalidation_for_current_wave_3_is_wave_1_top() -> None:
    """current_wave='3' → invalidation at wave 1 end."""
    pivots = impulse_up_pivots()
    count = ElliottCount(
        pattern="impulse",
        degree="Minor",
        waves=[
            WaveSegment(label="1", start_pivot_idx=0, end_pivot_idx=20),
            WaveSegment(label="2", start_pivot_idx=20, end_pivot_idx=35),
            WaveSegment(label="3", start_pivot_idx=35, end_pivot_idx=80),
        ],
        current_wave="3",
        rationale="In wave 3.",
    )
    inv = compute_elliott_invalidation(count, pivots)
    assert inv is not None
    assert inv.price == 120.0  # wave 1 end
    assert inv.direction == "below"  # upward impulse
    assert "pivot #20" in inv.reason


def test_invalidation_for_zigzag_wave_b_is_wave_a_start() -> None:
    pivots = [
        make_pivot(0, 100.0, "H"),
        make_pivot(10, 80.0, "L"),
        make_pivot(20, 95.0, "H"),
    ]
    count = ElliottCount(
        pattern="zigzag",
        degree="Minor",
        waves=[
            WaveSegment(label="A", start_pivot_idx=0, end_pivot_idx=10),
            WaveSegment(label="B", start_pivot_idx=10, end_pivot_idx=20),
        ],
        current_wave="B",
        rationale="Zigzag wave B in progress.",
    )
    inv = compute_elliott_invalidation(count, pivots)
    assert inv is not None
    assert inv.price == 100.0  # wave A start
    assert inv.direction == "above"  # downward A → invalidation above the start


def test_combined_validate_timeframe_partitions_correctly() -> None:
    pivots = impulse_up_pivots()
    e_out = ElliottAgentOutput(counts=[impulse_up_count()])
    n_out = NeowaveAgentOutput(
        counts=[
            NeowaveCount(
                pattern="impulse",
                mono_waves=[
                    WaveSegment(label="m1", start_pivot_idx=0, end_pivot_idx=20),
                    WaveSegment(label="m2", start_pivot_idx=20, end_pivot_idx=35),
                    WaveSegment(label="m3", start_pivot_idx=35, end_pivot_idx=80),
                    WaveSegment(label="m4", start_pivot_idx=80, end_pivot_idx=95),
                    WaveSegment(label="m5", start_pivot_idx=95, end_pivot_idx=130),
                ],
                current_position="in m5",
                rationale="Synthetic impulse with m3 extended.",
            )
        ]
    )
    outcome = validate_timeframe(e_out, n_out, pivots, timeframe="1D")
    assert outcome.timeframe == "1D"
    assert len(outcome.elliott_surviving) == 1
    assert len(outcome.neowave_surviving) == 1


def test_invalid_pivot_ref_is_rejected_not_crashed() -> None:
    """LLMs sometimes hallucinate pivot indices. The Validator must reject the
    count cleanly, not crash on a KeyError inside the rule engine."""
    pivots = impulse_up_pivots()  # actual indices: 0, 20, 35, 80, 95, 130
    bogus = ElliottCount(
        pattern="impulse",
        degree="Minor",
        waves=[
            WaveSegment(label="1", start_pivot_idx=0, end_pivot_idx=9),  # 9 doesn't exist
            WaveSegment(label="2", start_pivot_idx=9, end_pivot_idx=20),
        ],
        current_wave="2",
        rationale="Hallucinated pivot index 9 — should be rejected, not crash.",
    )
    output = ElliottAgentOutput(counts=[bogus])
    surviving, rejected = validate_elliott(output, pivots, timeframe="1D")
    assert len(surviving) == 0
    assert len(rejected) == 1
    failure = rejected[0].compliance.hard_failures[0]
    assert failure.rule_id == "EW-PIVOT-REF"
    assert "not in the StructureSummary" in failure.message


def test_neowave_invalid_pivot_ref_also_rejected() -> None:
    pivots = impulse_up_pivots()  # 0, 20, 35, 80, 95, 130
    bogus = NeowaveCount(
        pattern="impulse",
        mono_waves=[
            WaveSegment(label="m1", start_pivot_idx=999, end_pivot_idx=20),
        ],
        current_position="in m1",
        rationale="Hallucinated index 999.",
    )
    output = NeowaveAgentOutput(counts=[bogus])
    surviving, rejected = validate_neowave(output, pivots, timeframe="1D")
    assert len(surviving) == 0
    assert len(rejected) == 1
    assert rejected[0].compliance.hard_failures[0].rule_id == "NW-PIVOT-REF"


def test_neowave_rejection_logs_reason() -> None:
    """A NEOWave impulse with monotonous motive waves is rejected (NW-H-2)."""
    pivots = [
        make_pivot(0, 100.0, "L"),
        make_pivot(10, 110.0, "H"),
        make_pivot(20, 105.0, "L"),
        make_pivot(30, 115.0, "H"),
        make_pivot(40, 110.0, "L"),
        make_pivot(50, 120.0, "H"),
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
        rationale="All three motive waves equal — should be rejected.",
    )
    output = NeowaveAgentOutput(counts=[count])
    surviving, rejected = validate_neowave(output, pivots, timeframe="1D")
    assert len(surviving) == 0
    assert len(rejected) == 1
    assert any(r.rule_id == "NW-H-2" for r in rejected[0].compliance.hard_failures)
