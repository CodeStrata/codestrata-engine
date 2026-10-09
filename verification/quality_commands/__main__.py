"""CLI: ``python -m verification.quality_commands``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verification.quality_commands.manifest import load_manifest
from verification.quality_commands.runner import run_quality_commands


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the Engine-owned quality-command manifest (E00.2).",
    )
    parser.add_argument(
        "--engine-root",
        type=Path,
        default=Path.cwd() if Path.cwd().name == "engine" else Path.cwd() / "engine",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Override manifest.yaml path.",
    )
    parser.add_argument(
        "--baseline-failure",
        action="append",
        default=[],
        help=(
            "Command id previously recorded as a G00 baseline failure. Repeatable. "
            "Marks a nonzero exit BASELINE_FAIL instead of NEW_FAIL; never PASS."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the manifest without executing commands.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    manifest = load_manifest(args.manifest)
    report = run_quality_commands(
        engine_root=args.engine_root,
        manifest=manifest,
        baseline_failure_ids=tuple(args.baseline_failure),
        execute=not args.dry_run,
    )
    payload = {
        "ok": report.ok,
        "merge_ready": report.merge_ready,
        "baseline_failure_ids": list(report.baseline_failure_ids),
        "notes": list(report.notes),
        "results": [
            {
                "id": item.id,
                "argv": list(item.argv),
                "exit_code": item.exit_code,
                "status": item.status.value,
                "duration_seconds": item.duration_seconds,
                "stdout_digest": item.stdout_digest,
                "stderr_digest": item.stderr_digest,
                "skip_reason": item.skip_reason,
            }
            for item in report.results
        ],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"E00.2 quality commands: {'PASS' if report.ok else 'NOT PASS'}")
        for item in report.results:
            exit_display = "n/a" if item.exit_code is None else str(item.exit_code)
            print(f"{item.id}: status={item.status.value} exit={exit_display}")
        for note in report.notes:
            print(f"note: {note}")
        print(
            "root engine-tests is not proof of lint/type/coverage; "
            "reviewer must inspect this evidence until a compatible runner executes it."
        )
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
