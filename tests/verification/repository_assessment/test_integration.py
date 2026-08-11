"""SV.4 integration tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from verification.repository_assessment.catalog import load_catalog, select_smoke_repository
from verification.repository_assessment.reporting import report_contains_forbidden_leak
from verification.repository_assessment.runner import run_repository_assessment_verification

ENGINE = Path(__file__).resolve().parents[3]
REPO = ENGINE.parent


def test_catalog_gap_is_explicit() -> None:
    catalog = load_catalog(REPO)
    entry, reason = select_smoke_repository(catalog)
    if catalog.qualification_gap:
        assert entry is None
        assert "qualified" in reason.lower()


def test_local_only_verification_integration(tmp_path: Path) -> None:
    if os.environ.get("CODESTRATA_SKIP_SV4_FULL") == "1":
        pytest.skip("CODESTRATA_SKIP_SV4_FULL=1")

    report = run_repository_assessment_verification(
        engine_root=ENGINE,
        output_dir=tmp_path / "reports",
        installation_method="pip_path_non_editable",
        local_only=True,
        with_catalog_network=False,
    )
    path = tmp_path / "reports" / "repository-assessment-verification.json"
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_name"] == "repository-assessment-verification"
    assert payload["schema_version"] == "1.0.0"
    assert payload["installation_method"] == "pip_path_non_editable"
    assert report_contains_forbidden_leak(payload) == []
    assert report.cli_version is not None
    assert len(report.scenarios) >= 14
    # Scenario A must record catalog gap clearly when unqualified.
    scenario_a = next(s for s in report.scenarios if s.scenario_id.startswith("A_"))
    if load_catalog(REPO).qualification_gap:
        assert "catalog_qualification_gap" in scenario_a.failures
    assert report.ok, (report.verdict, report.failures)


def test_catalog_network_requires_qualification() -> None:
    """Remote catalog run is separately gated; without qualification it fails A clearly."""

    if os.environ.get("CODESTRATA_SV4_CATALOG_NETWORK") != "1":
        pytest.skip("set CODESTRATA_SV4_CATALOG_NETWORK=1 to attempt catalog clone")

    catalog = load_catalog(REPO)
    entry, _ = select_smoke_repository(catalog)
    if entry is None:
        pytest.skip("no qualified catalog revision available")

    report = run_repository_assessment_verification(
        engine_root=ENGINE,
        output_dir=ENGINE / "reports" / "verification-sv4-catalog",
        installation_method="pip_path_non_editable",
        local_only=False,
        with_catalog_network=True,
    )
    assert report.ok, (report.verdict, report.failures)
