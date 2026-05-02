"""Post-load validators: monotonicity, duplicates, OHLC sanity, gap detection.

These run on the canonical DataFrame produced by `csv_loader.load_csv`.
Errors raise `ValidationFailed` with structured `ValidationIssue` records;
warnings (e.g. detected gaps) are returned alongside the cleaned DataFrame.
"""

from __future__ import annotations

import pandas as pd

from app.core.config import get_settings
from app.schemas.input import ValidationIssue


class ValidationFailed(ValueError):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        super().__init__("; ".join(i.message for i in issues))


def _ohlc_sanity_issues(df: pd.DataFrame) -> list[ValidationIssue]:
    """Check that high >= max(open, close) and low <= min(open, close), high >= low, volume >= 0."""
    issues: list[ValidationIssue] = []
    high, low, open_, close, volume = df["high"], df["low"], df["open"], df["close"], df["volume"]

    bad_hi = (high < open_) | (high < close) | (high < low)
    bad_lo = (low > open_) | (low > close)
    bad_vol = volume < 0

    if bad_hi.any():
        i = int(bad_hi.idxmax()) + 1
        issues.append(
            ValidationIssue(
                severity="error",
                code="OHLC_SANITY",
                row=i,
                message=(
                    f"Row {i}: high must be >= max(open, close, low). "
                    f"high={high.iloc[i - 1]}, open={open_.iloc[i - 1]}, "
                    f"close={close.iloc[i - 1]}, low={low.iloc[i - 1]}."
                ),
            )
        )
    if bad_lo.any():
        i = int(bad_lo.idxmax()) + 1
        issues.append(
            ValidationIssue(
                severity="error",
                code="OHLC_SANITY",
                row=i,
                message=(
                    f"Row {i}: low must be <= min(open, close). "
                    f"low={low.iloc[i - 1]}, open={open_.iloc[i - 1]}, "
                    f"close={close.iloc[i - 1]}."
                ),
            )
        )
    if bad_vol.any():
        i = int(bad_vol.idxmax()) + 1
        issues.append(
            ValidationIssue(
                severity="error",
                code="NEGATIVE_VOLUME",
                row=i,
                message=f"Row {i}: volume must be >= 0 (got {volume.iloc[i - 1]}).",
            )
        )
    return issues


def _monotonicity_issues(df: pd.DataFrame) -> list[ValidationIssue]:
    """Datetime must be strictly increasing — no duplicates, no out-of-order rows."""
    issues: list[ValidationIssue] = []
    dt = df["datetime"]
    dup_mask = dt.duplicated(keep=False)
    if dup_mask.any():
        i = int(dup_mask.idxmax()) + 1
        issues.append(
            ValidationIssue(
                severity="error",
                code="DUPLICATE_DATETIME",
                row=i,
                message=(
                    f"Row {i}: datetime {dt.iloc[i - 1]} is duplicated. Each row must have "
                    f"a unique datetime."
                ),
            )
        )
    nondec = dt.diff().dropna() <= pd.Timedelta(0)
    if nondec.any():
        bad = nondec.idxmax()
        i = int(bad) + 1
        issues.append(
            ValidationIssue(
                severity="error",
                code="NON_MONOTONIC_DATETIME",
                row=i,
                message=(
                    f"Row {i}: datetime {dt.iloc[i - 1]} is not strictly greater than the "
                    f"previous row's datetime ({dt.iloc[i - 2]}). Sort the CSV by datetime ascending."
                ),
            )
        )
    return issues


def _gap_warnings(df: pd.DataFrame) -> list[ValidationIssue]:
    """Detect gaps: rows where dt-delta exceeds 3× the median delta.

    Warns rather than rejects — markets close on weekends/holidays and intraday
    gaps are common. The threshold (3×) tolerates weekend gaps in daily data.
    """
    issues: list[ValidationIssue] = []
    if len(df) < 3:
        return issues
    deltas = df["datetime"].diff().dropna()
    median = deltas.median()
    if pd.isna(median) or median == pd.Timedelta(0):
        return issues
    threshold = median * 3
    gap_mask = deltas > threshold
    if gap_mask.any():
        # Report up to 3 gaps; collapse the rest into a count.
        gap_rows = list(deltas.index[gap_mask][:3])
        for idx in gap_rows:
            i = int(idx) + 1
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="DETECTED_GAP",
                    row=i,
                    message=(
                        f"Row {i}: gap of {deltas.loc[idx]} (median bar = {median}). "
                        f"Probably weekend/holiday. Continuing."
                    ),
                )
            )
        remaining = int(gap_mask.sum()) - len(gap_rows)
        if remaining > 0:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="DETECTED_GAPS_TRUNCATED",
                    message=f"{remaining} additional gap(s) detected (not shown).",
                )
            )
    return issues


def _row_count_issues(df: pd.DataFrame) -> list[ValidationIssue]:
    """Reject too-short or too-long CSVs."""
    settings = get_settings()
    issues: list[ValidationIssue] = []
    n = len(df)
    if n < settings.min_csv_rows:
        issues.append(
            ValidationIssue(
                severity="error",
                code="TOO_FEW_ROWS",
                message=(
                    f"CSV has {n} rows; minimum is {settings.min_csv_rows}. "
                    f"Too little data for any meaningful structural analysis."
                ),
            )
        )
    if n > settings.max_csv_rows:
        issues.append(
            ValidationIssue(
                severity="error",
                code="TOO_MANY_ROWS",
                message=(
                    f"CSV has {n} rows; maximum is {settings.max_csv_rows}. "
                    f"Downsample first (e.g. resample 1m → 5m or trim history)."
                ),
            )
        )
    return issues


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, list[ValidationIssue]]:
    """Run all post-load validators.

    Returns `(df, warnings)`. Errors raise `ValidationFailed`.
    """
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    errors.extend(_row_count_issues(df))
    if errors:
        raise ValidationFailed(errors)

    errors.extend(_monotonicity_issues(df))
    errors.extend(_ohlc_sanity_issues(df))
    if errors:
        raise ValidationFailed(errors)

    warnings.extend(_gap_warnings(df))
    return df, warnings
