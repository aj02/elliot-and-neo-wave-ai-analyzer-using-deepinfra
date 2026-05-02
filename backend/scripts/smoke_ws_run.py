"""Smoke test for the live POST /upload → POST /analyze → WS /ws/runs flow.

Run against a live `wave-agent-backend` container — exercises the actual
event loop the WS handler and orchestrator background task share. This is
what unit tests can't reach because TestClient isolates loops per request.

Usage:
    python scripts/smoke_ws_run.py --backend-url http://localhost:8003 \\
        --csv samples/NIFTY_1D.csv --instrument "NIFTY 50" --timeframe 1D
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx
import websockets


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--backend-url", default="http://localhost:8003")
    p.add_argument("--csv", required=True, type=Path)
    p.add_argument("--instrument", default="NIFTY 50")
    p.add_argument("--timeframe", default="1D")
    return p.parse_args()


async def main() -> int:
    args = _parse_args()
    if not args.csv.exists():
        print(f"FATAL: {args.csv} does not exist", file=sys.stderr)
        return 2

    base = args.backend_url.rstrip("/")
    ws_base = base.replace("https://", "wss://").replace("http://", "ws://")

    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. POST /upload
        files = {"files": (args.csv.name, args.csv.read_bytes(), "text/csv")}
        data = {"instrument_name": args.instrument, "timeframes": args.timeframe}
        upload = await client.post(f"{base}/upload", files=files, data=data)
        upload.raise_for_status()
        upload_body = upload.json()
        if not upload_body.get("accepted"):
            print(f"Upload rejected: {json.dumps(upload_body, indent=2)}", file=sys.stderr)
            return 1
        session_id = upload_body["session_id"]
        print(f"upload OK  session_id={session_id}", flush=True)

        # 2. POST /analyze
        analyze = await client.post(
            f"{base}/analyze",
            json={"session_id": session_id, "instrument_name": args.instrument},
        )
        analyze.raise_for_status()
        analyze_body = analyze.json()
        run_id = analyze_body["run_id"]
        ws_path = analyze_body["websocket_url"]
        print(f"analyze OK run_id={run_id}  ws={ws_path}", flush=True)

        # 3. WS /ws/runs/{run_id} — stream events to stdout until run_completed
        async with websockets.connect(f"{ws_base}{ws_path}") as ws:
            async for raw in ws:
                evt = json.loads(raw)
                t = evt.get("type")
                d = evt.get("data") or {}
                print(f"  [event] {t}: {json.dumps(d)}", flush=True)
                if t in ("run_completed", "error"):
                    break

        # 4. GET /runs/{run_id} for the persisted report
        report = await client.get(f"{base}/runs/{run_id}")
        report.raise_for_status()
        body = report.json()
        print()
        print(f"report.status={body['status']}  total_cost_usd=${body['total_cost_usd']:.6f}")
        if body.get("synthesis", {}).get("scenarios"):
            for s in body["synthesis"]["scenarios"]:
                print(f"  [{s['label']}] rank={s['rank']}: {s['summary'][:140]}")
        return 0 if body["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
