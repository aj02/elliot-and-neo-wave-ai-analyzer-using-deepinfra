"""POST /upload — multipart upload of 1..N OHLCV CSVs with timeframe labels.

Each file is validated synchronously. If any file fails, the request is
rejected with HTTP 422 and a structured per-file error report. If all files
pass, a session is staged in Redis (24h TTL) and the session_id returned.
"""

from __future__ import annotations

import io
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.api.deps import SessionStoreDep, StorageDep
from app.core.config import get_settings
from app.core.disclaimer import DISCLAIMER
from app.core.logging import get_logger
from app.preprocessing.csv_loader import CsvLoadError, load_csv
from app.preprocessing.validators import ValidationFailed, validate
from app.schemas.input import FileValidation, UploadedTimeframe, ValidationIssue
from app.schemas.timeframe import Timeframe
from app.schemas.upload import UploadResponse


router = APIRouter(prefix="/upload", tags=["upload"])
log = get_logger("api.upload")


MAX_INSTRUMENT_LEN = 80
MAX_FILES_PER_UPLOAD = 8


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def post_upload(
    sessions: SessionStoreDep,
    storage: StorageDep,
    instrument_name: Annotated[str, Form(min_length=1, max_length=MAX_INSTRUMENT_LEN)],
    timeframes: Annotated[list[str], Form()],
    files: Annotated[list[UploadFile], File()],
) -> UploadResponse:
    """Validate and stage 1..N OHLCV CSVs.

    Form fields:
        instrument_name: free-text label, e.g. "NIFTY 50".
        timeframes: list of timeframe strings, parallel to `files`.
        files: list of CSV uploads.
    """
    settings = get_settings()

    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "At least one file is required.")
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Too many files: limit is {MAX_FILES_PER_UPLOAD} per upload.",
        )
    if len(timeframes) != len(files):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"`timeframes` length ({len(timeframes)}) must match `files` length ({len(files)}).",
        )

    # Reject duplicate timeframe labels — one CSV per timeframe per session.
    seen_tfs: set[str] = set()
    for tf in timeframes:
        if tf in seen_tfs:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Duplicate timeframe label '{tf}'. Each timeframe may appear at most once.",
            )
        seen_tfs.add(tf)

    parsed_tfs: list[Timeframe] = []
    for tf in timeframes:
        try:
            parsed_tfs.append(Timeframe(tf))
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Unknown timeframe '{tf}'. Valid values: "
                f"{[t.value for t in Timeframe]}.",
            ) from exc

    # Validate each file. Stage to a tentative session id; if any file fails, no session is created.
    from app.upload.sessions import new_session_id

    session_id = new_session_id()

    file_validations: list[FileValidation] = []
    accepted_uploads: list[UploadedTimeframe] = []

    for upload, tf in zip(files, parsed_tfs, strict=True):
        content = await upload.read()
        if len(content) > settings.max_upload_bytes:
            file_validations.append(
                FileValidation(
                    filename=upload.filename or "<unknown>",
                    timeframe=tf,
                    rows=0,
                    date_range=None,
                    issues=[
                        ValidationIssue(
                            severity="error",
                            code="FILE_TOO_LARGE",
                            message=(
                                f"File exceeds {settings.max_upload_bytes // (1024 * 1024)} MiB; "
                                "trim history or downsample first."
                            ),
                        )
                    ],
                )
            )
            continue

        result = _validate_one(content, filename=upload.filename or "<unknown>", timeframe=tf)
        file_validations.append(result)

        if result.is_valid:
            staged = storage.write(session_id, tf, content)
            assert result.date_range is not None  # noqa: S101 - guaranteed by is_valid path
            accepted_uploads.append(
                UploadedTimeframe(
                    filename=result.filename,
                    timeframe=result.timeframe,
                    rows=result.rows,
                    date_range=result.date_range,
                    storage_path=str(staged),
                    warnings=result.warnings,
                )
            )

    all_passed = all(v.is_valid for v in file_validations)

    if not all_passed:
        # Roll back staged files for this would-be session.
        try:
            storage.remove_session(session_id)
        except OSError:  # noqa: PERF203 — best-effort cleanup
            pass
        log.info(
            "upload.rejected",
            instrument_name=instrument_name,
            files=[v.filename for v in file_validations],
            error_count=sum(len(v.errors) for v in file_validations),
        )
        return UploadResponse(
            session_id="",
            instrument_name=instrument_name,
            files=file_validations,
            accepted=False,
            disclaimer=DISCLAIMER,
        )

    session = await sessions.create(
        instrument_name=instrument_name,
        timeframes=accepted_uploads,
    )
    log.info(
        "upload.accepted",
        session_id=session.id,
        instrument_name=instrument_name,
        timeframe_count=len(accepted_uploads),
    )

    return UploadResponse(
        session_id=session.id,
        instrument_name=instrument_name,
        files=file_validations,
        accepted=True,
        disclaimer=DISCLAIMER,
    )


def _validate_one(content: bytes, *, filename: str, timeframe: Timeframe) -> FileValidation:
    """Run csv_loader + validators on a single uploaded file's bytes."""
    try:
        df, _ = load_csv(io.BytesIO(content))
    except CsvLoadError as exc:
        return FileValidation(
            filename=filename,
            timeframe=timeframe,
            rows=0,
            date_range=None,
            issues=list(exc.issues),
        )

    try:
        df, warnings = validate(df)
    except ValidationFailed as exc:
        return FileValidation(
            filename=filename,
            timeframe=timeframe,
            rows=int(len(df)),
            date_range=(
                df["datetime"].iloc[0].to_pydatetime(),
                df["datetime"].iloc[-1].to_pydatetime(),
            )
            if len(df)
            else None,
            issues=list(exc.issues),
        )

    return FileValidation(
        filename=filename,
        timeframe=timeframe,
        rows=int(len(df)),
        date_range=(
            df["datetime"].iloc[0].to_pydatetime(),
            df["datetime"].iloc[-1].to_pydatetime(),
        ),
        issues=list(warnings),
    )
