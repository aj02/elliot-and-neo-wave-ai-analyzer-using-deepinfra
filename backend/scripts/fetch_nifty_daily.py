"""Fetch NIFTY 50 daily OHLCV from Yahoo Finance and write the canonical CSV.

Usage (inside the backend container):
    python scripts/fetch_nifty_daily.py [--range 2y] [--out samples/NIFTY_1D.csv]

The Yahoo chart API is unauthenticated and returns enough history for a
multi-year structural picture. This script exists only to generate sample
data committed to the repo; it is not part of the runtime path.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


SYMBOL = "%5ENSEI"  # ^NSEI URL-encoded
USER_AGENT = "wave-agent-sample-fetcher/0.1 (educational demo)"


def fetch(range_: str = "2y", interval: str = "1d") -> dict:
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{SYMBOL}"
        f"?range={range_}&interval={interval}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def to_canonical_rows(payload: dict) -> list[dict[str, object]]:
    result = payload["chart"]["result"][0]
    timestamps: list[int] = result["timestamp"]
    quote = result["indicators"]["quote"][0]
    rows: list[dict[str, object]] = []
    for i, ts in enumerate(timestamps):
        o, h, l, c, v = quote["open"][i], quote["high"][i], quote["low"][i], quote["close"][i], quote["volume"][i]
        if None in (o, h, l, c):  # holidays / partial bars
            continue
        rows.append(
            {
                "datetime": datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d"),
                "open": round(float(o), 4),
                "high": round(float(h), 4),
                "low": round(float(l), 4),
                "close": round(float(c), 4),
                "volume": int(v) if v is not None else 0,
            }
        )
    return rows


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["datetime", "open", "high", "low", "close", "volume"]
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--range", default="2y", help="Yahoo range string, e.g. 2y, 5y, max.")
    parser.add_argument("--out", default="samples/NIFTY_1D.csv", help="Output CSV path.")
    args = parser.parse_args()

    payload = fetch(range_=args.range)
    rows = to_canonical_rows(payload)
    if not rows:
        print("No usable rows in response.", file=sys.stderr)
        return 1
    out_path = Path(args.out)
    write_csv(rows, out_path)
    print(f"Wrote {len(rows)} rows to {out_path} ({rows[0]['datetime']} .. {rows[-1]['datetime']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
