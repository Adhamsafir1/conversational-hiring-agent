#!/usr/bin/env python3
"""Run the full automated test suite (for reviewers, CI, and local checks).

Usage:
  python scripts/run_automated_tests.py
  API_BASE_URL=https://your-deployment.hf.space python scripts/run_automated_tests.py
  python scripts/run_automated_tests.py --offline-only
  python scripts/run_automated_tests.py --full-replay
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_API_BASE_URL = "https://adhamsafir-conversational-hiring-agent.hf.space"


def _run_pytest(args: list[str]) -> int:
    cmd = [sys.executable, "-m", "pytest", *args]
    print(f"\n>> {' '.join(cmd)}\n")
    return subprocess.call(cmd, cwd=PROJECT_ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run automated tests for SHL hiring agent")
    parser.add_argument(
        "--api-url",
        default=os.environ.get("API_BASE_URL", DEFAULT_API_BASE_URL),
        help=f"Base URL of deployed API (default: {DEFAULT_API_BASE_URL})",
    )
    parser.add_argument(
        "--offline-only",
        action="store_true",
        help="Run parser/catalog tests only (no HTTP)",
    )
    parser.add_argument(
        "--full-replay",
        action="store_true",
        help="Replay all 10 sample conversations (slow)",
    )
    parser.add_argument(
        "--no-replay",
        action="store_true",
        help="Skip sample conversation replay (smoke + contract only)",
    )
    args = parser.parse_args()

    os.environ["API_BASE_URL"] = args.api_url.rstrip("/")
    print("=" * 60)
    print("SHL Conversational Hiring Agent — Automated Tests")
    print(f"API_BASE_URL: {os.environ['API_BASE_URL']}")
    print("=" * 60)

    exit_code = _run_pytest(["-v", "tests/test_parser.py"])
    if exit_code != 0:
        return exit_code

    if args.offline_only:
        print("\nOffline tests passed.")
        return 0

    exit_code = _run_pytest(
        [
            "-v",
            "tests/test_smoke.py",
            "tests/test_api_contract.py",
        ]
    )
    if exit_code != 0:
        return exit_code

    if args.no_replay:
        print("\nCore automated tests passed (replay skipped).")
        return 0

    if args.full_replay:
        os.environ["FULL_SAMPLE_REPLAY"] = "1"
    code = _run_pytest(["-v", "tests/test_sample_replay.py"])
    if code != 0:
        print(
            "\nNote: sample replay may skip when the deployment is rate-limited. "
            "Core API tests above are the required pass criteria."
        )
    return code


if __name__ == "__main__":
    sys.exit(main())
