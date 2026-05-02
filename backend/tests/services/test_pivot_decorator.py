"""Tests for the pivot-decorator service."""

from __future__ import annotations

from datetime import datetime

from app.rules.types import RuleCompliance
from app.schemas.structure import (
    ChannelLine,
    ChannelLines,
    FibZones,
    Pivot,
    StructureSummary,
)
from app.schemas.synthesis import CountRef, SynthesisReport, SynthesisScenario
from app.schemas.timeframe import Timeframe
from app.schemas.validated import (
    ValidatedElliottCount,
    ValidationOutcome,
)
from app.schemas.waves import ElliottCount, WaveSegment
from app.services.pivot_decorator import (
    _decorate,
    _format_pivot,
    decorate_synthesis,
    decorate_validation_outcome,
)


def _pivot(idx: int, year: int, month: int, price: float) -> Pivot:
    return Pivot(
        idx=idx,
        datetime=datetime(year, month, 1),
        price=price,
        type="L",
        label="?",
        swing_pct=0.0,
        swing_bars=0,
        fib_retrace_of_prior=None,
        confirmed=True,
    )


def test_decorate_replaces_pivot_refs_with_price_and_date() -> None:
    pivots = {
        244: _pivot(244, 2010, 11, 6092.0),
        296: _pivot(296, 2015, 3, 8491.0),
    }
    text = "Wave 3 extends from #244 to #296."
    out = _decorate(text, pivots, "1M")
    assert "6092 (Nov 2010)" in out
    assert "8491 (Mar 2015)" in out
    assert "#244" not in out
    assert "#296" not in out


def test_decorate_leaves_unknown_pivot_indices_untouched() -> None:
    out = _decorate("References #999 unknown.", {}, "1M")
    assert out == "References #999 unknown."


def test_decorate_does_not_match_inside_words() -> None:
    out = _decorate("web#244 should not match.", {244: _pivot(244, 2010, 11, 6092.0)}, "1M")
    assert "web#244" in out
    assert "6092" not in out


def test_format_uses_iso_date_for_daily() -> None:
    p = _pivot(10, 2024, 3, 22000.0)
    p_d = p.model_copy(update={"datetime": datetime(2024, 3, 15)})
    assert _format_pivot(p_d, "1D") == "22000 (2024-03-15)"
    assert _format_pivot(p_d, "1M") == "22000 (Mar 2024)"


def test_decorate_validation_outcome_rewrites_count_rationale() -> None:
    pivots = [_pivot(0, 2020, 1, 12000.0), _pivot(20, 2024, 6, 22000.0)]
    summary = StructureSummary(
        instrument="TEST",
        timeframe=Timeframe.D1,
        date_range=(datetime(2020, 1, 1), datetime(2024, 6, 1)),
        bar_count=1000,
        pivots=pivots,
        recent_pivots=pivots,
        current_price=22000.0,
        price_position_pct=0.5,
        channel_lines=ChannelLines(
            upper=ChannelLine(slope=0.0, intercept=0.0),
            lower=ChannelLine(slope=0.0, intercept=0.0),
            slope_angle_deg=0.0,
            fit_pivot_indices=[],
        ),
        atr_14=0.0,
        realized_vol_20_pct=0.0,
        structural_phase_hints=[],
        fibonacci_zones=FibZones(),
    )
    count = ElliottCount(
        pattern="impulse",
        degree="Minor",
        waves=[WaveSegment(label="1", start_pivot_idx=0, end_pivot_idx=20)],
        current_wave="1",
        rationale="Impulse from #0 to #20 in progress.",
    )
    validated = ValidatedElliottCount(
        count=count,
        compliance=RuleCompliance(rule_results=[]),
        invalidation=None,
    )
    outcome = ValidationOutcome(
        timeframe="1D",
        elliott_surviving=[validated],
        elliott_rejected=[],
        neowave_surviving=[],
        neowave_rejected=[],
    )
    decorated = decorate_validation_outcome(outcome, summary)
    new_rationale = decorated.elliott_surviving[0].count.rationale
    assert "12000 (2020-01-01)" in new_rationale
    assert "22000 (2024-06-01)" in new_rationale


def test_decorate_synthesis_uses_supporting_count_timeframe() -> None:
    pivots = [_pivot(244, 2010, 11, 6092.0)]
    summary = StructureSummary(
        instrument="TEST",
        timeframe=Timeframe.MO1,
        date_range=(datetime(1990, 7, 1), datetime(2026, 4, 1)),
        bar_count=430,
        pivots=pivots,
        recent_pivots=pivots,
        current_price=24000.0,
        price_position_pct=0.5,
        channel_lines=ChannelLines(
            upper=ChannelLine(slope=0.0, intercept=0.0),
            lower=ChannelLine(slope=0.0, intercept=0.0),
            slope_angle_deg=0.0,
            fit_pivot_indices=[],
        ),
        atr_14=0.0,
        realized_vol_20_pct=0.0,
        structural_phase_hints=[],
        fibonacci_zones=FibZones(),
    )
    outcome = ValidationOutcome(
        timeframe="1M", elliott_surviving=[], elliott_rejected=[],
        neowave_surviving=[], neowave_rejected=[],
    )
    scenario = SynthesisScenario(
        rank=1,
        label="Primary",
        summary="Wave 5 from pivot #244.",
        cross_timeframe_alignment="Single TF.",
        cross_framework_agreement="EW + NW concur.",
        supporting=[CountRef(timeframe="1M", framework="elliott", count_idx=0)],
    )
    report = SynthesisReport(scenarios=[scenario], methodology_note="")
    decorated = decorate_synthesis(report, [(summary, outcome)])
    assert "6092 (Nov 2010)" in decorated.scenarios[0].summary
    assert "#244" not in decorated.scenarios[0].summary
