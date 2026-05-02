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
          CSVs, then orchestrates schema-bound LLM agents to propose ranked
          Elliott Wave + NEOWave structural interpretations. The agents only
          see compact ~80&ndash;150-token summaries of pivots, swings,
          channels, and Fibonacci zones — never raw price data.
        </p>
        <p>
          Three providers are wired up via a single env switch
          (<code>LLM_PROVIDER</code>):
          DeepInfra (DeepSeek-V3.1, Kimi-K2, Llama, GLM, …),
          Anthropic (Claude Haiku for per-timeframe agents + Sonnet for the
          single cross-timeframe synthesis call), and OpenAI
          (gpt-4o-mini + gpt-4o). The same prompts, schemas, and validator
          pipeline run regardless of which model serves the call.
        </p>
        <p>
          Every numeric level in the final report (invalidation prices,
          Fibonacci confluence, channel projections) is computed in Python.
          The LLM&apos;s job is interpretive ranking and cross-timeframe
          alignment, not arithmetic. Wave counts that violate hard rules
          (Frost &amp; Prechter / Glenn Neely) are rejected by the
          deterministic Validator before they reach the user. A second
          deterministic post-processor replaces every <code>#&lt;idx&gt;</code>
          {" "}pivot reference in the LLM&apos;s prose with the actual price
          and date pulled from the StructureSummary, so a human reader can
          audit the count without learning the system&apos;s internal indexing.
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
          A typical single-timeframe analysis runs 2 fast-tier agent calls
          (Elliott + NEOWave) + 1 smart-tier synthesis call. Indicative cost
          per run on a real 1990&ndash;2026 NIFTY 50 monthly dataset:
        </p>
        <ul className="ml-4 list-disc space-y-1">
          <li>
            <strong className="text-[color:var(--color-fg)]">DeepInfra (DeepSeek-V3.1):</strong>{" "}
            ~$0.003&ndash;$0.005 per run
          </li>
          <li>
            <strong className="text-[color:var(--color-fg)]">OpenAI (gpt-4o-mini + gpt-4o):</strong>{" "}
            ~$0.01&ndash;$0.03 per run
          </li>
          <li>
            <strong className="text-[color:var(--color-fg)]">Anthropic (Haiku + Sonnet):</strong>{" "}
            ~$0.02&ndash;$0.05 per run
          </li>
        </ul>
        <p>
          Identical inputs hit a Redis-backed cache (content-keyed by
          SHA-256(StructureSummary + agent name + model name), 7-day TTL)
          and skip the LLM entirely. A configurable cap
          (<code>MAX_RUN_COST_USD</code>) rejects pathologically expensive
          runs before any LLM call is made.
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
