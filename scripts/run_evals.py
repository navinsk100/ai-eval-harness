#!/usr/bin/env python3
"""Run the eval harness from the command line.

Examples:
    # Run all scenarios with defaults
    python scripts/run_evals.py

    # Run a single scenario
    python scripts/run_evals.py --scenarios 001_jdbc_pool_exhaustion

    # Try a new prompt version with a descriptive tag
    python scripts/run_evals.py --prompt v2 --tag "added-self-critique"

    # Fast iteration: skip LLM judges (deterministic graders only)
    python scripts/run_evals.py --skip-llm-graders
"""
from __future__ import annotations

import argparse
import sys

# Make the perf_eval package importable when running this script directly.
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from perf_eval.runner import run_evals  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the perf-eval harness.")
    parser.add_argument("--model", default="claude-sonnet-4-5",
                        help="Anthropic model to use as the agent.")
    parser.add_argument("--prompt", default="v1",
                        help="Prompt version identifier (for run logging).")
    parser.add_argument("--scenarios", nargs="*", default=None,
                        help="Specific scenario IDs to run (default: all).")
    parser.add_argument("--threshold", type=float, default=0.7,
                        help="Pass threshold for a scenario.")
    parser.add_argument("--tag", default="",
                        help="Free-form tag describing this run.")
    parser.add_argument("--skip-llm-graders", action="store_true",
                        help="Skip LLM-as-judge graders for fast iteration.")
    args = parser.parse_args()

    summary = run_evals(
        model=args.model,
        prompt_version=args.prompt,
        scenario_filter=args.scenarios,
        pass_threshold=args.threshold,
        tag=args.tag,
        skip_llm_graders=args.skip_llm_graders,
    )

    # Non-zero exit if pass rate is below 70% — useful for CI gating.
    return 0 if summary.pass_rate >= 0.7 else 1


if __name__ == "__main__":
    sys.exit(main())
