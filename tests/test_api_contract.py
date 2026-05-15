"""Contract tests for POST /chat — schema, grounded URLs, catalog integrity."""

from __future__ import annotations

import httpx
import pytest

SHL_PREFIX = "https://www.shl.com/"


def _post_chat(client: httpx.Client, content: str, history: list[dict] | None = None) -> dict:
    messages = list(history or [])
    messages.append({"role": "user", "content": content})
    response = client.post("/chat", json={"messages": messages})
    assert response.status_code == 200, response.text
    return response.json()


def test_chat_response_has_required_fields(http_client: httpx.Client) -> None:
    data = _post_chat(
        http_client,
        "Recommend SHL assessments for a mid-level Java developer using Spring Boot.",
    )
    assert isinstance(data["reply"], str) and len(data["reply"]) > 0
    assert isinstance(data["recommendations"], list)
    assert isinstance(data["end_of_conversation"], bool)


def test_recommendation_objects_shape(http_client: httpx.Client) -> None:
    data = _post_chat(
        http_client,
        "Hiring a senior Java engineer with AWS and Docker. Recommend assessments.",
    )
    for rec in data["recommendations"]:
        assert "name" in rec and rec["name"]
        assert "url" in rec and rec["url"]
        assert "test_type" in rec and rec["test_type"]


def test_recommendation_urls_are_shl_domain(http_client: httpx.Client) -> None:
    data = _post_chat(
        http_client,
        "Entry-level contact centre hiring in English US — recommend assessments.",
    )
    for rec in data["recommendations"]:
        assert rec["url"].lower().startswith(SHL_PREFIX)


def test_recommendation_urls_exist_in_catalog(
    http_client: httpx.Client, catalog_urls: set[str]
) -> None:
    data = _post_chat(
        http_client,
        "Graduate financial analyst hiring — numerical and finance knowledge tests.",
    )
    for rec in data["recommendations"]:
        normalized = rec["url"].rstrip("/").lower()
        assert normalized in catalog_urls, f"URL not in catalog: {rec['url']}"


def test_multi_turn_conversation(http_client: httpx.Client) -> None:
    first = _post_chat(http_client, "We need a solution for senior leadership.")
    history = [
        {"role": "user", "content": "We need a solution for senior leadership."},
        {"role": "assistant", "content": first["reply"]},
    ]
    second = _post_chat(
        http_client,
        "Selection — comparing candidates against a leadership benchmark for CXOs.",
        history=history,
    )
    assert isinstance(second["reply"], str)
