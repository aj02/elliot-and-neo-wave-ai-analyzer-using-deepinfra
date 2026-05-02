"use client";

import { ShieldAlert } from "lucide-react";

export function DisclaimerBanner() {
  return (
    <div className="flex items-start gap-3 rounded-md border border-amber-700/30 bg-amber-900/10 p-3 text-xs text-amber-200/90">
      <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <p className="leading-relaxed">
        <strong className="text-amber-100">Educational demo, not investment advice.</strong>{" "}
        Numeric levels (invalidation, Fibonacci, channel projections) are
        properties of past price geometry, not forecasts. Wave counts are
        structural interpretations; humans decide actions.
      </p>
    </div>
  );
}
