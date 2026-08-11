"""Independent Community anonymous analytics policy (Epic 10 Slice 10.1).

Contract-only. Independent from telemetry runtime policy, Community Cloud,
Data Lake, and installation-identity policy. Does not enable collection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_ID = "community-anonymous-analytics-policy"
COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION = "1.0"
COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_URN = (
    f"{COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_ID}:"
    f"{COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION}"
)

COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_ID = "community-anonymous-analytics-schema"
COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION = "1.0"
COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_URN = (
    f"{COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_ID}:"
    f"{COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION}"
)

DEFAULT_MAX_EVENT_SIZE_BYTES = 4096
DEFAULT_MAX_PROPERTY_COUNT = 32
DEFAULT_MAX_STRING_LENGTH = 64

_REVIEW_STATUS = "contract_only_no_collection_no_transmission"

_LIMITATIONS: tuple[str, ...] = (
    "contract_only",
    "no_collection_in_slice_10_1",
    "no_persistence_in_slice_10_1",
    "no_transmission_in_slice_10_1",
    "installation_identity_not_in_base_analytics_events",
    "runtime_analytics_local_envelope_may_include_installation_id",
    "no_http_endpoint",
    "no_telemetry_transport_modification",
    "no_telemetry_consent_modification",
    "requires_prior_privacy_projection",
    "community_cloud_mapping_deferred",
    "data_lake_mapping_deferred",
    "vscode_collection_deferred",
    "fail_silent_required_when_activated",
)


class AnalyticsPolicyError(ValueError):
    """Raised when analytics-policy invariants fail."""


@dataclass(frozen=True, slots=True)
class CommunityAnonymousAnalyticsPolicy:
    """Deterministic, versioned anonymous analytics product-policy contract."""

    policy_id: str = COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_ID
    policy_version: str = COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION
    schema_id: str = COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_ID
    schema_version: str = COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION
    collection_enabled: bool = False
    persistence_enabled: bool = False
    transmission_enabled: bool = False
    installation_id_allowed: bool = False
    requires_prior_privacy_projection: bool = True
    requires_validation_before_persistence: bool = True
    requires_validation_before_transmission: bool = True
    independent_from_telemetry_runtime_policy: bool = True
    independent_from_telemetry_event_schema: bool = True
    fail_silent: bool = True
    max_event_size_bytes: int = DEFAULT_MAX_EVENT_SIZE_BYTES
    max_property_count: int = DEFAULT_MAX_PROPERTY_COUNT
    max_string_length: int = DEFAULT_MAX_STRING_LENGTH
    review_status: str = _REVIEW_STATUS
    limitations: tuple[str, ...] = _LIMITATIONS

    def __post_init__(self) -> None:
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        self.validate()

    @property
    def policy_token(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    @property
    def schema_token(self) -> str:
        return f"{self.schema_id}:{self.schema_version}"

    def validate(self) -> None:
        if self.policy_id != COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_ID:
            raise AnalyticsPolicyError("unsupported analytics policy id")
        if self.policy_version != COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION:
            raise AnalyticsPolicyError("unsupported analytics policy version")
        if self.schema_id != COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_ID:
            raise AnalyticsPolicyError("unsupported analytics schema id")
        if self.schema_version != COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION:
            raise AnalyticsPolicyError("unsupported analytics schema version")
        if self.review_status != _REVIEW_STATUS:
            raise AnalyticsPolicyError("unsupported analytics review_status")
        if self.collection_enabled:
            raise AnalyticsPolicyError("collection_enabled must be false in Slice 10.1")
        if self.persistence_enabled:
            raise AnalyticsPolicyError("persistence_enabled must be false in Slice 10.1")
        if self.transmission_enabled:
            raise AnalyticsPolicyError("transmission_enabled must be false in Slice 10.1")
        if self.installation_id_allowed:
            raise AnalyticsPolicyError("installation_id_allowed must be false")
        if not self.requires_prior_privacy_projection:
            raise AnalyticsPolicyError("requires_prior_privacy_projection must be true")
        if not self.requires_validation_before_persistence:
            raise AnalyticsPolicyError(
                "requires_validation_before_persistence must be true"
            )
        if not self.requires_validation_before_transmission:
            raise AnalyticsPolicyError(
                "requires_validation_before_transmission must be true"
            )
        if not self.independent_from_telemetry_runtime_policy:
            raise AnalyticsPolicyError(
                "independent_from_telemetry_runtime_policy must be true"
            )
        if not self.independent_from_telemetry_event_schema:
            raise AnalyticsPolicyError(
                "independent_from_telemetry_event_schema must be true"
            )
        if not self.fail_silent:
            raise AnalyticsPolicyError("fail_silent must be true")
        if self.max_event_size_bytes <= 0 or self.max_property_count <= 0:
            raise AnalyticsPolicyError("size limits must be positive")
        if self.max_string_length <= 0:
            raise AnalyticsPolicyError("max_string_length must be positive")

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "collection_enabled": self.collection_enabled,
            "fail_silent": self.fail_silent,
            "independent_from_telemetry_event_schema": (
                self.independent_from_telemetry_event_schema
            ),
            "independent_from_telemetry_runtime_policy": (
                self.independent_from_telemetry_runtime_policy
            ),
            "installation_id_allowed": self.installation_id_allowed,
            "limitations": list(self.limitations),
            "max_event_size_bytes": self.max_event_size_bytes,
            "max_property_count": self.max_property_count,
            "max_string_length": self.max_string_length,
            "persistence_enabled": self.persistence_enabled,
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "requires_prior_privacy_projection": self.requires_prior_privacy_projection,
            "requires_validation_before_persistence": (
                self.requires_validation_before_persistence
            ),
            "requires_validation_before_transmission": (
                self.requires_validation_before_transmission
            ),
            "review_status": self.review_status,
            "schema_id": self.schema_id,
            "schema_token": self.schema_token,
            "schema_version": self.schema_version,
            "transmission_enabled": self.transmission_enabled,
        }

    @classmethod
    def default(cls) -> CommunityAnonymousAnalyticsPolicy:
        return cls()


def default_analytics_policy() -> CommunityAnonymousAnalyticsPolicy:
    return CommunityAnonymousAnalyticsPolicy.default()


__all__ = [
    "COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_ID",
    "COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_URN",
    "COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION",
    "COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_ID",
    "COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_URN",
    "COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION",
    "AnalyticsPolicyError",
    "CommunityAnonymousAnalyticsPolicy",
    "default_analytics_policy",
]
