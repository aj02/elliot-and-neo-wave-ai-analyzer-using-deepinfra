"""Upload-flow API schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.input import FileValidation
from app.schemas.responses import _BaseResponse


class UploadResponse(_BaseResponse):
    """Response from POST /upload."""

    session_id: str
    instrument_name: str
    files: list[FileValidation]
    accepted: bool = Field(
        description="True iff every file passed validation. False rejects the session."
    )


class SessionView(_BaseResponse):
    """GET /sessions/{id} payload."""

    session_id: str
    instrument_name: str
    files: list[FileValidation]


class UploadError(BaseModel):
    """Per-file error block surfaced when *any* file failed validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    filename: str
    issues: list[dict[str, str | int | None]]
