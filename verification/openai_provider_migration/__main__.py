"""CLI entry: ``python -m verification.openai_provider_migration``."""

from __future__ import annotations

import argparse
from pathlib import Path

from verification.openai_provider_migration.contract import REPORT_FILENAME, REPORT_MD_FILENAME
from verification.openai_provider_migration.runner import (
    run_openai_provider_migration_verification,
    verdict_is_acceptable,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "SV.11.6 OpenAI Provider Migration verification "
            "(CodeStrata v0.2.0 Epic 11, Slice 11.6)"
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

    report = run_openai_provider_migration_verification(
        engine_root=args.engine_root,
        output_dir=args.output_dir,
        write_markdown=not args.no_markdown,
    )
    print(f"SV.11.6 OpenAI Provider Migration verification: {report.verdict}")
    print(f"checks={report.check_counts} scenarios={len(report.negative_scenarios)}")
    out = args.output_dir or (
        (args.engine_root or Path(__file__).resolve().parents[2])
        / "reports"
        / "verification"
        / "sv11-6"
    )
    print(f"report: {out / REPORT_FILENAME}")
    if not args.no_markdown:
        print(f"summary: {out / REPORT_MD_FILENAME}")
    return 0 if verdict_is_acceptable(report.verdict) else 1


if __name__ == "__main__":
    raise SystemExit(main())
