"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import * as React from "react";

import { PriceChart } from "@/components/price-chart";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiBase } from "@/lib/api";
import type { ChartDataResponse, TimeframeReport } from "@/lib/report-types";


async function fetchChartData(runId: string, timeframe: string): Promise<ChartDataResponse> {
  const resp = await fetch(`${apiBase}/runs/${runId}/chart-data/${timeframe}`);
  if (!resp.ok) {
    throw new Error(`chart-data fetch failed: ${resp.status} ${resp.statusText}`);
  }
  return (await resp.json()) as ChartDataResponse;
}


export function ReportTimeframe({
  runId,
  tf,
}: {
  runId: string;
  tf: TimeframeReport;
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["chart-data", runId, tf.timeframe],
    queryFn: () => fetchChartData(runId, tf.timeframe),
    staleTime: Infinity,
  });

  const [showPivots, setShowPivots] = React.useState(true);
  const [showChannel, setShowChannel] = React.useState(true);
  const [showFibs, setShowFibs] = React.useState(true);
  const [showInvalidation, setShowInvalidation] = React.useState(true);
  const [activeCountIdx, setActiveCountIdx] = React.useState<number>(0);

  if (isLoading) {
    return (
      <div className="flex items-center gap-3 py-12 text-sm text-[color:var(--color-muted)]">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Loading chart data…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-md border border-red-700/40 bg-red-950/30 p-3 text-sm text-red-200">
        Failed to load chart data: {(error as Error)?.message ?? "unknown error"}
      </div>
    );
  }

  const fibs = data.fibonacci_zones?.last_impulse_retracements ?? [];
  // Show invalidation levels for the selected count first, falling back to all surviving counts.
  const survivingElliott = data.elliott_counts;
  const activeCount = survivingElliott[activeCountIdx];
  const invalidationLevels = activeCount?.invalidation
    ? [activeCount.invalidation]
    : data.invalidation_levels;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {survivingElliott.length > 0 ? (
            <div className="flex items-center gap-1">
              <span className="text-xs text-[color:var(--color-muted)]">Count:</span>
              {survivingElliott.map((c, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setActiveCountIdx(i)}
                  className={
                    "rounded border px-2 py-0.5 text-xs transition " +
                    (i === activeCountIdx
                      ? "border-[color:var(--color-accent)] bg-[color:var(--color-accent)]/10 text-[color:var(--color-fg)]"
                      : "border-[color:var(--color-border)] text-[color:var(--color-muted)] hover:text-[color:var(--color-fg)]")
                  }
                >
                  E{i} · {c.count.pattern} · {c.count.current_wave}
                </button>
              ))}
            </div>
          ) : (
            <span className="text-xs text-[color:var(--color-muted)]">
              No Elliott counts survived rule validation on this timeframe.
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs text-[color:var(--color-muted)]">
          <Toggle label="Pivots" checked={showPivots} onChange={setShowPivots} />
          <Toggle label="Channel" checked={showChannel} onChange={setShowChannel} />
          <Toggle label="Fibs" checked={showFibs} onChange={setShowFibs} />
          <Toggle label="Invalidation" checked={showInvalidation} onChange={setShowInvalidation} />
        </div>
      </div>

      <PriceChart
        bars={data.bars}
        pivots={data.pivots}
        channelLines={data.channel_lines}
        fibonacciRetracements={fibs}
        invalidationLevels={invalidationLevels}
        showPivots={showPivots}
        showChannel={showChannel}
        showFibs={showFibs}
        showInvalidation={showInvalidation}
      />

      {activeCount ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Active count rationale —{" "}
              <span className="font-mono text-sm text-[color:var(--color-muted)]">
                {activeCount.count.pattern} · {activeCount.count.degree}
              </span>
            </CardTitle>
            <CardDescription>{activeCount.count.rationale}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-md border border-[color:var(--color-border)] bg-[color:var(--color-bg)] p-3 text-xs">
                <p className="mb-1 font-medium text-[color:var(--color-fg)]">
                  Wave structure
                </p>
                <ul className="space-y-1 font-mono text-[11px] text-[color:var(--color-muted)]">
                  {activeCount.count.waves.map((w) => (
                    <li key={w.label}>
                      {w.label}: pivot #{w.start_pivot_idx} → #{w.end_pivot_idx}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="rounded-md border border-[color:var(--color-border)] bg-[color:var(--color-bg)] p-3 text-xs">
                <p className="mb-1 font-medium text-[color:var(--color-fg)]">
                  Rule compliance
                </p>
                <ul className="space-y-1">
                  {activeCount.compliance.rule_results.map((r) => (
                    <li key={r.rule_id} className="flex items-start gap-2">
                      <Badge tone={r.passed ? "success" : "error"} className="font-mono">
                        {r.rule_id}
                      </Badge>
                      <span className="text-[color:var(--color-muted)]">{r.name}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Structural snapshot</CardTitle>
          <CardDescription>
            Deterministic geometric observations (not wave counts).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-3 text-xs">
            <Stat label="Bars" value={data.bars.length.toString()} />
            <Stat label="Pivots" value={data.pivots.length.toString()} />
            <Stat
              label="Channel slope"
              value={`${tf.structure.channel_lines.slope_angle_deg.toFixed(1)}°`}
            />
            <Stat label="ATR(14)" value={tf.structure.atr_14.toFixed(2)} />
            <Stat label="Realized vol" value={`${tf.structure.realized_vol_20_pct.toFixed(2)}%`} />
            <Stat
              label="Price position"
              value={`${(tf.structure.price_position_pct * 100).toFixed(0)}% of recent range`}
            />
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {tf.structure.structural_phase_hints.map((hint, i) => (
              <Badge key={i} tone="muted">
                {hint}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}


function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-1.5 select-none">
      <input
        type="checkbox"
        className="h-3.5 w-3.5 accent-[color:var(--color-accent)]"
        checked={checked}
        onChange={(e) => onChange(e.currentTarget.checked)}
      />
      <span>{label}</span>
    </label>
  );
}


function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[color:var(--color-muted)]">{label}</span>
      <span className="font-mono text-[color:var(--color-fg)]">{value}</span>
    </div>
  );
}
