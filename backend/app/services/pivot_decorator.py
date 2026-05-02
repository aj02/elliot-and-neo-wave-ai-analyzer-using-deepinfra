"""Decorate LLM-emitted text with pivot context.

LLM agents reference pivots by their bar index (e.g. "pivot #244"), but a bar
index is meaningless to a human reader. This module scans rationale strings
and synthesis-scenario text for `#<idx>` tokens and replaces them with the
actual price + date pulled deterministically from the StructureSummary.

Example transform on a 1M NIFTY rationale:

    "Wave 3 extends from #244 to #296"
        ↓
    "Wave 3 extends from 6134 (Nov 2010) to 26330 (Jan 2026)"

If the LLM's prose adds a numeric claim that disagrees with the real value
(it sometimes does), the user can see the disagreement directly. Numbers in
this module come from `Pivot.price` / `Pivot.datetime` — never from the LLM.
"""

from __future__ import annotations

import re

from app.schemas.structure import Pivot, StructureSummary
from app.schemas.synthesis import SynthesisReport
from app.schemas.validated import (
    ValidatedElliottCount,
    ValidatedNeowaveCount,
    ValidationOutcome,
)


# `#244` but not `web#244` or `1.244`. Cap at 5 digits — max_csv_rows is 50_000.
_PIVOT_REF_RE = re.compile(r"(?<!\w)#(\d{1,5})\b")


def _format_date(pivot: Pivot, timeframe: str) -> str:
    """Render the pivot's datetime at the timeframe's natural resolution."""
    dt = pivot.datetime
    if timeframe == "1M":
        return dt.strftime("%b %Y")
    if timeframe == "1W":
        return dt.strftime("%Y-%m-%d")
    if timeframe in ("1D", "4h"):
        return dt.strftime("%Y-%m-%d")
    return dt.strftime("%Y-%m-%d %H:%M")


def _format_pivot(pivot: Pivot, timeframe: str) -> str:
    """`<price> (<date>)`, e.g. `6134 (Nov 2010)`."""
    return f"{pivot.price:.0f} ({_format_date(pivot, timeframe)})"


def _decorate(text: str, pivots: dict[int, Pivot], timeframe: str) -> str:
    """Replace each `#<idx>` whose pivot is known. Unknown indices left as-is."""
    if not text:
        return text

    def repl(m: re.Match[str]) -> str:
        idx = int(m.group(1))
        pivot = pivots.get(idx)
        if pivot is None:
            return m.group(0)  # leave as-is — caller may want to inspect
        return _format_pivot(pivot, timeframe)

    return _PIVOT_REF_RE.sub(repl, text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def decorate_validation_outcome(
    outcome: ValidationOutcome, summary: StructureSummary
) -> ValidationOutcome:
    """Decorate every Elliott + NEOWave count rationale (surviving + rejected)."""
    pivots = {p.idx: p for p in summary.pivots}
    tf = summary.timeframe.value

    def _decorate_elliott(v: ValidatedElliottCount) -> ValidatedElliottCount:
        new_count = v.count.model_copy(
            update={"rationale": _decorate(v.count.rationale, pivots, tf)}
        )
        return v.model_copy(update={"count": new_count})

    def _decorate_neowave(v: ValidatedNeowaveCount) -> ValidatedNeowaveCount:
        new_count = v.count.model_copy(
            update={"rationale": _decorate(v.count.rationale, pivots, tf)}
        )
        return v.model_copy(update={"count": new_count})

    return outcome.model_copy(
        update={
            "elliott_surviving": [_decorate_elliott(v) for v in outcome.elliott_surviving],
            "elliott_rejected": [_decorate_elliott(v) for v in outcome.elliott_rejected],
            "neowave_surviving": [_decorate_neowave(v) for v in outcome.neowave_surviving],
            "neowave_rejected": [_decorate_neowave(v) for v in outcome.neowave_rejected],
        }
    )


def decorate_synthesis(
    report: SynthesisReport,
    parts: list[tuple[StructureSummary, ValidationOutcome]],
) -> SynthesisReport:
    """Decorate every scenario's free-text fields.

    For multi-timeframe runs, each scenario uses the timeframe of its first
    `supporting` count as the lookup context. Single-timeframe runs are
    unambiguous; bare `#<idx>` references in cross-timeframe scenarios where
    `supporting` is empty are left undecorated.
    """
    pivots_by_tf: dict[str, dict[int, Pivot]] = {
        summary.timeframe.value: {p.idx: p for p in summary.pivots}
        for summary, _ in parts
    }

    def _canonical_tf(s) -> str | None:  # noqa: ANN001 — Pydantic model
        if s.supporting:
            return s.supporting[0].timeframe
        if len(parts) == 1:
            return parts[0][0].timeframe.value
        return None

    def _decorate_scenario(s):  # noqa: ANN001 — Pydantic model
        tf = _canonical_tf(s)
        if tf is None:
            return s
        pivots = pivots_by_tf.get(tf, {})
        if not pivots:
            return s
        return s.model_copy(
            update={
                "summary": _decorate(s.summary, pivots, tf),
                "cross_timeframe_alignment": _decorate(s.cross_timeframe_alignment, pivots, tf),
                "cross_framework_agreement": _decorate(s.cross_framework_agreement, pivots, tf),
            }
        )

    return report.model_copy(
        update={"scenarios": [_decorate_scenario(s) for s in report.scenarios]}
    )
