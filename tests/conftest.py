"""Shared fixtures for automated API and offline tests."""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest

# Default deployed API (HuggingFace Space) — graders can override with API_BASE_URL
DEFAULT_API_BASE_URL = "https://adhamsafir-conversational-hiring-agent.hf.space"
API_TIMEOUT_SECONDS = 120.0

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = PROJECT_ROOT / "GenAI_SampleConversations"
CATALOG_PATH = PROJECT_ROOT / "data" / "catalog_clean.json"


@pytest.fixture(scope="session")
def api_base_url() -> str:
    return os.environ.get("API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")


@pytest.fixture(scope="session")
def http_client(api_base_url: str) -> httpx.Client:
    with httpx.Client(base_url=api_base_url, timeout=API_TIMEOUT_SECONDS) as client:
        yield client


@pytest.fixture(scope="session")
def catalog_urls() -> set[str]:
    with CATALOG_PATH.open(encoding="utf-8") as f:
        catalog = json.load(f)
    return {item["link"].rstrip("/").lower() for item in catalog if item.get("link")}


@pytest.fixture(scope="session")
def sample_files() -> list[Path]:
    return sorted(SAMPLES_DIR.glob("C*.md"))
