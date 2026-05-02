"""FastAPI entrypoint.

Exposes /health (liveness), /ready (readiness — checks Postgres + Redis), and a
small handful of metadata routes. Real API endpoints live under app/api/ and are
mounted in later steps.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.router import api_router
from app.core.config import get_settings
from app.core.disclaimer import DISCLAIMER
from app.core.logging import configure_logging, get_logger
from app.schemas.responses import HealthResponse, ReadyResponse, RootResponse


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """App startup / shutdown. Configures logging on startup."""
    configure_logging()
    log = get_logger("app.lifespan")
    settings = get_settings()
    log.info(
        "wave-agent.startup",
        version=__version__,
        environment=settings.environment,
        llm_provider=settings.llm_provider,
    )
    yield
    log.info("wave-agent.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="wave-agent",
        version=__version__,
        description=(
            "Educational engineering demo — multi-agent Elliott Wave + NEOWave "
            "structural analysis on uploaded OHLCV CSVs. NOT investment advice."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )

    # Permissive CORS for local development. Tighten in production.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else [],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", response_model=RootResponse, tags=["meta"])
    async def root() -> RootResponse:
        return RootResponse(
            name="wave-agent",
            version=__version__,
            disclaimer=DISCLAIMER,
        )

    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    async def health() -> HealthResponse:
        """Liveness check — returns 200 if the process is up.

        Does not check downstream dependencies; use /ready for that.
        """
        return HealthResponse(status="ok", version=__version__, disclaimer=DISCLAIMER)

    @app.get(
        "/ready",
        response_model=ReadyResponse,
        tags=["meta"],
        responses={503: {"model": ReadyResponse}},
    )
    async def ready() -> JSONResponse:
        """Readiness check — verifies Postgres and Redis are reachable."""
        from app.core.health_checks import check_postgres, check_redis

        pg_ok, pg_detail = await check_postgres()
        rd_ok, rd_detail = await check_redis()
        body = ReadyResponse(
            status="ok" if (pg_ok and rd_ok) else "degraded",
            checks={"postgres": pg_detail, "redis": rd_detail},
            disclaimer=DISCLAIMER,
        )
        code = status.HTTP_200_OK if (pg_ok and rd_ok) else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(status_code=code, content=body.model_dump(mode="json"))

    app.include_router(api_router)
    return app


app = create_app()
