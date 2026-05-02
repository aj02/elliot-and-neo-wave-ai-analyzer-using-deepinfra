# syntax=docker/dockerfile:1.7

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# System deps: build-essential for scipy/numpy wheels on slim, libpq for psycopg.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        libpq5 \
        ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# uv: fast Python package installer/resolver. Pinned for reproducibility.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first so this layer caches across source-only changes.
# Source of truth for versions is pyproject.toml; we install via the project file.
COPY pyproject.toml README.md ./
RUN mkdir -p app && touch app/__init__.py \
 && uv pip install --system --no-cache .

# Copy the real application source over the placeholder package.
COPY . .

# Non-root runtime user. /app/storage is pre-created so the docker named-volume
# inherits appuser ownership on first mount; otherwise the volume defaults to
# root and writes from the app fail.
RUN groupadd --gid 1000 appuser \
 && useradd  --uid 1000 --gid 1000 --create-home appuser \
 && mkdir -p /app/storage/sessions \
 && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
