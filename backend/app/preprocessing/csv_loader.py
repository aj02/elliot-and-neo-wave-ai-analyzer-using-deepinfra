"""CSV loader.

Canonical schema is `datetime, open, high, low, close, volume`. The loader is
permissive about real-world variants:

* `Date` / `Time` / `Timestamp` columns are aliased to `datetime`.
* `volume` is optional — indices and many backtesting exports lack it. If
  missing, every row is filled with 0 and a warning is surfaced.
* Datetime strings with a trailing parenthetical timezone name (e.g. the
  `"... GMT+0530 (India Standard Time)"` shape some Date-string exports use)
  are pre-stripped before parsing — pandas can read the offset but not the
  trailing name.

Errors are user-actionable — every rejection includes a row number when
applicable and a concrete instruction.
"""

from __future__ import annotations

from pathlib import Path
from typing import IO

import pandas as pd

from app.schemas.input import ValidationIssue


REQUIRED_COLUMNS: tuple[str, ...] = ("datetime", "open", "high", "low", "close", "volume")
DATETIME_ALIASES: tuple[str, ...] = ("date", "time", "timestamp")
# Trailing parenthetical that follows a numeric offset, e.g. " (India Standard Time)".
_TRAILING_TZ_NAME = r"\s*\([^)]*\)\s*$"


class CsvLoadError(ValueError):
    """Raised when a CSV cannot be loaded into the canonical schema.

    The `issues` attribute contains structured `ValidationIssue` records.
    """

    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        super().__init__("; ".join(i.message for i in issues))


def load_csv(source: str | Path | IO[bytes] | IO[str]) -> tuple[pd.DataFrame, list[ValidationIssue]]:
    """Load an OHLCV CSV into the canonical schema.

    Returns the parsed DataFrame and a list of warnings (non-fatal). On a fatal
    error a `CsvLoadError` is raised with one or more `ValidationIssue`s.

    Canonical schema:
        - `datetime`  : pd.Timestamp (UTC-naive), unique, monotonically increasing
        - `open/high/low/close` : float64
        - `volume` : int64 (>= 0). 0 if the source CSV has no volume column.
    """
    warnings: list[ValidationIssue] = []

    try:
        df = pd.read_csv(source)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        raise CsvLoadError(
            [
                ValidationIssue(
                    severity="error",
                    code="CSV_PARSE",
                    message=f"Could not parse CSV: {exc}.",
                    row=None,
                )
            ]
        ) from exc

    # Normalise column names: strip whitespace, lower-case.
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Alias any of {date, time, timestamp} → datetime if `datetime` is missing.
    if "datetime" not in df.columns:
        for alias in DATETIME_ALIASES:
            if alias in df.columns:
                df = df.rename(columns={alias: "datetime"})
                warnings.append(
                    ValidationIssue(
                        severity="warning",
                        code="ALIASED_DATETIME_COLUMN",
                        message=f"Column '{alias}' was treated as 'datetime'.",
                    )
                )
                break

    # Volume is optional — synthesise zero-volume rows + warn if absent.
    has_volume_column = "volume" in df.columns
    if not has_volume_column:
        df = df.copy()
        df["volume"] = 0
        warnings.append(
            ValidationIssue(
                severity="warning",
                code="MISSING_VOLUME_COLUMN",
                message=(
                    "CSV has no 'volume' column — every row was set to 0. "
                    "Volume-aware heuristics (EW-S-6) are skipped on this dataset."
                ),
            )
        )

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise CsvLoadError(
            [
                ValidationIssue(
                    severity="error",
                    code="MISSING_COLUMNS",
                    message=(
                        f"CSV is missing required columns: {missing}. "
                        f"Expected columns are {list(REQUIRED_COLUMNS)} (case-insensitive). "
                        f"'datetime' is also accepted as 'date', 'time', or 'timestamp'."
                    ),
                )
            ]
        )

    df = df[list(REQUIRED_COLUMNS)].copy()

    # Datetime parsing. Strip the trailing parenthetical timezone NAME first
    # (pandas reads numeric offsets but stumbles on the trailing "(India ...)").
    raw_dt = df["datetime"]
    if raw_dt.dtype == object:
        raw_dt = raw_dt.astype(str).str.replace(_TRAILING_TZ_NAME, "", regex=True)
    parsed_dt = pd.to_datetime(raw_dt, errors="coerce", utc=False)
    bad_rows = df.index[parsed_dt.isna()].tolist()
    if bad_rows:
        first_bad = bad_rows[0] + 1  # 1-based
        raw_value = df["datetime"].iloc[bad_rows[0]]
        raise CsvLoadError(
            [
                ValidationIssue(
                    severity="error",
                    code="UNPARSEABLE_DATETIME",
                    message=(
                        f"Row {first_bad}: 'datetime' value {raw_value!r} could not be parsed. "
                        f"Use ISO 8601 (e.g. 2024-03-15 or 2024-03-15T09:15:00) or a "
                        f"recognisable form like 'Mon Jul 02 1990 00:00:00 GMT+0530'."
                    ),
                    row=first_bad,
                )
            ]
        )
    # tz-naive UTC timestamps for downstream determinism.
    if hasattr(parsed_dt.dtype, "tz") and parsed_dt.dt.tz is not None:
        parsed_dt = parsed_dt.dt.tz_convert("UTC").dt.tz_localize(None)
    df["datetime"] = parsed_dt

    # Numeric columns
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    nan_mask = df[["open", "high", "low", "close", "volume"]].isna().any(axis=1)
    if nan_mask.any():
        first_bad = int(nan_mask.idxmax()) + 1
        raise CsvLoadError(
            [
                ValidationIssue(
                    severity="error",
                    code="NON_NUMERIC_OHLCV",
                    message=(
                        f"Row {first_bad}: one of open/high/low/close/volume is "
                        f"non-numeric or empty. Every row must have numeric OHLCV."
                    ),
                    row=first_bad,
                )
            ]
        )

    df["volume"] = df["volume"].astype("int64")
    for col in ("open", "high", "low", "close"):
        df[col] = df[col].astype("float64")

    return df, warnings
