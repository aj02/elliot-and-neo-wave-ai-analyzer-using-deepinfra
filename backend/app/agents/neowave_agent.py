"""NEOWave Agent (Claude Haiku, schema-bound JSON output).

Per-timeframe agent: takes one StructureSummary, proposes 1–3 candidate
NEOWave structural identifications (impulse, zigzag, flat, triangle,
diametric, symmetrical, double/triple combination) ranked by structural fit.

Output is `NeowaveAgentOutput`. Each candidate is then passed through the
deterministic Validator (`app.rules.neowave_rules.evaluate_count`) which
rejects rule-violating counts before they reach the user.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.agents.deps import AgentDeps, AgentRunCost
from app.agents.llm import cost_usd, make_model
from app.agents.prompts import NEOWAVE_AGENT_SYSTEM_PROMPT
from app.agents.safety import filter_rationales
from app.core.logging import get_logger
from app.schemas.structure import StructureSummary
from app.schemas.waves import NeowaveCount
from app.services.cache import AgentCache, cache_key


log = get_logger("agents.neowave")
AGENT_NAME = "neowave"


class NeowaveAgentOutput(BaseModel):
    """The NEOWave agent's schema-bound output. Up to 3 ranked counts."""

    model_config = ConfigDict(extra="forbid")
    counts: list[NeowaveCount] = Field(default_factory=list, max_length=3)


def _filter_output(output: NeowaveAgentOutput) -> NeowaveAgentOutput:
    return NeowaveAgentOutput(counts=filter_rationales(output.counts, agent_name=AGENT_NAME))


def _build_agent(model, system_prompt: str = NEOWAVE_AGENT_SYSTEM_PROMPT):
    from pydantic_ai import Agent

    # retries=1 — see elliott_agent.py. 90s HTTP timeout caps worst case.
    return Agent(
        model=model,
        output_type=NeowaveAgentOutput,
        system_prompt=system_prompt,
        retries=1,
        name="neowave",
    )


async def run_neowave_agent(
    summary: StructureSummary,
    *,
    deps: AgentDeps | None = None,
    cache: AgentCache | None = None,
) -> tuple[NeowaveAgentOutput, AgentRunCost]:
    """Run the NEOWave agent on a single timeframe."""
    deps = deps or AgentDeps()
    cache = cache or deps.cache

    summary_json = summary.model_dump_json()
    model, handle = make_model("haiku")
    deps.handle = handle

    key = cache_key(summary_json=summary_json, agent_name=AGENT_NAME, model_name=handle.name)

    if cache is not None:
        cached = await cache.get(key)
        if cached is not None:
            output = NeowaveAgentOutput.model_validate(cached)
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
            log.info("agents.neowave.cache_hit", timeframe=summary.timeframe.value)
            return output, cost_record

    agent = _build_agent(model)
    user_prompt = summary.to_llm_text()

    log.info(
        "agents.neowave.run.start",
        timeframe=summary.timeframe.value,
        model=handle.name,
        is_test=handle.is_test,
        input_chars=len(user_prompt),
    )
    result = await agent.run(user_prompt, deps=deps)
    output = _filter_output(result.output)

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
        "agents.neowave.run.complete",
        timeframe=summary.timeframe.value,
        candidates=len(output.counts),
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=spend,
    )
    return output, cost_record
