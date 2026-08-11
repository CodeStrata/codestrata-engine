"""Independent assessment analytics policy (Epic 10 Slice 10.4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.analytics.policy import (
    COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION,
    COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION,
)

COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_ID = "community-assessment-analytics-policy"
COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_VERSION = "1.0"
COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_URN = (
    f"{COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_ID}:"
    f"{COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_VERSION}"
)

COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_ID = "community-assessment-analytics-schema"
COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_VERSION = "1.0"
COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_URN = (
    f"{COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_ID}:"
    f"{COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_VERSION}"
)

DEFAULT_MAX_ENABLED_HEADS = 9

_REVIEW_STATUS = (
    "local_construction_only_no_transmission_no_analytics_persistence_unwired"
)

_LIMITATIONS: tuple[str, ...] = (
    "assessment_category_only",
    "local_construction_only",
    "no_transmission",
    "no_analytics_persistence",
    "installation_identity_only_identifier",
    "requires_prior_privacy_projection",
    "not_wired_into_cli_product_path",
    "command_category_assess_only",
    "coarse_duration_buckets_only",
    "no_exact_duration",
    "no_repository_derived_identity",
    "no_findings_evidence_recommendations",
    "no_file_rule_finding_counts",
    "no_ai_provider_model_analytics",
    "canonical_assessment_heads_only",
    "enabled_means_selected_configured",
    "fail_silent_optional_integration",
    "repository_aggregates_deferred_to_slice_10_5",
    "repository_aggregates_available_as_construction_api_in_slice_10_5",
    "no_telemetry_transport_modification",
    "no_telemetry_consent_modification",
    "community_cloud_deferred",
    "data_lake_deferred",
)


class AssessmentAnalyticsPolicyError(ValueError):
    """Raised when assessment-analytics policy invariants fail."""


@dataclass(frozen=True, slots=True)
class CommunityAssessmentAnalyticsPolicy:
    """Independent policy for local assessment analytics construction."""

    policy_id: str = COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_ID
    policy_version: str = COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_VERSION
    schema_id: str = COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_ID
    schema_version: str = COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_VERSION
    analytics_schema_version: str = COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION
    analytics_policy_version: str = COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION
    local_collection_allowed: bool = True
    persistence_enabled: bool = False
    transmission_enabled: bool = False
    installation_id_required: bool = True
    installation_id_only_identifier: bool = True
    requires_prior_privacy_projection: bool = True
    category_assessment_only: bool = True
    command_category_assess_only: bool = True
    coarse_duration_buckets_only: bool = True
    exact_duration_forbidden: bool = True
    failure_category_required_on_failure: bool = True
    failure_category_forbidden_on_success: bool = True
    max_enabled_heads: int = DEFAULT_MAX_ENABLED_HEADS
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
        if self.policy_id != COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_ID:
            raise AssessmentAnalyticsPolicyError(
                "unsupported assessment analytics policy id"
            )
        if self.policy_version != COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_VERSION:
            raise AssessmentAnalyticsPolicyError(
                "unsupported assessment analytics policy version"
            )
        if self.schema_id != COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_ID:
            raise AssessmentAnalyticsPolicyError(
                "unsupported assessment analytics schema id"
            )
        if self.schema_version != COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_VERSION:
            raise AssessmentAnalyticsPolicyError(
                "unsupported assessment analytics schema version"
            )
        if self.review_status != _REVIEW_STATUS:
            raise AssessmentAnalyticsPolicyError(
                "unsupported assessment analytics review_status"
            )
        if not self.local_collection_allowed:
            raise AssessmentAnalyticsPolicyError("local_collection_allowed must be true")
        if self.persistence_enabled:
            raise AssessmentAnalyticsPolicyError("persistence_enabled must be false")
        if self.transmission_enabled:
            raise AssessmentAnalyticsPolicyError("transmission_enabled must be false")
        if not self.installation_id_required:
            raise AssessmentAnalyticsPolicyError("installation_id_required must be true")
        if not self.installation_id_only_identifier:
            raise AssessmentAnalyticsPolicyError(
                "installation_id_only_identifier must be true"
            )
        if not self.requires_prior_privacy_projection:
            raise AssessmentAnalyticsPolicyError(
                "requires_prior_privacy_projection must be true"
            )
        if not self.category_assessment_only:
            raise AssessmentAnalyticsPolicyError("category_assessment_only must be true")
        if not self.command_category_assess_only:
            raise AssessmentAnalyticsPolicyError(
                "command_category_assess_only must be true"
            )
        if not self.coarse_duration_buckets_only:
            raise AssessmentAnalyticsPolicyError(
                "coarse_duration_buckets_only must be true"
            )
        if not self.exact_duration_forbidden:
            raise AssessmentAnalyticsPolicyError("exact_duration_forbidden must be true")
        if self.max_enabled_heads <= 0 or self.max_enabled_heads > DEFAULT_MAX_ENABLED_HEADS:
            raise AssessmentAnalyticsPolicyError("max_enabled_heads out of range")
        if not self.fail_silent_optional_integration:
            raise AssessmentAnalyticsPolicyError(
                "fail_silent_optional_integration must be true"
            )

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "analytics_policy_version": self.analytics_policy_version,
            "analytics_schema_version": self.analytics_schema_version,
            "category_assessment_only": self.category_assessment_only,
            "coarse_duration_buckets_only": self.coarse_duration_buckets_only,
            "command_category_assess_only": self.command_category_assess_only,
            "exact_duration_forbidden": self.exact_duration_forbidden,
            "fail_silent_optional_integration": self.fail_silent_optional_integration,
            "failure_category_forbidden_on_success": (
                self.failure_category_forbidden_on_success
            ),
            "failure_category_required_on_failure": (
                self.failure_category_required_on_failure
            ),
            "installation_id_only_identifier": self.installation_id_only_identifier,
            "installation_id_required": self.installation_id_required,
            "limitations": list(self.limitations),
            "local_collection_allowed": self.local_collection_allowed,
            "max_enabled_heads": self.max_enabled_heads,
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
    def default(cls) -> CommunityAssessmentAnalyticsPolicy:
        return cls()


def default_assessment_analytics_policy() -> CommunityAssessmentAnalyticsPolicy:
    return CommunityAssessmentAnalyticsPolicy.default()


__all__ = [
    "COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_ID",
    "COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_URN",
    "COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_VERSION",
    "COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_ID",
    "COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_URN",
    "COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_VERSION",
    "DEFAULT_MAX_ENABLED_HEADS",
    "AssessmentAnalyticsPolicyError",
    "CommunityAssessmentAnalyticsPolicy",
    "default_assessment_analytics_policy",
]
