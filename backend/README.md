# wave-agent backend

> **Disclaimer:** wave-agent is an educational and engineering demo. It is not investment advice.

FastAPI service that runs deterministic preprocessing on uploaded OHLCV CSVs and orchestrates LLM agents (Anthropic Claude Haiku for per-timeframe wave-rule agents, Sonnet for cross-timeframe synthesis) to propose Elliott Wave + NEOWave structural interpretations.

See the [top-level README](../README.md) for the full system overview and the disclaimer in full. See [ARCHITECTURE.md](../ARCHITECTURE.md) for the deterministic-vs-LLM split.

## Local development (without Docker)

```bash
uv venv
uv pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Migrations:

```bash
alembic upgrade head
alembic revision --autogenerate -m "your message"
```

## Tests

```bash
pytest
```

`pytest-asyncio` runs in auto mode. PydanticAI agents are tested with `TestModel` — no live LLM calls in CI.

## Lint / type-check

```bash
ruff check .
ruff format --check .
mypy
```
