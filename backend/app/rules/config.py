"""Tunable tolerances for rule checks.

Kept here so they can be adjusted without editing rule code. Exposed as a
frozen dataclass; if tolerances ever need to vary by timeframe, add a per-
timeframe override layer here rather than in the rules.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuleTolerances:
    # Elliott
    flat_b_min_retrace: float = 0.90       # EW-H-6: wave B retraces ≥ 90% of A
    wave_2_typical_min: float = 0.382      # EW-S-1: typical wave-2 retracement floor
    wave_2_typical_max: float = 0.786      # EW-S-1: typical wave-2 retracement ceiling
    wave_4_typical_min: float = 0.236      # EW-S-2: typical wave-4 retracement floor
    wave_4_typical_max: float = 0.5        # EW-S-2: typical wave-4 retracement ceiling
    # NEOWave
    similarity_size_ratio: float = 3.0     # NW-H-1: max ratio between same-degree corrective waves
    monotony_motive_ratio: float = 1.30    # NW-H-2: at least one of 1/3/5 must exceed median by this factor
    correction_time_min: float = 1.0       # NW-H-4: corrective time / impulse time ≥ 1.0
    correction_time_max: float = 1.618     # NW-H-4: corrective time / impulse time ≤ 1.618


DEFAULT_TOLERANCES = RuleTolerances()
