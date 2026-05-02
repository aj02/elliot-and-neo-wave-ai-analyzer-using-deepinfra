"""Single source of truth for the project disclaimer.

The disclaimer must appear:
  * at the top of the README
  * permanently in the UI footer
  * in every API response as a "disclaimer" field
  * on every report page
  * adjacent to every numeric target / invalidation level
"""

from typing import Final

DISCLAIMER: Final[str] = (
    "wave-agent is an educational and engineering demo. It is NOT investment advice "
    "and NOT a trading recommendation. The system proposes structural interpretations "
    "and deterministic levels; humans decide actions. Numeric levels (invalidation, "
    "Fibonacci, channel projections) are properties of past price geometry, not "
    "forecasts."
)
