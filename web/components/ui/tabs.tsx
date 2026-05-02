"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

export interface TabsProps {
  value: string;
  onValueChange: (next: string) => void;
  options: { value: string; label: React.ReactNode; badge?: React.ReactNode }[];
  className?: string;
}

export function Tabs({ value, onValueChange, options, className }: TabsProps) {
  return (
    <div
      role="tablist"
      aria-orientation="horizontal"
      className={cn(
        "flex flex-wrap gap-1 rounded-md border border-[color:var(--color-border)] bg-[color:var(--color-card)] p-1",
        className,
      )}
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onValueChange(opt.value)}
            className={cn(
              "flex items-center gap-2 rounded px-3 py-1.5 text-xs font-medium transition-colors duration-150",
              active
                ? "bg-[color:var(--color-bg)] text-[color:var(--color-fg)]"
                : "text-[color:var(--color-muted)] hover:text-[color:var(--color-fg)]",
            )}
          >
            {opt.label}
            {opt.badge}
          </button>
        );
      })}
    </div>
  );
}
