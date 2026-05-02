"use client";

import { motion } from "framer-motion";
import { CheckCircle2, FileText, Loader2, Trash2, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import type { FileValidation } from "@/lib/schemas";
import { TIMEFRAMES, type Timeframe } from "@/lib/timeframes";
import { cn } from "@/lib/utils";

export type FileRowState = "pending" | "validating" | "valid" | "invalid";

export interface FileRowProps {
  file: File;
  timeframe: Timeframe;
  state: FileRowState;
  validation?: FileValidation | null;
  onTimeframeChange: (tf: Timeframe) => void;
  onRemove: () => void;
}

export function FileRow({
  file,
  timeframe,
  state,
  validation,
  onTimeframeChange,
  onRemove,
}: FileRowProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className={cn(
        "flex flex-col gap-3 rounded-md border border-[color:var(--color-border)] bg-[color:var(--color-card)] p-4",
        state === "invalid" && "border-red-700/50",
        state === "valid" && "border-emerald-700/40",
      )}
    >
      <div className="flex items-center gap-3">
        <FileText className="h-4 w-4 text-[color:var(--color-muted)]" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-[color:var(--color-fg)]">{file.name}</p>
          <p className="text-xs text-[color:var(--color-muted)]">
            {(file.size / 1024).toFixed(1)} KB
            {validation ? ` · ${validation.rows} rows` : null}
          </p>
        </div>

        <Select
          aria-label={`Timeframe for ${file.name}`}
          value={timeframe}
          onChange={(e) => onTimeframeChange(e.currentTarget.value as Timeframe)}
        >
          {TIMEFRAMES.map((tf) => (
            <option key={tf} value={tf}>
              {tf}
            </option>
          ))}
        </Select>

        <StatusIndicator state={state} />

        <button
          type="button"
          aria-label={`Remove ${file.name}`}
          onClick={onRemove}
          className="rounded-md p-1.5 text-[color:var(--color-muted)] transition-colors hover:bg-[color:var(--color-bg)] hover:text-[color:var(--color-fg)]"
        >
          <Trash2 className="h-4 w-4" aria-hidden />
        </button>
      </div>

      {validation?.issues.length ? (
        <ul className="space-y-1 border-t border-[color:var(--color-border)] pt-3 text-xs">
          {validation.issues.map((issue, idx) => (
            <li
              key={`${issue.code}-${idx}`}
              className={cn(
                "flex items-start gap-2",
                issue.severity === "error"
                  ? "text-red-300"
                  : "text-amber-300",
              )}
            >
              <Badge tone={issue.severity === "error" ? "error" : "warning"}>
                {issue.severity}
              </Badge>
              <span className="flex-1">{issue.message}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </motion.div>
  );
}

function StatusIndicator({ state }: { state: FileRowState }) {
  if (state === "validating") {
    return (
      <span className="flex items-center gap-1.5 text-xs text-[color:var(--color-muted)]">
        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
        Validating
      </span>
    );
  }
  if (state === "valid") {
    return (
      <span className="flex items-center gap-1.5 text-xs text-emerald-300">
        <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
        Valid
      </span>
    );
  }
  if (state === "invalid") {
    return (
      <span className="flex items-center gap-1.5 text-xs text-red-300">
        <XCircle className="h-3.5 w-3.5" aria-hidden />
        Invalid
      </span>
    );
  }
  return (
    <Badge tone="muted" className="text-xs">
      Pending
    </Badge>
  );
}
