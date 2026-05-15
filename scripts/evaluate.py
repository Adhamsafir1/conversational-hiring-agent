"""Evaluate the agent against GenAI sample conversations (C1–C10).

Replays user turns turn-by-turn, compares recommendation URLs to gold tables,
and reports precision, recall, and F1 per scenario and in aggregate.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from scripts.sample_parser import (  # noqa: E402
    SampleConversation,
    normalize_url,
    parse_sample_file,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SAMPLES_DIR = BASE_DIR / "GenAI_SampleConversations"


@dataclass
class TurnMetrics:
    turn: int
    gold_count: int
    pred_count: int
    precision: float | None
    recall: float | None
    f1: float | None
    premature: bool
    missed: bool
    grounded: bool


@dataclass
class ScenarioResult:
    file: str
    turns: list[TurnMetrics]
    final_precision: float | None
    final_recall: float | None
    final_f1: float | None
    api_failed: bool


def _prf(pred: set[str], gold: set[str]) -> tuple[float | None, float | None, float | None]:
    if not gold:
        return None, None, None
    if not pred:
        return 0.0, 0.0, 0.0
    tp = len(pred & gold)
    precision = tp / len(pred)
    recall = tp / len(gold)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def _urls_from_response(recommendations) -> set[str]:
    return {normalize_url(r.url) for r in recommendations if r.url}


def _is_grounded(recommendations) -> bool:
    prefix = "https://www.shl.com/"
    return all(r.url.lower().startswith(prefix) for r in recommendations)


def evaluate_scenario(
    sample: SampleConversation,
    delay_seconds: float,
) -> ScenarioResult:
    """Replay one sample conversation through the agent."""
    from app.agent import agent
    from app.models import ChatRequest, Message

    messages: list[Message] = []
    turn_metrics: list[TurnMetrics] = []
    api_failed = False
    final_precision = final_recall = final_f1 = None

    for turn in sample.turns:
        if not turn.user_message:
            logger.warning("  Turn %s: empty user message, skipping", turn.number)
            continue

        messages.append(Message(role="user", content=turn.user_message))
        response = agent.chat(ChatRequest(messages=messages))
        pred_urls = _urls_from_response(response.recommendations)
        gold_urls = set(turn.gold_urls)

        if response.reply.startswith("I apologize, but all my AI brains"):
            api_failed = True

        precision, recall, f1 = _prf(pred_urls, gold_urls)
        premature = not turn.expects_recommendations and bool(pred_urls)
        missed = turn.expects_recommendations and not pred_urls

        turn_metrics.append(
            TurnMetrics(
                turn=turn.number,
                gold_count=len(gold_urls),
                pred_count=len(pred_urls),
                precision=precision,
                recall=recall,
                f1=f1,
                premature=premature,
                missed=missed,
                grounded=_is_grounded(response.recommendations),
            )
        )

        if turn.expects_recommendations:
            final_precision, final_recall, final_f1 = precision, recall, f1

        messages.append(Message(role="assistant", content=response.reply))

        if delay_seconds > 0:
            time.sleep(delay_seconds)

    return ScenarioResult(
        file=sample.name,
        turns=turn_metrics,
        final_precision=final_precision,
        final_recall=final_recall,
        final_f1=final_f1,
        api_failed=api_failed,
    )


def _aggregate(results: list[ScenarioResult]) -> dict:
    scored_turns = [
        t for r in results for t in r.turns if t.precision is not None
    ]
    final_turns = [r for r in results if r.final_f1 is not None]

    def _mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    return {
        "scenarios": len(results),
        "turns_with_gold_recs": len(scored_turns),
        "mean_turn_precision": _mean([t.precision for t in scored_turns if t.precision is not None]),
        "mean_turn_recall": _mean([t.recall for t in scored_turns if t.recall is not None]),
        "mean_turn_f1": _mean([t.f1 for t in scored_turns if t.f1 is not None]),
        "mean_final_f1": _mean([r.final_f1 for r in final_turns if r.final_f1 is not None]),
        "premature_turns": sum(1 for r in results for t in r.turns if t.premature),
        "missed_turns": sum(1 for r in results for t in r.turns if t.missed),
        "api_failures": sum(1 for r in results if r.api_failed),
    }


def _print_scenario(result: ScenarioResult) -> None:
    logger.info("\n--- %s ---", result.file)
    if result.api_failed:
        logger.warning("  API quota/rate-limit errors detected")
    for t in result.turns:
        if t.precision is not None:
            logger.info(
                "  Turn %s: P=%.2f R=%.2f F1=%.2f (gold=%s pred=%s)%s",
                t.turn,
                t.precision,
                t.recall,
                t.f1,
                t.gold_count,
                t.pred_count,
                " [premature]" if t.premature else "",
            )
        elif t.premature:
            logger.info(
                "  Turn %s: no gold recs, pred=%s [premature]",
                t.turn,
                t.pred_count,
            )
        else:
            logger.info("  Turn %s: no recommendations (clarifying)", t.turn)

    if result.final_f1 is not None:
        logger.info(
            "  Final rec turn: P=%.2f R=%.2f F1=%.2f",
            result.final_precision,
            result.final_recall,
            result.final_f1,
        )


def dry_run_parse(samples: list[Path]) -> None:
    """Parse samples only (no API calls)."""
    for path in samples:
        sample = parse_sample_file(path)
        logger.info("\n%s: %s turns", sample.name, len(sample.turns))
        for turn in sample.turns:
            logger.info(
                "  Turn %s: expects_recs=%s gold_urls=%s | user: %.60s...",
                turn.number,
                turn.expects_recommendations,
                len(turn.gold_urls),
                turn.user_message.replace("\n", " "),
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate agent vs GenAI samples")
    parser.add_argument(
        "--file",
        help="Evaluate a single sample file (e.g. C1.md)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse samples only; do not call the agent",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds to wait between turns (default: 2)",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        help="Write detailed results to a JSON file",
    )
    args = parser.parse_args()

    if not SAMPLES_DIR.exists():
        logger.error("Samples directory not found: %s", SAMPLES_DIR)
        sys.exit(1)

    if args.file:
        sample_paths = [SAMPLES_DIR / args.file]
        if not sample_paths[0].exists():
            logger.error("File not found: %s", sample_paths[0])
            sys.exit(1)
    else:
        sample_paths = sorted(SAMPLES_DIR.glob("C*.md"))

    if not sample_paths:
        logger.error("No sample files found in %s", SAMPLES_DIR)
        sys.exit(1)

    if args.dry_run:
        dry_run_parse(sample_paths)
        return

    logger.info("Evaluating %s sample(s) with %.1fs delay between turns...", len(sample_paths), args.delay)

    results: list[ScenarioResult] = []
    for path in sample_paths:
        sample = parse_sample_file(path)
        result = evaluate_scenario(sample, delay_seconds=args.delay)
        results.append(result)
        _print_scenario(result)

    agg = _aggregate(results)
    logger.info("\n========== Aggregate ==========")
    logger.info("Scenarios:              %s", agg["scenarios"])
    logger.info("Turns with gold recs:   %s", agg["turns_with_gold_recs"])
    logger.info("Mean turn F1:           %.3f", agg["mean_turn_f1"])
    logger.info("Mean final-turn F1:     %.3f", agg["mean_final_f1"])
    logger.info("Mean turn precision:    %.3f", agg["mean_turn_precision"])
    logger.info("Mean turn recall:       %.3f", agg["mean_turn_recall"])
    logger.info("Premature rec turns:    %s", agg["premature_turns"])
    logger.info("Missed rec turns:       %s", agg["missed_turns"])
    logger.info("API failures:           %s", agg["api_failures"])
    logger.info("===============================")

    if args.json_out:
        payload = {
            "aggregate": agg,
            "scenarios": [asdict(r) for r in results],
        }
        args.json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Wrote %s", args.json_out)


if __name__ == "__main__":
    main()
