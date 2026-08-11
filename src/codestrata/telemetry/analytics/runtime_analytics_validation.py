"""Runtime analytics validation (Epic 10 Slice 10.3)."""

from __future__ import annotations

from typing import Any

from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import (
    _APPROVED_ARCHITECTURES,
    _APPROVED_OS_FAMILIES,
)
from codestrata.telemetry.analytics.installation_identity import is_uuid_v4
from codestrata.telemetry.analytics.runtime_analytics import (
    COMMUNITY_RUNTIME_ANALYTICS_POLICY_VERSION,
    COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_VERSION,
    CommunityRuntimeAnalyticsPolicy,
    RuntimeAnalyticsEvent,
    default_runtime_analytics_policy,
    is_safe_cli_version,
    is_safe_release_adoption,
    is_safe_runtime_version,
)
from codestrata.telemetry.analytics.runtime_analytics_compatibility import (
    assert_runtime_analytics_schema_compatible,
)
from codestrata.telemetry.analytics.runtime_analytics_projection import (
    RuntimeAnalyticsProjection,
    project_runtime_analytics_event,
)
from codestrata.telemetry.analytics.validation import (
    assert_persistence_blocked,
    assert_transmission_blocked,
    validate_analytics_event,
)


def validate_runtime_analytics_event(
    event: RuntimeAnalyticsEvent,
    *,
    policy: CommunityRuntimeAnalyticsPolicy | None = None,
) -> RuntimeAnalyticsProjection:
    active = policy or default_runtime_analytics_policy()
    active.validate()
    assert_runtime_analytics_schema_compatible(event.schema_version)

    if event.policy_version != COMMUNITY_RUNTIME_ANALYTICS_POLICY_VERSION:
        raise AnalyticsError(AnalyticsErrorCode.INCOMPATIBLE_SCHEMA)
    if event.schema_version != COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_VERSION:
        raise AnalyticsError(AnalyticsErrorCode.INCOMPATIBLE_SCHEMA)
    if not event.privacy_projection_applied:
        raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REQUIRED)
    if active.installation_id_required and not is_uuid_v4(event.installation_id):
        raise AnalyticsError(AnalyticsErrorCode.VALIDATION_FAILED)
    if event.category != "runtime":
        raise AnalyticsError(AnalyticsErrorCode.UNKNOWN_CATEGORY)
    if event.os_family not in _APPROVED_OS_FAMILIES:
        raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)
    if event.architecture not in _APPROVED_ARCHITECTURES:
        raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)
    if not is_safe_cli_version(event.cli_version):
        raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)
    if not is_safe_runtime_version(event.runtime_version):
        raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)
    if not is_safe_release_adoption(event.release_adoption):
        raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)

    projected = project_runtime_analytics_event(event, policy=active)
    # AnalyticsEvent side remains subject to Slice 10.1 contract (no installation_id).
    validate_analytics_event(event.to_analytics_event())
    # Analytics persistence/transmission remain blocked by Slice 10.1 policy.
    assert_persistence_blocked()
    assert_transmission_blocked()
    if active.persistence_enabled or active.transmission_enabled:
        raise AnalyticsError(AnalyticsErrorCode.TRANSMISSION_DISABLED)
    return projected


def validate_runtime_analytics_mapping(
    payload: dict[str, Any],
    *,
    policy: CommunityRuntimeAnalyticsPolicy | None = None,
) -> RuntimeAnalyticsProjection:
    required = (
        "installation_id",
        "cli_version",
        "os_family",
        "architecture",
        "runtime_version",
        "release_adoption",
        "event_type",
        "category",
        "privacy_projection_applied",
        "schema_version",
        "policy_version",
    )
    for key in required:
        if key not in payload:
            raise AnalyticsError(AnalyticsErrorCode.VALIDATION_FAILED)

    event = RuntimeAnalyticsEvent(
        installation_id=str(payload["installation_id"]),
        cli_version=str(payload["cli_version"]),
        os_family=str(payload["os_family"]),
        architecture=str(payload["architecture"]),
        runtime_version=str(payload["runtime_version"]),
        release_adoption=str(payload["release_adoption"]),
        event_type=str(payload.get("event_type", "analytics_runtime_collected")),
        category=str(payload.get("category", "runtime")),
        client_name=str(payload.get("client_name", "codestrata_cli")),
        lifecycle=str(payload.get("lifecycle", "projected")),
        schema_version=str(
            payload.get("schema_version", COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_VERSION)
        ),
        policy_version=str(
            payload.get("policy_version", COMMUNITY_RUNTIME_ANALYTICS_POLICY_VERSION)
        ),
        analytics_schema_version=str(
            payload.get("analytics_schema_version", "1.0")
        ),
        analytics_policy_version=str(
            payload.get("analytics_policy_version", "1.0")
        ),
        privacy_projection_applied=bool(payload["privacy_projection_applied"]),
        offline_mode=bool(payload.get("offline_mode", True)),
        operation_category=str(payload.get("operation_category", "runtime")),
        result=str(payload.get("result", "success")),
    )
    return validate_runtime_analytics_event(event, policy=policy)


__all__ = [
    "validate_runtime_analytics_event",
    "validate_runtime_analytics_mapping",
]
