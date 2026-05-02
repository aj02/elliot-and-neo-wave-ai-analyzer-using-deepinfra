"""Tests for the Elliott Wave Agent.

No live LLM calls. Uses PydanticAI's `TestModel` for shape verification and a
fake Redis to exercise the cache path.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pytest

from app.agents.elliott_agent import (
    AGENT_NAME,
    ElliottAgentOutput,
    _contains_forbidden,
    _filter_output,
    run_elliott_agent,
)
from app.schemas.structure import (
    ChannelLine,
    ChannelLines,
    FibZones,
    Pivot,
    StructureSummary,
)
from app.schemas.timeframe import Timeframe
from app.schemas.waves import ElliottCount, WaveSegment
from app.services.cache import AgentCache, cache_key


# ---------- helpers ---------------------------------------------------------


def _summary() -> StructureSummary:
    p = lambda i, price, t, lbl, sp, sb, conf=True: Pivot(  # noqa: E731
        idx=i,
        datetime=datetime(2024, 1, 1 + (i % 28)),
        price=price,
        type=t,  # type: ignore[arg-type]
        label=lbl,  # type: ignore[arg-type]
        swing_pct=sp,
        swing_bars=sb,
        fib_retrace_of_prior=None,
        confirmed=conf,
    )
    pivots = [
        p(0, 100, "L", "?", 0.0, 0),
        p(20, 130, "H", "HH", 30.0, 20),
        p(35, 115, "L", "HL", -11.5, 15),
        p(80, 165, "H", "HH", 43.5, 45),
        p(95, 150, "L", "HL", -9.1, 15),
        p(130, 175, "H", "HH", 16.7, 35, conf=False),
    ]
    chan = ChannelLines(
        upper=ChannelLine(slope=0.5, intercept=110.0),
        lower=ChannelLine(slope=0.5, intercept=95.0),
        slope_angle_deg=10.0,
        fit_pivot_indices=[0, 20, 35, 80, 95],
    )
    return StructureSummary(
        instrument="TEST",
        timeframe=Timeframe.D1,
        date_range=(datetime(2024, 1, 1), datetime(2024, 5, 10)),
        bar_count=131,
        pivots=pivots,
        recent_pivots=pivots,
        current_price=170.0,
        price_position_pct=0.78,
        channel_lines=chan,
        atr_14=2.5,
        realized_vol_20_pct=0.8,
        structural_phase_hints=["uptrend(HH/HL)", "in-progress H-swing pct=+16.7"],
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
        n = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                n += 1
        return n


# ---------- forbidden-language filter --------------------------------------


def test_forbidden_language_detector() -> None:
    # Hard hits
    assert _contains_forbidden("Buy at the breakout") == "buy"
    assert _contains_forbidden("This count predicts a rally") == "predicts"
    assert _contains_forbidden("Sell aggressively") == "sell"
    assert _contains_forbidden("Go long here") == "long"
    assert _contains_forbidden("Recommend entering at this level") == "recommend"
    # No false positives on hyphenated compounds and derivative suffixes
    assert _contains_forbidden("Long-term primary degree count") is None
    assert _contains_forbidden("The shorter wave 2 alternates with the longer wave 4") is None
    assert _contains_forbidden("Short-term retracement bounded by pivot #80") is None
    assert _contains_forbidden("longstanding pattern") is None
    # Real wave-rationale text passes
    assert _contains_forbidden("If wave 3 completes, structure invalidates below 100.") is None
    assert _contains_forbidden("Wave 4 retraces 38.2% of wave 3 from pivot #80 to #95.") is None
    assert _contains_forbidden("Primary 1 from cycle low; long-term degree alignment.") is None


def test_filter_output_drops_offending_counts() -> None:
    bad_count = ElliottCount(
        pattern="impulse",
        degree="Minor",
        waves=[WaveSegment(label="1", start_pivot_idx=0, end_pivot_idx=20)],
        current_wave="1",
        rationale="Buy at pivot #20.",  # forbidden
    )
    good_count = ElliottCount(
        pattern="impulse",
        degree="Minor",
        waves=[WaveSegment(label="1", start_pivot_idx=0, end_pivot_idx=20)],
        current_wave="1",
        rationale="If this count is correct, structure invalidates below pivot #0.",
    )
    out = ElliottAgentOutput(counts=[bad_count, good_count])
    filtered = _filter_output(out)
    assert len(filtered.counts) == 1
    assert "invalidates" in filtered.counts[0].rationale


# ---------- agent shape (TestModel-backed) ---------------------------------


@pytest.mark.asyncio
async def test_agent_runs_with_test_model_and_returns_typed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without an API key, the agent must still produce a typed output via TestModel."""
    # Force the no-key path even if the dev environment has a key in .env
    from app.core import config as cfg

    monkeypatch.setattr(cfg.get_settings(), "anthropic_api_key", None, raising=False)
    monkeypatch.setattr(cfg.get_settings(), "openai_api_key", None, raising=False)

    summary = _summary()
    output, cost = await run_elliott_agent(summary)

    assert isinstance(output, ElliottAgentOutput)
    # TestModel returns a default-valued instance — counts may be empty or stubbed.
    assert isinstance(output.counts, list)
    assert cost.is_test is True
    assert cost.cost_usd == 0.0
    assert cost.cache_hit is False


# ---------- cache hit path -------------------------------------------------


@pytest.mark.asyncio
async def test_cache_hit_returns_cached_output_without_llm_call() -> None:
    """A pre-populated cache entry must be returned with cache_hit=True and zero spend."""
    summary = _summary()
    # Match what `run_elliott_agent` would key on. The model name for the no-key
    # path is `test:haiku`.
    key = cache_key(
        summary_json=summary.model_dump_json(),
        agent_name=AGENT_NAME,
        model_name="test:haiku",
    )
    cached_payload = {
        "counts": [
            {
                "pattern": "impulse",
                "degree": "Minor",
                "waves": [{"label": "1", "start_pivot_idx": 0, "end_pivot_idx": 20}],
                "current_wave": "1",
                "rationale": "Cached structural fit; invalidation below pivot #0.",
            }
        ]
    }
    fake = _FakeRedis()
    fake.store[key] = json.dumps(cached_payload).encode()
    cache = AgentCache(fake, ttl_seconds=60)  # type: ignore[arg-type]

    output, cost = await run_elliott_agent(summary, cache=cache)

    assert cost.cache_hit is True
    assert cost.input_tokens == 0
    assert cost.output_tokens == 0
    assert cost.cost_usd == 0.0
    assert len(output.counts) == 1
    assert output.counts[0].pattern == "impulse"


# ---------- cache populated on first miss ----------------------------------


@pytest.mark.asyncio
async def test_cache_is_populated_on_first_call() -> None:
    summary = _summary()
    fake = _FakeRedis()
    cache = AgentCache(fake, ttl_seconds=60)  # type: ignore[arg-type]
    assert not fake.store

    await run_elliott_agent(summary, cache=cache)

    # One key written matching the cache_key contract.
    assert len(fake.store) == 1
    written_key = next(iter(fake.store))
    assert written_key.startswith("wave-agent:agent-cache:")
