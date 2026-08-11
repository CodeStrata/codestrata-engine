"""SV.3 full integration against a non-editable installed CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from verification.cli_initialization.reporting import report_contains_forbidden_leak
from verification.cli_initialization.runner import run_cli_initialization_verification

ENGINE = Path(__file__).resolve().parents[3]


def test_cli_initialization_verification_integration(tmp_path: Path) -> None:
    if os.environ.get("CODESTRATA_SKIP_SV3_FULL") == "1":
        pytest.skip("CODESTRATA_SKIP_SV3_FULL=1")

    report = run_cli_initialization_verification(
        engine_root=ENGINE,
        output_dir=tmp_path / "reports",
        installation_method="pip_path_non_editable",
    )
    path = tmp_path / "reports" / "cli-initialization-verification.json"
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_name"] == "cli-initialization-verification"
    assert payload["schema_version"] == "1.0.0"
    assert payload["installation_method"] == "pip_path_non_editable"
    assert report_contains_forbidden_leak(payload) == []
    assert report.ok, (report.verdict, report.failures)
    assert report.cli_version is not None
    assert len(report.scenarios) >= 10
