# Encoded rules

> **Disclaimer:** wave-agent is an educational and engineering demo. It is not investment advice.

This document lists every rule encoded in [`backend/app/rules/elliott_rules.py`](backend/app/rules/elliott_rules.py) and [`backend/app/rules/neowave_rules.py`](backend/app/rules/neowave_rules.py). Rules are deterministic Python checks run **after** an LLM agent proposes a count; rule-violating counts are rejected before reaching the user.

The list below also notes which rules are *hard rules* (a violation rejects the count outright) vs. *heuristics* (a violation lowers the rule-compliance score but does not reject), and the **status** column makes the implementation boundary explicit.

> **Sources.** Elliott rules follow Frost & Prechter, *Elliott Wave Principle: Key to Market Behavior* (Prechter). NEOWave rules follow Glenn Neely, *Mastering Elliott Wave* (Neely).

## Elliott Wave rules (`elliott_rules.py`)

### Hard rules (rejection on violation)

| ID         | Rule                                                                                       | Citation        | Status |
| ---------- | ------------------------------------------------------------------------------------------ | --------------- | ------ |
| EW-H-1     | Wave 2 cannot retrace more than 100% of wave 1.                                            | Prechter, Ch. 1 | ✅ encoded |
| EW-H-2     | Wave 3 is never the shortest of waves 1, 3, 5.                                             | Prechter, Ch. 1 | ✅ encoded |
| EW-H-3     | In a non-diagonal impulse, wave 4 cannot enter the price territory of wave 1.              | Prechter, Ch. 1 | ✅ encoded |
| EW-H-4     | Waves 1, 3, 5 are net directional with the trend; waves 2 / 4 retrace.                     | Prechter, Ch. 1 | ✅ encoded |
| EW-H-5     | In a zigzag, wave B retracement of wave A is < 100%.                                       | Prechter, Ch. 2 | ✅ encoded |
| EW-H-6     | In a flat, wave B retraces wave A by ≥ 90%.                                                | Prechter, Ch. 2 | ✅ encoded |
| EW-H-7     | In a contracting triangle, successive same-direction legs shorten.                         | Prechter, Ch. 2 | ✅ encoded |

### Heuristics (score-only)

| ID         | Heuristic                                                                                  | Status |
| ---------- | ------------------------------------------------------------------------------------------ | ------ |
| EW-S-1     | Wave 2 commonly retraces 38.2–78.6% of wave 1.                                             | ✅ encoded |
| EW-S-2     | Wave 4 commonly retraces 23.6–50% of wave 3.                                               | ✅ encoded |
| EW-S-3     | Alternation: if wave 2 is sharp, wave 4 tends to be sideways.                              | 🟡 in agent rationale only |
| EW-S-4     | Wave 5 frequently equals wave 1 in price, or projects 0.618 × (wave 1 + wave 3).           | 🟡 surfaced as Fibonacci zone, not yet a scoring rule |
| EW-S-5     | Channeling: 1–3 trendline parallel through wave 2 contains wave 4.                         | 🟡 channel is computed deterministically; rule check pending |
| EW-S-6     | Volume divergence in wave 5.                                                               | 🟡 requires volume data wiring (most CSV sources omit it) |

## NEOWave rules (`neowave_rules.py`)

### Hard rules (rejection on violation)

| ID         | Rule                                                                                       | Citation               | Status |
| ---------- | ------------------------------------------------------------------------------------------ | ---------------------- | ------ |
| NW-H-1     | Rule of Similarity & Balance: same-degree corrective waves share similar duration and price extent. | Neely, Ch. 5 | ✅ encoded (size spread ≤ 3.0×) |
| NW-H-2     | Monotony: an impulse cannot have all three motive waves of similar size — one must be extended. | Neely, Ch. 5 | ✅ encoded (largest/median ≥ 1.30×) |
| NW-H-3     | Channeling: a valid impulse must channel through specific pivot pairs (m1–m3 / m2–m4).     | Neely, Ch. 5           | 🟡 deferred (channel geometry is computed; pattern-specific check pending) |
| NW-H-4     | Time relationships: corrective patterns generally consume 100–161.8% of the prior impulse's time. | Neely, Ch. 6   | ✅ encoded |
| NW-H-5     | Diametric pattern: 7 segments, alternation between contraction and expansion.              | Neely, Ch. 6           | 🟡 deferred (requires diametric mono-wave segmentation) |
| NW-H-6     | Symmetrical pattern: 7 segments of similar size and duration.                              | Neely, Ch. 6           | 🟡 deferred |
| NW-H-7     | Triangle progression rules: contracting / expanding / neutral classification.              | Neely, Ch. 6           | 🟡 partially covered by EW-H-7; full classification pending |

### Heuristics (score-only)

| ID         | Heuristic                                                                                  | Status |
| ---------- | ------------------------------------------------------------------------------------------ | ------ |
| NW-S-1     | Logic Rule: a complex correction is followed by an impulse, not another correction.        | 🟡 cross-timeframe synthesis only |
| NW-S-2     | Power Ratings.                                                                             | 🟡 deferred |
| NW-S-3     | Mono-wave classification (F1–F3) constrains valid pattern continuations.                   | 🟡 deferred |

> **Legend.**  ✅ encoded — exercised by the test suite, runs against every proposed count.  🟡 deferred — listed for transparency; not blocking the validator. The methodology page on the report mirrors this status.

## What is *not* encoded

These are intentionally left out of the deterministic validator:

- Sentiment alignment (no sentiment data is ingested).
- Intermarket relationships (this project analyses one instrument at a time).
- Wave personality (psychological characteristics) — interpretive, not structural; belongs in agent rationale.

## Implementation notes

- Each rule function takes `(count, pivots, tolerances)` and returns `RuleResult(rule_id, name, severity, passed, message)`. Inapplicable rules return `None` and are skipped.
- The aggregator `evaluate_count` returns `RuleCompliance` with `is_valid` (no hard failures) and `score` (soft-rule pass-rate in [0, 1]).
- Tolerances live in [`backend/app/rules/config.py`](backend/app/rules/config.py) — single place to tune.
- Test coverage: 16 rule tests in [`backend/tests/rules/`](backend/tests/rules/). Each ✅ rule has at least one positive and one negative case.
