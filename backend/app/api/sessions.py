"""GET /sessions/{id} — fetch a staged upload session."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from app.api.deps import SessionStoreDep
from app.core.disclaimer import DISCLAIMER
from app.schemas.input import FileValidation
from app.schemas.upload import SessionView


router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/{session_id}", response_model=SessionView)
async def get_session(session_id: str, sessions: SessionStoreDep) -> SessionView:
    session = await sessions.get(session_id)
    if session is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No upload session with id '{session_id}'. Sessions expire after 24h.",
        )

    files: list[FileValidation] = [
        FileValidation(
            filename=t.filename,
            timeframe=t.timeframe,
            rows=t.rows,
            date_range=_to_tuple(t.date_range),
            issues=list(t.warnings),
        )
        for t in session.timeframes
    ]
    return SessionView(
        session_id=session.id,
        instrument_name=session.instrument_name,
        files=files,
        disclaimer=DISCLAIMER,
    )


def _to_tuple(rng: tuple[datetime, datetime]) -> tuple[datetime, datetime]:
    """No-op coercion kept explicit so future tz/locale shifts have one place to land."""
    return (rng[0], rng[1])
