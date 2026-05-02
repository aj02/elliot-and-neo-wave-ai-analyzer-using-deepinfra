"""Tests for the /analyze + /runs HTTP endpoints.

The full WebSocket streaming path is verified end-to-end against the running
backend (see scripts/smoke_ws_run.py). FastAPI's sync TestClient runs ASGI
requests on per-request event loops, which breaks asyncio.Condition shared
between the orchestrator background task and a WS subscriber — so we keep
the unit tests focused on the synchronous request/response surface and lean
on the orchestrator's own end-to-end test (tests/agents/test_orchestrator.py)
for the streaming guarantees.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import app


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value.encode() if isinstance(value, str) else value

    async def get(self, key: str) -> bytes | None:
        return self.store.get(key)

    async def delete(self, *keys: str) -> int:
        return sum(1 for k in keys if self.store.pop(k, None) is not None)


@pytest.fixture
def client(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from app.core import config as cfg

    monkeypatch.setattr(cfg.get_settings(), "anthropic_api_key", None, raising=False)
    monkeypatch.setattr(cfg.get_settings(), "openai_api_key", None, raising=False)

    fake = _FakeRedis()

    async def _fake_redis() -> Any:  # noqa: ANN401
        yield fake

    def _fake_storage() -> Any:  # noqa: ANN401
        from app.upload.storage import FileSystemStorage

        return FileSystemStorage(root=tmp_path)

    app.dependency_overrides[deps.get_redis] = _fake_redis
    app.dependency_overrides[deps.get_storage] = _fake_storage
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_analyze_404s_on_unknown_session(client: TestClient) -> None:
    resp = client.post(
        "/analyze",
        json={"session_id": "does-not-exist", "instrument_name": "X"},
    )
    assert resp.status_code == 404
    assert "No upload session" in resp.json()["detail"]


def test_get_run_404s_on_unknown_run(client: TestClient) -> None:
    resp = client.get("/runs/no-such-run")
    assert resp.status_code == 404


def test_analyze_returns_run_id_for_valid_session(client: TestClient, good_csv_bytes: bytes) -> None:
    """End-to-end: upload → analyze. Verifies the response shape and
    that a websocket URL is returned. The actual streaming is verified
    by tests/agents/test_orchestrator.py and scripts/smoke_ws_run.py."""
    files = [("files", ("test.csv", good_csv_bytes, "text/csv"))]
    data = {"instrument_name": "TEST", "timeframes": "1D"}
    upload_resp = client.post("/upload", files=files, data=data)
    assert upload_resp.status_code == 201
    session_id = upload_resp.json()["session_id"]

    analyze_resp = client.post(
        "/analyze",
        json={"session_id": session_id, "instrument_name": "TEST"},
    )
    assert analyze_resp.status_code == 202, analyze_resp.text
    body = analyze_resp.json()
    assert body["run_id"]
    assert body["websocket_url"] == f"/ws/runs/{body['run_id']}"
    assert "disclaimer" in body
