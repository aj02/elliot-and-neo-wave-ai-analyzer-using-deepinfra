"""Shared pytest fixtures."""

from __future__ import annotations

import io
from datetime import datetime, timedelta

import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _force_test_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip all three LLM provider keys for every test, so agent runs fall
    back to PydanticAI's `TestModel` (zero spend, deterministic shape).

    Without this, a developer's `.env` containing a real `DEEPINFRA_API_KEY`
    or `ANTHROPIC_API_KEY` would make every agent test attempt a live LLM call.
    """
    from app.core import config as cfg

    monkeypatch.setattr(cfg.get_settings(), "anthropic_api_key", None, raising=False)
    monkeypatch.setattr(cfg.get_settings(), "openai_api_key", None, raising=False)
    monkeypatch.setattr(cfg.get_settings(), "deepinfra_api_key", None, raising=False)


def _date_at(start: datetime, offset_days: int) -> str:
    return (start + timedelta(days=offset_days)).strftime("%Y-%m-%d")


@pytest.fixture
def good_csv_bytes() -> bytes:
    """A 200-row synthetic OHLCV CSV that passes all validators."""
    start = datetime(2024, 1, 1)
    rows = []
    price = 100.0
    for i in range(200):
        dt = start + timedelta(days=i)
        open_ = price
        close = price * (1.0 + 0.001 * ((i % 7) - 3))
        high = max(open_, close) * 1.005
        low = min(open_, close) * 0.995
        rows.append(
            {
                "datetime": dt.strftime("%Y-%m-%d"),
                "open": round(open_, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(close, 4),
                "volume": 1000 + i * 10,
            }
        )
        price = close
    df = pd.DataFrame(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


@pytest.fixture
def csv_missing_columns() -> bytes:
    return b"date,open,close\n2024-01-01,100,101\n"


@pytest.fixture
def csv_unparseable_datetime() -> bytes:
    return b"datetime,open,high,low,close,volume\nnot-a-date,100,101,99,100,1000\n"


@pytest.fixture
def csv_bad_ohlc() -> bytes:
    """Row 1 has high < close, which violates OHLC sanity."""
    start = datetime(2024, 1, 1)
    rows = ["datetime,open,high,low,close,volume"]
    rows.append(f"{_date_at(start, 0)},100,100,99,105,1000")  # high=100, close=105 — invalid
    for i in range(1, 150):
        rows.append(f"{_date_at(start, i)},100,101,99,100,1000")
    return ("\n".join(rows) + "\n").encode("utf-8")


@pytest.fixture
def csv_too_few_rows() -> bytes:
    """Only 50 rows — below the 100-row minimum."""
    start = datetime(2024, 1, 1)
    rows = ["datetime,open,high,low,close,volume"]
    for i in range(50):
        rows.append(f"{_date_at(start, i)},100,101,99,100,1000")
    return ("\n".join(rows) + "\n").encode("utf-8")


@pytest.fixture
def csv_duplicate_datetime() -> bytes:
    start = datetime(2024, 1, 1)
    rows = ["datetime,open,high,low,close,volume"]
    rows.append(f"{_date_at(start, 0)},100,101,99,100,1000")
    rows.append(f"{_date_at(start, 0)},101,102,100,101,1000")  # duplicate
    for i in range(2, 150):
        rows.append(f"{_date_at(start, i)},100,101,99,100,1000")
    return ("\n".join(rows) + "\n").encode("utf-8")
