"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error("wave-agent.ui.error", error);
  }, [error]);

  return (
    <section className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-20">
      <div className="flex items-center gap-3 text-sm text-amber-300">
        <AlertTriangle className="h-5 w-5" aria-hidden />
        <span className="font-medium">Something went wrong rendering this page.</span>
      </div>
      <p className="text-sm text-[color:var(--color-muted)]">
        {error.message || "Unknown error. The console may have more detail."}
        {error.digest ? (
          <code className="ml-2 rounded bg-[color:var(--color-card)] px-1.5 py-0.5 text-xs">
            {error.digest}
          </code>
        ) : null}
      </p>
      <div>
        <Button variant="secondary" onClick={() => reset()}>
          <RefreshCw className="h-4 w-4" aria-hidden />
          Try again
        </Button>
      </div>
    </section>
  );
}
