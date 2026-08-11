"""CLI entry: ``python -m verification.curated_repository_validation``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from verification.curated_repository_validation.contract import TIER_ORDER
from verification.curated_repository_validation.runner import (
    run_curated_repository_validation,
    run_tier,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SV.10 Validate 22 Curated OSS Repositories",
    )
    parser.add_argument("--engine-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--tier",
        choices=TIER_ORDER,
        action="append",
        dest="tiers",
        help="Run one catalog tier (repeatable). Default with --all: all tiers.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all four tiers then determinism samples.",
    )
    parser.add_argument(
        "--skip-determinism",
        action="store_true",
        help="Skip post-tier determinism sample repeats.",
    )
    parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Retain temporary clone/home workspaces for debugging.",
    )
    parser.add_argument(
        "--repository",
        action="append",
        dest="repositories",
        help="Optional catalog repository id filter within selected tiers.",
    )
    args = parser.parse_args(argv)

    if args.all and args.tiers:
        parser.error("use either --all or --tier, not both")
    if not args.all and not args.tiers:
        parser.error("specify --all or one or more --tier values")

    if args.all:
        report = run_curated_repository_validation(
            engine_root=args.engine_root,
            output_dir=args.output_dir,
            keep_workspace=args.keep_workspace,
            run_determinism=not args.skip_determinism,
        )
        print(f"SV.10 curated repository validation: {report.overall_verdict}")
        print(f"executed={report.executed_repository_count} passed={report.passed_count} failed={report.failed_count}")
        out = args.output_dir or Path("reports/verification/sv10")
        print(f"report: {out / 'curated-repository-validation.json'}")
        return 0 if report.overall_verdict in {"PASS", "PASS_WITH_LIMITATIONS"} else 1

    # Single / multi-tier without full orchestration install sharing.
    from verification.cli_installation.environment import engine_root_from_package
    from verification.curated_repository_validation.assessment import (
        cleanup_venv,
        install_codestrata_cli,
    )
    from verification.curated_repository_validation.summary import build_final_report
    from verification.curated_repository_validation.catalog import load_catalog_document

    engine = (args.engine_root or engine_root_from_package()).resolve()
    out = (args.output_dir or (engine / "reports" / "verification" / "sv10")).resolve()
    codestrata, venv_dir = install_codestrata_cli(engine)
    all_results = []
    summaries = []
    try:
        for tier in args.tiers:
            results, summary = run_tier(
                tier,
                engine_root=engine,
                output_dir=out,
                codestrata=codestrata,
                venv_dir=venv_dir,
                keep_workspace=args.keep_workspace,
                repository_ids=args.repositories,
            )
            all_results.extend(results)
            summaries.append(summary)
            print(f"{tier}: {summary.verdict} passed={summary.passed} failed={summary.failed}")
    finally:
        cleanup_venv(venv_dir)

    catalog = load_catalog_document(engine)
    report = build_final_report(
        catalog_id=catalog.get("catalog_id"),
        catalog_schema_version=catalog.get("schema_version"),
        target_count=len(all_results),
        tier_summaries=summaries,
        records=all_results,
        determinism_samples=[],
        defects=[],
        blockers=[],
        warnings=["partial_tier_run" if not args.all else ""],
        limitations=[],
    )
    report.write_json(out / "curated-repository-validation.json")
    # For partial tier runs, prefer aggregated tier verdicts.
    tier_ok = all(s.verdict in {"PASS", "PASS_WITH_LIMITATIONS"} for s in summaries)
    print(f"SV.10 tier run: {'PASS' if tier_ok else report.overall_verdict}")
    return 0 if tier_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
