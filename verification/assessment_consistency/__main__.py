"""CLI entry: ``python -m verification.assessment_consistency``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from verification.assessment_consistency.contract import REPORT_FILENAME, SV11_OUTPUT_RELATIVE
from verification.assessment_consistency.runner import run_assessment_consistency


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SV.11 Assessment Consistency Verification (22 curated repos)",
    )
    parser.add_argument("--engine-root", type=Path, default=None)
    parser.add_argument("--sv10-dir", type=Path, default=None, help="SV.10 output directory")
    parser.add_argument("--output-dir", type=Path, default=None, help="SV.11 output directory")
    args = parser.parse_args(argv)

    report = run_assessment_consistency(
        engine_root=args.engine_root,
        sv10_dir=args.sv10_dir,
        output_dir=args.output_dir,
    )
    out = args.output_dir or Path(SV11_OUTPUT_RELATIVE)
    print(f"SV.11 assessment consistency: {report.verdict}")
    print(
        f"repositories={report.repository_count} "
        f"defects={len(report.defect_candidates)} "
        f"outliers={len(report.outlier_records)}"
    )
    print(f"report: {out / REPORT_FILENAME}")
    return 0 if report.verdict in {"PASS", "PASS_WITH_LIMITATIONS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
