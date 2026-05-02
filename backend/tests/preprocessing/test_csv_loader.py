"""Tests for the strict CSV loader."""

from __future__ import annotations

import io

import pytest

from app.preprocessing.csv_loader import CsvLoadError, load_csv


def test_loads_canonical_csv(good_csv_bytes: bytes) -> None:
    df, warnings = load_csv(io.BytesIO(good_csv_bytes))
    assert list(df.columns) == ["datetime", "open", "high", "low", "close", "volume"]
    assert len(df) == 200
    assert warnings == []
    # Datetime parsed
    assert df["datetime"].iloc[0].year == 2024
    # Numeric types
    for col in ("open", "high", "low", "close"):
        assert df[col].dtype.kind == "f"
    assert df["volume"].dtype.kind == "i"


def test_rejects_missing_columns(csv_missing_columns: bytes) -> None:
    with pytest.raises(CsvLoadError) as ei:
        load_csv(io.BytesIO(csv_missing_columns))
    codes = [i.code for i in ei.value.issues]
    assert "MISSING_COLUMNS" in codes
    assert "high" in ei.value.issues[0].message  # mentions a missing column


def test_rejects_unparseable_datetime(csv_unparseable_datetime: bytes) -> None:
    with pytest.raises(CsvLoadError) as ei:
        load_csv(io.BytesIO(csv_unparseable_datetime))
    codes = [i.code for i in ei.value.issues]
    assert "UNPARSEABLE_DATETIME" in codes
    # Error message must reference the offending row
    assert ei.value.issues[0].row == 1


def test_normalises_column_names() -> None:
    csv = b"DateTime,Open,HIGH,Low,Close,Volume\n2024-01-01,100,101,99,100,1000\n"
    df, _ = load_csv(io.BytesIO(csv))
    assert "datetime" in df.columns
    assert "high" in df.columns


def test_rejects_non_numeric_ohlcv() -> None:
    csv = b"datetime,open,high,low,close,volume\n2024-01-01,not-a-number,101,99,100,1000\n"
    with pytest.raises(CsvLoadError) as ei:
        load_csv(io.BytesIO(csv))
    assert any(i.code == "NON_NUMERIC_OHLCV" for i in ei.value.issues)


def test_aliases_date_column_to_datetime() -> None:
    """`Date` column (common in real exports) is treated as `datetime` with a warning."""
    csv = b'"Date","Open","High","Low","Close","Volume"\n"2024-01-01","100","101","99","100","1000"\n'
    df, warnings = load_csv(io.BytesIO(csv))
    assert "datetime" in df.columns
    assert any(w.code == "ALIASED_DATETIME_COLUMN" for w in warnings)


def test_volume_is_optional_and_defaults_to_zero() -> None:
    """Indices and many backtest exports have no volume column. Loader fills 0 + warns."""
    csv = b'"Date","Open","High","Low","Close"\n"2024-01-01","100","101","99","100"\n'
    df, warnings = load_csv(io.BytesIO(csv))
    assert (df["volume"] == 0).all()
    assert any(w.code == "MISSING_VOLUME_COLUMN" for w in warnings)


def test_strips_trailing_parenthetical_timezone_name() -> None:
    """Date strings of the form 'Mon Jul 02 1990 00:00:00 GMT+0530 (India Standard Time)'
    are common from JS `Date.toString()` exports; pandas parses the offset but
    not the trailing TZ name, so the loader strips it before parsing."""
    csv = (
        b'"Date","Open","High","Low","Close"\n'
        b'"Mon Jul 02 1990 00:00:00 GMT+0530 (India Standard Time)","279.00","347.40","279.00","347.40"\n'
        b'"Wed Aug 01 1990 00:00:00 GMT+0530 (India Standard Time)","337.20","400.00","322.10","400.00"\n'
    )
    df, _ = load_csv(io.BytesIO(csv))
    assert len(df) == 2
    # 1990-07-02 in IST (+0530) → 1990-07-01 18:30:00 UTC
    assert df["datetime"].iloc[0].year == 1990
    assert df["datetime"].iloc[0].month == 7
