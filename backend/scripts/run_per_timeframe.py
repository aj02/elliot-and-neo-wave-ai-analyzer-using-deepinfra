"""Run BOTH per-timeframe agents (Elliott + NEOWave) on a CSV.

Used for the Step 6 + Step 7 checkpoints. Runs the two agents in parallel via
asyncio.gather (which is also what the orchestrator does in Step 10).

Usage:
    python scripts/run_per_timeframe.py --csv samples/NIFTY_1D.csv \
        --instrument "NIFTY 50" --timeframe 1D
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agents.deps import AgentDeps  # noqa: E402
from app.agents.elliott_agent import run_elliott_agent  # noqa: E402
from app.agents.neowave_agent import run_neowave_agent  # noqa: E402
from app.preprocessing.csv_loader import load_csv  # noqa: E402
from app.preprocessing.structure import build  # noqa: E402
from app.preprocessing.validators import validate  # noqa: E402
from app.schemas.timeframe import Timeframe  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True, type=Path)
    p.add_argument("--instrument", default="NIFTY 50")
    p.add_argument("--timeframe", default="1D", choices=[t.value for t in Timeframe])
    p.add_argument("--threshold", type=float, default=None)
    return p.parse_args()


async def main() -> int:
    args = _parse_args()

    df, _ = load_csv(args.csv)
    df, _ = validate(df)
    summary = build(
        df,
        instrument=args.instrument,
        timeframe=Timeframe(args.timeframe),
        threshold_pct=args.threshold,
    )

    print("================ StructureSummary (LLM input) ================")
    print(summary.to_llm_text())
    print("==============================================================\n")

    deps = AgentDeps()
    elliott_out, neowave_out = await asyncio.gather(
        run_elliott_agent(summary, deps=deps),
        run_neowave_agent(summary, deps=deps),
    )

    print("================ Elliott Agent output ========================")
    print(json.dumps(elliott_out[0].model_dump(mode="json"), indent=2))
    print()
    print("================ NEOWave Agent output ========================")
    print(json.dumps(neowave_out[0].model_dump(mode="json"), indent=2))
    print()

    print("================ Cost breakdown ==============================")
    total = 0.0
    for c in deps.costs:
        print(
            f"  {c.agent_name:>8s}  model={c.model:24s}  is_test={c.is_test!s:5}  "
            f"cache_hit={c.cache_hit!s:5}  in={c.input_tokens:>5d}  "
            f"out={c.output_tokens:>5d}  cost=${c.cost_usd:.6f}"
        )
        total += c.cost_usd
    print(f"  {'TOTAL':>8s}  ${total:.6f}")

    if any(c.is_test for c in deps.costs):
        print(
            "\n*** Ran on TestModel (no API key set). Shape validated, prompts not "
            "exercised. Set ANTHROPIC_API_KEY in .env and re-run for the live "
            "checkpoint. ***",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
