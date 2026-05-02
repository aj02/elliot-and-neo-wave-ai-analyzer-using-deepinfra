"""Print resolved LLM config (for verifying .env reaches the running backend)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402


def main() -> int:
    get_settings.cache_clear()
    s = get_settings()
    key_set = bool(s.deepinfra_api_key and s.deepinfra_api_key.get_secret_value())
    print(f"provider:        {s.llm_provider}")
    print(f"deepinfra key:   <{'set' if key_set else 'empty — TestModel will be used'}>")
    print(f"deepinfra base:  {s.deepinfra_base_url}")
    print(f"model fast:      {s.deepinfra_model_fast}")
    print(f"model smart:     {s.deepinfra_model_smart}")
    print(f"price in:        ${s.deepinfra_input_price_per_mtok}/Mtok")
    print(f"price out:       ${s.deepinfra_output_price_per_mtok}/Mtok")
    print(f"cost cap:        ${s.max_run_cost_usd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
