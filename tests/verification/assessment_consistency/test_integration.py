"""Integration: run SV.11 against preserved SV.10 outputs when present.

HISTORICAL_FROZEN_CHARACTERIZATION: depends on superseded SV.10
``report.json`` artifacts. Not an ACTIVE 0.2.0 release gate.
Collect with ``CODESTRATA_RUN_HISTORICAL_FROZEN=1``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from verification.assessment_consistency.contract import RELEASE_VALIDATION_TARGET
from verification.assessment_consistency.runner import run_assessment_consistency


def test_sv11_against_sv10_artifacts() -> None:
    engine = Path(__file__).resolve().parents[3]
    sv10 = engine / "reports" / "verification" / "sv10"
    if not (sv10 / "curated-repository-validation.json").is_file():
        pytest.skip("SV.10 outputs not present")
    report = run_assessment_consistency(engine_root=engine, sv10_dir=sv10)
    assert report.repository_count == RELEASE_VALIDATION_TARGET
    assert report.verdict in {"PASS", "PASS_WITH_LIMITATIONS", "FAIL"}
    assert len(report.included_repository_ids) == 22
    assert all(report.engineering_intelligence_input_ready.values()) or report.verdict == "FAIL"
