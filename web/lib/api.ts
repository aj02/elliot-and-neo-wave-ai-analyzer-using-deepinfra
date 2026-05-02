/** Typed wave-agent API client. Mirrors the FastAPI shape via Zod. */

import {
  AnalyzeResponseSchema,
  UploadResponseSchema,
  type AnalyzeResponse,
  type UploadResponse,
} from "@/lib/schemas";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

const WS_BASE =
  process.env.NEXT_PUBLIC_WS_URL?.replace(/\/$/, "") ?? "ws://localhost:8000";

export const apiBase = BASE_URL;
export const wsBase = WS_BASE;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function jsonOrThrow<T>(resp: Response, schema: { parse: (raw: unknown) => T }): Promise<T> {
  const raw: unknown = await resp.json().catch(() => null);
  if (!resp.ok) {
    const message =
      typeof raw === "object" && raw !== null && "detail" in raw
        ? String((raw as { detail: unknown }).detail)
        : `${resp.status} ${resp.statusText}`;
    throw new ApiError(resp.status, message, raw);
  }
  return schema.parse(raw);
}

/** POST /upload — multipart upload of OHLCV CSVs with timeframe labels. */
export async function postUpload(args: {
  instrumentName: string;
  files: { file: File; timeframe: string }[];
}): Promise<UploadResponse> {
  const fd = new FormData();
  fd.append("instrument_name", args.instrumentName);
  for (const item of args.files) {
    fd.append("files", item.file);
    fd.append("timeframes", item.timeframe);
  }
  const resp = await fetch(`${BASE_URL}/upload`, { method: "POST", body: fd });
  return jsonOrThrow(resp, UploadResponseSchema);
}

/** POST /analyze — kick off a run on a previously-uploaded session. */
export async function postAnalyze(args: {
  sessionId: string;
  instrumentName?: string;
}): Promise<AnalyzeResponse> {
  const resp = await fetch(`${BASE_URL}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: args.sessionId,
      instrument_name: args.instrumentName ?? null,
    }),
  });
  return jsonOrThrow(resp, AnalyzeResponseSchema);
}

/** GET /runs/{run_id} — fetch a completed (or failed) report. */
export async function getRun(runId: string): Promise<unknown> {
  const resp = await fetch(`${BASE_URL}/runs/${runId}`);
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new ApiError(resp.status, text || resp.statusText);
  }
  return resp.json();
}

/** WebSocket URL for live run events. */
export function runEventStreamUrl(websocketPath: string): string {
  return `${WS_BASE}${websocketPath}`;
}
