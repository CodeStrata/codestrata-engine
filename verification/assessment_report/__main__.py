"""CLI entry: ``python -m verification.assessment_report``."""

from __future__ import annotations

import argparse
from pathlib import Path

from verification.assessment_report.runner import run_assessment_report_verification


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SV.5 Assessment Report Verification",
    )
    parser.add_argument("--engine-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Verify controlled local fixture report only (no catalog clone)",
    )
    parser.add_argument(
        "--with-catalog-network",
        action="store_true",
        help="Include catalog-backed CleanArchitecture (or policy-selected) report",
    )
    parser.add_argument(
        "--repository",
        type=str,
        default=None,
        help="Optional catalog id hint (selection remains catalog-policy driven)",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        action="append",
        default=None,
        help="Reuse an existing assessment run directory (repeatable)",
    )
    parser.add_argument(
        "--keep-output",
        action="store_true",
        default=True,
        help="Retain prepared assessment run copies under the output directory",
    )
    args = parser.parse_args(argv)

    local_only = args.local_only or not args.with_catalog_network
    if args.repository and not args.with_catalog_network and not args.artifact_dir:
        print(
            "note: --repository is informational; enable --with-catalog-network "
            "for catalog-backed assessment inputs"
        )

    report = run_assessment_report_verification(
        engine_root=args.engine_root,
        output_dir=args.output_dir,
        local_only=local_only,
        with_catalog_network=args.with_catalog_network,
        keep_output=args.keep_output,
        artifact_dirs=args.artifact_dir,
    )
    print(f"SV.5 assessment report verification: {'PASS' if report.ok else 'FAIL'}")
    print(f"verdict: {report.verdict}")
    if report.defects:
        print(f"defects: {', '.join(report.defects[:8])}")
    out = (
        (args.output_dir or Path("reports/verification"))
        / "assessment-report-verification.json"
    )
    print(f"report: {out}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
