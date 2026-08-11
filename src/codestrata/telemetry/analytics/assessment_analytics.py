"""Anonymous assessment analytics model and local construction (Epic 10 Slice 10.4).

Construction-API only — not wired into the CLI assess product path. Does not
transmit. Does not persist analytics payloads. May ensure anonymous installation
identity only when an explicit construction API is invoked.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codestrata.reporting.html_v2.assessment_heads import AssessmentHead
from codestrata.telemetry.analytics.assessment_analytics_policy import (
    COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_VERSION,
    COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_VERSION,
    CommunityAssessmentAnalyticsPolicy,
    default_assessment_analytics_policy,
)
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import (
    AnalyticsCategory,
    AnalyticsEvent,
    AnalyticsLifecycle,
    _APPROVED_ASSESSMENT_HEADS,
    _APPROVED_DURATION_BUCKETS,
    _APPROVED_FAILURE_CATEGORIES,
)
from codestrata.telemetry.analytics.installation_identity import (
    AnonymousInstallationIdentity,
    ensure_anonymous_installation_identity,
    is_uuid_v4,
)
from codestrata.telemetry.analytics.policy import (
    COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION,
    COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION,
)

ASSESSMENT_ANALYTICS_EVENT_TYPE = "analytics_assessment_collected"

APPROVED_COMMAND_CATEGORIES: frozenset[str] = frozenset({"assess"})
APPROVED_OUTCOMES: frozenset[str] = frozenset({"success", "failure", "cancelled"})

# Authoritative coarse buckets aligned with telemetry DurationBucket + analytics unknown.
# Thresholds are inclusive upper bounds in milliseconds (except gt_5m).
DURATION_BUCKET_THRESHOLDS_MS: tuple[tuple[str, int | None], ...] = (
    ("lt_1s", 1_000),
    ("s_1_10", 10_000),
    ("s_10_60", 60_000),
    ("m_1_5", 300_000),
    ("gt_5m", None),
)


def classify_duration_bucket_ms(duration_ms: float | int | None) -> str:
    """Map elapsed milliseconds to the approved analytics duration vocabulary.

    Does not invent a second vocabulary — aligns with ``DurationBucket`` names
    plus analytics ``unknown`` when duration is unavailable.
    """

    if duration_ms is None:
        return "unknown"
    try:
        value = float(duration_ms)
    except (TypeError, ValueError):
        return "unknown"
    if value < 0 or value != value:  # NaN
        return "unknown"
    for name, upper in DURATION_BUCKET_THRESHOLDS_MS:
        if upper is None:
            return name
        if value < upper:
            return name
    return "gt_5m"


def normalize_enabled_assessment_heads(
    heads: tuple[str, ...] | list[str] | None,
    *,
    max_heads: int,
) -> tuple[str, ...]:
    if heads is None:
        return ()
    if len(heads) > max_heads:
        raise AnalyticsError(AnalyticsErrorCode.TOO_MANY_HEADS)
    normalized: list[str] = []
    seen: set[str] = set()
    for head in heads:
        if not isinstance(head, str) or head not in _APPROVED_ASSESSMENT_HEADS:
            raise AnalyticsError(AnalyticsErrorCode.INVALID_HEAD)
        if head not in seen:
            seen.add(head)
            normalized.append(head)
    return tuple(sorted(normalized))


def canonical_assessment_head_vocabulary() -> frozenset[str]:
    """Return the reporting AssessmentHead registry values."""

    return frozenset(item.value for item in AssessmentHead)


@dataclass(frozen=True, slots=True)
class AssessmentAnalyticsEvent:
    """Local assessment analytics record (category=assessment).

    ``installation_id`` is the only identifier. Enabled heads mean
    selected/configured before execution (not necessarily executed).
    """

    installation_id: str
    command_category: str
    duration_bucket: str
    outcome: str
    enabled_assessment_heads: tuple[str, ...]
    offline_mode: bool = True
    ai_requested: bool = False
    ai_used: bool = False
    failure_category: str | None = None
    event_type: str = ASSESSMENT_ANALYTICS_EVENT_TYPE
    category: str = AnalyticsCategory.ASSESSMENT.value
    client_name: str = "codestrata_cli"
    lifecycle: str = AnalyticsLifecycle.PROJECTED.value
    schema_version: str = COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_VERSION
    policy_version: str = COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_VERSION
    analytics_schema_version: str = COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION
    analytics_policy_version: str = COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION
    privacy_projection_applied: bool = True
    operation_category: str = "assess"

    def to_stable_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ai_requested": self.ai_requested,
            "ai_used": self.ai_used,
            "analytics_policy_version": self.analytics_policy_version,
            "analytics_schema_version": self.analytics_schema_version,
            "category": self.category,
            "client_name": self.client_name,
            "command_category": self.command_category,
            "duration_bucket": self.duration_bucket,
            "enabled_assessment_heads": list(self.enabled_assessment_heads),
            "event_type": self.event_type,
            "installation_id": self.installation_id,
            "lifecycle": self.lifecycle,
            "offline_mode": self.offline_mode,
            "operation_category": self.operation_category,
            "outcome": self.outcome,
            "policy_version": self.policy_version,
            "privacy_projection_applied": self.privacy_projection_applied,
            "schema_version": self.schema_version,
        }
        if self.failure_category is not None:
            payload["failure_category"] = self.failure_category
        return {key: payload[key] for key in sorted(payload)}

    def to_analytics_event(self) -> AnalyticsEvent:
        """Produce the Slice 10.1 AnalyticsEvent (no installation_id field)."""

        return AnalyticsEvent(
            event_type=self.event_type,
            category=AnalyticsCategory.ASSESSMENT,
            client_name=self.client_name,
            lifecycle=AnalyticsLifecycle(self.lifecycle),
            schema_version=self.analytics_schema_version,
            policy_version=self.analytics_policy_version,
            privacy_projection_applied=self.privacy_projection_applied,
            offline_mode=self.offline_mode,
            ai_used=self.ai_used,
            ai_requested=self.ai_requested,
            operation_category=self.operation_category,
            result=self.outcome,
            duration_bucket=self.duration_bucket,
            enabled_assessment_heads=self.enabled_assessment_heads,
            failure_category=self.failure_category,
        )


def build_assessment_analytics_event(
    *,
    identity: AnonymousInstallationIdentity,
    command_category: str = "assess",
    duration_bucket: str,
    outcome: str,
    enabled_assessment_heads: tuple[str, ...] | list[str] | None = (),
    offline_mode: bool = True,
    ai_requested: bool = False,
    ai_used: bool = False,
    failure_category: str | None = None,
    privacy_projection_applied: bool = True,
    policy: CommunityAssessmentAnalyticsPolicy | None = None,
) -> AssessmentAnalyticsEvent:
    active = policy or default_assessment_analytics_policy()
    heads = normalize_enabled_assessment_heads(
        enabled_assessment_heads, max_heads=active.max_enabled_heads
    )
    return AssessmentAnalyticsEvent(
        installation_id=identity.installation_id,
        command_category=command_category,
        duration_bucket=duration_bucket,
        outcome=outcome,
        enabled_assessment_heads=heads,
        offline_mode=offline_mode,
        ai_requested=ai_requested,
        ai_used=ai_used,
        failure_category=failure_category,
        privacy_projection_applied=privacy_projection_applied,
    )


def collect_assessment_analytics(
    *,
    home: Path | None = None,
    identity: AnonymousInstallationIdentity | None = None,
    command_category: str = "assess",
    duration_ms: float | int | None = None,
    duration_bucket: str | None = None,
    outcome: str,
    enabled_assessment_heads: tuple[str, ...] | list[str] | None = (),
    offline_mode: bool = True,
    ai_requested: bool = False,
    ai_used: bool = False,
    failure_category: str | None = None,
    clock_ms: Callable[[], float] | None = None,
    policy: CommunityAssessmentAnalyticsPolicy | None = None,
) -> AssessmentAnalyticsEvent:
    """Locally construct an assessment analytics event (no transmit / no persist).

    Not wired into the assess CLI product path. Identity ensure runs only when
    this explicit construction API is invoked without a provided identity.
    ``clock_ms`` is reserved for injected monotonic clocks in tests; duration is
    supplied via ``duration_ms`` / ``duration_bucket`` from the caller.
    """

    from codestrata.telemetry.analytics.assessment_analytics_projection import (
        project_assessment_analytics_event,
    )
    from codestrata.telemetry.analytics.assessment_analytics_validation import (
        validate_assessment_analytics_event,
    )

    active = policy or default_assessment_analytics_policy()
    active.validate()

    if identity is None:
        try:
            identity, _, _ = ensure_anonymous_installation_identity(home=home)
        except Exception as error:  # noqa: BLE001 — bounded remapping only
            raise AnalyticsError(AnalyticsErrorCode.IDENTITY_UNAVAILABLE) from error
    if not is_uuid_v4(identity.installation_id):
        raise AnalyticsError(AnalyticsErrorCode.IDENTITY_UNAVAILABLE)

    # Injected clock seam: available for future elapsed measurement helpers.
    if clock_ms is not None and duration_ms is None and duration_bucket is None:
        try:
            _ = float(clock_ms())
        except Exception as error:  # noqa: BLE001
            raise AnalyticsError(AnalyticsErrorCode.INVALID_DURATION_BUCKET) from error

    bucket = (
        duration_bucket
        if duration_bucket is not None
        else classify_duration_bucket_ms(duration_ms)
    )
    if bucket not in _APPROVED_DURATION_BUCKETS:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_DURATION_BUCKET)
    if command_category not in APPROVED_COMMAND_CATEGORIES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_COMMAND_CATEGORY)
    if outcome not in APPROVED_OUTCOMES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_OUTCOME)
    if failure_category is not None and failure_category not in _APPROVED_FAILURE_CATEGORIES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_FAILURE_CATEGORY)

    event = build_assessment_analytics_event(
        identity=identity,
        command_category=command_category,
        duration_bucket=bucket,
        outcome=outcome,
        enabled_assessment_heads=enabled_assessment_heads,
        offline_mode=offline_mode,
        ai_requested=ai_requested,
        ai_used=ai_used,
        failure_category=failure_category,
        privacy_projection_applied=True,
        policy=active,
    )
    projected = project_assessment_analytics_event(event, policy=active)
    validate_assessment_analytics_event(event, policy=active)
    _ = projected
    return event


__all__ = [
    "APPROVED_COMMAND_CATEGORIES",
    "APPROVED_OUTCOMES",
    "ASSESSMENT_ANALYTICS_EVENT_TYPE",
    "DURATION_BUCKET_THRESHOLDS_MS",
    "AssessmentAnalyticsEvent",
    "build_assessment_analytics_event",
    "canonical_assessment_head_vocabulary",
    "classify_duration_bucket_ms",
    "collect_assessment_analytics",
    "normalize_enabled_assessment_heads",
]
