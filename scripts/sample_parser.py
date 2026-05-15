"""Parse GenAI sample conversation markdown files into structured turns."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

TURN_HEADER = re.compile(r"^### Turn (\d+)\s*$", re.MULTILINE)
USER_BLOCK = re.compile(r"\*\*User\*\*\s*\n+(.*?)(?=\*\*Agent\*\*)", re.DOTALL)
URL_PATTERN = re.compile(r"<?(https://www\.shl\.com/[^>\s|]+)>?")
END_OF_CONV = re.compile(r"`end_of_conversation`:\s*\*\*(true|false)\*\*", re.IGNORECASE)


@dataclass
class GoldTurn:
    """One turn from a sample conversation file."""

    number: int
    user_message: str
    gold_urls: frozenset[str]
    expects_recommendations: bool
    end_of_conversation: bool


@dataclass
class SampleConversation:
    """Parsed sample trace."""

    name: str
    turns: list[GoldTurn]

    @property
    def final_turn(self) -> GoldTurn | None:
        for turn in reversed(self.turns):
            if turn.expects_recommendations:
                return turn
        return self.turns[-1] if self.turns else None


def normalize_url(url: str) -> str:
    """Canonicalize SHL product URLs for set comparison."""
    u = url.strip().strip("<>").rstrip("/").lower()
    return u


def _extract_user_message(block: str) -> str:
    match = USER_BLOCK.search(block)
    if not match:
        return ""
    lines = []
    for line in match.group(1).splitlines():
        line = line.strip()
        if line.startswith(">"):
            lines.append(line[1:].strip())
        elif line and not line.startswith("_"):
            lines.append(line)
    return "\n".join(lines).strip()


def _extract_gold_urls(block: str) -> set[str]:
    agent_idx = block.find("**Agent**")
    if agent_idx == -1:
        return set()
    agent_section = block[agent_idx:]
    return {normalize_url(u) for u in URL_PATTERN.findall(agent_section)}


def _expects_recommendations(block: str, gold_urls: set[str]) -> bool:
    if "recommendations: null" in block.lower():
        return False
    return bool(gold_urls)


def _extract_end_of_conversation(block: str) -> bool:
    matches = END_OF_CONV.findall(block)
    if not matches:
        return False
    return matches[-1].lower() == "true"


def parse_sample_file(path: Path) -> SampleConversation:
    """Parse a single C*.md sample conversation."""
    text = path.read_text(encoding="utf-8")
    headers = list(TURN_HEADER.finditer(text))
    if not headers:
        raise ValueError(f"No turns found in {path.name}")

    turns: list[GoldTurn] = []
    for i, header in enumerate(headers):
        start = header.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[start:end]
        gold_urls = _extract_gold_urls(block)
        turns.append(
            GoldTurn(
                number=int(header.group(1)),
                user_message=_extract_user_message(block),
                gold_urls=frozenset(gold_urls),
                expects_recommendations=_expects_recommendations(block, gold_urls),
                end_of_conversation=_extract_end_of_conversation(block),
            )
        )

    return SampleConversation(name=path.name, turns=turns)
