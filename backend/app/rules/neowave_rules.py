"""NEOWave rule validators (Glenn Neely, *Mastering Elliott Wave*).

Implemented hard rules:
  NW-H-1  Rule of Similarity & Balance (corrective same-degree wave consistency)
  NW-H-2  Monotony (an impulse cannot have all three motive waves of similar size)
  NW-H-4  Time relationships (correction time / impulse time ∈ [1.0, 1.618])

NW-H-3 (channeling), NW-H-5 (diametric), NW-H-6 (symmetrical), NW-H-7
(triangle progression) are pattern-specific and require deeper mono-wave
machinery; they are skipped at the rule level today and noted in the
methodology page so users know the boundary of the deterministic check.
"""

from __future__ import annotations

import statistics
from typing import Callable

from app.rules.config import DEFAULT_TOLERANCES, RuleTolerances
from app.rules.types import RuleCompliance, RuleResult
from app.schemas.structure import Pivot
from app.schemas.waves import NeowaveCount, WaveSegment


def _by_idx(pivots: list[Pivot]) -> dict[int, Pivot]:
    return {p.idx: p for p in pivots}


def _amp(seg: WaveSegment, by_idx: dict[int, Pivot]) -> float:
    return abs(by_idx[seg.end_pivot_idx].price - by_idx[seg.start_pivot_idx].price)


def _bars(seg: WaveSegment) -> int:
    return seg.end_pivot_idx - seg.start_pivot_idx


def _pass(rule_id: str, name: str, severity: str, msg: str) -> RuleResult:
    return RuleResult(rule_id=rule_id, name=name, severity=severity, passed=True, message=msg)  # type: ignore[arg-type]


def _fail(rule_id: str, name: str, severity: str, msg: str) -> RuleResult:
    return RuleResult(rule_id=rule_id, name=name, severity=severity, passed=False, message=msg)  # type: ignore[arg-type]


# ---------- hard rules ------------------------------------------------------


def rule_nw_h_1(count: NeowaveCount, pivots: list[Pivot], t: RuleTolerances) -> RuleResult | None:
    """NW-H-1: Rule of Similarity & Balance — same-degree corrective waves are similar in size and time."""
    name = "Rule of Similarity & Balance"
    # Only meaningful for corrective patterns with >= 3 components at the same degree.
    if count.pattern not in (
        "flat",
        "zigzag",
        "triangle_contracting",
        "triangle_expanding",
        "diametric",
        "symmetrical",
    ):
        return None
    if len(count.mono_waves) < 3:
        return None
    by_idx = _by_idx(pivots)
    sizes = [_amp(w, by_idx) for w in count.mono_waves]
    if any(s == 0 for s in sizes):
        return _fail("NW-H-1", name, "hard", "One or more mono-waves have zero amplitude.")
    median = statistics.median(sizes)
    max_ratio = max(s / median for s in sizes)
    min_ratio = min(s / median for s in sizes)
    spread = max_ratio / min_ratio
    if spread > t.similarity_size_ratio:
        return _fail(
            "NW-H-1", name, "hard",
            f"Mono-wave size spread {spread:.2f}× exceeds the {t.similarity_size_ratio:.1f}× "
            f"Similarity & Balance limit (sizes={[round(s, 2) for s in sizes]}).",
        )
    return _pass("NW-H-1", name, "hard", f"Mono-wave size spread {spread:.2f}× is within tolerance.")


def rule_nw_h_2(count: NeowaveCount, pivots: list[Pivot], t: RuleTolerances) -> RuleResult | None:
    """NW-H-2: An impulse cannot have all three motive waves (m1, m3, m5) of similar size."""
    name = "Monotony — at least one motive wave must be extended"
    if count.pattern != "impulse":
        return None
    # NEOWave impulses have 5 mono-waves (m1..m5). Motive waves are 1, 3, 5 (indices 0, 2, 4).
    if len(count.mono_waves) < 5:
        return None
    by_idx = _by_idx(pivots)
    motive = [count.mono_waves[i] for i in (0, 2, 4)]
    sizes = [_amp(w, by_idx) for w in motive]
    if any(s == 0 for s in sizes):
        return _fail("NW-H-2", name, "hard", "Motive wave with zero amplitude.")
    median = statistics.median(sizes)
    largest = max(sizes)
    if largest / median < t.monotony_motive_ratio:
        return _fail(
            "NW-H-2", name, "hard",
            f"All three motive waves are similarly sized "
            f"(largest/median={largest / median:.2f}× < {t.monotony_motive_ratio:.2f}× threshold) — "
            f"violates monotony.",
        )
    return _pass(
        "NW-H-2", name, "hard",
        f"At least one motive wave is extended (largest/median={largest / median:.2f}×).",
    )


def rule_nw_h_4(count: NeowaveCount, pivots: list[Pivot], t: RuleTolerances) -> RuleResult | None:
    """NW-H-4: Corrective patterns generally consume 100–161.8% of the prior impulse's time.

    For this check the count must include both an impulse identification (in
    `current_position` referencing 'after impulse') AND the prior impulse's
    bar-count via the `mono_waves` list. The agent supplies these via the
    schema; if absent, the rule is skipped.
    """
    name = "Corrective time ∈ [1.0, 1.618] × prior impulse time"
    if count.pattern not in ("flat", "zigzag", "triangle_contracting", "triangle_expanding"):
        return None
    if len(count.mono_waves) < 2:
        return None
    # Treat the first mono-wave as the impulse reference; the remainder as the correction.
    impulse_bars = _bars(count.mono_waves[0])
    correction_bars = sum(_bars(w) for w in count.mono_waves[1:])
    if impulse_bars <= 0:
        return None
    ratio = correction_bars / impulse_bars
    if t.correction_time_min <= ratio <= t.correction_time_max:
        return _pass(
            "NW-H-4", name, "hard",
            f"Correction/impulse time ratio = {ratio:.2f}, within [{t.correction_time_min:.2f}, {t.correction_time_max:.2f}].",
        )
    return _fail(
        "NW-H-4", name, "hard",
        f"Correction/impulse time ratio = {ratio:.2f}, outside [{t.correction_time_min:.2f}, "
        f"{t.correction_time_max:.2f}].",
    )


# ---------- aggregator ------------------------------------------------------


_HARD_RULES: tuple[Callable[..., RuleResult | None], ...] = (
    rule_nw_h_1, rule_nw_h_2, rule_nw_h_4,
)


def evaluate_count(
    count: NeowaveCount,
    pivots: list[Pivot],
    tolerances: RuleTolerances = DEFAULT_TOLERANCES,
) -> RuleCompliance:
    """Run every applicable NEOWave rule against `count`."""
    results: list[RuleResult] = []
    for rule in _HARD_RULES:
        outcome = rule(count, pivots, tolerances)
        if outcome is not None:
            results.append(outcome)
    return RuleCompliance(rule_results=results)
