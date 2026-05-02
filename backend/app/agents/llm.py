"""LLM provider abstraction + cost tracking.

Three providers are supported:
  * `anthropic` (default) — Claude Haiku per-timeframe + Sonnet synthesis.
  * `openai`              — GPT-4o-mini per-timeframe + GPT-4o synthesis.
  * `deepinfra`           — DeepSeek via DeepInfra's OpenAI-compatible endpoint.
                            Single model for both tiers by default; override
                            via `DEEPSEEK_MODEL_FAST` / `DEEPSEEK_MODEL_SMART`.

If neither key is set, falls back to PydanticAI's `TestModel` so unit tests
and shape-verification work without spending anything — but real agent calls
require a key.

Pricing is carried on the `ModelHandle` so a single `cost_usd()` works for
every provider; provider-specific defaults live below and are overridable
via env (DeepSeek pricing in particular changes more often than Anthropic's).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from app.core.config import get_settings


if TYPE_CHECKING:
    from pydantic_ai.models import Model


ModelTier = Literal["haiku", "sonnet"]
"""Logical tier — `haiku` = fast/cheap, `sonnet` = smart. Each provider maps
the tier to a concrete model in `make_model`."""


@dataclass(frozen=True, slots=True)
class ModelHandle:
    """What the agent layer needs to know about the model it just ran on."""

    name: str
    tier: ModelTier
    is_test: bool
    input_price_per_mtok: float
    output_price_per_mtok: float


# Anthropic published pricing per 1M tokens (USD). Update if Anthropic changes.
_ANTHROPIC_PRICING: dict[ModelTier, tuple[float, float]] = {
    "haiku": (0.80, 4.00),    # Haiku 4.5 input/output
    "sonnet": (3.00, 15.00),  # Sonnet 4.6 input/output
}

# OpenAI published pricing per 1M tokens (USD).
_OPENAI_PRICING: dict[ModelTier, tuple[float, float]] = {
    "haiku": (0.15, 0.60),    # gpt-4o-mini
    "sonnet": (2.50, 10.00),  # gpt-4o
}


def make_model(tier: ModelTier) -> tuple["Model", ModelHandle]:
    """Return a PydanticAI `Model` instance + handle for the requested tier.

    Selection respects `LLM_PROVIDER` first, then falls back through the keys
    that are set. If no key is available, returns `TestModel` (zero spend).
    """
    settings = get_settings()
    provider = settings.llm_provider

    # Anthropic
    if (
        provider == "anthropic"
        and settings.anthropic_api_key
        and settings.anthropic_api_key.get_secret_value()
    ):
        from pydantic_ai.models.anthropic import AnthropicModel

        name = settings.haiku_model if tier == "haiku" else settings.sonnet_model
        in_p, out_p = _ANTHROPIC_PRICING[tier]
        return AnthropicModel(name), ModelHandle(
            name=name,
            tier=tier,
            is_test=False,
            input_price_per_mtok=in_p,
            output_price_per_mtok=out_p,
        )

    # OpenAI (native)
    if (
        provider == "openai"
        and settings.openai_api_key
        and settings.openai_api_key.get_secret_value()
    ):
        # PydanticAI ≥ 0.4 renamed `OpenAIModel` → `OpenAIChatModel` to make room
        # for `OpenAIResponsesModel`. We use the chat-completions variant because
        # it's what DeepInfra (and most OpenAI-compatible providers) speak.
        try:
            from pydantic_ai.models.openai import OpenAIChatModel as OpenAIModel
        except ImportError:  # older pydantic-ai
            from pydantic_ai.models.openai import OpenAIModel  # type: ignore[no-redef]

        name = "gpt-4o-mini" if tier == "haiku" else "gpt-4o"
        in_p, out_p = _OPENAI_PRICING[tier]
        return OpenAIModel(name), ModelHandle(
            name=name,
            tier=tier,
            is_test=False,
            input_price_per_mtok=in_p,
            output_price_per_mtok=out_p,
        )

    # DeepInfra (OpenAI-compatible endpoint serving DeepSeek + others)
    if (
        provider == "deepinfra"
        and settings.deepinfra_api_key
        and settings.deepinfra_api_key.get_secret_value()
    ):
        # PydanticAI ≥ 0.4 renamed `OpenAIModel` → `OpenAIChatModel` to make room
        # for `OpenAIResponsesModel`. We use the chat-completions variant because
        # it's what DeepInfra (and most OpenAI-compatible providers) speak.
        try:
            from pydantic_ai.models.openai import OpenAIChatModel as OpenAIModel
        except ImportError:  # older pydantic-ai
            from pydantic_ai.models.openai import OpenAIModel  # type: ignore[no-redef]
        from pydantic_ai.providers.openai import OpenAIProvider

        name = (
            settings.deepinfra_model_fast
            if tier == "haiku"
            else settings.deepinfra_model_smart
        )
        provider_inst = OpenAIProvider(
            base_url=settings.deepinfra_base_url,
            api_key=settings.deepinfra_api_key.get_secret_value(),
        )
        return OpenAIModel(name, provider=provider_inst), ModelHandle(
            name=name,
            tier=tier,
            is_test=False,
            input_price_per_mtok=settings.deepinfra_input_price_per_mtok,
            output_price_per_mtok=settings.deepinfra_output_price_per_mtok,
        )

    # No key — fall back to TestModel. Real prompt-quality verification requires a key.
    from pydantic_ai.models.test import TestModel

    return TestModel(), ModelHandle(
        name=f"test:{tier}",
        tier=tier,
        is_test=True,
        input_price_per_mtok=0.0,
        output_price_per_mtok=0.0,
    )


def cost_usd(handle: ModelHandle, *, input_tokens: int, output_tokens: int) -> float:
    """Estimate the spend for one call. Returns 0.0 for the TestModel."""
    if handle.is_test:
        return 0.0
    return round(
        (
            input_tokens * handle.input_price_per_mtok
            + output_tokens * handle.output_price_per_mtok
        )
        / 1_000_000,
        6,
    )
