"""CLI entry: ``python -m verification.cli_initialization``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from verification.cli_initialization.runner import run_cli_initialization_verification


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SV.3 CLI Initialization Workflow Verification",
    )
    parser.add_argument("--engine-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--method",
        choices=("pip_path_non_editable", "pip_wheel"),
        default="pip_path_non_editable",
    )
    args = parser.parse_args(argv)
    report = run_cli_initialization_verification(
        engine_root=args.engine_root,
        output_dir=args.output_dir,
        installation_method=args.method,
    )
    print(f"SV.3 cli initialization verification: {'PASS' if report.ok else 'FAIL'}")
    print(f"verdict: {report.verdict}")
    if report.failures:
        print(f"failures: {', '.join(report.failures)}")
    out = (args.output_dir or Path("reports/verification")) / "cli-initialization-verification.json"
    print(f"report: {out if args.output_dir else 'reports/verification/cli-initialization-verification.json'}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
