"""CLI entry: ``python -m verification.ai_provider_contracts``."""

from __future__ import annotations

import argparse
from pathlib import Path

from verification.ai_provider_contracts.contract import REPORT_FILENAME, REPORT_MD_FILENAME
from verification.ai_provider_contracts.runner import run_ai_provider_contract_verification


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "SV.11.2 Common AI Provider Contracts verification "
            "(CodeStrata v0.2.0 Epic 11, Slice 11.2)"
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

    report = run_ai_provider_contract_verification(
        engine_root=args.engine_root,
        output_dir=args.output_dir,
        write_markdown=not args.no_markdown,
    )
    print(f"SV.11.2 Common AI Provider Contracts verification: {report.verdict}")
    print(f"checks={report.check_counts} scenarios={len(report.negative_scenarios)}")
    out = args.output_dir or (
        (args.engine_root or Path(__file__).resolve().parents[2])
        / "reports"
        / "verification"
        / "sv11-2"
    )
    print(f"report: {out / REPORT_FILENAME}")
    if not args.no_markdown:
        print(f"summary: {out / REPORT_MD_FILENAME}")
    return 0 if report.verdict in {"pass", "pass_with_limitations"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
