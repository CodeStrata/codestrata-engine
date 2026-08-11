"""SV.2 runner integration — non-editable path install in a fresh venv."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from verification.cli_installation.runner import run_cli_installation_verification

ENGINE = Path(__file__).resolve().parents[3]


def test_clean_path_install_verification(tmp_path: Path) -> None:
    """Full SV.2 flow using non-editable path install (CI-friendly)."""

    if os.environ.get("CODESTRATA_SKIP_SV2_FULL") == "1":
        pytest.skip("CODESTRATA_SKIP_SV2_FULL=1")

    report = run_cli_installation_verification(
        engine_root=ENGINE,
        output_dir=tmp_path / "reports",
        installation_method="pip_path_non_editable",
    )
    assert report.report_path is not None
    assert Path(report.report_path).is_file()
    assert report.environment.get("editable_install") is False
    assert report.environment.get("developer_pythonpath") is False
    assert "pip_install" not in report.failures
    assert report.ok, (report.summary, report.failures)
    assert report.codestrata_version is not None
