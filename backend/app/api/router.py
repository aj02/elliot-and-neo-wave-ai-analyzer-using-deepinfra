"""Top-level API router. Mounts feature routers under their own prefixes."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import runs, sessions, upload


api_router = APIRouter()
api_router.include_router(upload.router)
api_router.include_router(sessions.router)
api_router.include_router(runs.router)
