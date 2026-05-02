"use client";

import { motion } from "framer-motion";
import { AlertTriangle, ArrowRight, CheckCircle2, Loader2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AgentRow } from "@/components/agent-row";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  type AgentRowState,
  useDerivedRunState,
  useRunEvents,
} from "@/lib/use-run-events";


export default function AnalyzePage() {
  const params = useParams<{ run_id: string }>();
  const router = useRouter();
  const runId = params.run_id;

  const { events, status, error } = useRunEvents(runId);
  const derived = useDerivedRunState(events);

  // Auto-redirect to /report once the run completes (after a short pause so
  // the user sees the "completed" state).
  useEffect(() => {
    if (derived.runPhase === "completed") {
      const t = setTimeout(() => router.replace(`/report/${runId}`), 1500);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [derived.runPhase, router, runId]);

  const startedAt = events[0]?.at;
  const elapsedMs = useElapsedMs(startedAt, derived.runPhase);
  const grouped = useMemo(() => groupByTimeframe(derived), [derived]);

  return (
    <section className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-12">
      <motion.header
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
        className="flex flex-col gap-2"
      >
        <span className="text-xs font-medium uppercase tracking-[0.18em] text-[color:var(--color-accent)]">
          Live analysis
        </span>
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className="text-2xl font-semibold tracking-tight text-[color:var(--color-fg)]">
            Run <code className="font-mono text-base text-[color:var(--color-muted)]">{runId}</code>
          </h1>
          {derived.timeframes.length > 0 ? (
            <div className="flex gap-1.5">
              {derived.timeframes.map((tf) => (
                <Badge key={tf} tone="muted" className="font-mono">
                  {tf}
                </Badge>
              ))}
            </div>
          ) : null}
        </div>
        <div className="flex items-center gap-3 text-xs text-[color:var(--color-muted)]">
          <ConnectionDot status={status} />
          <span>
            {status === "open"
              ? "live"
              : status === "connecting"
              ? "connecting…"
              : status}
          </span>
          <span aria-hidden>·</span>
          <span>{(elapsedMs / 1000).toFixed(1)}s elapsed</span>
        </div>
      </motion.header>

      {error ? <ErrorPanel message={error} /> : null}
      {derived.runPhase === "error" ? (
        <ErrorPanel message={derived.errorMessage ?? "Run failed."} />
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Agent activity</CardTitle>
          <CardDescription>
            Per-timeframe Elliott + NEOWave agents run in parallel; the
            deterministic Validator filters each agent&apos;s output before it
            reaches the user.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {grouped.length === 0 ? (
            <div className="flex items-center gap-3 py-6 text-sm text-[color:var(--color-muted)]">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              <span>Waiting for the run to start…</span>
            </div>
          ) : (
            grouped.map(({ timeframe, rows, validation }) => (
              <div key={timeframe} className="space-y-2">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-[color:var(--color-fg)]">
                    Timeframe <code className="font-mono">{timeframe}</code>
                  </h3>
                  {validation ? (
                    <span className="text-xs text-[color:var(--color-muted)]">
                      Validator:{" "}
                      <strong className="text-emerald-300">
                        {validation.elliott_surviving + validation.neowave_surviving}
                      </strong>{" "}
                      surviving ·{" "}
                      <strong className="text-red-300">
                        {validation.elliott_rejected + validation.neowave_rejected}
                      </strong>{" "}
                      rejected
                    </span>
                  ) : null}
                </div>
                <div className="space-y-2">
                  {rows.map((row, idx) => (
                    <AgentRow key={`${row.agent}:${row.timeframe}`} row={row} index={idx} />
                  ))}
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Cross-timeframe synthesis</CardTitle>
          <CardDescription>
            One Sonnet call combines the surviving counts across every
            timeframe. Numeric invalidation prices are then attached
            deterministically by Python — never generated by the model.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SynthesisRow
            phase={derived.synthesisPhase}
            scenarios={derived.synthesisScenarios}
          />
        </CardContent>
      </Card>

      {derived.runPhase === "completed" ? (
        <div className="flex items-center justify-between rounded-md border border-emerald-700/30 bg-emerald-950/20 p-4 text-sm">
          <div className="flex items-center gap-2 text-emerald-200">
            <CheckCircle2 className="h-4 w-4" aria-hidden />
            <span>Run completed. Redirecting to report…</span>
          </div>
          <Button variant="primary" size="sm">
            <Link href={`/report/${runId}`} className="flex items-center gap-1.5">
              View report <ArrowRight className="h-3.5 w-3.5" aria-hidden />
            </Link>
          </Button>
        </div>
      ) : null}
    </section>
  );
}


// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------


type GroupedRows = {
  timeframe: string;
  rows: AgentRowState[];
  validation:
    | {
        elliott_surviving: number;
        elliott_rejected: number;
        neowave_surviving: number;
        neowave_rejected: number;
      }
    | undefined;
};


function groupByTimeframe(
  derived: ReturnType<typeof useDerivedRunState>,
): GroupedRows[] {
  return derived.timeframes.map((tf) => ({
    timeframe: tf,
    rows: derived.agentRows.filter((r) => r.timeframe === tf),
    validation: derived.validationByTimeframe[tf],
  }));
}


function useElapsedMs(startedAt: string | undefined, phase: string): number {
  const [now, setNow] = useState<number>(() => Date.now());
  useEffect(() => {
    if (phase !== "running") return undefined;
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, [phase]);
  if (!startedAt) return 0;
  return Math.max(0, now - new Date(startedAt).getTime());
}


function ConnectionDot({
  status,
}: {
  status: "connecting" | "open" | "closed" | "error";
}) {
  const cls =
    status === "open"
      ? "bg-emerald-400 shadow-emerald-400/40"
      : status === "connecting"
      ? "bg-amber-400 shadow-amber-400/40"
      : "bg-red-400 shadow-red-400/40";
  return (
    <span
      aria-hidden
      className={`h-2 w-2 rounded-full shadow-[0_0_8px] ${cls}`}
    />
  );
}


function ErrorPanel({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2 rounded-md border border-red-700/40 bg-red-950/30 p-3 text-sm text-red-200">
      <AlertTriangle className="mt-0.5 h-4 w-4" aria-hidden />
      <span>{message}</span>
    </div>
  );
}


function SynthesisRow({
  phase,
  scenarios,
}: {
  phase: "queued" | "running" | "completed";
  scenarios: number | undefined;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex items-center justify-between rounded-md border border-[color:var(--color-border)] bg-[color:var(--color-card)] px-4 py-3 text-sm"
    >
      <div className="flex items-center gap-3">
        {phase === "completed" ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-400" aria-hidden />
        ) : phase === "running" ? (
          <Loader2 className="h-4 w-4 animate-spin text-[color:var(--color-accent)]" aria-hidden />
        ) : (
          <span className="h-4 w-4 rounded-full border border-[color:var(--color-muted)]" />
        )}
        <span className="font-medium text-[color:var(--color-fg)]">
          Synthesis (Sonnet)
        </span>
      </div>
      <span className="text-xs text-[color:var(--color-muted)]">
        {phase === "queued" ? "queued" : null}
        {phase === "running" ? "running…" : null}
        {phase === "completed"
          ? `${scenarios ?? 0} scenario${scenarios === 1 ? "" : "s"}`
          : null}
      </span>
    </motion.div>
  );
}
