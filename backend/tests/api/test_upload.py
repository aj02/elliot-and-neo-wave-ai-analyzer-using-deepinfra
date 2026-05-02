"""Smoke tests for POST /upload.

Uses an in-memory fake Redis so the test does not require a running Redis.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import app


class _FakeRedis:
    """Tiny in-memory Redis stand-in covering the calls SessionStore makes."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value.encode() if isinstance(value, str) else value

    async def get(self, key: str) -> bytes | None:
        return self._store.get(key)

    async def delete(self, *keys: str) -> int:
        n = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                n += 1
        return n


@pytest.fixture
def client(tmp_path: Any) -> TestClient:
    fake = _FakeRedis()

    async def _fake_redis() -> Any:  # noqa: ANN401 — duck-typed redis.Redis
        yield fake

    def _fake_storage() -> Any:  # noqa: ANN401
        from app.upload.storage import FileSystemStorage

        return FileSystemStorage(root=tmp_path)

    app.dependency_overrides[deps.get_redis] = _fake_redis
    app.dependency_overrides[deps.get_storage] = _fake_storage
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_upload_accepts_a_clean_csv(client: TestClient, good_csv_bytes: bytes) -> None:
    files = [("files", ("test.csv", good_csv_bytes, "text/csv"))]
    data = {"instrument_name": "TEST", "timeframes": "1D"}
    resp = client.post("/upload", files=files, data=data)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["accepted"] is True
    assert body["session_id"]
    assert "disclaimer" in body
    assert len(body["files"]) == 1
    assert body["files"][0]["timeframe"] == "1D"
    assert body["files"][0]["rows"] == 200


def test_upload_rejects_a_bad_csv(client: TestClient, csv_bad_ohlc: bytes) -> None:
    files = [("files", ("bad.csv", csv_bad_ohlc, "text/csv"))]
    data = {"instrument_name": "TEST", "timeframes": "1D"}
    resp = client.post("/upload", files=files, data=data)
    assert resp.status_code == 201
    body = resp.json()
    assert body["accepted"] is False
    assert body["session_id"] == ""
    error_codes = [i["code"] for i in body["files"][0]["issues"]]
    assert "OHLC_SANITY" in error_codes


def test_upload_rejects_mismatched_timeframes(client: TestClient, good_csv_bytes: bytes) -> None:
    files = [("files", ("a.csv", good_csv_bytes, "text/csv"))]
    data = {"instrument_name": "TEST", "timeframes": ["1D", "1W"]}
    resp = client.post("/upload", files=files, data=data)
    assert resp.status_code == 400
    assert "match" in resp.json()["detail"].lower()


def test_upload_rejects_unknown_timeframe(client: TestClient, good_csv_bytes: bytes) -> None:
    files = [("files", ("a.csv", good_csv_bytes, "text/csv"))]
    data = {"instrument_name": "TEST", "timeframes": "13m"}  # not in enum
    resp = client.post("/upload", files=files, data=data)
    assert resp.status_code == 400
    assert "13m" in resp.json()["detail"]
