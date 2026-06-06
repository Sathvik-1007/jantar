"""Unit tests for jantar.api — auth middleware and route behavior.

Uses FastAPI's TestClient (synchronous ASGI) which exercises real middleware
without needing a running server or network calls.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient

from jantar.api.app import create_app
from jantar.config import settings
from jantar.models import AgentResponse


@pytest.fixture
def client(monkeypatch):
    """TestClient with model warmup skipped (no GPU in CI)."""
    monkeypatch.setattr("jantar.rag.embeddings.warmup_embeddings", lambda: None)
    monkeypatch.setattr("jantar.rag.reranker.warmup_reranker", lambda: None)
    app = create_app()
    return TestClient(app)


# --- Health endpoint (no auth) ---


def test_health_no_auth_required(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# --- Auth middleware ---


def test_agent_run_requires_api_key(client):
    resp = client.post("/agent/run", json={"text": "hello"})
    assert resp.status_code == 401
    assert "API key" in resp.json()["error"]


def test_agent_run_wrong_key_rejected(client):
    resp = client.post("/agent/run", json={"text": "hello"}, headers={"x-api-key": "wrong-key"})
    assert resp.status_code == 401


def test_agent_run_correct_key_passes_auth(client):
    """With correct key, auth passes (route may still fail on LLM — that's fine, 
    we're testing auth not the pipeline)."""
    with patch("jantar.api.routes.agent.run_agent", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = AgentResponse(answer="test answer", run_id="abc")
        resp = client.post(
            "/agent/run",
            json={"text": "hello", "language": "en"},
            headers={"x-api-key": settings.api_key},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "test answer"
    assert data["run_id"] == "abc"


def test_empty_configured_key_denies_all(client, monkeypatch):
    """If API_KEY env is empty, ALL requests are denied (fail closed)."""
    monkeypatch.setattr(settings, "api_key", "")
    resp = client.post("/agent/run", json={"text": "hi"}, headers={"x-api-key": ""})
    assert resp.status_code == 401


# --- Request validation ---


def test_agent_run_rejects_empty_body(client):
    resp = client.post(
        "/agent/run",
        json={},
        headers={"x-api-key": settings.api_key},
    )
    assert resp.status_code == 422  # Pydantic validation error


def test_agent_run_rejects_missing_text(client):
    resp = client.post(
        "/agent/run",
        json={"language": "hi"},
        headers={"x-api-key": settings.api_key},
    )
    assert resp.status_code == 422


# --- Error handling ---


def test_agent_run_500_on_unhandled_exception(client):
    """Unhandled exception returns 500 with generic message (no stack trace leak)."""
    with patch("jantar.api.routes.agent.run_agent", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = RuntimeError("something broke")
        resp = client.post(
            "/agent/run",
            json={"text": "hello"},
            headers={"x-api-key": settings.api_key},
        )
    assert resp.status_code == 500
    assert "Internal server error" in resp.json()["error"]
    assert "something broke" not in resp.json()["error"]  # no leak
