"""AgentDeps — shared resources passed into every agent run.

PydanticAI agents accept a typed `deps` parameter. This module defines the
single deps type used by all agents: cache, cost tracker, and the LLM
provider configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.agents.llm import ModelHandle


if TYPE_CHECKING:
    from app.services.cache import AgentCache


@dataclass(slots=True)
class AgentRunCost:
    """Per-call cost record. Aggregated across a run by the orchestrator."""

    agent_name: str
    model: str
    is_test: bool
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cache_hit: bool


@dataclass
class AgentDeps:
    """Resources every agent has access to."""

    cache: "AgentCache | None" = None
    handle: ModelHandle | None = None
    # The orchestrator appends per-call costs as agents run.
    costs: list[AgentRunCost] = field(default_factory=list)
