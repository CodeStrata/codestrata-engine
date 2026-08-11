"""CLI entry: ``python -m verification.bedrock_provider_migration``."""

from __future__ import annotations

import argparse
from pathlib import Path

from verification.bedrock_provider_migration.contract import (
    REPORT_FILENAME,
    REPORT_MD_FILENAME,
)
from verification.bedrock_provider_migration.reporting import (
    report_directory,
    verdict_is_allowed,
)
from verification.bedrock_provider_migration.runner import engine_root, run_verification


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "SV.11.7 AWS Bedrock Provider Migration verification "
            "(CodeStrata v0.2.0 Epic 11, Slice 11.7)"
        ),
    )
    parser.add_argument("--engine-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--no-markdown",
        action="store_true",
        help="Skip writing the companion Markdown summary.",
    )
    args = parser.parse_args(argv)

    root = args.engine_root or engine_root()
    report = run_verification(root)
    directory = args.output_dir or report_directory(root)
    report.write_json(directory / REPORT_FILENAME)
    if not args.no_markdown:
        report.write_markdown(directory / REPORT_MD_FILENAME)

    print(f"SV.11.7 AWS Bedrock Provider Migration verification: {report.verdict}")
    print(f"checks={report.check_counts} scenarios={len(report.negative_scenarios)}")
    for check in report.checks:
        if not check.ok:
            print(f"  FAILED check: {check.category}/{check.name} :: {check.detail}")
    for scenario in report.negative_scenarios:
        if not scenario.ok:
            print(f"  FAILED scenario {scenario.scenario_id}: {scenario.detail}")
    print(f"report: {directory / REPORT_FILENAME}")
    if not args.no_markdown:
        print(f"summary: {directory / REPORT_MD_FILENAME}")
    return 0 if verdict_is_allowed(report.verdict) else 1


if __name__ == "__main__":
    raise SystemExit(main())
