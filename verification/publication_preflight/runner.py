"""Run E14.4 publication preflight and write reports."""

from __future__ import annotations

import argparse
from pathlib import Path

from codestrata.application.release.publication.r01_gate import WorkflowPublisherView
from codestrata.application.release.publication.service import (
    run_publication_preflight,
    write_r01_sidecar,
)
from verification.live_release_baseline.publisher import evaluate_r01
from verification.live_release_baseline.workflows import load_root_workflows


def engine_root_from_here() -> Path:
    return Path(__file__).resolve().parents[2]


def repo_root_from_engine(engine_root: Path) -> Path:
    if engine_root.name == "engine" and (engine_root.parent / ".github").is_dir():
        return engine_root.parent
    return engine_root


def _views(workflows: object) -> tuple[WorkflowPublisherView, ...]:
    return tuple(
        WorkflowPublisherView(
            path=item.path,
            name=item.name,
            pypi_oidc_publish=item.pypi_oidc_publish,
            engine_only_publish=item.engine_only_publish,
            aws_oidc=item.aws_oidc,
            id_token_write=item.id_token_write,
        )
        for item in workflows  # type: ignore[union-attr]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="E14.4 publication preflight (rehearsal only)")
    parser.add_argument(
        "--engine-root",
        type=Path,
        default=engine_root_from_here(),
        help="Engine checkout root.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Monorepo root for R01 workflow inventory (defaults to parent of engine/).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/publication-preflight"),
        help="Output directory for candidate artifacts and preflight JSON.",
    )
    args = parser.parse_args(argv)
    engine_root = args.engine_root.resolve()
    repo_root = (args.repo_root or repo_root_from_engine(engine_root)).resolve()
    output = args.output.resolve()

    inventory = evaluate_r01(load_root_workflows(repo_root))
    views = _views(inventory.workflows)
    summary = run_publication_preflight(
        engine_root=engine_root,
        output_directory=output,
        r01_status=inventory.status.value,
        r01_reason=inventory.reason,
        engine_only_oidc_publisher=inventory.engine_only_oidc_publisher,
        required_outside_engine_change=inventory.required_outside_engine_change,
        workflows=views,
    )
    if summary.r01 is not None:
        write_r01_sidecar(output, summary.r01)

    status = "PASS" if summary.ok else "FAIL"
    print(f"publication preflight rehearsal: {status}")
    print(f"build_ok={summary.build_ok} public_rehearsal_ok={summary.public_rehearsal_ok}")
    print(f"r01={inventory.status.value} r01_ready={summary.r01_ready}")
    if inventory.status.value == "BLOCKED":
        print("R01 BLOCKED (no live publication performed):")
        print(inventory.required_outside_engine_change or inventory.reason)
    if summary.public_rehearsal is not None:
        print(
            f"wheel rehearsal: {summary.public_rehearsal.verification_status} "
            f"({summary.public_rehearsal.verification_reason})"
        )
        print(f"oidc identity={summary.public_rehearsal.oidc_identity}")
    if summary.provenance is not None:
        print(f"wheel sha256: {summary.provenance.primary_artifact_digest('wheel')}")
        print(f"sbom digest: {summary.provenance.sbom_digest}")
    return 0 if summary.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
