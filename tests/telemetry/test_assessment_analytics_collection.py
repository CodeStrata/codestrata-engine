"""Assessment analytics collection tests (Epic 10 Slice 10.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from codestrata.telemetry.analytics.assessment_analytics import (
    classify_duration_bucket_ms,
    collect_assessment_analytics,
)
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import AnalyticsCategory
from codestrata.telemetry.analytics.installation_identity import (
    AnonymousInstallationIdentity,
    new_anonymous_installation_identity,
)
from codestrata.telemetry.analytics.assessment_analytics_projection import (
    project_assessment_analytics_to_analytics_event,
)


def _identity() -> AnonymousInstallationIdentity:
    return AnonymousInstallationIdentity(
        installation_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    )


@pytest.mark.parametrize(
    ("ms", "bucket"),
    [
        (0, "lt_1s"),
        (999, "lt_1s"),
        (1_000, "s_1_10"),
        (9_999, "s_1_10"),
        (10_000, "s_10_60"),
        (59_999, "s_10_60"),
        (60_000, "m_1_5"),
        (299_999, "m_1_5"),
        (300_000, "gt_5m"),
        (None, "unknown"),
    ],
)
def test_duration_bucket_thresholds(ms: float | None, bucket: str) -> None:
    assert classify_duration_bucket_ms(ms) == bucket


def test_collect_success_local_only(tmp_path: Path) -> None:
    home = tmp_path / "home"
    event = collect_assessment_analytics(
        home=home,
        outcome="success",
        duration_ms=2_500,
        enabled_assessment_heads=("security_intelligence", "cloud_readiness"),
        ai_requested=False,
        ai_used=False,
    )
    assert event.command_category == "assess"
    assert event.outcome == "success"
    assert event.duration_bucket == "s_1_10"
    assert event.enabled_assessment_heads == (
        "cloud_readiness",
        "security_intelligence",
    )
    assert event.failure_category is None
    names = {path.name for path in home.iterdir()}
    assert names == {"anonymous-installation-identity.json"}


def test_collect_failure_requires_failure_category() -> None:
    with pytest.raises(AnalyticsError) as exc:
        collect_assessment_analytics(
            identity=_identity(),
            outcome="failure",
            duration_bucket="unknown",
            failure_category=None,
        )
    assert exc.value.code is AnalyticsErrorCode.OUTCOME_FAILURE_MISMATCH


def test_collect_failure_with_category() -> None:
    event = collect_assessment_analytics(
        identity=_identity(),
        outcome="failure",
        duration_ms=12_000,
        failure_category="assessment_failed",
        enabled_assessment_heads=("architecture_intelligence",),
    )
    assert event.outcome == "failure"
    assert event.failure_category == "assessment_failed"
    assert event.duration_bucket == "s_10_60"


def test_collect_rejects_scan_command() -> None:
    with pytest.raises(AnalyticsError) as exc:
        collect_assessment_analytics(
            identity=_identity(),
            command_category="scan",
            outcome="success",
            duration_bucket="lt_1s",
        )
    assert exc.value.code is AnalyticsErrorCode.INVALID_COMMAND_CATEGORY


def test_base_analytics_event_identity_free() -> None:
    event = collect_assessment_analytics(
        identity=new_anonymous_installation_identity(),
        outcome="success",
        duration_bucket="m_1_5",
        enabled_assessment_heads=("ai_readiness",),
        ai_requested=True,
        ai_used=False,
    )
    analytics = project_assessment_analytics_to_analytics_event(event)
    assert analytics.category is AnalyticsCategory.ASSESSMENT
    payload = analytics.to_intake_dict()
    assert "installation_id" not in payload
    assert payload["operation_category"] == "assess"
    assert payload["result"] == "success"
    assert payload["ai_requested"] is True
    assert payload["enabled_assessment_heads"] == ["ai_readiness"]


def test_product_path_still_does_not_auto_collect(tmp_path: Path, monkeypatch) -> None:
    from codestrata.telemetry.service import get_telemetry_service, reset_telemetry_singletons

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    get_telemetry_service().record_report_opened()
    assert list(home.iterdir()) == []
