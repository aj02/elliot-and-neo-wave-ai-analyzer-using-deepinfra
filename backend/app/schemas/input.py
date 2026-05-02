"""Input schemas for upload + validation."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.timeframe import Timeframe


class ValidationIssue(BaseModel):
    """A single problem found during CSV validation.

    `severity = "error"` rejects the file. `severity = "warning"` surfaces a hint
    (e.g. detected gap) without rejecting.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    severity: Literal["error", "warning"]
    code: str = Field(description="Machine-readable code, e.g. 'OHLC_SANITY'.")
    message: str = Field(description="User-facing message — must be actionable.")
    row: int | None = Field(default=None, description="1-based row number, when applicable.")


class FileValidation(BaseModel):
    """Validation result for a single uploaded CSV."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    filename: str
    timeframe: Timeframe
    rows: int
    date_range: tuple[datetime, datetime] | None
    issues: list[ValidationIssue]

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


class UploadedTimeframe(BaseModel):
    """A successfully validated CSV ready for preprocessing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    filename: str
    timeframe: Timeframe
    rows: int
    date_range: tuple[datetime, datetime]
    storage_path: str = Field(description="Filesystem path where the CSV is staged.")
    warnings: list[ValidationIssue] = Field(default_factory=list)
