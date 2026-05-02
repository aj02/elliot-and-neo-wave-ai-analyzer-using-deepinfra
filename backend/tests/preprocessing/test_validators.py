"""Tests for the post-load validators."""

from __future__ import annotations

import io

import pytest

from app.preprocessing.csv_loader import load_csv
from app.preprocessing.validators import ValidationFailed, validate


def test_passes_a_clean_csv(good_csv_bytes: bytes) -> None:
    df, _ = load_csv(io.BytesIO(good_csv_bytes))
    df, warnings = validate(df)
    assert warnings == []
    assert len(df) == 200


def test_rejects_too_few_rows(csv_too_few_rows: bytes) -> None:
    df, _ = load_csv(io.BytesIO(csv_too_few_rows))
    with pytest.raises(ValidationFailed) as ei:
        validate(df)
    assert any(i.code == "TOO_FEW_ROWS" for i in ei.value.issues)


def test_rejects_bad_ohlc(csv_bad_ohlc: bytes) -> None:
    df, _ = load_csv(io.BytesIO(csv_bad_ohlc))
    with pytest.raises(ValidationFailed) as ei:
        validate(df)
    assert any(i.code == "OHLC_SANITY" for i in ei.value.issues)
    # Error references the actual offending row (1) and is human-actionable.
    issue = next(i for i in ei.value.issues if i.code == "OHLC_SANITY")
    assert issue.row == 1
    assert "high" in issue.message
    assert "close" in issue.message


def test_rejects_duplicate_datetime(csv_duplicate_datetime: bytes) -> None:
    df, _ = load_csv(io.BytesIO(csv_duplicate_datetime))
    with pytest.raises(ValidationFailed) as ei:
        validate(df)
    codes = [i.code for i in ei.value.issues]
    assert "DUPLICATE_DATETIME" in codes or "NON_MONOTONIC_DATETIME" in codes
