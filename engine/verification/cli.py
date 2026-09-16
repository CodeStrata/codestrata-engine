"""CLI for the Engine-owned scope guard and quality-command runner.

From ``engine/`` (or ``PYTHONPATH=engine`` at the repo root)::

    python -m verification scope
    python -m verification quality --suite harness

Exit codes: 0 PASS, 1 FAIL, 2 BLOCKED/ERROR, 3 BUDGET, 4 BASELINE_FAIL.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from verification.git_changes import DEFAULT_MAX_EVENTS
from verification.quality_commands import load_manifest, overall_status, run_suite
from verification.scope_guard import evaluate_repository

ENGINE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = Path(__file__).resolve().parent / "quality-commands.yaml"
DEFAULT_INVENTORY = Path(__file__).resolve().parent / "preexisting-working-tree-inventory.json"


def _repo_root_from_engine() -> Path:
    return ENGINE_DIR.parent


def _print_verdict(verdict_status: str, payload: dict[str, object]) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    if verdict_status == "PASS":
        return 0
    if verdict_status in {"BLOCKED", "ERROR"}:
        return 2
    if verdict_status == "BUDGET":
        return 3
    if verdict_status == "BASELINE_FAIL":
        return 4
    return 1


def cmd_scope(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve() if args.repo else _repo_root_from_engine()
    inventory = Path(args.inventory) if args.inventory else DEFAULT_INVENTORY
    verdict = evaluate_repository(
        repo,
        base_ref=args.base,
        inventory_path=inventory if inventory.is_file() else None,
        max_events=args.max_events,
    )
    payload = {
        "status": verdict.status,
        "inspected_count": verdict.inspected_count,
        "message": verdict.message,
        "findings": [
            {
                "origin": finding.event.origin,
                "status": finding.event.status,
                "path": finding.event.path,
                "source_path": finding.event.source_path,
                "dest_path": finding.event.dest_path,
                "reason": finding.reason,
            }
            for finding in verdict.findings
        ],
        "preexisting_ignored": [
            {
                "origin": event.origin,
                "path": event.path,
                "status": event.status,
            }
            for event in verdict.preexisting_ignored
        ],
    }
    return _print_verdict(verdict.status, payload)


def cmd_quality(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve() if args.repo else _repo_root_from_engine()
    manifest = load_manifest(Path(args.manifest) if args.manifest else DEFAULT_MANIFEST)
    results = run_suite(manifest, repo, suite=args.suite)
    status = overall_status(results)
    payload = {
        "status": status,
        "suite": args.suite,
        "coverage_source": manifest.coverage_source,
        "coverage_floor": manifest.coverage_floor,
        "branch_measurement": manifest.branch_measurement,
        "engine_tests_job": manifest.engine_tests_job,
        "results": [
            {
                "id": result.command.id,
                "exit_code": result.exit_code,
                "status": result.status,
                "record_as_baseline": result.command.record_as_baseline,
                "notes": result.command.notes,
                "stderr_tail": result.stderr_tail,
            }
            for result in results
        ],
    }
    return _print_verdict(status, payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engine-owned scope guard and quality commands")
    sub = parser.add_subparsers(dest="command", required=True)
    scope = sub.add_parser("scope", help="inspect git changes against engine/ boundary")
    scope.add_argument("--repo", default=None)
    scope.add_argument("--base", default=None, help="cumulative diff base ref")
    scope.add_argument("--inventory", default=None)
    scope.add_argument("--max-events", type=int, default=DEFAULT_MAX_EVENTS)
    scope.set_defaults(func=cmd_scope)
    quality = sub.add_parser("quality", help="run a suite from the quality-command manifest")
    quality.add_argument("--repo", default=None)
    quality.add_argument("--manifest", default=None)
    quality.add_argument(
        "--suite",
        choices=("harness", "product", "security"),
        default="harness",
    )
    quality.set_defaults(func=cmd_quality)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

# Subcommands: scope (git boundary) and quality (YAML command suites).
