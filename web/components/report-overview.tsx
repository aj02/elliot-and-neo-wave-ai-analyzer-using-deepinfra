"use client";

import { motion } from "framer-motion";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { SynthesisReport } from "@/lib/report-types";


type Tone = "default" | "success" | "warning" | "error" | "muted";


export function ReportOverview({ synthesis }: { synthesis: SynthesisReport | null }) {
  const scenarios = synthesis?.scenarios ?? [];

  if (scenarios.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>No surviving scenarios</CardTitle>
          <CardDescription>
            The deterministic Validator rejected every count proposed by the
            agents, or the Synthesis agent could not commit to a structural
            reading on this dataset. Try a longer history or a different
            timeframe set.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="grid gap-4">
      {scenarios.map((s, idx) => {
        const supporting = s.supporting ?? [];
        const invalidations = s.invalidation_levels ?? [];
        return (
          <motion.div
            key={`${s.rank}-${idx}`}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, ease: "easeOut", delay: Math.min(idx * 0.04, 0.2) }}
          >
            <Card>
              <CardHeader className="flex flex-row items-start justify-between gap-4">
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <Badge tone={labelTone(s.label)}>{s.label ?? "Scenario"}</Badge>
                    <span className="text-xs text-[color:var(--color-muted)]">rank {s.rank ?? idx + 1}</span>
                  </div>
                  <CardTitle className="text-base">{s.summary ?? ""}</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm leading-relaxed text-[color:var(--color-muted)]">
                {s.cross_timeframe_alignment ? (
                  <p>
                    <span className="font-medium text-[color:var(--color-fg)]">Cross-timeframe.</span>{" "}
                    {s.cross_timeframe_alignment}
                  </p>
                ) : null}
                {s.cross_framework_agreement ? (
                  <p>
                    <span className="font-medium text-[color:var(--color-fg)]">Cross-framework.</span>{" "}
                    {s.cross_framework_agreement}
                  </p>
                ) : null}

                {invalidations.length > 0 ? (
                  <div className="rounded-md border border-[color:var(--color-border)] bg-[color:var(--color-bg)] p-3">
                    <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[color:var(--color-muted)]">
                      Deterministic invalidation levels (computed in Python)
                    </p>
                    <ul className="space-y-1.5 text-xs">
                      {invalidations.map((inv, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <Badge tone="warning" className="font-mono">
                            {inv?.direction ?? "?"} {formatPrice(inv?.price)}
                          </Badge>
                          <span className="text-[color:var(--color-muted)]">{inv?.reason ?? ""}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {supporting.length > 0 ? (
                  <p className="text-xs">
                    <span className="font-medium text-[color:var(--color-fg)]">Supporting counts.</span>{" "}
                    {supporting.map((ref, i) => (
                      <span key={i}>
                        {i > 0 ? " · " : ""}
                        <code className="rounded bg-[color:var(--color-bg)] px-1.5 py-0.5 font-mono">
                          {(ref?.framework ?? "?").charAt(0).toUpperCase()}
                          {ref?.count_idx ?? "?"} ({ref?.timeframe ?? "?"})
                        </code>
                      </span>
                    ))}
                  </p>
                ) : null}
              </CardContent>
            </Card>
          </motion.div>
        );
      })}
      {synthesis?.methodology_note ? (
        <p className="text-xs text-[color:var(--color-muted)]">
          <strong className="text-[color:var(--color-fg)]">Note.</strong>{" "}
          {synthesis.methodology_note}
        </p>
      ) : null}
    </div>
  );
}


function formatPrice(price: number | undefined | null): string {
  if (typeof price !== "number" || !Number.isFinite(price)) return "—";
  return price.toFixed(2);
}


function labelTone(label: string | undefined | null): Tone {
  switch (label) {
    case "Primary":
      return "success";
    case "Alternate":
      return "warning";
    case "Counter":
      return "muted";
    default:
      return "default";
  }
}
