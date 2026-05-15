"""Shared LLM helpers: retries, rate-limit detection, catalog test-type codes."""
from __future__ import annotations

import re
import time
from typing import Callable, TypeVar

from app.config import LLM_MAX_RETRIES, LLM_RETRY_BASE_DELAY

T = TypeVar("T")

KEY_TO_TEST_TYPE = {
    "Knowledge & Skills": "K",
    "Personality & Behavior": "P",
    "Simulations": "S",
    "Ability & Aptitude": "A",
    "Competencies": "C",
    "Biodata & Situational Judgment": "B",
    "Development & 360": "D",
    "Assessment Exercises": "E",
}

GREETING_RE = re.compile(
    r"^(hi|hello|hey|good\s+(morning|afternoon|evening)|howdy)[\s!.,?]*$",
    re.IGNORECASE,
)

CLARIFY_GREETING_REPLY = (
    "Hello! I'm here to help you find the right SHL assessments for your hiring needs. "
    "Tell me about the role you're filling — for example job title, seniority, and key "
    "skills (e.g. Java, Spring, AWS), or paste a job description."
)


def is_rate_limited_error(exc: BaseException) -> bool:
    err = str(exc).lower()
    return "429" in str(exc) or "rate" in err or "quota" in err or "resource_exhausted" in err


def keys_to_test_type(keys: list[str]) -> str:
    for key in keys:
        if key in KEY_TO_TEST_TYPE:
            return KEY_TO_TEST_TYPE[key]
    return "K"


def is_greeting_only(text: str) -> bool:
    return bool(GREETING_RE.match(text.strip()))


def call_with_retries(fn: Callable[[], T], label: str) -> T | None:
    """Call fn up to LLM_MAX_RETRIES times with exponential backoff on rate limits."""
    delay = LLM_RETRY_BASE_DELAY
    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            return fn()
        except Exception as e:
            if is_rate_limited_error(e) and attempt < LLM_MAX_RETRIES:
                logger_msg = f"{label}: rate limited (attempt {attempt}/{LLM_MAX_RETRIES}), retry in {delay:.1f}s"
                import logging

                logging.getLogger(__name__).warning(logger_msg)
                time.sleep(delay)
                delay *= 1.5
                continue
            raise
    return None
