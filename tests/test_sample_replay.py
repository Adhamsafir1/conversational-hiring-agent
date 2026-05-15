"""Replay gold sample conversations against the live API and score URL overlap."""

from __future__ import annotations

import os

import httpx
import pytest

from scripts.sample_parser import normalize_url, parse_sample_file
from tests.conftest import SAMPLES_DIR

# Full replay of all 10 samples is slow; default runs C1 + C10 only.
DEFAULT_REPLAY_FILES = ("C1.md", "C10.md")
RATE_LIMIT_SNIPPET = "all my AI brains are currently busy"


def _replay_files() -> list[str]:
    if os.environ.get("FULL_SAMPLE_REPLAY") == "1":
        return sorted(p.name for p in SAMPLES_DIR.glob("C*.md"))
    return list(DEFAULT_REPLAY_FILES)


def _chat_turn(client: httpx.Client, messages: list[dict]) -> dict:
    response = client.post("/chat", json={"messages": messages})
    assert response.status_code == 200, response.text
    return response.json()


def _replay_file(client: httpx.Client, filename: str) -> dict:
    sample = parse_sample_file(SAMPLES_DIR / filename)
    messages: list[dict] = []
    final_f1 = None
    api_failed = False
    premature = 0

    for turn in sample.turns:
        if not turn.user_message:
            continue
        messages.append({"role": "user", "content": turn.user_message})
        data = _chat_turn(client, messages)
        if RATE_LIMIT_SNIPPET in data.get("reply", ""):
            api_failed = True

        pred = {normalize_url(r["url"]) for r in data.get("recommendations", [])}
        gold = set(turn.gold_urls)

        if not turn.expects_recommendations and pred:
            premature += 1
        if gold:
            tp = len(pred & gold)
            precision = tp / len(pred) if pred else 0.0
            recall = tp / len(gold)
            f1 = (
                2 * precision * recall / (precision + recall)
                if (precision + recall)
                else 0.0
            )
            final_f1 = f1

        messages.append({"role": "assistant", "content": data["reply"]})

    return {
        "file": filename,
        "final_f1": final_f1,
        "premature": premature,
        "api_failed": api_failed,
    }


@pytest.mark.parametrize("filename", _replay_files())
def test_sample_conversation_replay(http_client: httpx.Client, filename: str) -> None:
    result = _replay_file(http_client, filename)
    if result["api_failed"]:
        pytest.skip(f"{filename}: deployment LLM rate-limited — retry or refresh API keys")
    assert result["final_f1"] is not None, f"{filename}: no scored recommendation turn"
    assert result["final_f1"] > 0.0, f"{filename}: zero URL overlap with gold trace"
