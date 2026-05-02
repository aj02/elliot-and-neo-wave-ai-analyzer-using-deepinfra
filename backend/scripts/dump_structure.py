"""Run the preprocessing pipeline on a CSV and print the StructureSummary.

Used for the Step 4 checkpoint and as a developer sanity check thereafter.

Usage:
    python scripts/dump_structure.py --csv samples/NIFTY_1D.csv \
        --instrument "NIFTY 50" --timeframe 1D
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

# Allow running both from the repo root and from /app inside the container.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

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
    p.add_argument(
        "--print-json",
        action="store_true",
        help="Also dump the full structured JSON (verbose).",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    df, _ = load_csv(args.csv)
    df, warnings = validate(df)
    if warnings:
        print(f"# {len(warnings)} warning(s) ignored for this dump:", file=sys.stderr)
        for w in warnings:
            print(f"#   {w.code}: {w.message}", file=sys.stderr)

    summary = build(
        df,
        instrument=args.instrument,
        timeframe=Timeframe(args.timeframe),
        threshold_pct=args.threshold,
    )

    text = summary.to_llm_text()
    chars = len(text)
    approx_tokens = math.ceil(chars / 4)

    print("================ StructureSummary (LLM input text) ================")
    print(text)
    print("====================================================================")
    print(
        f"chars={chars}  approx_tokens={approx_tokens}  bars={summary.bar_count}  "
        f"pivots={len(summary.pivots)}  recent_pivots={len(summary.recent_pivots)}",
        flush=True,
    )

    if args.print_json:
        print()
        print("---- structured JSON ----")
        print(json.dumps(summary.model_dump(mode="json"), indent=2, default=str))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
