import Link from "next/link";

export default function AboutPage() {
  return (
    <article className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-12 text-sm leading-relaxed text-[color:var(--color-muted)]">
      <header className="flex flex-col gap-2">
        <span className="text-xs font-medium uppercase tracking-[0.18em] text-[color:var(--color-accent)]">
          About wave-agent
        </span>
        <h1 className="text-3xl font-semibold tracking-tight text-[color:var(--color-fg)]">
          What this project is, and what it is not.
        </h1>
      </header>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-[color:var(--color-fg)]">
          What it is
        </h2>
        <p>
          wave-agent runs deterministic Python preprocessing on uploaded OHLCV
          CSVs, then orchestrates specialised LLM agents (Anthropic Claude
          Haiku for per-timeframe wave-rule agents, Sonnet for the cross-
          timeframe synthesis agent) to propose ranked Elliott Wave + NEOWave
          structural interpretations. The agents only see compact
          ~80&ndash;150-token summaries of pivots, swings, channels, and
          Fibonacci zones — never raw price data.
        </p>
        <p>
          Every numeric level in the final report (invalidation prices,
          Fibonacci confluence, channel projections) is computed in Python.
          The LLM&apos;s job is interpretive ranking and cross-timeframe
          alignment, not arithmetic. Wave counts that violate hard rules
          (Frost &amp; Prechter / Glenn Neely) are rejected by the
          deterministic Validator before they reach the user.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-[color:var(--color-fg)]">
          What it is not
        </h2>
        <p>
          It is not a trading system. It does not predict prices, signal
          entries or exits, or estimate probabilities of future moves. There
          are no &ldquo;buy&rdquo; or &ldquo;sell&rdquo; recommendations
          anywhere in the project — the prompt forbids them, the schema does
          not accept them, and a third-layer output filter scrubs any leakage.
        </p>
        <p>
          Treat every output as a structural interpretation of past price.
          The deterministic levels are properties of the data&apos;s
          geometry; the LLM&apos;s rationale is a candidate reading, not a
          forecast. Decisions belong to the human reading the report.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-[color:var(--color-fg)]">
          Token economics
        </h2>
        <p>
          A typical 5-timeframe analysis runs ~10 Haiku calls + 1 Sonnet call,
          totalling roughly $0.02&ndash;$0.05 per run. Identical inputs hit a
          Redis-backed cache and skip the LLM entirely. A configurable cap
          rejects pathologically expensive runs before any LLM call is made.
        </p>
      </section>

      <p>
        See the project repository&apos;s{" "}
        <Link
          href="/"
          className="text-[color:var(--color-accent)] underline-offset-4 hover:underline"
        >
          README
        </Link>{" "}
        and <code>ARCHITECTURE.md</code> for the deterministic-vs-LLM split,
        and <code>ELLIOTT_RULES.md</code> for the rules encoded in the
        Validator.
      </p>
    </article>
  );
}
