"""CLI entry: ``python -m verification.openrouter_doctor_integration``."""

from __future__ import annotations

import argparse
from pathlib import Path

from verification.openrouter_doctor_integration.contract import REPORT_FILENAME, REPORT_MD_FILENAME
from verification.openrouter_doctor_integration.reporting import report_directory, verdict_is_allowed
from verification.openrouter_doctor_integration.runner import engine_root, run_verification


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SV.11.11 OpenRouter Doctor Integration Verification"
    )
    parser.add_argument("--engine-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--no-markdown", action="store_true")
    args = parser.parse_args(argv)

    root = args.engine_root or engine_root()
    report = run_verification(root)
    directory = args.output_dir or report_directory(root)
    report.write_json(directory / REPORT_FILENAME)
    if not args.no_markdown:
        report.write_markdown(directory / REPORT_MD_FILENAME)

    print(f"SV.11.11 OpenRouter Doctor Integration Verification: {report.verdict}")
    print(f"checks={report.check_counts} scenarios={len(report.negative_scenarios)}")
    for check in report.checks:
        if not check.ok:
            print(f"  FAILED check: {check.category}/{check.name} :: {check.detail}")
    for scenario in report.negative_scenarios:
        if not scenario.ok:
            print(f"  FAILED scenario {scenario.scenario_id}: {scenario.detail}")
    print(f"report: {directory / REPORT_FILENAME}")
    return 0 if verdict_is_allowed(report.verdict) else 1


if __name__ == "__main__":
    raise SystemExit(main())
