"""Integration test for E14.2 build verification service."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.release.standalone.service import run_build_verification

ENGINE_ROOT = Path(__file__).resolve().parents[3]


def test_run_build_verification_smoke(tmp_path: Path) -> None:
    summary = run_build_verification(engine_root=ENGINE_ROOT, output_directory=tmp_path)
    assert summary.provenance is not None
    assert summary.install_outside_checkout is True
    assert all(check.ok for check in summary.packaging_checks)
    assert summary.ok is True
    assert (tmp_path / "provenance.json").is_file()
    assert (tmp_path / "runtime-sbom.cdx.json").is_file()
