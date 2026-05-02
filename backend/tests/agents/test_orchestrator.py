"""End-to-end orchestrator test on the committed sample CSV (TestModel-backed).

Verifies the full pipeline runs without hitting an LLM, that events fire in
the expected order, and that the final report has the disclaimer attached.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agents.orchestrator import run_pipeline
from app.schemas.input import UploadedTimeframe
from app.schemas.timeframe import Timeframe


SAMPLE_CSV = Path("/app/samples/NIFTY_1D.csv")


# The conftest-level `_force_test_model` autouse fixture already strips all
# three provider keys for every test, so we don't need a local override here.


@pytest.mark.asyncio
async def test_run_pipeline_end_to_end_on_real_nifty() -> None:
    if not SAMPLE_CSV.exists():
        pytest.skip(f"Sample CSV not present at {SAMPLE_CSV}")

    tf = UploadedTimeframe(
        filename="NIFTY_1D.csv",
        timeframe=Timeframe.D1,
        rows=740,
        date_range=(__import__("datetime").datetime(2023, 5, 2),
                    __import__("datetime").datetime(2026, 4, 30)),
        storage_path=str(SAMPLE_CSV),
        warnings=[],
    )

    events: list[dict] = []

    async def collector(evt: dict) -> None:
        events.append(evt)

    report = await run_pipeline(
        instrument_name="NIFTY 50",
        timeframes=[tf],
        on_event=collector,
    )

    assert report.status == "completed"
    assert report.disclaimer.startswith("wave-agent is an educational")
    assert len(report.timeframes) == 1
    assert report.timeframes[0].timeframe == "1D"
    # Real NIFTY → 38 pivots, 13 in recent window, ~130-token summary
    assert report.timeframes[0].structure.bar_count == 740
    assert 80 <= report.timeframes[0].structure.approx_token_count <= 150

    # Synthesis runs even with TestModel (returns empty scenarios list)
    assert report.synthesis is not None
    # Cost is zero on TestModel
    assert all(c.is_test for c in report.cost_breakdown)
    assert report.total_cost_usd == 0.0

    # Event ordering
    types = [e["type"] for e in events]
    assert types[0] == "preprocessing_started"
    assert "preprocessing_completed" in types
    assert "agent_started" in types
    assert "agent_completed" in types
    assert "validation_completed" in types
    assert "synthesis_started" in types
    assert "synthesis_completed" in types
    assert types[-1] == "run_completed"


@pytest.mark.asyncio
async def test_cost_cap_rejects_pathological_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lower the cost cap below the per-timeframe estimate; expect rejection."""
    from app.core import config as cfg

    monkeypatch.setattr(cfg.get_settings(), "max_run_cost_usd", 0.000001, raising=False)

    tf = UploadedTimeframe(
        filename="dummy.csv",
        timeframe=Timeframe.D1,
        rows=200,
        date_range=(__import__("datetime").datetime(2024, 1, 1),
                    __import__("datetime").datetime(2024, 7, 1)),
        storage_path="/nonexistent/path.csv",
        warnings=[],
    )
    report = await run_pipeline(
        instrument_name="TEST",
        timeframes=[tf, tf, tf, tf, tf],  # 5 timeframes — well above the artificial cap
    )
    assert report.status == "rejected_cost_cap"
    assert report.error is not None
    assert "exceeds cap" in report.error
