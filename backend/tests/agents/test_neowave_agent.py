"""Tests for the NEOWave Agent (TestModel-backed, no live LLM)."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from app.agents.neowave_agent import (
    AGENT_NAME,
    NeowaveAgentOutput,
    _filter_output,
    run_neowave_agent,
)
from app.schemas.structure import (
    ChannelLine,
    ChannelLines,
    FibZones,
    Pivot,
    StructureSummary,
)
from app.schemas.timeframe import Timeframe
from app.schemas.waves import NeowaveCount, WaveSegment
from app.services.cache import AgentCache, cache_key


def _summary() -> StructureSummary:
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
            confirmed=(i < 5),
        )
        for i in range(6)
    ]
    return StructureSummary(
        instrument="TEST",
        timeframe=Timeframe.D1,
        date_range=(datetime(2024, 1, 1), datetime(2024, 1, 6)),
        bar_count=6,
        pivots=pivots,
        recent_pivots=pivots,
        current_price=105.0,
        price_position_pct=0.5,
        channel_lines=ChannelLines(
            upper=ChannelLine(slope=0.0, intercept=110.0),
            lower=ChannelLine(slope=0.0, intercept=100.0),
            slope_angle_deg=0.0,
            fit_pivot_indices=[0, 1, 2, 3, 4],
        ),
        atr_14=1.0,
        realized_vol_20_pct=0.5,
        structural_phase_hints=["range"],
        fibonacci_zones=FibZones(),
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


def test_filter_output_drops_offending_counts() -> None:
    bad = NeowaveCount(
        pattern="impulse",
        mono_waves=[WaveSegment(label="m1", start_pivot_idx=0, end_pivot_idx=1)],
        current_position="m1",
        rationale="Buy at pivot #1.",
    )
    good = NeowaveCount(
        pattern="impulse",
        mono_waves=[WaveSegment(label="m1", start_pivot_idx=0, end_pivot_idx=1)],
        current_position="m1",
        rationale="Pivot #0 to #1 forms m1; structural fit follows.",
    )
    out = NeowaveAgentOutput(counts=[bad, good])
    filtered = _filter_output(out)
    assert len(filtered.counts) == 1
    assert "structural fit" in filtered.counts[0].rationale


@pytest.mark.asyncio
async def test_runs_with_test_model_returns_typed_output(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import config as cfg

    monkeypatch.setattr(cfg.get_settings(), "anthropic_api_key", None, raising=False)
    monkeypatch.setattr(cfg.get_settings(), "openai_api_key", None, raising=False)

    output, cost = await run_neowave_agent(_summary())
    assert isinstance(output, NeowaveAgentOutput)
    assert isinstance(output.counts, list)
    assert cost.is_test is True
    assert cost.cost_usd == 0.0
    assert cost.cache_hit is False


@pytest.mark.asyncio
async def test_cache_hit_returns_cached_output_without_llm_call() -> None:
    summary = _summary()
    key = cache_key(
        summary_json=summary.model_dump_json(),
        agent_name=AGENT_NAME,
        model_name="test:haiku",
    )
    cached_payload = {
        "counts": [
            {
                "pattern": "triangle_contracting",
                "mono_waves": [
                    {"label": "a", "start_pivot_idx": 0, "end_pivot_idx": 1},
                    {"label": "b", "start_pivot_idx": 1, "end_pivot_idx": 2},
                    {"label": "c", "start_pivot_idx": 2, "end_pivot_idx": 3},
                ],
                "current_position": "in c",
                "rationale": "Cached: legs contract from a to c per Similarity & Balance.",
            }
        ]
    }
    fake = _FakeRedis()
    fake.store[key] = json.dumps(cached_payload).encode()
    cache = AgentCache(fake, ttl_seconds=60)  # type: ignore[arg-type]

    output, cost = await run_neowave_agent(summary, cache=cache)

    assert cost.cache_hit is True
    assert cost.cost_usd == 0.0
    assert len(output.counts) == 1
    assert output.counts[0].pattern == "triangle_contracting"
