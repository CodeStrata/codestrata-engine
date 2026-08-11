"""Independent AI analytics policy (Epic 10 Slice 10.6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.analytics.ai_analytics_catalogs import (
    AI_ANALYTICS_CAPABILITY_CATALOG_VERSION,
    AI_ANALYTICS_MODEL_FAMILY_CATALOG_VERSION,
    AI_ANALYTICS_PROVIDER_FAMILY_CATALOG_VERSION,
)
from codestrata.telemetry.analytics.policy import (
    COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION,
    COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION,
)

COMMUNITY_AI_ANALYTICS_POLICY_ID = "community-ai-analytics-policy"
COMMUNITY_AI_ANALYTICS_POLICY_VERSION = "1.0"
COMMUNITY_AI_ANALYTICS_POLICY_URN = (
    f"{COMMUNITY_AI_ANALYTICS_POLICY_ID}:{COMMUNITY_AI_ANALYTICS_POLICY_VERSION}"
)

COMMUNITY_AI_ANALYTICS_SCHEMA_ID = "community-ai-analytics-schema"
COMMUNITY_AI_ANALYTICS_SCHEMA_VERSION = "1.0"
COMMUNITY_AI_ANALYTICS_SCHEMA_URN = (
    f"{COMMUNITY_AI_ANALYTICS_SCHEMA_ID}:{COMMUNITY_AI_ANALYTICS_SCHEMA_VERSION}"
)

_REVIEW_STATUS = (
    "local_construction_only_no_transmission_no_analytics_persistence_unwired"
)

_LIMITATIONS: tuple[str, ...] = (
    "ai_usage_category_only",
    "local_construction_only",
    "no_transmission",
    "no_analytics_persistence",
    "installation_identity_only_identifier",
    "requires_prior_privacy_projection",
    "not_wired_into_cli_product_path",
    "bounded_capability_catalog_only",
    "bounded_provider_family_only",
    "bounded_model_family_only",
    "raw_provider_and_model_ids_prohibited",
    "prompts_responses_source_prohibited",
    "credentials_endpoints_regions_prohibited",
    "exact_tokens_latency_cost_prohibited",
    "token_usage_bucket_excluded_in_slice_10_6",
    "tool_rag_graph_omitted_in_slice_10_6",
    "openrouter_family_only_no_endpoints_or_keys",
    "ai_provider_platform_redesign_deferred",
    "vscode_analytics_deferred_to_slice_10_7",
    "fail_silent_optional_integration",
    "no_telemetry_transport_modification",
    "no_telemetry_consent_modification",
    "community_cloud_deferred",
    "data_lake_deferred",
)


class AIAnalyticsPolicyError(ValueError):
    """Raised when AI-analytics policy invariants fail."""


@dataclass(frozen=True, slots=True)
class CommunityAIAnalyticsPolicy:
    """Independent policy for local AI analytics construction."""

    policy_id: str = COMMUNITY_AI_ANALYTICS_POLICY_ID
    policy_version: str = COMMUNITY_AI_ANALYTICS_POLICY_VERSION
    schema_id: str = COMMUNITY_AI_ANALYTICS_SCHEMA_ID
    schema_version: str = COMMUNITY_AI_ANALYTICS_SCHEMA_VERSION
    analytics_schema_version: str = COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION
    analytics_policy_version: str = COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION
    capability_catalog_version: str = AI_ANALYTICS_CAPABILITY_CATALOG_VERSION
    provider_family_catalog_version: str = AI_ANALYTICS_PROVIDER_FAMILY_CATALOG_VERSION
    model_family_catalog_version: str = AI_ANALYTICS_MODEL_FAMILY_CATALOG_VERSION
    local_collection_allowed: bool = True
    persistence_enabled: bool = False
    transmission_enabled: bool = False
    installation_id_required: bool = True
    installation_id_only_identifier: bool = True
    requires_prior_privacy_projection: bool = True
    category_ai_usage_only: bool = True
    raw_provider_ids_prohibited: bool = True
    raw_model_ids_prohibited: bool = True
    prompts_responses_source_prohibited: bool = True
    exact_tokens_latency_cost_prohibited: bool = True
    token_usage_bucket_allowed: bool = False
    tool_rag_graph_allowed: bool = False
    failure_category_required_on_failure: bool = True
    failure_category_forbidden_on_success: bool = True
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
        if self.policy_id != COMMUNITY_AI_ANALYTICS_POLICY_ID:
            raise AIAnalyticsPolicyError("unsupported AI analytics policy id")
        if self.policy_version != COMMUNITY_AI_ANALYTICS_POLICY_VERSION:
            raise AIAnalyticsPolicyError("unsupported AI analytics policy version")
        if self.schema_id != COMMUNITY_AI_ANALYTICS_SCHEMA_ID:
            raise AIAnalyticsPolicyError("unsupported AI analytics schema id")
        if self.schema_version != COMMUNITY_AI_ANALYTICS_SCHEMA_VERSION:
            raise AIAnalyticsPolicyError("unsupported AI analytics schema version")
        if self.review_status != _REVIEW_STATUS:
            raise AIAnalyticsPolicyError("unsupported AI analytics review_status")
        if not self.local_collection_allowed:
            raise AIAnalyticsPolicyError("local_collection_allowed must be true")
        if self.persistence_enabled:
            raise AIAnalyticsPolicyError("persistence_enabled must be false")
        if self.transmission_enabled:
            raise AIAnalyticsPolicyError("transmission_enabled must be false")
        if not self.installation_id_required:
            raise AIAnalyticsPolicyError("installation_id_required must be true")
        if not self.installation_id_only_identifier:
            raise AIAnalyticsPolicyError(
                "installation_id_only_identifier must be true"
            )
        if not self.requires_prior_privacy_projection:
            raise AIAnalyticsPolicyError(
                "requires_prior_privacy_projection must be true"
            )
        if not self.category_ai_usage_only:
            raise AIAnalyticsPolicyError("category_ai_usage_only must be true")
        if not self.raw_provider_ids_prohibited or not self.raw_model_ids_prohibited:
            raise AIAnalyticsPolicyError("raw provider/model IDs must be prohibited")
        if not self.prompts_responses_source_prohibited:
            raise AIAnalyticsPolicyError(
                "prompts_responses_source_prohibited must be true"
            )
        if not self.exact_tokens_latency_cost_prohibited:
            raise AIAnalyticsPolicyError(
                "exact_tokens_latency_cost_prohibited must be true"
            )
        if self.token_usage_bucket_allowed:
            raise AIAnalyticsPolicyError(
                "token_usage_bucket_allowed must be false in Slice 10.6"
            )
        if self.tool_rag_graph_allowed:
            raise AIAnalyticsPolicyError(
                "tool_rag_graph_allowed must be false in Slice 10.6"
            )
        if not self.fail_silent_optional_integration:
            raise AIAnalyticsPolicyError(
                "fail_silent_optional_integration must be true"
            )

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "analytics_policy_version": self.analytics_policy_version,
            "analytics_schema_version": self.analytics_schema_version,
            "capability_catalog_version": self.capability_catalog_version,
            "category_ai_usage_only": self.category_ai_usage_only,
            "exact_tokens_latency_cost_prohibited": (
                self.exact_tokens_latency_cost_prohibited
            ),
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
            "model_family_catalog_version": self.model_family_catalog_version,
            "persistence_enabled": self.persistence_enabled,
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "prompts_responses_source_prohibited": (
                self.prompts_responses_source_prohibited
            ),
            "provider_family_catalog_version": self.provider_family_catalog_version,
            "raw_model_ids_prohibited": self.raw_model_ids_prohibited,
            "raw_provider_ids_prohibited": self.raw_provider_ids_prohibited,
            "requires_prior_privacy_projection": self.requires_prior_privacy_projection,
            "review_status": self.review_status,
            "schema_id": self.schema_id,
            "schema_token": self.schema_token,
            "schema_version": self.schema_version,
            "token_usage_bucket_allowed": self.token_usage_bucket_allowed,
            "tool_rag_graph_allowed": self.tool_rag_graph_allowed,
            "transmission_enabled": self.transmission_enabled,
        }

    @classmethod
    def default(cls) -> CommunityAIAnalyticsPolicy:
        return cls()


def default_ai_analytics_policy() -> CommunityAIAnalyticsPolicy:
    return CommunityAIAnalyticsPolicy.default()


__all__ = [
    "COMMUNITY_AI_ANALYTICS_POLICY_ID",
    "COMMUNITY_AI_ANALYTICS_POLICY_URN",
    "COMMUNITY_AI_ANALYTICS_POLICY_VERSION",
    "COMMUNITY_AI_ANALYTICS_SCHEMA_ID",
    "COMMUNITY_AI_ANALYTICS_SCHEMA_URN",
    "COMMUNITY_AI_ANALYTICS_SCHEMA_VERSION",
    "AIAnalyticsPolicyError",
    "CommunityAIAnalyticsPolicy",
    "default_ai_analytics_policy",
]
