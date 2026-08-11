"""Assessment analytics isolation and product-path boundary (Slice 10.4).

Decision A: construction API only — not wired into assess. These tests prove
the assess product path does not invoke assessment analytics and that analytics
errors cannot substitute for primary assessment errors.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.application.assessment.service import AssessmentCommandError
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode


def test_assess_cli_does_not_import_assessment_analytics_collect() -> None:
    import codestrata.cli.assess as assess_mod

    source = Path(assess_mod.__file__).read_text(encoding="utf-8")
    assert "collect_assessment_analytics" not in source
    assert "AssessmentAnalyticsEvent" not in source


def test_assessment_isolation_does_not_call_assessment_analytics() -> None:
    import codestrata.telemetry.assessment_isolation as iso

    source = Path(iso.__file__).read_text(encoding="utf-8")
    assert "collect_assessment_analytics" not in source
    assert "assessment_analytics" not in source


def test_analytics_error_is_not_assessment_command_error() -> None:
    err = AnalyticsError(AnalyticsErrorCode.OUTCOME_FAILURE_MISMATCH)
    assert not isinstance(err, AssessmentCommandError)
    assert str(err) == "outcome_failure_mismatch"


def test_primary_result_unchanged_when_analytics_api_unused(tmp_path: Path, monkeypatch) -> None:
    """Without wiring, invoking telemetry product facade leaves home empty."""

    from codestrata.telemetry.service import get_telemetry_service, reset_telemetry_singletons

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    with patch(
        "codestrata.telemetry.analytics.assessment_analytics.collect_assessment_analytics"
    ) as collect:
        get_telemetry_service().record_assessment_started(ai_enabled=False)
        get_telemetry_service().record_assessment_completed(
            ai_enabled=False,
            ai_executed=False,
            success=True,
            duration_ms=100,
        )
        collect.assert_not_called()
    assert list(home.iterdir()) == []


def test_no_platform_or_data_lake_imports_in_assessment_analytics() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "codestrata" / "telemetry" / "analytics"
    for path in root.glob("assessment_analytics*.py"):
        text = path.read_text(encoding="utf-8")
        assert "codestrata_platform" not in text
        assert "boto3" not in text
        assert "data_lake" not in text.lower() or "deferred" in text.lower()
