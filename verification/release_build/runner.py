"""Run E14.2 wheel/sdist build verification and write reports."""

from __future__ import annotations

import argparse
from pathlib import Path

from codestrata.application.release.standalone.service import run_build_verification


def engine_root_from_here() -> Path:
    return Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="E14.2 standalone wheel/sdist build verifier")
    parser.add_argument(
        "--engine-root",
        type=Path,
        default=engine_root_from_here(),
        help="Engine checkout root (defaults to parent of verification/).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/release-build"),
        help="Directory for dist/, provenance, SBOM and summary JSON.",
    )
    args = parser.parse_args(argv)
    summary = run_build_verification(
        engine_root=args.engine_root.resolve(),
        output_directory=args.output.resolve(),
    )
    status = "PASS" if summary.ok else "FAIL"
    print(f"release build verification: {status}")
    if summary.provenance is not None:
        wheel = summary.provenance.primary_artifact_digest("wheel")
        sdist = summary.provenance.primary_artifact_digest("sdist")
        print(f"wheel sha256: {wheel}")
        print(f"sdist sha256: {sdist}")
        print(f"sbom digest: {summary.provenance.sbom_digest}")
    for check in summary.packaging_checks:
        mark = "PASS" if check.ok else "FAIL"
        print(f"  [{mark}] {check.name}: {check.detail}")
    print(f"install_outside_checkout: {summary.install_outside_checkout}")
    return 0 if summary.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
