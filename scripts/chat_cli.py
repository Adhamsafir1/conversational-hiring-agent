#!/usr/bin/env python3
"""Interactive terminal chat with the SHL Assessment Recommender.

Speak naturally turn-by-turn (like the GenAI sample conversations).
Uses the local agent by default, or a remote API with --api URL.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

DEFAULT_API = "https://adhamsafir-conversational-hiring-agent.hf.space"


def _print_agent(data: dict) -> None:
    print(f"\n{'─' * 60}")
    print("Agent:")
    print(data.get("reply", ""))
    recs = data.get("recommendations") or []
    if recs:
        print(f"\nRecommendations ({len(recs)}):")
        for i, r in enumerate(recs, 1):
            print(f"  {i}. {r['name']} [{r.get('test_type', '?')}]")
            print(f"     {r['url']}")
    if data.get("end_of_conversation"):
        print("\n[Conversation complete]")
    print(f"{'─' * 60}\n")


def _chat_local(messages: list[dict]) -> dict:
    from app.agent import agent
    from app.models import ChatRequest, Message

    req = ChatRequest(messages=[Message(role=m["role"], content=m["content"]) for m in messages])
    resp = agent.chat(req)
    return resp.model_dump()


def _chat_remote(api_base: str, messages: list[dict]) -> dict:
    import httpx

    url = api_base.rstrip("/") + "/chat"
    r = httpx.post(url, json={"messages": messages}, timeout=120.0)
    r.raise_for_status()
    return r.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Conversational CLI for SHL hiring agent")
    parser.add_argument(
        "--api",
        default=None,
        help=f"Remote API base URL (default: local agent). Example: {DEFAULT_API}",
    )
    args = parser.parse_args()

    chat_fn = _chat_remote if args.api else _chat_local
    api_label = args.api or "local agent"

    print("=" * 60)
    print("SHL Assessment Recommender — Conversational Chat")
    print(f"Backend: {api_label}")
    print("Type your message and press Enter. Commands: /quit  /new")
    print("=" * 60)

    messages: list[dict] = []

    while True:
        try:
            user_text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user_text:
            continue
        if user_text.lower() in ("/quit", "/exit", "/q"):
            print("Bye.")
            break
        if user_text.lower() in ("/new", "/reset"):
            messages = []
            print("\n--- New conversation ---\n")
            continue

        messages.append({"role": "user", "content": user_text})
        print("\nThinking…")

        try:
            data = chat_fn(args.api, messages) if args.api else chat_fn(messages)
        except Exception as e:
            print(f"\nError: {e}\n")
            messages.pop()
            continue

        messages.append({"role": "assistant", "content": data["reply"]})
        _print_agent(data)

        if data.get("end_of_conversation"):
            print("Start a new conversation with /new or exit with /quit.")
            messages = []


if __name__ == "__main__":
    main()
