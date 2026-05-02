"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";

import { DisclaimerBanner } from "@/components/disclaimer-banner";
import { ReportMethodology } from "@/components/report-methodology";
import { ReportOverview } from "@/components/report-overview";
import { ReportTimeframe } from "@/components/report-timeframe";
import { Badge } from "@/components/ui/badge";
import { Tabs } from "@/components/ui/tabs";
import { apiBase } from "@/lib/api";
import type { AnalysisReport } from "@/lib/report-types";


async function fetchReport(runId: string): Promise<AnalysisReport> {
  const resp = await fetch(`${apiBase}/runs/${runId}`);
  if (!resp.ok) {
    throw new Error(`failed to fetch run ${runId}: ${resp.status}`);
  }
  return (await resp.json()) as AnalysisReport;
}


export default function ReportPage() {
  const params = useParams<{ run_id: string }>();
  const runId = params.run_id;
  const [tab, setTab] = useState<string>("overview");

  const { data: report, isLoading, error } = useQuery({
    queryKey: ["report", runId],
    queryFn: () => fetchReport(runId),
  });

  if (isLoading) {
    return (
      <section className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-12">
        <div className="flex items-center gap-3 text-sm text-[color:var(--color-muted)]">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Loading report…
        </div>
      </section>
    );
  }

  if (error || !report) {
    return (
      <section className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-12">
        <div className="rounded-md border border-red-700/40 bg-red-950/30 p-3 text-sm text-red-200">
          Failed to load report: {(error as Error)?.message ?? "unknown error"}
        </div>
      </section>
    );
  }

  const tabOptions = [
    { value: "overview", label: "Overview" },
    ...report.timeframes.map((tf) => ({
      value: tf.timeframe,
      label: <span className="font-mono">{tf.timeframe}</span>,
    })),
    { value: "synthesis", label: "Synthesis" },
    { value: "methodology", label: "Methodology" },
  ];

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-12">
      <header className="flex flex-col gap-3">
        <span className="text-xs font-medium uppercase tracking-[0.18em] text-[color:var(--color-accent)]">
          Analysis report
        </span>
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className="text-3xl font-semibold tracking-tight text-[color:var(--color-fg)] sm:text-4xl">
            {report.instrument_name}
          </h1>
          {report.timeframes.map((tf) => (
            <Badge key={tf.timeframe} tone="muted" className="font-mono">
              {tf.timeframe}
            </Badge>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs text-[color:var(--color-muted)]">
          <span>
            run <code className="font-mono">{report.run_id}</code>
          </span>
          <span aria-hidden>·</span>
          <span>
            {report.completed_at
              ? new Date(report.completed_at).toLocaleString()
              : "in progress"}
          </span>
          <span aria-hidden>·</span>
          <span>${report.total_cost_usd.toFixed(6)} spent</span>
        </div>
      </header>

      <DisclaimerBanner />

      <Tabs value={tab} onValueChange={setTab} options={tabOptions} />

      {tab === "overview" ? <ReportOverview synthesis={report.synthesis} /> : null}
      {report.timeframes.map((tf) =>
        tab === tf.timeframe ? (
          <ReportTimeframe key={tf.timeframe} runId={runId} tf={tf} />
        ) : null,
      )}
      {tab === "synthesis" ? <ReportOverview synthesis={report.synthesis} /> : null}
      {tab === "methodology" ? <ReportMethodology report={report} /> : null}
    </section>
  );
}
