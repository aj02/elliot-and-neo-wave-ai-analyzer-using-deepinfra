"""Elliott Wave rule validators (Frost & Prechter, *Elliott Wave Principle*).

Each rule is a pure function of `(count, pivots, tolerances) -> RuleResult`.
The aggregator `evaluate_count` runs every applicable rule and packages the
results.

References (see ELLIOTT_RULES.md for the full table with citations):
  EW-H-1 .. EW-H-7 — hard rules; failure rejects the count.
  EW-S-1 .. EW-S-2 — heuristics; failure lowers the score, does not reject.
"""

from __future__ import annotations

from typing import Callable

from app.rules.config import DEFAULT_TOLERANCES, RuleTolerances
from app.rules.types import RuleCompliance, RuleResult
from app.schemas.structure import Pivot
from app.schemas.waves import ElliottCount, WaveSegment


# ---------- helpers ---------------------------------------------------------


def _by_idx(pivots: list[Pivot]) -> dict[int, Pivot]:
    return {p.idx: p for p in pivots}


def _wave(count: ElliottCount, label: str) -> WaveSegment | None:
    return next((w for w in count.waves if w.label == label), None)


def _amplitude(seg: WaveSegment, by_idx: dict[int, Pivot]) -> float:
    """Signed end-minus-start price."""
    return by_idx[seg.end_pivot_idx].price - by_idx[seg.start_pivot_idx].price


def _direction(seg: WaveSegment, by_idx: dict[int, Pivot]) -> int:
    return 1 if _amplitude(seg, by_idx) > 0 else -1


def _bars(seg: WaveSegment) -> int:
    return seg.end_pivot_idx - seg.start_pivot_idx


def _pass(rule_id: str, name: str, severity: str, msg: str) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        name=name,
        severity=severity,  # type: ignore[arg-type]
        passed=True,
        message=msg,
    )


def _fail(rule_id: str, name: str, severity: str, msg: str) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        name=name,
        severity=severity,  # type: ignore[arg-type]
        passed=False,
        message=msg,
    )


# ---------- hard rules ------------------------------------------------------


def rule_ew_h_1(count: ElliottCount, pivots: list[Pivot], _t: RuleTolerances) -> RuleResult | None:
    """EW-H-1: Wave 2 cannot retrace more than 100% of wave 1."""
    name = "Wave 2 ≤ 100% retracement of wave 1"
    if count.pattern not in ("impulse", "leading_diagonal", "ending_diagonal"):
        return None
    w1, w2 = _wave(count, "1"), _wave(count, "2")
    if not w1 or not w2:
        return _fail("EW-H-1", name, "hard", "Pattern requires waves 1 and 2 — at least one is missing.")

    by_idx = _by_idx(pivots)
    direction = _direction(w1, by_idx)
    w1_start = by_idx[w1.start_pivot_idx].price

    # For an upward wave 1, wave 2's end must remain above wave 1's start.
    # For a downward wave 1, wave 2's end must remain below wave 1's start.
    w2_end = by_idx[w2.end_pivot_idx].price
    if direction == 1 and w2_end <= w1_start:
        return _fail(
            "EW-H-1", name, "hard",
            f"Wave 2 end ({w2_end:.2f}) retraced past wave 1 start ({w1_start:.2f}) — "
            f"violates the 100% retracement limit.",
        )
    if direction == -1 and w2_end >= w1_start:
        return _fail(
            "EW-H-1", name, "hard",
            f"Wave 2 end ({w2_end:.2f}) retraced past wave 1 start ({w1_start:.2f}) — "
            f"violates the 100% retracement limit.",
        )
    return _pass("EW-H-1", name, "hard", "Wave 2 retraces less than 100% of wave 1.")


def rule_ew_h_2(count: ElliottCount, pivots: list[Pivot], _t: RuleTolerances) -> RuleResult | None:
    """EW-H-2: Wave 3 is never the shortest of waves 1, 3, 5."""
    name = "Wave 3 not the shortest of (1, 3, 5)"
    if count.pattern not in ("impulse", "leading_diagonal", "ending_diagonal"):
        return None
    w1, w3, w5 = _wave(count, "1"), _wave(count, "3"), _wave(count, "5")
    if not (w1 and w3):
        return None  # Wave 5 may not have started yet — skip rather than fail.
    by_idx = _by_idx(pivots)
    a1 = abs(_amplitude(w1, by_idx))
    a3 = abs(_amplitude(w3, by_idx))
    if w5 is None:
        # Without wave 5, only wave 3 vs wave 1 matters.
        if a3 < a1:
            return _fail(
                "EW-H-2", name, "hard",
                f"Wave 3 amplitude ({a3:.2f}) is shorter than wave 1 ({a1:.2f}); "
                f"wave 3 cannot be the shortest motive wave.",
            )
        return _pass("EW-H-2", name, "hard", "Wave 3 is at least as long as wave 1.")
    a5 = abs(_amplitude(w5, by_idx))
    if a3 < a1 and a3 < a5:
        return _fail(
            "EW-H-2", name, "hard",
            f"Wave 3 ({a3:.2f}) is shorter than wave 1 ({a1:.2f}) AND wave 5 ({a5:.2f}); "
            f"wave 3 must not be the shortest of (1, 3, 5).",
        )
    return _pass("EW-H-2", name, "hard", "Wave 3 is not the shortest of (1, 3, 5).")


def rule_ew_h_3(count: ElliottCount, pivots: list[Pivot], _t: RuleTolerances) -> RuleResult | None:
    """EW-H-3: In a non-diagonal impulse, wave 4 cannot enter wave 1's price territory."""
    name = "Wave 4 does not overlap wave 1 (non-diagonal)"
    if count.pattern != "impulse":
        return None  # Diagonals are allowed to overlap.
    w1, w4 = _wave(count, "1"), _wave(count, "4")
    if not (w1 and w4):
        return None

    by_idx = _by_idx(pivots)
    direction = _direction(w1, by_idx)
    w1_start = by_idx[w1.start_pivot_idx].price
    w1_end = by_idx[w1.end_pivot_idx].price
    w4_end = by_idx[w4.end_pivot_idx].price

    if direction == 1:
        wave1_top = max(w1_start, w1_end)
        if w4_end <= wave1_top:
            return _fail(
                "EW-H-3", name, "hard",
                f"Wave 4 end ({w4_end:.2f}) entered wave 1 territory (top={wave1_top:.2f}) — "
                f"forbidden in a non-diagonal impulse.",
            )
    else:
        wave1_bottom = min(w1_start, w1_end)
        if w4_end >= wave1_bottom:
            return _fail(
                "EW-H-3", name, "hard",
                f"Wave 4 end ({w4_end:.2f}) entered wave 1 territory (bottom={wave1_bottom:.2f}) — "
                f"forbidden in a non-diagonal impulse.",
            )
    return _pass("EW-H-3", name, "hard", "Wave 4 stays outside wave 1's price range.")


def rule_ew_h_4(count: ElliottCount, pivots: list[Pivot], _t: RuleTolerances) -> RuleResult | None:
    """EW-H-4: Motive (1/3/5) and corrective (2/4) waves move in the expected direction."""
    name = "Motive/corrective directional consistency"
    if count.pattern not in ("impulse", "leading_diagonal", "ending_diagonal"):
        return None
    w1 = _wave(count, "1")
    if not w1:
        return None
    by_idx = _by_idx(pivots)
    motive_dir = _direction(w1, by_idx)

    expectations: list[tuple[str, int]] = [
        ("1", motive_dir),
        ("2", -motive_dir),
        ("3", motive_dir),
        ("4", -motive_dir),
        ("5", motive_dir),
    ]
    for label, expected in expectations:
        seg = _wave(count, label)
        if seg is None:
            continue
        if _direction(seg, by_idx) != expected:
            return _fail(
                "EW-H-4", name, "hard",
                f"Wave {label} moves opposite the expected direction "
                f"(expected {'up' if expected == 1 else 'down'}).",
            )
    return _pass("EW-H-4", name, "hard", "Motive and corrective waves move in expected directions.")


def rule_ew_h_5(count: ElliottCount, pivots: list[Pivot], _t: RuleTolerances) -> RuleResult | None:
    """EW-H-5: In a zigzag, wave B retraces less than 100% of wave A."""
    name = "Zigzag wave B retraces < 100% of wave A"
    if count.pattern != "zigzag":
        return None
    a, b = _wave(count, "A"), _wave(count, "B")
    if not (a and b):
        return None
    by_idx = _by_idx(pivots)
    a_start = by_idx[a.start_pivot_idx].price
    b_end = by_idx[b.end_pivot_idx].price
    direction = _direction(a, by_idx)
    # Failure means wave B retraced ≥ 100%, i.e. crossed back through A's start.
    # Up A (B retraces down): fail if b_end ≤ a_start.
    # Down A (B retraces up):  fail if b_end ≥ a_start.
    if direction == 1 and b_end <= a_start:
        return _fail("EW-H-5", name, "hard", f"Wave B ({b_end:.2f}) reached/exceeded wave A start ({a_start:.2f}).")
    if direction == -1 and b_end >= a_start:
        return _fail("EW-H-5", name, "hard", f"Wave B ({b_end:.2f}) reached/exceeded wave A start ({a_start:.2f}).")
    return _pass("EW-H-5", name, "hard", "Wave B retracement of wave A is < 100%.")


def rule_ew_h_6(count: ElliottCount, pivots: list[Pivot], t: RuleTolerances) -> RuleResult | None:
    """EW-H-6: In a (regular) flat, wave B retraces ≥ 90% of wave A."""
    name = f"Flat wave B retraces ≥ {t.flat_b_min_retrace * 100:.0f}% of wave A"
    if count.pattern not in ("flat", "expanded_flat", "running_flat"):
        return None
    a, b = _wave(count, "A"), _wave(count, "B")
    if not (a and b):
        return None
    by_idx = _by_idx(pivots)
    a_amp = abs(_amplitude(a, by_idx))
    b_amp = abs(_amplitude(b, by_idx))
    if a_amp == 0:
        return _fail("EW-H-6", name, "hard", "Wave A has zero amplitude.")
    ratio = b_amp / a_amp
    if ratio < t.flat_b_min_retrace:
        return _fail(
            "EW-H-6", name, "hard",
            f"Wave B retraced only {ratio * 100:.1f}% of wave A — "
            f"below the {t.flat_b_min_retrace * 100:.0f}% flat threshold.",
        )
    return _pass("EW-H-6", name, "hard", f"Wave B retraces {ratio * 100:.1f}% of wave A.")


def rule_ew_h_7(count: ElliottCount, pivots: list[Pivot], _t: RuleTolerances) -> RuleResult | None:
    """EW-H-7: In a contracting triangle, each subsequent leg is shorter than the prior leg of the same direction."""
    name = "Contracting triangle: successive same-direction legs shorten"
    if count.pattern != "triangle_contracting":
        return None
    legs = [_wave(count, lbl) for lbl in ("a", "b", "c", "d", "e")]
    if not all(legs):
        return None
    by_idx = _by_idx(pivots)
    amps = [abs(_amplitude(seg, by_idx)) for seg in legs if seg]  # type: ignore[arg-type]
    # Compare same-direction legs: a vs c vs e (all one direction); b vs d (opposite).
    if not (amps[0] > amps[2] > amps[4]):
        return _fail(
            "EW-H-7", name, "hard",
            f"Contracting triangle requires |a|>|c|>|e|; got |a|={amps[0]:.2f}, "
            f"|c|={amps[2]:.2f}, |e|={amps[4]:.2f}.",
        )
    if not (amps[1] > amps[3]):
        return _fail(
            "EW-H-7", name, "hard",
            f"Contracting triangle requires |b|>|d|; got |b|={amps[1]:.2f}, |d|={amps[3]:.2f}.",
        )
    return _pass("EW-H-7", name, "hard", "Triangle legs contract monotonically.")


# ---------- soft rules (heuristics) ----------------------------------------


def rule_ew_s_1(count: ElliottCount, pivots: list[Pivot], t: RuleTolerances) -> RuleResult | None:
    """EW-S-1: Wave 2 typically retraces 38.2–78.6% of wave 1."""
    name = f"Wave 2 typical retracement {t.wave_2_typical_min:.3f}–{t.wave_2_typical_max:.3f}"
    if count.pattern not in ("impulse", "leading_diagonal", "ending_diagonal"):
        return None
    w1, w2 = _wave(count, "1"), _wave(count, "2")
    if not (w1 and w2):
        return None
    by_idx = _by_idx(pivots)
    a1 = abs(_amplitude(w1, by_idx))
    a2 = abs(_amplitude(w2, by_idx))
    if a1 == 0:
        return None
    ratio = a2 / a1
    if t.wave_2_typical_min <= ratio <= t.wave_2_typical_max:
        return _pass("EW-S-1", name, "soft", f"Wave 2 retraces {ratio * 100:.1f}% of wave 1.")
    return _fail(
        "EW-S-1", name, "soft",
        f"Wave 2 retraces {ratio * 100:.1f}% of wave 1 — outside the typical "
        f"{t.wave_2_typical_min * 100:.0f}–{t.wave_2_typical_max * 100:.0f}% range.",
    )


def rule_ew_s_2(count: ElliottCount, pivots: list[Pivot], t: RuleTolerances) -> RuleResult | None:
    """EW-S-2: Wave 4 typically retraces 23.6–50% of wave 3."""
    name = f"Wave 4 typical retracement {t.wave_4_typical_min:.3f}–{t.wave_4_typical_max:.3f}"
    if count.pattern not in ("impulse", "leading_diagonal", "ending_diagonal"):
        return None
    w3, w4 = _wave(count, "3"), _wave(count, "4")
    if not (w3 and w4):
        return None
    by_idx = _by_idx(pivots)
    a3 = abs(_amplitude(w3, by_idx))
    a4 = abs(_amplitude(w4, by_idx))
    if a3 == 0:
        return None
    ratio = a4 / a3
    if t.wave_4_typical_min <= ratio <= t.wave_4_typical_max:
        return _pass("EW-S-2", name, "soft", f"Wave 4 retraces {ratio * 100:.1f}% of wave 3.")
    return _fail(
        "EW-S-2", name, "soft",
        f"Wave 4 retraces {ratio * 100:.1f}% of wave 3 — outside the typical "
        f"{t.wave_4_typical_min * 100:.0f}–{t.wave_4_typical_max * 100:.0f}% range.",
    )


# ---------- aggregator ------------------------------------------------------


_HARD_RULES: tuple[Callable[..., RuleResult | None], ...] = (
    rule_ew_h_1, rule_ew_h_2, rule_ew_h_3, rule_ew_h_4,
    rule_ew_h_5, rule_ew_h_6, rule_ew_h_7,
)
_SOFT_RULES: tuple[Callable[..., RuleResult | None], ...] = (
    rule_ew_s_1, rule_ew_s_2,
)


def evaluate_count(
    count: ElliottCount,
    pivots: list[Pivot],
    tolerances: RuleTolerances = DEFAULT_TOLERANCES,
) -> RuleCompliance:
    """Run every applicable Elliott rule against `count`. Inapplicable rules are skipped."""
    results: list[RuleResult] = []
    for rule in (*_HARD_RULES, *_SOFT_RULES):
        outcome = rule(count, pivots, tolerances)
        if outcome is not None:
            results.append(outcome)
    return RuleCompliance(rule_results=results)
