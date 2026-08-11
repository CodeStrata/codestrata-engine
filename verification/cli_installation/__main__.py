"""CLI entry: ``python -m verification.cli_installation``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from verification.cli_installation.runner import run_cli_installation_verification


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SV.2 Clean CLI Installation Verification",
    )
    parser.add_argument(
        "--engine-root",
        type=Path,
        default=None,
        help="Path to the Engine package root (directory with pyproject.toml).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for cli-installation-verification.json.",
    )
    parser.add_argument(
        "--method",
        choices=("pip_wheel", "pip_sdist", "pip_path_non_editable"),
        default="pip_wheel",
        help="Installation method under test (default: pip_wheel).",
    )
    parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Retain the temporary verification workspace for debugging.",
    )
    args = parser.parse_args(argv)

    report = run_cli_installation_verification(
        engine_root=args.engine_root,
        output_dir=args.output_dir,
        installation_method=args.method,
        keep_workspace=args.keep_workspace,
    )
    print(f"SV.2 cli installation verification: {'PASS' if report.ok else 'FAIL'}")
    print(f"summary: {report.summary}")
    if report.report_path:
        print(f"report: {report.report_path}")
    if report.failures:
        print(f"failures: {', '.join(report.failures)}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
