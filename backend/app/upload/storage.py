"""Filesystem-backed storage for staged CSV uploads.

Files are written to `<storage_root>/sessions/<session_id>/<timeframe>.csv`. The
storage root is configurable via env (`STORAGE_ROOT`, default `/app/storage`).
A docker volume is mounted on this path in production so files persist across
container restarts.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.schemas.timeframe import Timeframe


class FileSystemStorage:
    """Per-session CSV staging on the local filesystem."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or _default_root()
        self.root.mkdir(parents=True, exist_ok=True)

    def session_dir(self, session_id: str) -> Path:
        path = self.root / "sessions" / session_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write(self, session_id: str, timeframe: Timeframe, content: bytes) -> Path:
        """Write a CSV file for the given session + timeframe. Overwrites if present."""
        target = self.session_dir(session_id) / f"{timeframe.value}.csv"
        target.write_bytes(content)
        return target

    def read(self, session_id: str, timeframe: Timeframe) -> bytes:
        target = self.session_dir(session_id) / f"{timeframe.value}.csv"
        return target.read_bytes()

    def path_for(self, session_id: str, timeframe: Timeframe) -> Path:
        return self.session_dir(session_id) / f"{timeframe.value}.csv"

    def remove_session(self, session_id: str) -> None:
        path = self.session_dir(session_id)
        if path.exists():
            for p in path.iterdir():
                p.unlink(missing_ok=True)
            path.rmdir()


def _default_root() -> Path:
    """Storage root — env-overridable, with a sensible default per environment."""
    import os

    root = os.environ.get("STORAGE_ROOT")
    if root:
        return Path(root)
    # Inside the container, /app/storage is the volume mount; on dev hosts it's a tempdir.
    if Path("/app").exists():
        return Path("/app/storage")
    settings = get_settings()
    if settings.environment == "production":
        return Path("/var/lib/wave-agent/storage")
    return Path.cwd() / "storage"
