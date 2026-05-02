"""Run the full end-to-end pipeline on a CSV (or set of CSVs) and dump the report.

Used for the Step 9 / Step 10 checkpoints and as a developer sanity check.

Usage (single timeframe):
    python scripts/run_full_pipeline.py --instrument "NIFTY 50" \\
        --tf 1D=samples/NIFTY_1D.csv

Multi-timeframe:
    python scripts/run_full_pipeline.py --instrument "NIFTY 50" \\
        --tf 1D=samples/NIFTY_1D.csv --tf 1W=samples/NIFTY_1W.csv
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agents.orchestrator import run_pipeline  # noqa: E402
from app.schemas.input import UploadedTimeframe  # noqa: E402
from app.schemas.timeframe import Timeframe  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--instrument", default="NIFTY 50")
    p.add_argument(
        "--tf",
        action="append",
        required=True,
        help="Repeatable: 1D=path/to/file.csv  1W=path/to/file.csv ...",
    )
    p.add_argument("--print-report", action="store_true", help="Dump the full report JSON.")
    return p.parse_args()


def _split_tf(spec: str) -> tuple[Timeframe, Path]:
    label, _, path = spec.partition("=")
    return Timeframe(label.strip()), Path(path.strip())


async def _print_event(evt: dict) -> None:
    t = evt.get("type")
    data = evt.get("data") or {}
    print(f"[event] {t}: {json.dumps(data)}", flush=True)


async def main() -> int:
    args = _parse_args()
    timeframes: list[UploadedTimeframe] = []
    for spec in args.tf:
        tf, path = _split_tf(spec)
        if not path.exists():
            print(f"FATAL: {path} does not exist", file=sys.stderr)
            return 2
        # Quick row count for the UploadedTimeframe metadata.
        rows = sum(1 for _ in path.open("r", encoding="utf-8")) - 1
        timeframes.append(
            UploadedTimeframe(
                filename=path.name,
                timeframe=tf,
                rows=rows,
                date_range=(datetime.now(UTC), datetime.now(UTC)),  # placeholder
                storage_path=str(path),
                warnings=[],
            )
        )

    report = await run_pipeline(
        instrument_name=args.instrument,
        timeframes=timeframes,
        on_event=_print_event,
    )

    print()
    print("================ Run summary ============================")
    print(f"  run_id:         {report.run_id}")
    print(f"  status:         {report.status}")
    print(f"  duration:       {(report.completed_at - report.started_at).total_seconds():.2f}s"
          if report.completed_at else "  duration:       n/a")
    print(f"  timeframes:     {len(report.timeframes)}")
    print(f"  total cost:     ${report.total_cost_usd:.6f}")
    print()
    if report.synthesis and report.synthesis.scenarios:
        print("================ Synthesis scenarios =====================")
        for s in report.synthesis.scenarios:
            print(f"  [{s.label}] rank={s.rank}")
            print(f"    summary: {s.summary[:200]}")
            for inv in s.invalidation_levels:
                print(f"    invalidation: {inv.direction} {inv.price:.2f} — {inv.reason[:80]}")
            print()
    else:
        print("(no synthesis scenarios — TestModel output or no surviving counts)")

    print()
    print("================ Cost breakdown =========================")
    for c in report.cost_breakdown:
        print(
            f"  {c.agent_name:>10s}  model={c.model:24s}  "
            f"is_test={c.is_test!s:5}  cache_hit={c.cache_hit!s:5}  "
            f"in={c.input_tokens:>5d}  out={c.output_tokens:>5d}  "
            f"cost=${c.cost_usd:.6f}"
        )

    if any(c.is_test for c in report.cost_breakdown):
        print(
            "\n*** Ran on TestModel (no API key set). Shape validated; prompts not "
            "exercised. Set ANTHROPIC_API_KEY in .env for the live checkpoint. ***",
            file=sys.stderr,
        )

    if args.print_report:
        print()
        print("================ Full report JSON ========================")
        print(json.dumps(report.model_dump(mode="json"), indent=2, default=str))

    return 0 if report.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
