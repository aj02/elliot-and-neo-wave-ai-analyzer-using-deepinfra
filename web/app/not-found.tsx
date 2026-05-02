import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <section className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-20">
      <span className="text-xs font-medium uppercase tracking-[0.18em] text-[color:var(--color-accent)]">
        404
      </span>
      <h1 className="text-3xl font-semibold tracking-tight">Page not found.</h1>
      <p className="text-sm text-[color:var(--color-muted)]">
        Likely a stale link or a run id whose 24-hour TTL has elapsed.
      </p>
      <div>
        <Button variant="secondary">
          <Link href="/">Back to upload</Link>
        </Button>
      </div>
    </section>
  );
}
