"""CLI entry: ``python -m verification.repository_assessment``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from verification.repository_assessment.runner import run_repository_assessment_verification


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SV.4 Repository Assessment End-to-End Verification",
    )
    parser.add_argument("--engine-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--method",
        choices=("pip_path_non_editable", "pip_wheel"),
        default="pip_path_non_editable",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Skip catalog network clones; treat catalog qualification gap as expected limitation",
    )
    parser.add_argument(
        "--with-catalog-network",
        action="store_true",
        help="Allow cloning a qualified catalog repository (requires qualified_revision)",
    )
    parser.add_argument(
        "--repository",
        type=str,
        default=None,
        help="Optional catalog repository id (reserved; selection remains policy-driven when qualified)",
    )
    parser.add_argument(
        "--keep-output",
        action="store_true",
        help="Retain temporary clone/workspace directories after the run",
    )
    args = parser.parse_args(argv)

    if args.repository and not args.with_catalog_network:
        print(
            "note: --repository is recorded for future qualified runs; "
            "selection still requires catalog qualified_revision",
            file=sys.stderr,
        )

    report = run_repository_assessment_verification(
        engine_root=args.engine_root,
        output_dir=args.output_dir,
        installation_method=args.method,
        local_only=args.local_only or not args.with_catalog_network,
        with_catalog_network=args.with_catalog_network,
        keep_output=args.keep_output,
    )
    print(
        f"SV.4 repository assessment verification: {'PASS' if report.ok else 'FAIL'}"
    )
    print(f"verdict: {report.verdict}")
    if report.failures:
        print(f"failures: {', '.join(report.failures)}")
    if report.limitations:
        print(f"limitations: {'; '.join(report.limitations[:5])}")
    out = (
        (args.output_dir or Path("reports/verification"))
        / "repository-assessment-verification.json"
    )
    print(f"report: {out}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
