"""Independent repository aggregate analytics policy (Epic 10 Slice 10.5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.analytics.policy import (
    COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION,
    COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION,
)

COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_ID = (
    "community-repository-aggregate-analytics-policy"
)
COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_VERSION = "1.0"
COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_URN = (
    f"{COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_ID}:"
    f"{COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_VERSION}"
)

COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_ID = (
    "community-repository-aggregate-analytics-schema"
)
COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_VERSION = "1.0"
COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_URN = (
    f"{COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_ID}:"
    f"{COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_VERSION}"
)

# Bounded exact counts (backlog: aggregated counts). Overflow rejects.
DEFAULT_MAX_LANGUAGE_FILE_COUNT = 10_000
DEFAULT_MAX_RULE_EXECUTION_COUNT = 10_000
DEFAULT_MAX_LANGUAGE_GROUPS = 6
DEFAULT_MAX_HEAD_RULE_GROUPS = 9

_REVIEW_STATUS = (
    "local_construction_only_no_transmission_no_analytics_persistence_unwired"
)

_LIMITATIONS: tuple[str, ...] = (
    "repository_aggregates_category_only",
    "local_construction_only",
    "no_transmission",
    "no_analytics_persistence",
    "installation_identity_only_identifier",
    "requires_prior_privacy_projection",
    "not_wired_into_cli_product_path",
    "bounded_exact_language_file_counts",
    "zero_count_language_groups_omitted",
    "no_repository_identity",
    "no_file_identity",
    "no_rule_identity",
    "no_findings_evidence_recommendations",
    "no_source_content",
    "no_ai_provider_model_analytics",
    "language_count_means_assessed_source_files",
    "rule_completion_not_finding_produced",
    "fingerprinting_limitation_of_aggregate_shape",
    "fail_silent_optional_integration",
    "ai_analytics_owned_by_slice_10_6",
    "no_telemetry_transport_modification",
    "no_telemetry_consent_modification",
    "community_cloud_deferred",
    "data_lake_deferred",
)


class RepositoryAggregateAnalyticsPolicyError(ValueError):
    """Raised when repository-aggregate policy invariants fail."""


@dataclass(frozen=True, slots=True)
class CommunityRepositoryAggregateAnalyticsPolicy:
    """Independent policy for local repository aggregate analytics construction."""

    policy_id: str = COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_ID
    policy_version: str = COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_VERSION
    schema_id: str = COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_ID
    schema_version: str = COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_VERSION
    analytics_schema_version: str = COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION
    analytics_policy_version: str = COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION
    local_collection_allowed: bool = True
    persistence_enabled: bool = False
    transmission_enabled: bool = False
    installation_id_required: bool = True
    installation_id_only_identifier: bool = True
    requires_prior_privacy_projection: bool = True
    category_repository_aggregates_only: bool = True
    bounded_exact_counts: bool = True
    max_language_file_count: int = DEFAULT_MAX_LANGUAGE_FILE_COUNT
    max_rule_execution_count: int = DEFAULT_MAX_RULE_EXECUTION_COUNT
    max_language_groups: int = DEFAULT_MAX_LANGUAGE_GROUPS
    max_head_rule_groups: int = DEFAULT_MAX_HEAD_RULE_GROUPS
    omit_zero_language_counts: bool = True
    fail_silent_optional_integration: bool = True
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
        if self.policy_id != COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_ID:
            raise RepositoryAggregateAnalyticsPolicyError("unsupported policy id")
        if self.policy_version != COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_VERSION:
            raise RepositoryAggregateAnalyticsPolicyError("unsupported policy version")
        if self.schema_id != COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_ID:
            raise RepositoryAggregateAnalyticsPolicyError("unsupported schema id")
        if self.schema_version != COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_VERSION:
            raise RepositoryAggregateAnalyticsPolicyError("unsupported schema version")
        if self.review_status != _REVIEW_STATUS:
            raise RepositoryAggregateAnalyticsPolicyError("unsupported review_status")
        if not self.local_collection_allowed:
            raise RepositoryAggregateAnalyticsPolicyError(
                "local_collection_allowed must be true"
            )
        if self.persistence_enabled:
            raise RepositoryAggregateAnalyticsPolicyError(
                "persistence_enabled must be false"
            )
        if self.transmission_enabled:
            raise RepositoryAggregateAnalyticsPolicyError(
                "transmission_enabled must be false"
            )
        if not self.installation_id_required:
            raise RepositoryAggregateAnalyticsPolicyError(
                "installation_id_required must be true"
            )
        if not self.installation_id_only_identifier:
            raise RepositoryAggregateAnalyticsPolicyError(
                "installation_id_only_identifier must be true"
            )
        if not self.requires_prior_privacy_projection:
            raise RepositoryAggregateAnalyticsPolicyError(
                "requires_prior_privacy_projection must be true"
            )
        if not self.category_repository_aggregates_only:
            raise RepositoryAggregateAnalyticsPolicyError(
                "category_repository_aggregates_only must be true"
            )
        if not self.bounded_exact_counts:
            raise RepositoryAggregateAnalyticsPolicyError(
                "bounded_exact_counts must be true"
            )
        if self.max_language_file_count <= 0 or self.max_rule_execution_count <= 0:
            raise RepositoryAggregateAnalyticsPolicyError("count maxima must be positive")
        if not self.fail_silent_optional_integration:
            raise RepositoryAggregateAnalyticsPolicyError(
                "fail_silent_optional_integration must be true"
            )

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "analytics_policy_version": self.analytics_policy_version,
            "analytics_schema_version": self.analytics_schema_version,
            "bounded_exact_counts": self.bounded_exact_counts,
            "category_repository_aggregates_only": (
                self.category_repository_aggregates_only
            ),
            "fail_silent_optional_integration": self.fail_silent_optional_integration,
            "installation_id_only_identifier": self.installation_id_only_identifier,
            "installation_id_required": self.installation_id_required,
            "limitations": list(self.limitations),
            "local_collection_allowed": self.local_collection_allowed,
            "max_head_rule_groups": self.max_head_rule_groups,
            "max_language_file_count": self.max_language_file_count,
            "max_language_groups": self.max_language_groups,
            "max_rule_execution_count": self.max_rule_execution_count,
            "omit_zero_language_counts": self.omit_zero_language_counts,
            "persistence_enabled": self.persistence_enabled,
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "requires_prior_privacy_projection": self.requires_prior_privacy_projection,
            "review_status": self.review_status,
            "schema_id": self.schema_id,
            "schema_token": self.schema_token,
            "schema_version": self.schema_version,
            "transmission_enabled": self.transmission_enabled,
        }

    @classmethod
    def default(cls) -> CommunityRepositoryAggregateAnalyticsPolicy:
        return cls()


def default_repository_aggregate_analytics_policy() -> (
    CommunityRepositoryAggregateAnalyticsPolicy
):
    return CommunityRepositoryAggregateAnalyticsPolicy.default()


__all__ = [
    "COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_ID",
    "COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_URN",
    "COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_VERSION",
    "COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_ID",
    "COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_URN",
    "COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_VERSION",
    "DEFAULT_MAX_HEAD_RULE_GROUPS",
    "DEFAULT_MAX_LANGUAGE_FILE_COUNT",
    "DEFAULT_MAX_LANGUAGE_GROUPS",
    "DEFAULT_MAX_RULE_EXECUTION_COUNT",
    "CommunityRepositoryAggregateAnalyticsPolicy",
    "RepositoryAggregateAnalyticsPolicyError",
    "default_repository_aggregate_analytics_policy",
]
