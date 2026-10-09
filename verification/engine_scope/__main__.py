"""CLI: ``python -m verification.engine_scope``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verification.engine_scope.git_changes import collect_working_tree, porcelain_to_inventory
from verification.engine_scope.guard import evaluate_scope
from verification.engine_scope.inventory import dump_inventory, load_inventory, write_inventory
from verification.engine_scope.models import ScopeReport


def _report_to_dict(report: ScopeReport) -> dict[str, object]:
    return {
        "ok": report.ok,
        "summary": report.summary(),
        "baseline_ref": report.baseline_ref,
        "inventory_size": report.inventory_size,
        "change_count": len(report.changes),
        "violation_count": len(report.violations),
        "grandfathered_count": len(report.grandfathered),
        "violations": [
            {
                "path": item.change.path,
                "old_path": item.change.old_path,
                "kind": item.change.kind.value,
                "origin": item.change.origin.value,
                "reason": item.reason,
                "named_surface": item.named_surface,
            }
            for item in report.violations
        ],
        "notes": list(report.notes),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Engine-only scope guard (E00.2). Inspects git changes; never resets.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd().parent if Path.cwd().name == "engine" else Path.cwd(),
        help="Monorepo root (directory that contains engine/).",
    )
    parser.add_argument(
        "--baseline",
        default="origin/main",
        help="Cumulative release baseline ref (default: origin/main).",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=None,
        help="Pre-existing working-tree inventory JSON. Paths listed there are not reset.",
    )
    parser.add_argument(
        "--write-inventory",
        type=Path,
        default=None,
        help="Write the current dirty/untracked inventory and exit 0.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON.",
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()

    # Snapshot first (optional), then evaluate. Writing inventory never resets.
    if args.write_inventory is not None:
        entries = porcelain_to_inventory(collect_working_tree(repo_root))
        payload = dump_inventory(
            entries,
            baseline_ref=args.baseline,
            repo_root=str(repo_root),
        )
        write_inventory(args.write_inventory, payload)
        print(f"wrote inventory {args.write_inventory} ({len(entries)} entries)")
        return 0

    inventory = load_inventory(args.inventory) if args.inventory else ()
    report = evaluate_scope(
        repo_root=repo_root,
        baseline_ref=args.baseline,
        inventory=inventory,
    )
    payload = _report_to_dict(report)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"E00.2 engine scope: {'PASS' if report.ok else 'FAIL'}")
        print(report.summary())
        for note in report.notes:
            print(f"note: {note}")
        for item in report.violations:
            print(f"violation: {item.reason}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
