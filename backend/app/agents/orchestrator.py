"""Orchestrator (Python, not an LLM agent).

For each uploaded timeframe:
  1. Preprocess CSV → StructureSummary
  2. Run Elliott + NEOWave agents in parallel (asyncio.gather)
  3. Run Validator (deterministic Python rules) on each
Then a single Synthesis call across all timeframes, hydrated with Python-
computed invalidation prices.

Emits typed events at every state transition. The events are streamed over
WebSocket by the Step 11 wiring; here we accept any callable as the sink so
this module remains independently testable.
"""

from __future__ import annotations

import asyncio
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Awaitable, Callable

from pydantic import BaseModel, ConfigDict

from app.agents.deps import AgentDeps, AgentRunCost
from app.agents.elliott_agent import run_elliott_agent
from app.agents.events import event
from app.agents.neowave_agent import run_neowave_agent
from app.agents.synthesis_agent import run_synthesis_agent
from app.core.config import get_settings
from app.core.disclaimer import DISCLAIMER
from app.core.logging import get_logger
from app.preprocessing.csv_loader import load_csv
from app.preprocessing.structure import build as build_structure
from app.preprocessing.validators import validate as validate_csv
from app.schemas.input import UploadedTimeframe
from app.schemas.report import (
    AnalysisReport,
    CostBreakdown,
    TimeframeReport,
)
from app.schemas.structure import StructureSummary
from app.services.cache import AgentCache
from app.services.validator import validate_timeframe


log = get_logger("agents.orchestrator")


# ---------------------------------------------------------------------------
# Cost guard: estimate worst-case spend for a run, reject if it exceeds the
# configured cap. Uses pessimistic upper bounds for token counts; a real run
# nearly always lands below the estimate.
# ---------------------------------------------------------------------------


class CostGuardError(RuntimeError):
    pass


def _estimate_max_cost(num_timeframes: int) -> float:
    """Conservative upper bound on a run's spend, respecting LLM_PROVIDER.

    Per timeframe: 2 fast-tier calls × ~1_500 in + ~400 out tokens.
    Plus 1 smart-tier synthesis call: ~3_000 in + ~800 out tokens.
    """
    settings = get_settings()
    haiku_in_tok, haiku_out_tok = 1500, 400
    sonnet_in_tok, sonnet_out_tok = 3000, 800

    if settings.llm_provider == "anthropic":
        haiku_in_p, haiku_out_p = 0.80, 4.00
        sonnet_in_p, sonnet_out_p = 3.00, 15.00
    elif settings.llm_provider == "openai":
        haiku_in_p, haiku_out_p = 0.15, 0.60
        sonnet_in_p, sonnet_out_p = 2.50, 10.00
    elif settings.llm_provider == "deepinfra":
        haiku_in_p = sonnet_in_p = settings.deepinfra_input_price_per_mtok
        haiku_out_p = sonnet_out_p = settings.deepinfra_output_price_per_mtok
    else:
        return 0.0

    haiku_per_call = (haiku_in_tok * haiku_in_p + haiku_out_tok * haiku_out_p) / 1_000_000
    sonnet_call = (sonnet_in_tok * sonnet_in_p + sonnet_out_tok * sonnet_out_p) / 1_000_000
    return num_timeframes * 2 * haiku_per_call + sonnet_call


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

EventSink = Callable[[dict], Awaitable[None]]


async def _noop_sink(_evt: dict) -> None:
    return None


class _PreparedTimeframe(BaseModel):
    """Internal: a per-timeframe slice carrying its summary post-preprocessing."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    label: str
    summary: StructureSummary


def new_run_id() -> str:
    """Stable, URL-safe run id (UUID4 hex truncated to 22 chars)."""
    return secrets.token_urlsafe(16)


async def run_pipeline(
    *,
    instrument_name: str,
    timeframes: list[UploadedTimeframe],
    cache: AgentCache | None = None,
    on_event: EventSink = _noop_sink,
    run_id: str | None = None,
) -> AnalysisReport:
    """Drive the full pipeline. Returns the AnalysisReport (also emit events)."""
    settings = get_settings()
    run_id = run_id or new_run_id()
    started_at = datetime.now(UTC)

    # Cost cap pre-check
    estimated = _estimate_max_cost(len(timeframes))
    if estimated > settings.max_run_cost_usd:
        msg = (
            f"Estimated max cost ${estimated:.4f} exceeds cap ${settings.max_run_cost_usd:.4f} "
            f"for {len(timeframes)} timeframes. Reduce timeframes or raise MAX_RUN_COST_USD."
        )
        await on_event(event(type="error", run_id=run_id, message=msg).model_dump(mode="json"))
        log.warning("orchestrator.rejected.cost_cap", run_id=run_id, estimated_usd=estimated)
        return AnalysisReport(
            disclaimer=DISCLAIMER,
            run_id=run_id,
            instrument_name=instrument_name,
            status="rejected_cost_cap",
            started_at=started_at,
            completed_at=datetime.now(UTC),
            timeframes=[],
            synthesis=None,
            error=msg,
        )

    # Step 1: preprocessing per timeframe
    await on_event(
        event(type="preprocessing_started", run_id=run_id,
              timeframes=[t.timeframe.value for t in timeframes]).model_dump(mode="json")
    )
    prepared = await asyncio.gather(
        *(_preprocess_one(tf, instrument_name) for tf in timeframes),
        return_exceptions=True,
    )
    summaries: list[StructureSummary] = []
    for tf, item in zip(timeframes, prepared, strict=True):
        if isinstance(item, BaseException):
            err = f"Preprocessing failed for {tf.timeframe.value}: {type(item).__name__}: {item}"
            await on_event(event(type="error", run_id=run_id, message=err).model_dump(mode="json"))
            log.exception("orchestrator.preprocessing.failed", run_id=run_id, timeframe=tf.timeframe.value)
            return AnalysisReport(
                disclaimer=DISCLAIMER,
                run_id=run_id,
                instrument_name=instrument_name,
                status="failed",
                started_at=started_at,
                completed_at=datetime.now(UTC),
                timeframes=[],
                synthesis=None,
                error=err,
            )
        summaries.append(item)
    await on_event(
        event(type="preprocessing_completed", run_id=run_id,
              token_counts={s.timeframe.value: s.approx_token_count for s in summaries}).model_dump(mode="json")
    )

    # Step 2 + 3: agents per timeframe + Validator
    deps = AgentDeps(cache=cache)
    timeframe_reports: list[TimeframeReport] = []
    cost_records: list[AgentRunCost] = []

    for summary in summaries:
        tf_label = summary.timeframe.value

        # Elliott + NEOWave in parallel
        await on_event(event(type="agent_started", run_id=run_id, agent="elliott", timeframe=tf_label).model_dump(mode="json"))
        await on_event(event(type="agent_started", run_id=run_id, agent="neowave", timeframe=tf_label).model_dump(mode="json"))

        (e_out, e_cost), (n_out, n_cost) = await asyncio.gather(
            run_elliott_agent(summary, deps=deps, cache=cache),
            run_neowave_agent(summary, deps=deps, cache=cache),
        )
        cost_records.extend([e_cost, n_cost])

        await on_event(event(type="agent_completed", run_id=run_id, agent="elliott", timeframe=tf_label,
                             candidates=len(e_out.counts), cache_hit=e_cost.cache_hit).model_dump(mode="json"))
        await on_event(event(type="agent_completed", run_id=run_id, agent="neowave", timeframe=tf_label,
                             candidates=len(n_out.counts), cache_hit=n_cost.cache_hit).model_dump(mode="json"))

        outcome = validate_timeframe(e_out, n_out, summary.pivots, timeframe=tf_label)
        await on_event(
            event(type="validation_completed", run_id=run_id, timeframe=tf_label,
                  elliott_surviving=len(outcome.elliott_surviving),
                  elliott_rejected=len(outcome.elliott_rejected),
                  neowave_surviving=len(outcome.neowave_surviving),
                  neowave_rejected=len(outcome.neowave_rejected)).model_dump(mode="json")
        )

        timeframe_reports.append(
            TimeframeReport(timeframe=tf_label, structure=summary, validation=outcome)
        )

    # Step 4: synthesis (single call)
    parts = [(tr.structure, tr.validation) for tr in timeframe_reports]
    await on_event(event(type="synthesis_started", run_id=run_id).model_dump(mode="json"))
    synthesis_report, syn_cost = await run_synthesis_agent(parts, deps=deps, cache=cache)
    cost_records.append(syn_cost)
    await on_event(
        event(type="synthesis_completed", run_id=run_id,
              scenarios=len(synthesis_report.scenarios)).model_dump(mode="json")
    )

    # Cost rollup
    breakdown = [
        CostBreakdown(
            agent_name=c.agent_name,
            model=c.model,
            is_test=c.is_test,
            input_tokens=c.input_tokens,
            output_tokens=c.output_tokens,
            cost_usd=c.cost_usd,
            cache_hit=c.cache_hit,
        )
        for c in cost_records
    ]
    total_cost = round(sum(c.cost_usd for c in cost_records), 6)

    completed_at = datetime.now(UTC)
    report = AnalysisReport(
        disclaimer=DISCLAIMER,
        run_id=run_id,
        instrument_name=instrument_name,
        status="completed",
        started_at=started_at,
        completed_at=completed_at,
        timeframes=timeframe_reports,
        synthesis=synthesis_report,
        cost_breakdown=breakdown,
        total_cost_usd=total_cost,
    )

    await on_event(
        event(type="run_completed", run_id=run_id,
              total_cost_usd=total_cost,
              scenarios=len(synthesis_report.scenarios),
              duration_ms=int((completed_at - started_at).total_seconds() * 1000)
              ).model_dump(mode="json")
    )
    log.info(
        "orchestrator.run.completed",
        run_id=run_id,
        instrument=instrument_name,
        timeframes=len(timeframe_reports),
        total_cost_usd=total_cost,
    )
    return report


async def _preprocess_one(tf: UploadedTimeframe, instrument_name: str) -> StructureSummary:
    """Read CSV from disk, validate, build StructureSummary. Runs on a worker thread."""
    def _sync() -> StructureSummary:
        path = Path(tf.storage_path)
        df, _ = load_csv(path)
        df, _ = validate_csv(df)
        return build_structure(
            df,
            instrument=instrument_name,
            timeframe=tf.timeframe,
        )

    return await asyncio.to_thread(_sync)
