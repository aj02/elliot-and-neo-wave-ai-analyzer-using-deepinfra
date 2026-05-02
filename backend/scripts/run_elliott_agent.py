"""Run the Elliott Wave Agent on a CSV and print the structured output.

Used for the Step 6 checkpoint and as a developer sanity check.

Usage:
    python scripts/run_elliott_agent.py --csv samples/NIFTY_1D.csv \
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

from app.agents.elliott_agent import run_elliott_agent  # noqa: E402
from app.preprocessing.csv_loader import load_csv  # noqa: E402
from app.preprocessing.structure import build  # noqa: E402
from app.preprocessing.validators import validate  # noqa: E402
from app.schemas.timeframe import Timeframe  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True, type=Path)
    p.add_argument("--instrument", default="NIFTY 50")
    p.add_argument(
        "--timeframe",
        default="1D",
        choices=[t.value for t in Timeframe],
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="ZigZag threshold % (auto-tuned if omitted).",
    )
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

    output, cost = await run_elliott_agent(summary)

    print("================ Elliott Agent output ========================")
    print(json.dumps(output.model_dump(mode="json"), indent=2))
    print("==============================================================\n")

    print(
        f"model={cost.model}  is_test={cost.is_test}  cache_hit={cost.cache_hit}  "
        f"input_tokens={cost.input_tokens}  output_tokens={cost.output_tokens}  "
        f"cost_usd={cost.cost_usd}",
        flush=True,
    )
    if cost.is_test:
        print(
            "\n*** Ran on TestModel (no API key set). The structured shape is "
            "validated, but the prompt itself was not exercised. Set "
            "ANTHROPIC_API_KEY in .env and re-run to see real output. ***",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
