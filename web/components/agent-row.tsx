"use client";

import { motion } from "framer-motion";
import { CheckCircle2, CircleDot, Database, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { AgentRowState } from "@/lib/use-run-events";
import { cn } from "@/lib/utils";


export function AgentRow({ row, index }: { row: AgentRowState; index: number }) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: "easeOut", delay: Math.min(index * 0.04, 0.2) }}
      className={cn(
        "flex items-center justify-between rounded-md border border-[color:var(--color-border)] bg-[color:var(--color-card)] px-4 py-3 text-sm",
        row.phase === "completed" && "border-emerald-700/30",
        row.phase === "running" && "border-[color:var(--color-accent)]/50",
      )}
    >
      <div className="flex items-center gap-3">
        <PhaseGlyph phase={row.phase} />
        <div className="flex items-baseline gap-2">
          <span className="font-medium capitalize text-[color:var(--color-fg)]">
            {row.agent}
          </span>
          <Badge tone="muted" className="font-mono">
            {row.timeframe}
          </Badge>
        </div>
      </div>
      <div className="flex items-center gap-2 text-xs text-[color:var(--color-muted)]">
        {row.phase === "queued" ? <span>queued</span> : null}
        {row.phase === "running" ? <span>running…</span> : null}
        {row.phase === "completed" ? (
          <>
            {row.cacheHit ? (
              <Badge tone="muted">
                <Database className="mr-1 h-3 w-3" aria-hidden /> cached
              </Badge>
            ) : null}
            <span>
              {row.candidates ?? 0} candidate{row.candidates === 1 ? "" : "s"}
            </span>
          </>
        ) : null}
      </div>
    </motion.div>
  );
}

function PhaseGlyph({ phase }: { phase: AgentRowState["phase"] }) {
  if (phase === "completed") {
    return <CheckCircle2 className="h-4 w-4 text-emerald-400" aria-hidden />;
  }
  if (phase === "running") {
    return <Loader2 className="h-4 w-4 animate-spin text-[color:var(--color-accent)]" aria-hidden />;
  }
  return <CircleDot className="h-4 w-4 text-[color:var(--color-muted)]" aria-hidden />;
}
