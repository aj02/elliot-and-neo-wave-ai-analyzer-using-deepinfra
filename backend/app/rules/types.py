"""Result types for rule evaluation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Severity = Literal["hard", "soft"]


class RuleResult(BaseModel):
    """Outcome of evaluating a single rule on a single count."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str = Field(description="e.g. 'EW-H-1', 'NW-H-2'.")
    name: str
    severity: Severity
    passed: bool
    message: str = Field(description="Human-readable explanation referencing pivot indices.")


class RuleCompliance(BaseModel):
    """Aggregate result of running every rule against one candidate count."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_results: list[RuleResult]

    @property
    def hard_failures(self) -> list[RuleResult]:
        return [r for r in self.rule_results if r.severity == "hard" and not r.passed]

    @property
    def soft_failures(self) -> list[RuleResult]:
        return [r for r in self.rule_results if r.severity == "soft" and not r.passed]

    @property
    def is_valid(self) -> bool:
        """True iff no hard rule failed."""
        return not self.hard_failures

    @property
    def score(self) -> float:
        """Soft-rule compliance score in [0, 1].

        1.0 means every soft rule passed; 0.0 means every soft rule failed. If no
        soft rules apply, the score is 1.0.
        """
        soft = [r for r in self.rule_results if r.severity == "soft"]
        if not soft:
            return 1.0
        return round(sum(1 for r in soft if r.passed) / len(soft), 4)
