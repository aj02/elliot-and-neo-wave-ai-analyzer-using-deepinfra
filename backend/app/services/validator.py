"""Validator service.

Runs Elliott/NEOWave rules against agent-proposed counts, partitions surviving
from rejected, and computes deterministic invalidation levels per surviving
count. Numeric outputs (the prices in InvalidationLevel) are computed in
Python — never produced by an LLM.

Pattern coverage:
  * Elliott impulse / leading_diagonal / ending_diagonal — invalidation for
    current_wave 1, 2, 3, 4, 5.
  * Elliott zigzag — invalidation for current_wave B / C.
  * Other patterns (flat, triangle, combinations) currently return
    invalidation=None and the report shows a "no deterministic invalidation
    for this pattern at this current_wave" note. Adding more is an iterative
    project.
"""

from __future__ import annotations

from app.agents.elliott_agent import ElliottAgentOutput
from app.agents.neowave_agent import NeowaveAgentOutput
from app.core.logging import get_logger
from app.rules import elliott_rules, neowave_rules
from app.rules.config import DEFAULT_TOLERANCES, RuleTolerances
from app.schemas.levels import InvalidationLevel
from app.schemas.structure import Pivot
from app.schemas.validated import (
    ValidatedElliottCount,
    ValidatedNeowaveCount,
    ValidationOutcome,
)
from app.rules.types import RuleCompliance, RuleResult
from app.schemas.waves import ElliottCount, NeowaveCount, WaveSegment


log = get_logger("services.validator")


# ---------------------------------------------------------------------------
# Pivot-reference sanity. LLMs sometimes hallucinate pivot indices that don't
# exist in the input (e.g. emit "9" when actual indices are 0, 56, 85, …).
# We reject such counts with a clear reason so the rest of the pipeline
# continues instead of crashing on a KeyError inside a rule check.
# ---------------------------------------------------------------------------


def _invalid_pivot_ref(
    segments: list[WaveSegment], valid_idx: set[int]
) -> tuple[str, int, int] | None:
    """Return `(wave_label, start_idx, end_idx)` of the first segment whose
    indices are not all present in `valid_idx`, or None if all are valid."""
    for seg in segments:
        if seg.start_pivot_idx not in valid_idx or seg.end_pivot_idx not in valid_idx:
            return (seg.label, seg.start_pivot_idx, seg.end_pivot_idx)
    return None


def _bad_pivot_compliance(
    bad: tuple[str, int, int], valid_idx: set[int], rule_id: str
) -> RuleCompliance:
    label, start, end = bad
    sample = sorted(valid_idx)[:6]
    sample_str = ", ".join(str(i) for i in sample)
    return RuleCompliance(
        rule_results=[
            RuleResult(
                rule_id=rule_id,
                name="Pivot reference validity",
                severity="hard",
                passed=False,
                message=(
                    f"Wave '{label}' references pivot indices ({start}, {end}) "
                    f"that are not in the StructureSummary. Valid indices begin: "
                    f"{sample_str}…. The agent likely confused 1-based positions "
                    f"with bar indices."
                ),
            )
        ]
    )


# ---------------------------------------------------------------------------
# Invalidation computation
# ---------------------------------------------------------------------------


def _wave(count: ElliottCount, label: str) -> WaveSegment | None:
    return next((w for w in count.waves if w.label == label), None)


def _direction_from_wave_1(count: ElliottCount, by_idx: dict[int, Pivot]) -> int:
    w1 = _wave(count, "1")
    if w1 is None:
        return 0
    return 1 if by_idx[w1.end_pivot_idx].price > by_idx[w1.start_pivot_idx].price else -1


def compute_elliott_invalidation(
    count: ElliottCount, pivots: list[Pivot]
) -> InvalidationLevel | None:
    """Return the deterministic invalidation level for an Elliott count.

    The level is the price whose violation contradicts the rule that defines
    the *current* wave. None for patterns/positions that don't have a
    universally-defined invalidation in this implementation.
    """
    by_idx = {p.idx: p for p in pivots}
    cw = count.current_wave

    if count.pattern in ("impulse", "leading_diagonal", "ending_diagonal"):
        direction = _direction_from_wave_1(count, by_idx)
        if direction == 0:
            return None
        invalidate_when_below = direction == 1  # up impulse → invalidation below
        side = "below" if invalidate_when_below else "above"

        if cw in ("1", "2"):
            w1 = _wave(count, "1")
            if w1 is None:
                return None
            price = by_idx[w1.start_pivot_idx].price
            return InvalidationLevel(
                price=price,
                direction=side,
                reason=(
                    f"Wave 2 cannot retrace 100% of wave 1 — count fails if price "
                    f"moves {side} pivot #{w1.start_pivot_idx} ({price:.2f})."
                ),
            )
        if cw == "3":
            w1 = _wave(count, "1")
            if w1 is None:
                return None
            price = by_idx[w1.end_pivot_idx].price
            return InvalidationLevel(
                price=price,
                direction=side,
                reason=(
                    f"Wave 3 must extend beyond wave 1 — count fails if price "
                    f"moves {side} pivot #{w1.end_pivot_idx} ({price:.2f})."
                ),
            )
        if cw == "4" and count.pattern == "impulse":
            w1 = _wave(count, "1")
            if w1 is None:
                return None
            price = by_idx[w1.end_pivot_idx].price
            return InvalidationLevel(
                price=price,
                direction=side,
                reason=(
                    f"Wave 4 cannot enter wave 1 territory — count fails if price "
                    f"moves {side} pivot #{w1.end_pivot_idx} ({price:.2f})."
                ),
            )
        if cw == "5":
            # An ongoing wave 5 must extend in the trend direction; falling back
            # past wave 4's terminal pivot signals truncation/failure.
            w4 = _wave(count, "4")
            if w4 is None:
                return None
            price = by_idx[w4.end_pivot_idx].price
            return InvalidationLevel(
                price=price,
                direction=side,
                reason=(
                    f"Wave 5 must extend beyond wave 4 end — count fails if price "
                    f"moves {side} pivot #{w4.end_pivot_idx} ({price:.2f})."
                ),
            )

    if count.pattern == "zigzag":
        a = _wave(count, "A")
        if a is None:
            return None
        a_start = by_idx[a.start_pivot_idx].price
        a_dir = 1 if by_idx[a.end_pivot_idx].price > a_start else -1
        if cw in ("B", "C"):
            side = "above" if a_dir == -1 else "below"
            return InvalidationLevel(
                price=a_start,
                direction=side,
                reason=(
                    f"Zigzag wave B cannot retrace 100% of wave A — count fails if "
                    f"price moves {side} pivot #{a.start_pivot_idx} ({a_start:.2f})."
                ),
            )
    return None


# ---------------------------------------------------------------------------
# Validation entry points
# ---------------------------------------------------------------------------


def validate_elliott(
    output: ElliottAgentOutput,
    pivots: list[Pivot],
    *,
    timeframe: str,
    tolerances: RuleTolerances = DEFAULT_TOLERANCES,
) -> tuple[list[ValidatedElliottCount], list[ValidatedElliottCount]]:
    """Run Elliott rules against each candidate; partition surviving / rejected."""
    surviving: list[ValidatedElliottCount] = []
    rejected: list[ValidatedElliottCount] = []
    valid_idx = {p.idx for p in pivots}

    for count in output.counts:
        bad = _invalid_pivot_ref(list(count.waves), valid_idx)
        if bad is not None:
            compliance = _bad_pivot_compliance(bad, valid_idx, rule_id="EW-PIVOT-REF")
            rejected.append(
                ValidatedElliottCount(count=count, compliance=compliance, invalidation=None)
            )
            log.info(
                "validator.elliott.rejected.pivot_ref",
                timeframe=timeframe,
                pattern=count.pattern,
                bad_wave=bad[0],
                bad_start=bad[1],
                bad_end=bad[2],
            )
            continue

        compliance = elliott_rules.evaluate_count(count, pivots, tolerances)
        invalidation = compute_elliott_invalidation(count, pivots) if compliance.is_valid else None
        validated = ValidatedElliottCount(
            count=count, compliance=compliance, invalidation=invalidation
        )
        if compliance.is_valid:
            surviving.append(validated)
        else:
            rejected.append(validated)
            log.info(
                "validator.elliott.rejected",
                timeframe=timeframe,
                pattern=count.pattern,
                current_wave=count.current_wave,
                reasons=[r.message for r in compliance.hard_failures],
            )
    surviving.sort(key=lambda v: -v.compliance.score)
    return surviving, rejected


def validate_neowave(
    output: NeowaveAgentOutput,
    pivots: list[Pivot],
    *,
    timeframe: str,
    tolerances: RuleTolerances = DEFAULT_TOLERANCES,
) -> tuple[list[ValidatedNeowaveCount], list[ValidatedNeowaveCount]]:
    """Run NEOWave rules against each candidate; partition surviving / rejected.

    NEOWave invalidation is pattern-specific and not yet implemented for most
    patterns; surviving counts get `invalidation=None` for now.
    """
    surviving: list[ValidatedNeowaveCount] = []
    rejected: list[ValidatedNeowaveCount] = []
    valid_idx = {p.idx for p in pivots}

    for count in output.counts:
        bad = _invalid_pivot_ref(list(count.mono_waves), valid_idx)
        if bad is not None:
            compliance = _bad_pivot_compliance(bad, valid_idx, rule_id="NW-PIVOT-REF")
            rejected.append(
                ValidatedNeowaveCount(count=count, compliance=compliance, invalidation=None)
            )
            log.info(
                "validator.neowave.rejected.pivot_ref",
                timeframe=timeframe,
                pattern=count.pattern,
                bad_wave=bad[0],
                bad_start=bad[1],
                bad_end=bad[2],
            )
            continue

        compliance = neowave_rules.evaluate_count(count, pivots, tolerances)
        validated = ValidatedNeowaveCount(count=count, compliance=compliance, invalidation=None)
        if compliance.is_valid:
            surviving.append(validated)
        else:
            rejected.append(validated)
            log.info(
                "validator.neowave.rejected",
                timeframe=timeframe,
                pattern=count.pattern,
                current_position=count.current_position,
                reasons=[r.message for r in compliance.hard_failures],
            )
    surviving.sort(key=lambda v: -v.compliance.score)
    return surviving, rejected


def validate_timeframe(
    elliott_output: ElliottAgentOutput,
    neowave_output: NeowaveAgentOutput,
    pivots: list[Pivot],
    *,
    timeframe: str,
    tolerances: RuleTolerances = DEFAULT_TOLERANCES,
) -> ValidationOutcome:
    """Combined Elliott + NEOWave validation for one timeframe."""
    e_surv, e_rej = validate_elliott(elliott_output, pivots, timeframe=timeframe, tolerances=tolerances)
    n_surv, n_rej = validate_neowave(neowave_output, pivots, timeframe=timeframe, tolerances=tolerances)
    return ValidationOutcome(
        timeframe=timeframe,
        elliott_surviving=e_surv,
        elliott_rejected=e_rej,
        neowave_surviving=n_surv,
        neowave_rejected=n_rej,
    )
