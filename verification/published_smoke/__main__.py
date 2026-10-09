"""CLI: ``python -m verification.published_smoke``."""

from __future__ import annotations

import argparse
from pathlib import Path

from verification.published_smoke.models import SmokeDecision
from verification.published_smoke.plan import load_targets
from verification.published_smoke.runner import evaluate_readiness, readiness_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="E16.3 published PyPI artifact readiness (not a local wheel build).",
    )
    parser.add_argument("--json", action="store_true", help="Emit readiness JSON.")
    parser.add_argument(
        "--targets",
        type=Path,
        default=None,
        help="Optional path to targets.yaml (default: package copy).",
    )
    args = parser.parse_args(argv)
    targets = load_targets(args.targets)
    readiness = evaluate_readiness(targets)
    if args.json:
        print(readiness_json(targets))
    else:
        print(f"decision={readiness.decision.value}")
        for note in readiness.notes:
            print(note)
    if readiness.decision is SmokeDecision.PASS:
        return 0
    if readiness.decision is SmokeDecision.FAIL:
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
