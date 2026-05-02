"""Application configuration. All settings are env-driven."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Runtime ----
    environment: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # ---- Database ----
    database_url: str = Field(
        default="postgresql+psycopg://waveagent:waveagent@postgres:5432/waveagent",
        description="SQLAlchemy URL for Postgres (psycopg v3 driver).",
    )

    # ---- Redis ----
    redis_url: str = Field(default="redis://redis:6379/0")

    # ---- LLM provider selection ----
    # `anthropic`  — Claude Haiku per-timeframe + Sonnet synthesis (default).
    # `openai`     — GPT-4o-mini per-timeframe + GPT-4o synthesis.
    # `deepinfra`  — DeepSeek (OpenAI-compatible endpoint), single model both tiers.
    llm_provider: Literal["anthropic", "openai", "deepinfra"] = "anthropic"
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    deepinfra_api_key: SecretStr | None = None
    deepinfra_base_url: str = "https://api.deepinfra.com/v1/openai"

    # ---- Anthropic models ----
    haiku_model: str = "claude-haiku-4-5-20251001"
    sonnet_model: str = "claude-sonnet-4-6"

    # ---- DeepInfra models (any OpenAI-compatible model: DeepSeek, Kimi, Llama, …) ----
    # The same model is used for both tiers by default. Override either tier
    # independently if you want a cheaper per-timeframe model + a smarter one
    # for synthesis (e.g. Kimi-K2-Instruct fast + Kimi-K2-Thinking smart).
    deepinfra_model_fast: str = "deepseek-ai/DeepSeek-V3.1"
    deepinfra_model_smart: str = "deepseek-ai/DeepSeek-V3.1"
    # Pricing per 1M tokens, USD. Override if DeepInfra changes prices or you
    # switch to a model with different rates.
    deepinfra_input_price_per_mtok: float = 0.27
    deepinfra_output_price_per_mtok: float = 1.10

    # ---- Cost guard ----
    max_run_cost_usd: float = Field(default=0.50, ge=0.0)

    # ---- Cache ----
    cache_ttl_seconds: int = Field(default=7 * 24 * 60 * 60)  # 7 days

    # ---- Upload limits ----
    max_csv_rows: int = 50_000
    min_csv_rows: int = 100
    max_upload_bytes: int = 25 * 1024 * 1024  # 25 MiB per file

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Use this everywhere; do not instantiate directly."""
    return Settings()
