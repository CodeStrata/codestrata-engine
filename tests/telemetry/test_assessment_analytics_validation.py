"""Assessment analytics validation tests (Slice 10.4)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.analytics.assessment_analytics import (
    AssessmentAnalyticsEvent,
    build_assessment_analytics_event,
)
from codestrata.telemetry.analytics.assessment_analytics_validation import (
    validate_assessment_analytics_event,
)
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.installation_identity import (
    AnonymousInstallationIdentity,
)


def _id() -> AnonymousInstallationIdentity:
    return AnonymousInstallationIdentity(
        installation_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    )


def test_validate_success() -> None:
    event = build_assessment_analytics_event(
        identity=_id(),
        duration_bucket="unknown",
        outcome="success",
        enabled_assessment_heads=(),
    )
    projected = validate_assessment_analytics_event(event)
    assert projected.fields["outcome"] == "success"


def test_validate_cancelled_requires_failure_category() -> None:
    event = AssessmentAnalyticsEvent(
        installation_id=_id().installation_id,
        command_category="assess",
        duration_bucket="lt_1s",
        outcome="cancelled",
        enabled_assessment_heads=(),
        failure_category=None,
    )
    with pytest.raises(AnalyticsError) as exc:
        validate_assessment_analytics_event(event)
    assert exc.value.code is AnalyticsErrorCode.OUTCOME_FAILURE_MISMATCH


def test_validate_cancelled_with_interrupted() -> None:
    event = AssessmentAnalyticsEvent(
        installation_id=_id().installation_id,
        command_category="assess",
        duration_bucket="lt_1s",
        outcome="cancelled",
        enabled_assessment_heads=(),
        failure_category="interrupted",
    )
    assert validate_assessment_analytics_event(event).fields["failure_category"] == (
        "interrupted"
    )


def test_invalid_duration_bucket() -> None:
    event = AssessmentAnalyticsEvent(
        installation_id=_id().installation_id,
        command_category="assess",
        duration_bucket="0-5s",
        outcome="success",
        enabled_assessment_heads=(),
    )
    with pytest.raises(AnalyticsError) as exc:
        validate_assessment_analytics_event(event)
    assert exc.value.code is AnalyticsErrorCode.INVALID_DURATION_BUCKET
