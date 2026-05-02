"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

type Tone = "default" | "success" | "warning" | "error" | "muted";

const TONES: Record<Tone, string> = {
  default:
    "border-[color:var(--color-border)] text-[color:var(--color-fg)] bg-[color:var(--color-card)]",
  success:
    "border-emerald-700/40 text-emerald-300 bg-emerald-900/30",
  warning:
    "border-amber-700/40 text-amber-300 bg-amber-900/30",
  error:
    "border-red-700/40 text-red-300 bg-red-900/30",
  muted:
    "border-[color:var(--color-border)] text-[color:var(--color-muted)] bg-[color:var(--color-bg)]",
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

export const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, tone = "default", ...props }, ref) => (
    <span
      ref={ref}
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        TONES[tone],
        className,
      )}
      {...props}
    />
  ),
);
Badge.displayName = "Badge";
