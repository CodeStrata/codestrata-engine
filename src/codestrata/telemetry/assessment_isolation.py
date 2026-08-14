"""Run assessment primary work with fail-silent telemetry side effects (Slice 9.12).

Primary assessment results, exceptions, and exit codes always win.
Telemetry never replaces a primary exception or converts failure to success.

Slice 20.8: gated assessment_metadata 1.1 emission is best-effort and OFF by
default (``emission_enabled=False``). Lifecycle consent alone never enables amd.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from codestrata.telemetry.assessment_isolation_diagnostics import (
    AssessmentIsolationDiagnostics,
)
from codestrata.telemetry.assessment_isolation_models import (
    AssessmentPrimaryStatus,
    AssessmentTelemetryIsolationResult,
    AssessmentTelemetrySideStatus,
)
from codestrata.telemetry.assessment_isolation_policy import (
    CommunityTelemetryAssessmentIsolationPolicy,
    default_assessment_isolation_policy,
)
from codestrata.telemetry.assessment_lifecycle import (
    record_assess_completed_safely,
    record_assess_invoked_safely,
)
from codestrata.telemetry.assessment_metadata.diagnostics import (
    AssessmentMetadataEmissionDiagnostics,
)
from codestrata.telemetry.assessment_metadata.emitter import emit_assessment_metadata_safely
from codestrata.telemetry.assessment_metadata.policy import (
    CommunityAssessmentMetadataEmissionPolicy,
    default_assessment_metadata_emission_policy,
)
from codestrata.telemetry.assessment_metadata.source import new_assessment_id
from codestrata.telemetry.assessment_metadata.transport import AssessmentMetadataTransport
from codestrata.telemetry.disabled_service import DisabledTelemetryFacade

T = TypeVar("T")


def run_assessment_with_telemetry_isolation(
    primary: Callable[[], T],
    *,
    telemetry: DisabledTelemetryFacade,
    ai_enabled: bool = False,
    domains: list[str] | None = None,
    repo_root: Path | None = None,
    policy: CommunityTelemetryAssessmentIsolationPolicy | None = None,
    diagnostics: AssessmentIsolationDiagnostics | None = None,
    assessment_metadata_policy: CommunityAssessmentMetadataEmissionPolicy | None = None,
    assessment_metadata_transport: AssessmentMetadataTransport | None = None,
    assessment_metadata_diagnostics: AssessmentMetadataEmissionDiagnostics | None = None,
    network_available: bool = True,
) -> tuple[T, AssessmentTelemetryIsolationResult]:
    """Execute primary assessment and isolate telemetry lifecycle events.

    Sequence:
      feature_invoked → primary() → feature_completed | operation_failed
      → (optional) gated assessment_metadata 1.1 emission

    ``KeyboardInterrupt`` / ``SystemExit`` from primary are re-raised without
    failure telemetry (primary interrupt behavior preserved).
    """

    active_policy = policy or default_assessment_isolation_policy()
    active_policy.validate()
    diag = diagnostics or AssessmentIsolationDiagnostics(
        policy_version=active_policy.policy_version
    )
    event_attempts = 0
    event_failures = 0
    telemetry_status = AssessmentTelemetrySideStatus.NOT_ATTEMPTED.value
    failure_category: str | None = None
    # One opaque UUID for this assessment invocation (success and failure share it).
    assessment_id = new_assessment_id()
    amd_policy = (
        assessment_metadata_policy or default_assessment_metadata_emission_policy()
    )
    amd_diag = assessment_metadata_diagnostics or AssessmentMetadataEmissionDiagnostics()

    def _attempt_record(ok: bool, *, category: str = "internal_failure") -> None:
        nonlocal event_attempts, event_failures, telemetry_status, failure_category
        event_attempts += 1
        diag.record_event_attempt()
        if ok:
            telemetry_status = AssessmentTelemetrySideStatus.COMPLETED.value
        else:
            event_failures += 1
            failure_category = category
            diag.record_event_failure(category)
            telemetry_status = AssessmentTelemetrySideStatus.FAILED_SILENTLY.value

    invoked_ok = record_assess_invoked_safely(
        telemetry,
        ai_enabled=ai_enabled,
        domains=domains,
        repo_root=repo_root,
    )
    _attempt_record(invoked_ok)

    try:
        result = primary()
    except Exception as exc:
        completed_ok = record_assess_completed_safely(
            telemetry,
            ai_enabled=ai_enabled,
            ai_executed=False,
            success=False,
            duration_ms=None,
            domains=domains,
            repo_root=repo_root,
        )
        _attempt_record(completed_ok)
        emit_assessment_metadata_safely(
            failure=exc,
            assessment_id=assessment_id,
            telemetry=telemetry,
            policy=amd_policy,
            transport=assessment_metadata_transport,
            network_available=network_available,
            offline_mode=True,
            ai_used=bool(ai_enabled),
            diagnostics=amd_diag,
        )
        diag.record_primary_failure()
        diag.last_telemetry_status = telemetry_status
        raise

    # Success path
    duration_ms = getattr(result, "duration_ms", None)
    ai_executed = bool(getattr(result, "ai_executed", False))
    completed_ok = record_assess_completed_safely(
        telemetry,
        ai_enabled=ai_enabled,
        ai_executed=ai_executed,
        success=True,
        duration_ms=duration_ms if isinstance(duration_ms, (int, float)) else None,
        domains=domains,
        repo_root=repo_root,
    )
    _attempt_record(completed_ok)
    emit_assessment_metadata_safely(
        result=result,
        assessment_id=assessment_id,
        telemetry=telemetry,
        policy=amd_policy,
        transport=assessment_metadata_transport,
        network_available=network_available,
        offline_mode=True,
        ai_used=bool(ai_enabled or ai_executed),
        diagnostics=amd_diag,
    )
    diag.record_primary_success()
    isolation = AssessmentTelemetryIsolationResult(
        primary_status=AssessmentPrimaryStatus.SUCCESS.value,
        telemetry_status=telemetry_status,
        primary_result_preserved=True,
        primary_exception_preserved=True,
        exit_code_preserved=True,
        artifacts_preserved=True,
        source_integrity_preserved=True,
        telemetry_failure_category=failure_category,
        telemetry_event_attempts=event_attempts,
        telemetry_event_failures=event_failures,
        policy_version=active_policy.policy_version,
        limitation_codes=active_policy.limitations,
    )
    return result, isolation


__all__ = [
    "run_assessment_with_telemetry_isolation",
]
