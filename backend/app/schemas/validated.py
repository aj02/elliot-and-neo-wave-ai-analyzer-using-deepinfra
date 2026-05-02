"""Schema for a count that has been through the deterministic Validator."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.rules.types import RuleCompliance
from app.schemas.levels import InvalidationLevel
from app.schemas.waves import ElliottCount, NeowaveCount


class ValidatedElliottCount(BaseModel):
    """An Elliott count after rule evaluation + invalidation computation."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    count: ElliottCount
    compliance: RuleCompliance
    invalidation: InvalidationLevel | None = None

    @property
    def is_valid(self) -> bool:
        return self.compliance.is_valid


class ValidatedNeowaveCount(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    count: NeowaveCount
    compliance: RuleCompliance
    invalidation: InvalidationLevel | None = None

    @property
    def is_valid(self) -> bool:
        return self.compliance.is_valid


class ValidationOutcome(BaseModel):
    """Per-timeframe Validator output.

    `surviving` are sorted by descending soft-rule score. `rejected` retains
    the original agent ordering so a debug view can correlate them.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    timeframe: str
    elliott_surviving: list[ValidatedElliottCount] = Field(default_factory=list)
    elliott_rejected: list[ValidatedElliottCount] = Field(default_factory=list)
    neowave_surviving: list[ValidatedNeowaveCount] = Field(default_factory=list)
    neowave_rejected: list[ValidatedNeowaveCount] = Field(default_factory=list)
