"""CLI: ``python -m verification.validation.release_gate``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verification.validation.release_gate.render import render_report
from verification.validation.release_gate.runner import run_release_gate_review


def _repo_root_from_cwd() -> Path:
    cwd = Path.cwd()
    if cwd.name == "engine":
        return cwd.parent
    return cwd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="E15.3 release-gate review (ledgers, tiers, M33 envelope, M15 confusion).",
    )
    parser.add_argument("--repo-root", type=Path, default=_repo_root_from_cwd())
    parser.add_argument(
        "--write-docs",
        type=Path,
        default=None,
        nargs="?",
        const=Path("engine/docs/validation/release-gate-review.md"),
        help="Write engine/docs/validation/release-gate-review.md (or a given path).",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    engine_root = repo_root / "engine"
    report = run_release_gate_review(engine_root=engine_root, repo_root=repo_root)
    if args.write_docs is not None:
        target = args.write_docs
        if not target.is_absolute():
            target = repo_root / target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_report(report), encoding="utf-8")
    if args.json:
        payload = {
            "ok": report.ok,
            "decision": report.decision.value,
            "candidate_sha": report.candidate_sha,
            "corpus_manifest_ok": report.corpus_manifest_ok,
            "regression_harness_ok": report.regression_harness_ok,
            "remote_tiers_enabled": report.remote_tiers_enabled,
            "tiers_executed": report.tiers_executed,
            "external_pin_count": report.external_pin_count,
            "m15_promotion_blocked": report.m15_promotion_blocked,
            "checkpoint_gates": [
                {
                    "id": item.gate_id,
                    "decision": item.decision.value,
                    "detail": item.detail,
                }
                for item in report.checkpoint_gates
            ],
            "story_prerequisites": [
                {
                    "id": item.story_id,
                    "status": item.status.value,
                    "detail": item.detail,
                }
                for item in report.story_prerequisites
            ],
            "repository_result_count": len(report.repository_results),
            "source_tree_digest": report.source_tree_digest,
            "budgets_published": report.resource_envelope.budgets_published,
            "repository_results": [
                {
                    "id": item.repository_id,
                    "tier": item.tier.value,
                    "status": item.status.value,
                    "detail": item.detail,
                    "wall_seconds": item.wall_seconds,
                    "peak_rss_bytes": item.peak_rss_bytes,
                }
                for item in report.repository_results
            ],
            "notes": list(report.notes),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
