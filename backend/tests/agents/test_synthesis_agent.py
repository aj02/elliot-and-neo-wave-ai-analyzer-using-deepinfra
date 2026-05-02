"""Tests for the Synthesis Agent (TestModel-backed)."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from app.agents.synthesis_agent import (
    AGENT_NAME,
    build_synthesis_input,
    hydrate_synthesis_invalidations,
    run_synthesis_agent,
)
from app.rules.types import RuleCompliance, RuleResult
from app.schemas.levels import InvalidationLevel
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
    ValidatedNeowaveCount,
    ValidationOutcome,
)
from app.schemas.waves import ElliottCount, NeowaveCount, WaveSegment
from app.services.cache import AgentCache, cache_key


# ---------- helpers ---------------------------------------------------------


def _summary(tf: Timeframe) -> StructureSummary:
    pivots = [
        Pivot(
            idx=i,
            datetime=datetime(2024, 1, 1 + (i % 28)),
            price=100.0 + i,
            type="L" if i % 2 == 0 else "H",
            label="?",
            swing_pct=2.0,
            swing_bars=1,
            fib_retrace_of_prior=None,
            confirmed=True,
        )
        for i in range(5)
    ]
    return StructureSummary(
        instrument="TEST",
        timeframe=tf,
        date_range=(datetime(2024, 1, 1), datetime(2024, 1, 5)),
        bar_count=5,
        pivots=pivots,
        recent_pivots=pivots,
        current_price=104.0,
        price_position_pct=0.5,
        channel_lines=ChannelLines(
            upper=ChannelLine(slope=0.0, intercept=104.0),
            lower=ChannelLine(slope=0.0, intercept=100.0),
            slope_angle_deg=0.0,
            fit_pivot_indices=[0, 1, 2, 3, 4],
        ),
        atr_14=1.0,
        realized_vol_20_pct=0.5,
        structural_phase_hints=["range"],
        fibonacci_zones=FibZones(),
    )


def _outcome(tf: Timeframe) -> ValidationOutcome:
    e_count = ElliottCount(
        pattern="impulse",
        degree="Minor",
        waves=[WaveSegment(label="1", start_pivot_idx=0, end_pivot_idx=1)],
        current_wave="1",
        rationale=f"In wave 1 from pivot #0 on {tf.value}.",
    )
    inv = InvalidationLevel(
        price=100.0,
        direction="below",
        reason="Wave 2 cannot retrace 100% of wave 1.",
    )
    e_validated = ValidatedElliottCount(
        count=e_count,
        compliance=RuleCompliance(
            rule_results=[
                RuleResult(
                    rule_id="EW-H-1",
                    name="Wave 2 ≤ 100% retracement",
                    severity="hard",
                    passed=True,
                    message="OK",
                )
            ]
        ),
        invalidation=inv,
    )
    n_count = NeowaveCount(
        pattern="impulse",
        mono_waves=[WaveSegment(label="m1", start_pivot_idx=0, end_pivot_idx=1)],
        current_position="in m1",
        rationale=f"Mono-wave m1 on {tf.value}.",
    )
    n_validated = ValidatedNeowaveCount(
        count=n_count,
        compliance=RuleCompliance(rule_results=[]),
        invalidation=None,
    )
    return ValidationOutcome(
        timeframe=tf.value,
        elliott_surviving=[e_validated],
        elliott_rejected=[],
        neowave_surviving=[n_validated],
        neowave_rejected=[],
    )


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value.encode() if isinstance(value, str) else value

    async def delete(self, *keys: str) -> int:
        return sum(1 for k in keys if self.store.pop(k, None) is not None)


# ---------- input rendering -------------------------------------------------


def test_build_synthesis_input_renders_all_timeframes() -> None:
    parts = [(_summary(Timeframe.D1), _outcome(Timeframe.D1)),
             (_summary(Timeframe.W1), _outcome(Timeframe.W1))]
    text = build_synthesis_input(parts)
    assert "== TIMEFRAME 1D ==" in text
    assert "== TIMEFRAME 1W ==" in text
    assert "Surviving Elliott counts:" in text
    assert "Surviving NEOWave counts:" in text
    assert "E0:" in text
    assert "N0:" in text
    # The deterministic invalidation must appear in the input so the agent can reference it.
    assert "inv=below 100.00" in text


def test_build_synthesis_input_token_budget() -> None:
    """5 timeframes × 3 surviving counts each must stay under ~6000 chars (~1500 tokens)."""
    parts = [(_summary(tf), _outcome(tf)) for tf in (Timeframe.D1, Timeframe.W1, Timeframe.MO1, Timeframe.H4, Timeframe.H1)]
    text = build_synthesis_input(parts)
    approx_tokens = len(text) // 4
    assert approx_tokens <= 1500, f"Synthesis input is {approx_tokens} tokens, breaches the 1500 cap"


# ---------- hydration -------------------------------------------------------


def test_hydrate_attaches_python_invalidations() -> None:
    parts_by_tf = {Timeframe.D1.value: _outcome(Timeframe.D1)}
    scenario = SynthesisScenario(
        rank=1,
        label="Primary",
        summary="Primary scenario referencing pivot #0.",
        cross_timeframe_alignment="Single timeframe.",
        cross_framework_agreement="Elliott and NEOWave both ID an impulse on 1D.",
        supporting=[CountRef(timeframe="1D", framework="elliott", count_idx=0)],
        invalidation_levels=[],  # agent leaves empty
    )
    report = SynthesisReport(scenarios=[scenario], methodology_note="Test note.")
    hydrated = hydrate_synthesis_invalidations(report, parts_by_tf)
    assert len(hydrated.scenarios[0].invalidation_levels) == 1
    assert hydrated.scenarios[0].invalidation_levels[0].price == 100.0


def test_hydrate_skips_invalid_refs() -> None:
    parts_by_tf = {Timeframe.D1.value: _outcome(Timeframe.D1)}
    scenario = SynthesisScenario(
        rank=1,
        label="Primary",
        summary="Refers to a count that does not exist (should be skipped).",
        cross_timeframe_alignment="-",
        cross_framework_agreement="-",
        supporting=[
            CountRef(timeframe="1D", framework="elliott", count_idx=2),  # OOB index
            CountRef(timeframe="9X", framework="elliott", count_idx=0),  # missing tf
        ],
    )
    report = SynthesisReport(scenarios=[scenario], methodology_note="Test note.")
    hydrated = hydrate_synthesis_invalidations(report, parts_by_tf)
    assert hydrated.scenarios[0].invalidation_levels == []


# ---------- live agent (TestModel) -----------------------------------------


@pytest.mark.asyncio
async def test_runs_with_test_model_returns_typed_output(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import config as cfg

    monkeypatch.setattr(cfg.get_settings(), "anthropic_api_key", None, raising=False)
    monkeypatch.setattr(cfg.get_settings(), "openai_api_key", None, raising=False)

    parts = [(_summary(Timeframe.D1), _outcome(Timeframe.D1))]
    report, cost = await run_synthesis_agent(parts)
    assert isinstance(report, SynthesisReport)
    assert isinstance(report.scenarios, list)
    assert cost.is_test is True
    assert cost.cost_usd == 0.0


@pytest.mark.asyncio
async def test_cache_hit_returns_cached_report() -> None:
    parts = [(_summary(Timeframe.D1), _outcome(Timeframe.D1))]
    user_prompt = build_synthesis_input(parts)
    key = cache_key(summary_json=user_prompt, agent_name=AGENT_NAME, model_name="test:sonnet")

    cached = {
        "scenarios": [
            {
                "rank": 1,
                "label": "Primary",
                "summary": "Cached primary scenario referencing pivot #0.",
                "cross_timeframe_alignment": "Single TF.",
                "cross_framework_agreement": "EW + NEOWave concur.",
                "supporting": [{"timeframe": "1D", "framework": "elliott", "count_idx": 0}],
                "invalidation_levels": [],
            }
        ],
        "methodology_note": "Cached methodology.",
    }
    fake = _FakeRedis()
    fake.store[key] = json.dumps(cached).encode()
    cache = AgentCache(fake, ttl_seconds=60)  # type: ignore[arg-type]

    report, cost = await run_synthesis_agent(parts, cache=cache)
    assert cost.cache_hit is True
    assert len(report.scenarios) == 1
    # Hydration must have re-attached the deterministic invalidation
    assert len(report.scenarios[0].invalidation_levels) == 1
    assert report.scenarios[0].invalidation_levels[0].price == 100.0
