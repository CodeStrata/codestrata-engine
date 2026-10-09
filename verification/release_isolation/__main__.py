"""CLI: ``python -m verification.release_isolation``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verification.release_isolation.inspect import inspect_checkout
from verification.release_isolation.render import render_isolation


def _repo_root_from_cwd() -> Path:
    cwd = Path.cwd()
    if cwd.name == "engine":
        return cwd.parent
    return cwd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="E00.3 integration/hotfix/prerelease isolation (read-only).",
    )
    parser.add_argument("--repo-root", type=Path, default=_repo_root_from_cwd())
    parser.add_argument(
        "--write-docs",
        type=Path,
        default=None,
        nargs="?",
        const=Path("engine/docs/release/isolation.md"),
        help="Write engine/docs/release/isolation.md (or a given path).",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    inspection = inspect_checkout(repo_root)
    if args.write_docs is not None:
        target = args.write_docs
        if not target.is_absolute():
            target = repo_root / target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_isolation(inspection), encoding="utf-8")
    if args.json:
        payload = {
            "status": inspection.status.value,
            "push_status": inspection.push.status.value,
            "push_patterns": list(inspection.push.patterns),
            "covers_release_glob": inspection.push.covers_required_glob,
            "story_ref_matches_push": inspection.push.story_ref_matches,
            "ordinary_merge_status": inspection.ordinary_merge.status.value,
            "ordinary_workflows": list(inspection.ordinary_merge.workflows_considered),
            "integration": inspection.policy.lanes.integration,
            "maintenance": inspection.policy.lanes.maintenance,
            "candidate_venv": inspection.policy.namespaces.venv,
            "rollback_sha256": inspection.policy.rollback.sha256,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_isolation(inspection))
    if inspection.status.value not in {"PASS", "PARTIAL"}:
        return 1
    if inspection.push.status.value != "PASS":
        return 1
    if inspection.ordinary_merge.status.value != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
