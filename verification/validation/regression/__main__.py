"""CLI: ``python -m verification.validation.regression``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verification.validation.regression.render import render_report
from verification.validation.regression.runner import run_harness


def _repo_root_from_cwd() -> Path:
    cwd = Path.cwd()
    if cwd.name == "engine":
        return cwd.parent
    return cwd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="E15.2 regression harness (planted artifacts; no remote clone).",
    )
    parser.add_argument("--repo-root", type=Path, default=_repo_root_from_cwd())
    parser.add_argument(
        "--write-docs",
        type=Path,
        default=None,
        nargs="?",
        const=Path("engine/docs/validation/regression.md"),
        help="Write engine/docs/validation/regression.md (or a given path).",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    engine_root = args.repo_root.resolve() / "engine"
    report = run_harness(engine_root=engine_root)
    if args.write_docs is not None:
        target = args.write_docs
        if not target.is_absolute():
            target = args.repo_root.resolve() / target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_report(report), encoding="utf-8")
    if args.json:
        payload = {
            "ok": report.ok,
            "status": report.status.value,
            "not_yet_due": list(report.not_yet_due),
            "failed": [
                {"id": item.id, "status": item.status.value, "detail": item.detail}
                for item in report.outcomes
                if item.status.value != "PASS"
            ],
            "outcome_count": len(report.outcomes),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
