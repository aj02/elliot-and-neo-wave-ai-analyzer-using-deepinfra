"""POST /analyze schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.responses import _BaseResponse


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    session_id: str = Field(min_length=1)
    instrument_name: str | None = Field(
        default=None,
        max_length=80,
        description=(
            "Override the session's instrument name. If omitted, the value from the "
            "upload session is used."
        ),
    )


class AnalyzeResponse(_BaseResponse):
    run_id: str
    websocket_url: str = Field(
        description="Relative WebSocket URL to subscribe to live run events."
    )
