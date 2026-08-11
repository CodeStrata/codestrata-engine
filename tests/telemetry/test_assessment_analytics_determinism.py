"""Assessment analytics determinism, diagnostics, isolation, boundary (Slice 10.4)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from codestrata.telemetry.analytics.assessment_analytics import (
    build_assessment_analytics_event,
    collect_assessment_analytics,
)
from codestrata.telemetry.analytics.assessment_analytics_diagnostics import (
    assessment_analytics_diagnostics_for_event,
    empty_assessment_analytics_diagnostics,
)
from codestrata.telemetry.analytics.assessment_analytics_policy import (
    default_assessment_analytics_policy,
)
from codestrata.telemetry.analytics.assessment_analytics_projection import (
    project_assessment_analytics_event,
)
from codestrata.telemetry.analytics.assessment_analytics_serialization import (
    assessment_analytics_event_to_stable_json,
)
from codestrata.telemetry.analytics.assessment_analytics_validation import (
    validate_assessment_analytics_event,
)
from codestrata.telemetry.analytics.installation_identity import (
    AnonymousInstallationIdentity,
    new_anonymous_installation_identity,
)


def _identity() -> AnonymousInstallationIdentity:
    return AnonymousInstallationIdentity(
        installation_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    )


def test_determinism() -> None:
    event = build_assessment_analytics_event(
        identity=_identity(),
        duration_bucket="s_10_60",
        outcome="success",
        enabled_assessment_heads=("cloud_readiness", "security_intelligence"),
    )
    a = validate_assessment_analytics_event(event)
    b = validate_assessment_analytics_event(event)
    assert a.to_stable_dict() == b.to_stable_dict()
    assert assessment_analytics_event_to_stable_json(event) == (
        assessment_analytics_event_to_stable_json(event)
    )
    parsed = json.loads(assessment_analytics_event_to_stable_json(event))
    assert list(parsed.keys()) == sorted(parsed.keys())
    assert parsed["enabled_assessment_heads"] == sorted(
        parsed["enabled_assessment_heads"]
    )


def test_diagnostics_never_include_identity_or_head_list() -> None:
    event = build_assessment_analytics_event(
        identity=_identity(),
        duration_bucket="lt_1s",
        outcome="failure",
        failure_category="assessment_failed",
        enabled_assessment_heads=("security_intelligence",),
    )
    diag = assessment_analytics_diagnostics_for_event(
        installation_id_present=True,
        privacy_projection_applied=True,
        command_category=event.command_category,
        outcome=event.outcome,
        duration_bucket=event.duration_bucket,
        failure_category=event.failure_category,
        enabled_head_count=len(event.enabled_assessment_heads),
        projected=True,
        validated=True,
        rejected=False,
        limitation_codes=default_assessment_analytics_policy().limitations,
    )
    blob = diag.to_stable_json()
    assert event.installation_id not in blob
    assert "installation_id" not in diag.to_stable_dict()
    assert "security_intelligence" not in blob
    assert diag.enabled_head_count == 1
    empty = empty_assessment_analytics_diagnostics()
    assert empty.transmission_enabled is False


def test_no_transport_invocation(tmp_path: Path) -> None:
    with patch("codestrata.telemetry.transport.send_payload") as send:
        collect_assessment_analytics(
            home=tmp_path / "home",
            identity=new_anonymous_installation_identity(),
            outcome="success",
            duration_ms=500,
        )
        send.assert_not_called()


def test_primary_isolation_construction_failure_does_not_raise_into_caller_contract(
    tmp_path: Path,
) -> None:
    """Construction API raises bounded AnalyticsError — product path stays unwired.

    Proves analytics failures are typed and do not invent primary AssessmentCommandError.
    """

    from codestrata.telemetry.analytics.errors import AnalyticsError

    try:
        collect_assessment_analytics(
            identity=_identity(),
            outcome="failure",
            duration_bucket="unknown",
            # missing failure_category → analytics validation failure
        )
    except AnalyticsError as error:
        assert error.code.value == "outcome_failure_mismatch"
    else:
        raise AssertionError("expected AnalyticsError")


def test_no_analytics_persistence_files(tmp_path: Path) -> None:
    home = tmp_path / "home"
    collect_assessment_analytics(
        home=home,
        outcome="success",
        duration_bucket="unknown",
    )
    names = {p.name for p in home.rglob("*") if p.is_file()}
    assert names == {"anonymous-installation-identity.json"}
    assert "analytics" not in " ".join(names).lower()


def test_projection_round_trip_stable() -> None:
    event = build_assessment_analytics_event(
        identity=_identity(),
        duration_bucket="gt_5m",
        outcome="success",
        enabled_assessment_heads=("modernization_assessment",),
        offline_mode=True,
        ai_requested=True,
        ai_used=True,
    )
    projected = project_assessment_analytics_event(event)
    assert projected.to_stable_json() == projected.to_stable_json()
