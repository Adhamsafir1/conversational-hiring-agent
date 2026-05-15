"""Smoke tests: verify the deployed API is reachable and documented."""

from __future__ import annotations

import httpx


def test_health_returns_ok(http_client: httpx.Client) -> None:
    response = http_client.get("/health")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}


def test_openapi_spec_available(http_client: httpx.Client) -> None:
    response = http_client.get("/openapi.json")
    assert response.status_code == 200, response.text
    spec = response.json()
    assert "/health" in spec.get("paths", {})
    assert "/chat" in spec.get("paths", {})


def test_docs_ui_available(http_client: httpx.Client) -> None:
    response = http_client.get("/docs")
    assert response.status_code == 200, response.text
