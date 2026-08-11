"""Runtime analytics projection (Epic 10 Slice 10.3).

Requires prior privacy projection. Produces an allowlisted local payload and a
Slice 10.1 AnalyticsEvent(category=runtime). Never transmits.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import (
    FORBIDDEN_ANALYTICS_FIELD_NAMES,
    AnalyticsEvent,
)
from codestrata.telemetry.analytics.installation_identity import is_uuid_v4
from codestrata.telemetry.analytics.projection import project_analytics_event
from codestrata.telemetry.analytics.runtime_analytics import (
    CommunityRuntimeAnalyticsPolicy,
    RuntimeAnalyticsEvent,
    default_runtime_analytics_policy,
    is_safe_cli_version,
    is_safe_release_adoption,
    is_safe_runtime_version,
)
from codestrata.telemetry.privacy import looks_like_path_or_secret_value

# Fields allowed on the runtime analytics envelope (includes installation_id).
APPROVED_RUNTIME_ANALYTICS_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "analytics_policy_version",
        "analytics_schema_version",
        "architecture",
        "category",
        "cli_version",
        "client_name",
        "event_type",
        "installation_id",
        "lifecycle",
        "offline_mode",
        "operation_category",
        "os_family",
        "policy_version",
        "privacy_projection_applied",
        "release_adoption",
        "result",
        "runtime_version",
        "schema_version",
    }
)

_FORBIDDEN_RUNTIME_IDENTIFIERS: frozenset[str] = frozenset(
    {
        "username",
        "email",
        "hostname",
        "host",
        "ip",
        "ip_address",
        "machine_id",
        "mac",
        "mac_address",
        "customer_id",
        "organization_id",
        "repository",
        "repository_name",
        "project",
        "project_name",
        "path",
        "argv",
        "command_line",
        "environment",
        "env",
    }
)


@dataclass(frozen=True, slots=True)
class RuntimeAnalyticsProjection:
    """Allowlisted runtime analytics payload (local only)."""

    fields: dict[str, Any]

    def to_stable_dict(self) -> dict[str, Any]:
        return {key: self.fields[key] for key in sorted(self.fields)}

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )

    @property
    def installation_id(self) -> str:
        value = self.fields["installation_id"]
        assert isinstance(value, str)
        return value


def _assert_privacy_envelope(payload: dict[str, Any]) -> None:
    for key in payload:
        if key in FORBIDDEN_ANALYTICS_FIELD_NAMES and key != "installation_id":
            raise AnalyticsError(AnalyticsErrorCode.UNSAFE_FIELD)
        if key in _FORBIDDEN_RUNTIME_IDENTIFIERS:
            raise AnalyticsError(AnalyticsErrorCode.UNSAFE_FIELD)
        if key not in APPROVED_RUNTIME_ANALYTICS_FIELD_NAMES:
            raise AnalyticsError(AnalyticsErrorCode.UNKNOWN_FIELD)
    if payload.get("privacy_projection_applied") is not True:
        raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REQUIRED)


def project_runtime_analytics_event(
    event: RuntimeAnalyticsEvent,
    *,
    policy: CommunityRuntimeAnalyticsPolicy | None = None,
) -> RuntimeAnalyticsProjection:
    active = policy or default_runtime_analytics_policy()
    active.validate()
    if not event.privacy_projection_applied:
        raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REQUIRED)
    if active.requires_prior_privacy_projection and not event.privacy_projection_applied:
        raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REQUIRED)

    payload = event.to_stable_dict()
    _assert_privacy_envelope(payload)

    if not is_uuid_v4(str(payload["installation_id"])):
        raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)
    if payload["category"] != "runtime":
        raise AnalyticsError(AnalyticsErrorCode.UNKNOWN_CATEGORY)
    if not is_safe_cli_version(str(payload["cli_version"])):
        raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)
    if not is_safe_runtime_version(str(payload["runtime_version"])):
        raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)
    if not is_safe_release_adoption(str(payload["release_adoption"])):
        raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)

    for key in ("cli_version", "runtime_version", "release_adoption", "event_type"):
        value = payload[key]
        if isinstance(value, str) and looks_like_path_or_secret_value(value):
            raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)

    # Also project the Slice 10.1 analytics event (without installation_id).
    analytics_event = event.to_analytics_event()
    project_analytics_event(analytics_event)

    return RuntimeAnalyticsProjection(
        fields={key: payload[key] for key in sorted(payload)}
    )


def project_runtime_analytics_to_analytics_event(
    event: RuntimeAnalyticsEvent,
) -> AnalyticsEvent:
    if not event.privacy_projection_applied:
        raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REQUIRED)
    analytics_event = event.to_analytics_event()
    project_analytics_event(analytics_event)
    return analytics_event


__all__ = [
    "APPROVED_RUNTIME_ANALYTICS_FIELD_NAMES",
    "RuntimeAnalyticsProjection",
    "project_runtime_analytics_event",
    "project_runtime_analytics_to_analytics_event",
]
