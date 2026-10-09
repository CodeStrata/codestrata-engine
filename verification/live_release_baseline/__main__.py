"""CLI: ``python -m verification.live_release_baseline``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verification.live_release_baseline.publisher import evaluate_r01
from verification.live_release_baseline.record import load_recorded, write_baseline
from verification.live_release_baseline.workflows import load_root_workflows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="E00.1 live artifact / R01 publisher inventory (read-only).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd().parent if Path.cwd().name == "engine" else Path.cwd(),
    )
    parser.add_argument(
        "--recorded",
        type=Path,
        default=None,
        help="recorded.yaml (default: package copy).",
    )
    parser.add_argument(
        "--write-baseline",
        type=Path,
        default=None,
        help="Write engine/docs/release/baseline.md (or given path).",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    record = load_recorded(args.recorded)
    live_workflows = load_root_workflows(repo_root)
    live_r01 = evaluate_r01(live_workflows)
    mismatch = live_r01.status is not record.r01.status
    payload = {
        "inspected_at": record.inspected_at,
        "pypi_name": record.pypi.name,
        "live_version": record.pypi.live_version,
        "pypi_versions": list(record.pypi.versions),
        "pyproject_version_ignored": record.pyproject_version_ignored,
        "tags_not_used_as_live": list(record.tags_not_used_as_live),
        "r01_recorded": record.r01.status.value,
        "r01_live_workflows": live_r01.status.value,
        "r01_publisher": record.r01.engine_only_oidc_publisher,
        "r01_reason": live_r01.reason,
        "workflow_count": len(live_workflows),
        "install_status": (
            record.install_rollback.status.value if record.install_rollback else None
        ),
        "mismatch": mismatch,
    }
    if args.write_baseline is not None:
        write_baseline(record, args.write_baseline)
    default_baseline = repo_root / "engine" / "docs" / "release" / "baseline.md"
    if args.write_baseline is None and default_baseline.parent.is_dir():
        # Explicit flag required so a dry inventory never rewrites the ledger.
        pass
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"E00.1 live artifact: {record.pypi.name}=={record.pypi.live_version} "
            f"(not pyproject {record.pyproject_version_ignored})"
        )
        print(f"R01 recorded={record.r01.status.value} live-workflows={live_r01.status.value}")
        print(live_r01.reason)
        if record.install_rollback is not None:
            print(f"install/rollback: {record.install_rollback.status.value}")
        if mismatch:
            print("FAIL: recorded R01 status does not match current root workflows")
    if mismatch:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
