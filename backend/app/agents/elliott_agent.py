"""Elliott Wave Agent (Claude Haiku, schema-bound JSON output).

Per-timeframe agent: takes one StructureSummary, proposes 1–3 candidate
Elliott Wave counts ranked by structural fit. The agent has NO tools — it
reasons over the pre-summarised structure only.

Output is `ElliottAgentOutput`. Each candidate is then passed through the
deterministic Validator (`app.rules.elliott_rules.evaluate_count`) which
rejects rule-violating counts before they reach the user.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from app.agents.deps import AgentDeps, AgentRunCost
from app.agents.llm import ModelHandle, cost_usd, make_model
from app.agents.prompts import ELLIOTT_AGENT_SYSTEM_PROMPT
from app.agents.safety import contains_forbidden, filter_rationales
from app.core.logging import get_logger
from app.schemas.structure import StructureSummary
from app.schemas.waves import ElliottCount
from app.services.cache import AgentCache, cache_key


if TYPE_CHECKING:
    pass


log = get_logger("agents.elliott")
AGENT_NAME = "elliott"


class ElliottAgentOutput(BaseModel):
    """The Elliott agent's schema-bound output. Up to 3 ranked counts."""

    model_config = ConfigDict(extra="forbid")
    counts: list[ElliottCount] = Field(default_factory=list, max_length=3)


def _filter_output(output: ElliottAgentOutput) -> ElliottAgentOutput:
    """Drop counts whose rationale contains forbidden language."""
    return ElliottAgentOutput(counts=filter_rationales(output.counts, agent_name=AGENT_NAME))


# Re-export for tests that monkey-import the old name.
_contains_forbidden = contains_forbidden


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------


def _build_agent(model, system_prompt: str = ELLIOTT_AGENT_SYSTEM_PROMPT):
    """Create a fresh PydanticAI Agent. Imported lazily so unit tests that mock
    the module path don't need pydantic-ai installed."""
    from pydantic_ai import Agent

    # retries=0 — fail fast on validation errors instead of retry-storms.
    # Some open-weights models (Kimi-K2 in particular) emit tool-call output
    # that fails strict schema validation; PydanticAI then retries with the
    # previous response in context, which balloons cost and hits HTTP timeouts.
    # The Validator filters malformed counts downstream anyway.
    return Agent(
        model=model,
        output_type=ElliottAgentOutput,
        system_prompt=system_prompt,
        retries=0,
        name="elliott",
    )


async def run_elliott_agent(
    summary: StructureSummary,
    *,
    deps: AgentDeps | None = None,
    cache: AgentCache | None = None,
) -> tuple[ElliottAgentOutput, AgentRunCost]:
    """Run the Elliott agent on a single timeframe.

    Returns the (filtered) output AND the cost record. Cache hits return with
    `cost_record.cache_hit=True` and zero token usage.
    """
    deps = deps or AgentDeps()
    cache = cache or deps.cache

    summary_json = summary.model_dump_json()

    model, handle = make_model("haiku")
    deps.handle = handle

    key = cache_key(
        summary_json=summary_json,
        agent_name=AGENT_NAME,
        model_name=handle.name,
    )

    # Cache lookup
    if cache is not None:
        cached = await cache.get(key)
        if cached is not None:
            output = ElliottAgentOutput.model_validate(cached)
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
            log.info("agents.elliott.cache_hit", timeframe=summary.timeframe.value)
            return output, cost_record

    # Live (or TestModel) call
    agent = _build_agent(model)
    user_prompt = summary.to_llm_text()

    log.info(
        "agents.elliott.run.start",
        timeframe=summary.timeframe.value,
        model=handle.name,
        is_test=handle.is_test,
        input_chars=len(user_prompt),
    )
    result = await agent.run(user_prompt, deps=deps)
    output = _filter_output(result.output)

    # Token usage. PydanticAI's Usage exposes input/output token counts when
    # the underlying provider returns them; TestModel returns 0/0.
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
        await cache.set(key, output.model_dump(mode="json"))

    log.info(
        "agents.elliott.run.complete",
        timeframe=summary.timeframe.value,
        candidates=len(output.counts),
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=spend,
    )
    return output, cost_record
