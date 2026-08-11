"""Analytics contract validation (Epic 10 Slice 10.1).

Validation is mandatory before any future persistence or transmission.
Slice 10.1 does not collect, persist, or transmit.
"""

from __future__ import annotations

from typing import Any

from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import AnalyticsEvent
from codestrata.telemetry.analytics.policy import (
    CommunityAnonymousAnalyticsPolicy,
    default_analytics_policy,
)
from codestrata.telemetry.analytics.projection import (
    AnalyticsProjection,
    project_analytics_event,
    project_analytics_from_mapping,
)


def validate_analytics_event(
    event: AnalyticsEvent,
    *,
    policy: CommunityAnonymousAnalyticsPolicy | None = None,
) -> AnalyticsProjection:
    """Validate a typed analytics event against the contract."""

    active = policy or default_analytics_policy()
    active.validate()
    projected = project_analytics_event(event, policy=active)
    return _assert_contract_invariants(projected, policy=active)


def validate_analytics_mapping(
    payload: dict[str, Any],
    *,
    policy: CommunityAnonymousAnalyticsPolicy | None = None,
) -> AnalyticsProjection:
    """Validate an untrusted mapping against the analytics contract."""

    active = policy or default_analytics_policy()
    active.validate()
    projected = project_analytics_from_mapping(payload, policy=active)
    return _assert_contract_invariants(projected, policy=active)


def _assert_contract_invariants(
    projected: AnalyticsProjection,
    *,
    policy: CommunityAnonymousAnalyticsPolicy,
) -> AnalyticsProjection:
    if projected.fields.get("privacy_projection_applied") is not True:
        raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REQUIRED)
    if policy.installation_id_allowed:
        raise AnalyticsError(AnalyticsErrorCode.UNSAFE_FIELD)
    # Slice 10.1: collection/persistence/transmission remain disabled by policy.
    if policy.collection_enabled:
        raise AnalyticsError(AnalyticsErrorCode.COLLECTION_DISABLED)
    if policy.persistence_enabled:
        raise AnalyticsError(AnalyticsErrorCode.PERSISTENCE_DISABLED)
    if policy.transmission_enabled:
        raise AnalyticsError(AnalyticsErrorCode.TRANSMISSION_DISABLED)
    return projected


def assert_persistence_blocked(
    policy: CommunityAnonymousAnalyticsPolicy | None = None,
) -> None:
    """Confirm persistence remains blocked under the active policy."""

    active = policy or default_analytics_policy()
    if active.persistence_enabled:
        raise AnalyticsError(AnalyticsErrorCode.PERSISTENCE_DISABLED)
    if not active.requires_validation_before_persistence:
        raise AnalyticsError(AnalyticsErrorCode.VALIDATION_FAILED)


def assert_transmission_blocked(
    policy: CommunityAnonymousAnalyticsPolicy | None = None,
) -> None:
    """Confirm transmission remains blocked under the active policy."""

    active = policy or default_analytics_policy()
    if active.transmission_enabled:
        raise AnalyticsError(AnalyticsErrorCode.TRANSMISSION_DISABLED)
    if not active.requires_validation_before_transmission:
        raise AnalyticsError(AnalyticsErrorCode.VALIDATION_FAILED)


def assert_collection_blocked(
    policy: CommunityAnonymousAnalyticsPolicy | None = None,
) -> None:
    """Confirm collection remains blocked under the active policy."""

    active = policy or default_analytics_policy()
    if active.collection_enabled:
        raise AnalyticsError(AnalyticsErrorCode.COLLECTION_DISABLED)


__all__ = [
    "assert_collection_blocked",
    "assert_persistence_blocked",
    "assert_transmission_blocked",
    "validate_analytics_event",
    "validate_analytics_mapping",
]
