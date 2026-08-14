"""SV.5 integration tests.

HISTORICAL_FROZEN_CHARACTERIZATION: verifies the superseded ``report.json``
full-document contract. Shipped 0.2.0 writes ``assessment.json`` manifests.
Not an ACTIVE 0.2.0 release gate. Collect with ``CODESTRATA_RUN_HISTORICAL_FROZEN=1``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from verification.assessment_report.reporting import report_contains_forbidden_leak
from verification.assessment_report.runner import run_assessment_report_verification

ENGINE = Path(__file__).resolve().parents[3]


def test_local_only_assessment_report_verification(tmp_path: Path) -> None:
    if os.environ.get("CODESTRATA_SKIP_SV5_FULL") == "1":
        pytest.skip("CODESTRATA_SKIP_SV5_FULL=1")

    report = run_assessment_report_verification(
        engine_root=ENGINE,
        output_dir=tmp_path / "reports",
        local_only=True,
        with_catalog_network=False,
        keep_output=True,
    )
    path = tmp_path / "reports" / "assessment-report-verification.json"
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_name"] == "assessment-report-verification"
    assert payload["schema_version"] == "1.0.0"
    assert report_contains_forbidden_leak(payload) == []
    assert any(run["source"] == "local_fixture" for run in payload["runs"])
    assert report.ok, (report.verdict, report.defects)


def test_catalog_network_assessment_report_verification(tmp_path: Path) -> None:
    if os.environ.get("CODESTRATA_SV5_CATALOG_NETWORK") != "1":
        pytest.skip("set CODESTRATA_SV5_CATALOG_NETWORK=1 for catalog-backed SV.5")

    report = run_assessment_report_verification(
        engine_root=ENGINE,
        output_dir=tmp_path / "reports",
        local_only=False,
        with_catalog_network=True,
        keep_output=True,
    )
    assert report.ok, (report.verdict, report.defects)
    catalog_runs = [run for run in report.runs if run.source == "catalog"]
    assert catalog_runs
    assert catalog_runs[0].repository_id == "cleanarchitecture"
    assert catalog_runs[0].qualified_revision_value == (
        "859b115072337b3b7074007f8231d19f24966f1a"
    )
    assert catalog_runs[0].report_schema_version == "1.2"
