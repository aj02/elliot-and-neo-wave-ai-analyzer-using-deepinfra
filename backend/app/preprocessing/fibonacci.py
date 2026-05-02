"""Fibonacci levels — pure math.

Three families:
  * Retracement: a level *between* the start and end of a swing.
  * Extension:   a level *beyond* the end of a swing, projected from the swing's amplitude.
  * Projection:  a separate swing's amplitude projected from a third point.
  * Time ratios: bar-count ratios between waves (e.g. wave 4 ≈ 0.382× wave 2).

These are all deterministic — never produced by an LLM.
"""

from __future__ import annotations

from app.schemas.structure import FibLevel


# Standard ratios used throughout the project.
RETRACEMENT_RATIOS: tuple[float, ...] = (0.236, 0.382, 0.5, 0.618, 0.786)
EXTENSION_RATIOS: tuple[float, ...] = (1.272, 1.414, 1.618, 2.0, 2.618)
TIME_RATIOS: tuple[float, ...] = (0.382, 0.5, 0.618, 1.0, 1.272, 1.618)


def retracement_levels(start_price: float, end_price: float) -> list[FibLevel]:
    """Levels between `start_price` and `end_price`.

    For a swing up (end > start), levels descend from end toward start.
    For a swing down (end < start), levels ascend from end toward start.
    """
    amplitude = end_price - start_price
    return [
        FibLevel(ratio=r, price=round(end_price - r * amplitude, 4))
        for r in RETRACEMENT_RATIOS
    ]


def extension_levels(start_price: float, end_price: float) -> list[FibLevel]:
    """Levels beyond `end_price`, projected by the swing's amplitude.

    Conceptually: "if the next leg = 1.618 × the prior leg, where would it land?"
    """
    amplitude = end_price - start_price
    return [
        FibLevel(ratio=r, price=round(end_price + (r - 1) * amplitude, 4))
        for r in EXTENSION_RATIOS
    ]


def projection_levels(
    leg_a_amplitude: float, projection_origin_price: float, direction: int = 1
) -> list[FibLevel]:
    """Project `leg_a_amplitude × ratio` from `projection_origin_price`.

    Used to compute, e.g., the price target for wave C of a flat given the
    amplitude of wave A. `direction` is +1 for an upward projection, -1 for a
    downward projection.
    """
    if direction not in (-1, 1):
        raise ValueError("direction must be +1 or -1")
    return [
        FibLevel(
            ratio=r,
            price=round(projection_origin_price + direction * r * abs(leg_a_amplitude), 4),
        )
        for r in EXTENSION_RATIOS
    ]


def time_projection_bars(reference_bars: int) -> list[tuple[float, int]]:
    """Compute bar-count projections at the standard time ratios."""
    return [(r, int(round(r * reference_bars))) for r in TIME_RATIOS]
