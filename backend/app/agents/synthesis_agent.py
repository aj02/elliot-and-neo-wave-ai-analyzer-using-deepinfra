"""Synthesis Agent — the only Sonnet call in the system.

Takes the surviving counts across all timeframes (already validated by the
deterministic rule engine) and produces a ranked cross-timeframe +
cross-framework synthesis. The agent does NOT generate numeric levels;
invalidation prices are looked up from the supporting counts after the agent
finishes via `hydrate_synthesis_invalidations`.
"""

from __future__ import annotations

from app.agents.deps import AgentDeps, AgentRunCost
from app.agents.llm import cost_usd, make_model
from app.agents.prompts import SYNTHESIS_AGENT_SYSTEM_PROMPT
from app.agents.safety import filter_rationales
from app.core.logging import get_logger
from app.schemas.structure import StructureSummary
from app.schemas.synthesis import SynthesisReport, SynthesisScenario
from app.schemas.validated import ValidationOutcome
from app.services.cache import AgentCache, cache_key


log = get_logger("agents.synthesis")
AGENT_NAME = "synthesis"


# ---------------------------------------------------------------------------
# Input rendering: surviving counts across timeframes → compact text
# ---------------------------------------------------------------------------


def build_synthesis_input(
    parts: list[tuple[StructureSummary, ValidationOutcome]],
) -> str:
    """Render the multi-timeframe synthesis input.

    Token budget target: ≤ 1500 tokens for 5 timeframes × 3 surviving counts
    each, including their full rationales. Truncates rationales to 240 chars
    (already the schema cap, but we enforce it here too).
    """
    lines: list[str] = []
    for summary, outcome in parts:
        lines.append(f"== TIMEFRAME {summary.timeframe.value} ==")
        lines.append(f"StructureSummary:")
        for sl in summary.to_llm_text().splitlines():
            lines.append(f"  {sl}")

        lines.append("Surviving Elliott counts:")
        if not outcome.elliott_surviving:
            lines.append("  (none)")
        for i, v in enumerate(outcome.elliott_surviving[:3]):
            inv = v.invalidation
            inv_str = f"inv={inv.direction} {inv.price:.2f}" if inv else "inv=N/A"
            lines.append(
                f"  E{i}: pattern={v.count.pattern} degree={v.count.degree} "
                f"current_wave={v.count.current_wave} score={v.compliance.score} {inv_str}"
            )
            lines.append(f"      rationale: {v.count.rationale[:240]}")

        lines.append("Surviving NEOWave counts:")
        if not outcome.neowave_surviving:
            lines.append("  (none)")
        for i, v in enumerate(outcome.neowave_surviving[:3]):
            lines.append(
                f"  N{i}: pattern={v.count.pattern} "
                f"current_position={v.count.current_position} score={v.compliance.score}"
            )
            lines.append(f"      rationale: {v.count.rationale[:240]}")
        lines.append("")
    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# Hydration: attach Python-computed invalidation prices to each scenario
# ---------------------------------------------------------------------------


def hydrate_synthesis_invalidations(
    report: SynthesisReport,
    parts_by_tf: dict[str, ValidationOutcome],
) -> SynthesisReport:
    """Replace each scenario's `invalidation_levels` with the deterministic
    levels of its supporting counts. The agent never produces these prices.
    """
    hydrated_scenarios: list[SynthesisScenario] = []
    for scenario in report.scenarios:
        levels = []
        for ref in scenario.supporting:
            outcome = parts_by_tf.get(ref.timeframe)
            if outcome is None:
                continue
            survivors = (
                outcome.elliott_surviving if ref.framework == "elliott"
                else outcome.neowave_surviving
            )
            if not (0 <= ref.count_idx < len(survivors)):
                continue
            inv = survivors[ref.count_idx].invalidation
            if inv is not None:
                levels.append(inv)
        hydrated_scenarios.append(scenario.model_copy(update={"invalidation_levels": levels}))
    return report.model_copy(update={"scenarios": hydrated_scenarios})


# ---------------------------------------------------------------------------
# Output filtering: drop scenarios whose summary contains forbidden language
# ---------------------------------------------------------------------------


def _filter_output(report: SynthesisReport) -> SynthesisReport:
    """Drop scenarios whose summary contains forbidden language. The
    `filter_rationales` helper inspects the `.rationale` attribute by name —
    SynthesisScenario doesn't have one, so we adapt by setting it temporarily.
    """
    safe: list[SynthesisScenario] = []
    for s in report.scenarios:
        # Concatenate all free-text fields and check.
        haystack = " ".join([s.summary, s.cross_timeframe_alignment, s.cross_framework_agreement])
        from app.agents.safety import contains_forbidden  # local to avoid cycle

        offending = contains_forbidden(haystack)
        if offending is None:
            safe.append(s)
        else:
            log.warning("agents.synthesis.dropped_forbidden_word", word=offending, rank=s.rank)
    return report.model_copy(update={"scenarios": safe})


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------


def _build_agent(model, system_prompt: str = SYNTHESIS_AGENT_SYSTEM_PROMPT):
    from pydantic_ai import Agent

    # retries=1 — see elliott_agent.py. 90s HTTP timeout caps worst case.
    return Agent(
        model=model,
        output_type=SynthesisReport,
        system_prompt=system_prompt,
        retries=1,
        name="synthesis",
    )


async def run_synthesis_agent(
    parts: list[tuple[StructureSummary, ValidationOutcome]],
    *,
    deps: AgentDeps | None = None,
    cache: AgentCache | None = None,
) -> tuple[SynthesisReport, AgentRunCost]:
    """Single Sonnet call. Returns the hydrated synthesis + cost record."""
    deps = deps or AgentDeps()
    cache = cache or deps.cache

    # Cache key includes a digest of every per-timeframe StructureSummary +
    # surviving-count rationale, so the cache invalidates cleanly when any
    # input changes.
    user_prompt = build_synthesis_input(parts)
    parts_by_tf = {summary.timeframe.value: outcome for summary, outcome in parts}

    model, handle = make_model("sonnet")
    deps.handle = handle

    key = cache_key(
        summary_json=user_prompt,  # uses the full multi-tf text as the cache contents
        agent_name=AGENT_NAME,
        model_name=handle.name,
    )

    if cache is not None:
        cached = await cache.get(key)
        if cached is not None:
            report = SynthesisReport.model_validate(cached)
            report = hydrate_synthesis_invalidations(report, parts_by_tf)
            cost_record = AgentRunCost(
                agent_name=AGENT_NAME,
                model=handle.name,
                is_test=handle.is_test,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                cache_hit=True,
            )
            deps.costs.append(cost_record)
            log.info("agents.synthesis.cache_hit")
            return report, cost_record

    agent = _build_agent(model)
    log.info(
        "agents.synthesis.run.start",
        model=handle.name,
        is_test=handle.is_test,
        input_chars=len(user_prompt),
        timeframes=list(parts_by_tf.keys()),
    )
    result = await agent.run(user_prompt, deps=deps)
    report = _filter_output(result.output)
    report = hydrate_synthesis_invalidations(report, parts_by_tf)

    usage = result.usage()
    in_tok = int(getattr(usage, "input_tokens", 0) or 0)
    out_tok = int(getattr(usage, "output_tokens", 0) or 0)
    spend = cost_usd(handle, input_tokens=in_tok, output_tokens=out_tok)

    cost_record = AgentRunCost(
        agent_name=AGENT_NAME,
        model=handle.name,
        is_test=handle.is_test,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=spend,
        cache_hit=False,
    )
    deps.costs.append(cost_record)

    if cache is not None:
        # Cache the un-hydrated form (so re-hydration always uses fresh deterministic levels).
        await cache.set(
            key,
            SynthesisReport(
                scenarios=[
                    s.model_copy(update={"invalidation_levels": []}) for s in report.scenarios
                ],
                methodology_note=report.methodology_note,
            ).model_dump(mode="json"),
        )

    log.info(
        "agents.synthesis.run.complete",
        scenarios=len(report.scenarios),
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=spend,
    )
    return report, cost_record
