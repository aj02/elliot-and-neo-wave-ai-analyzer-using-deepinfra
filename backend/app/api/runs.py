"""POST /analyze, GET /runs/{run_id}, WS /ws/runs/{run_id}.

The orchestrator is kicked off as a background asyncio task. The WebSocket
endpoint subscribes to that run's event queue and streams events as they
fire. Once the run completes, the final report is persisted to Redis with a
24h TTL — `GET /runs/{run_id}` reads from Redis so it survives WebSocket
disconnects and process restarts within the TTL window.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status

from app.agents.orchestrator import new_run_id, run_pipeline
from app.api.deps import RedisDep, SessionStoreDep
from app.core.disclaimer import DISCLAIMER
from app.core.logging import get_logger
from app.preprocessing.csv_loader import load_csv
from app.preprocessing.validators import validate as validate_csv
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.schemas.chart import ChartBar, ChartDataResponse
from app.schemas.report import AnalysisReport
from app.services.cache import AgentCache
from app.services.runs import (
    fetch_chart_paths,
    fetch_report,
    get_registry,
    persist_chart_paths,
    persist_report,
)


router = APIRouter(tags=["analyze"])
log = get_logger("api.runs")


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_analyze(
    body: AnalyzeRequest,
    sessions: SessionStoreDep,
    redis: RedisDep,
) -> AnalyzeResponse:
    """Kick off a run on a previously-uploaded session.

    Returns immediately with `run_id` + `websocket_url`. The actual work
    proceeds in the background and is observable via the WebSocket.
    """
    session = await sessions.get(body.session_id)
    if session is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No upload session with id '{body.session_id}'. Sessions expire after 24h.",
        )

    run_id = new_run_id()
    instrument = body.instrument_name or session.instrument_name
    registry = get_registry()
    state = registry.create(run_id=run_id, instrument_name=instrument)

    # Persist a tf → CSV-path mapping so /chart-data can find the right file
    # later. Keys are timeframe.value strings (e.g. "1D").
    await persist_chart_paths(
        redis,
        run_id,
        {tf.timeframe.value: tf.storage_path for tf in session.timeframes},
    )

    cache = AgentCache(redis)

    async def event_sink(evt: dict) -> None:
        await state.emit(evt)

    async def _runner() -> None:
        state.phase = "running"
        try:
            report = await run_pipeline(
                instrument_name=instrument,
                timeframes=list(session.timeframes),
                cache=cache,
                on_event=event_sink,
                run_id=run_id,
            )
            state.report = report
            state.phase = report.status  # type: ignore[assignment]
            await persist_report(redis, report)
        except Exception as exc:  # noqa: BLE001 — top-level safety net
            log.exception("orchestrator.fatal", run_id=run_id)
            err_report = AnalysisReport(
                disclaimer=DISCLAIMER,
                run_id=run_id,
                instrument_name=instrument,
                status="failed",
                started_at=state.created_at,
                completed_at=datetime.now(UTC),
                timeframes=[],
                synthesis=None,
                error=f"{type(exc).__name__}: {exc}",
            )
            state.report = err_report
            state.phase = "failed"
            await persist_report(redis, err_report)
            await state.emit({"type": "error", "run_id": run_id, "data": {"message": str(exc)}})
        finally:
            await state.close()

    # Background task — survives this request.
    asyncio.create_task(_runner())

    return AnalyzeResponse(
        run_id=run_id,
        websocket_url=f"/ws/runs/{run_id}",
        disclaimer=DISCLAIMER,
    )


@router.get("/runs/{run_id}", response_model=AnalysisReport)
async def get_run(run_id: str, redis: RedisDep) -> AnalysisReport:
    """Fetch a completed (or failed) run report.

    Tries the in-process registry first (fastest, hot data) then falls back
    to Redis (cold reads, surviving cross-restart).
    """
    state = get_registry().get(run_id)
    if state is not None and state.report is not None:
        return state.report
    report = await fetch_report(redis, run_id)
    if report is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No report for run '{run_id}'. Reports expire after 24h.",
        )
    return report


@router.get(
    "/runs/{run_id}/chart-data/{timeframe}",
    response_model=ChartDataResponse,
)
async def get_chart_data(
    run_id: str, timeframe: str, redis: RedisDep
) -> ChartDataResponse:
    """OHLCV bars + overlay metadata for one timeframe of a completed run.

    Bars are streamed straight from the original staged CSV; pivots, channel
    lines, fibs, and validated counts come from the persisted report.
    Returned in Lightweight-Charts-compatible shape (UTC unix-second `time`).
    """
    report = await fetch_report(redis, run_id)
    if report is None:
        # Fall back to in-memory registry (hot path before TTL fully writes).
        state = get_registry().get(run_id)
        report = state.report if state else None
    if report is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No report for run '{run_id}'. Reports expire after 24h.",
        )

    tf_report = next((t for t in report.timeframes if t.timeframe == timeframe), None)
    if tf_report is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Run '{run_id}' has no data for timeframe '{timeframe}'.",
        )

    paths = await fetch_chart_paths(redis, run_id)
    if not paths or timeframe not in paths:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Underlying CSV for timeframe '{timeframe}' is no longer staged.",
        )

    csv_path = Path(paths[timeframe])
    if not csv_path.exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Staged CSV for '{timeframe}' is missing on disk.",
        )

    df, _ = load_csv(csv_path)
    df, _ = validate_csv(df)
    bars: list[ChartBar] = []
    for _, row in df.iterrows():
        ts = int(row["datetime"].timestamp())
        bars.append(
            ChartBar(
                time=ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"]),
            )
        )

    invalidations = [
        v.invalidation
        for v in (
            *tf_report.validation.elliott_surviving,
            *tf_report.validation.neowave_surviving,
        )
        if v.invalidation is not None
    ]

    return ChartDataResponse(
        disclaimer=DISCLAIMER,
        run_id=run_id,
        timeframe=timeframe,
        instrument_name=report.instrument_name,
        bars=bars,
        pivots=list(tf_report.structure.pivots),
        elliott_counts=list(tf_report.validation.elliott_surviving),
        neowave_counts=list(tf_report.validation.neowave_surviving),
        invalidation_levels=invalidations,
        fibonacci_zones=tf_report.structure.fibonacci_zones,
        channel_lines=tf_report.structure.channel_lines,
    )


@router.websocket("/ws/runs/{run_id}")
async def ws_run(websocket: WebSocket, run_id: str) -> None:
    """Stream live events for a run.

    On connect: replays any events already buffered (so a slightly-late
    subscriber doesn't miss the start), then forwards new events as they
    fire. Closes when an end-of-stream sentinel is received.
    """
    state = get_registry().get(run_id)
    if state is None:
        await websocket.close(code=4404, reason="run not found")
        return

    await websocket.accept()
    log.info("ws.run.connected", run_id=run_id, buffered_events=len(state.events))

    cursor = 0
    try:
        while True:
            new_events, closed = await state.wait_for_events_after(cursor)
            for evt in new_events:
                await websocket.send_json(evt)
            cursor += len(new_events)
            if closed:
                break
    except WebSocketDisconnect:
        log.info("ws.run.client_disconnected", run_id=run_id, cursor=cursor)
    finally:
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001 — already closed in some paths
            pass
