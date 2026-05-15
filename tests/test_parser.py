"""Offline tests: GenAI sample markdown parser (no API calls)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.sample_parser import parse_sample_file


def test_all_ten_sample_files_parse(sample_files: list[Path]) -> None:
    assert len(sample_files) == 10


@pytest.mark.parametrize("path", sorted((Path(__file__).parent.parent / "GenAI_SampleConversations").glob("C*.md")))
def test_each_sample_has_user_turns(path: Path) -> None:
    sample = parse_sample_file(path)
    assert len(sample.turns) >= 1
    user_turns = [t for t in sample.turns if t.user_message]
    assert user_turns, f"{path.name} has no user messages"
    for turn in user_turns:
        assert len(turn.user_message.strip()) >= 1


def test_c1_gold_urls_on_final_turns(sample_files: list[Path]) -> None:
    c1 = parse_sample_file(next(p for p in sample_files if p.name == "C1.md"))
    rec_turns = [t for t in c1.turns if t.expects_recommendations]
    assert len(rec_turns) == 2
    assert all(len(t.gold_urls) == 3 for t in rec_turns)
