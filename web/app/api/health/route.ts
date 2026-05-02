import { NextResponse } from "next/server";

const DISCLAIMER =
  "wave-agent is an educational and engineering demo. It is NOT investment advice " +
  "and NOT a trading recommendation. The system proposes structural interpretations " +
  "and deterministic levels; humans decide actions.";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export function GET() {
  return NextResponse.json({
    status: "ok",
    service: "wave-agent-web",
    disclaimer: DISCLAIMER,
  });
}
