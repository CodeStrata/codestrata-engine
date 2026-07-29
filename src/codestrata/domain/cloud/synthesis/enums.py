"""Cloud synthesis enums (Phase 4.7.5)."""

from __future__ import annotations

from enum import StrEnum


class CloudThemeKind(StrEnum):
    """Bounded theme kinds derived from Cloud assessment inventory."""

    CLOUD_HYGIENE_LANDSCAPE = "cloud_hygiene_landscape"
    RULE_EXECUTION_COVERAGE = "rule_execution_coverage"
    CLOUD_PLATFORM_ADOPTION = "cloud_platform_adoption"
    MULTI_CLOUD_PRESENCE = "multi_cloud_presence"
    CONTAINERIZATION_MATURITY = "containerization_maturity"
    KUBERNETES_ORCHESTRATION_ADOPTION = "kubernetes_orchestration_adoption"
    IAC_MATURITY = "iac_maturity"
    SERVERLESS_ADOPTION = "serverless_adoption"
    MANAGED_CLOUD_SERVICE_USAGE = "managed_cloud_service_usage"
    CLOUD_DEPLOYMENT_AUTOMATION = "cloud_deployment_automation"
    CLOUD_TECHNOLOGY_COVERAGE = "cloud_technology_coverage"
    DEPLOYMENT_WITHOUT_PLATFORM = "deployment_without_platform"
    NO_HYGIENE_FINDINGS = "no_hygiene_findings"
    UNSUPPORTED_ANALYSIS_SCOPE = "unsupported_analysis_scope"


class CloudThemeScope(StrEnum):
    REPOSITORY = "repository"
    COVERAGE = "coverage"
    HYGIENE = "hygiene"
    STATUS = "status"


class CloudConclusionKind(StrEnum):
    """Bounded deterministic conclusion kinds."""

    CLOUD_HYGIENE_LANDSCAPE_IDENTIFIED = "cloud_hygiene_landscape_identified"
    RULE_EXECUTION_SUMMARY = "rule_execution_summary"
    CLOUD_PLATFORM_ADOPTION_OBSERVED = "cloud_platform_adoption_observed"
    MULTI_CLOUD_PRESENCE_OBSERVED = "multi_cloud_presence_observed"
    CONTAINERIZATION_OBSERVED = "containerization_observed"
    KUBERNETES_ORCHESTRATION_OBSERVED = "kubernetes_orchestration_observed"
    IAC_MATURITY_OBSERVED = "iac_maturity_observed"
    SERVERLESS_ADOPTION_OBSERVED = "serverless_adoption_observed"
    MANAGED_CLOUD_SERVICES_OBSERVED = "managed_cloud_services_observed"
    CLOUD_DEPLOYMENT_AUTOMATION_OBSERVED = "cloud_deployment_automation_observed"
    CLOUD_TECHNOLOGY_COVERAGE_OBSERVED = "cloud_technology_coverage_observed"
    DEPLOYMENT_WITHOUT_PLATFORM_OBSERVED = "deployment_without_platform_observed"
    NO_HYGIENE_FINDINGS_IN_SUPPORTED_SCOPE = "no_hygiene_findings_in_supported_scope"
    UNSUPPORTED_CLOUD_ANALYSIS_SCOPE = "unsupported_cloud_analysis_scope"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SYNTHESIS_DISABLED = "synthesis_disabled"


class CloudConclusionAudience(StrEnum):
    REPOSITORY = "repository"
    HYGIENE = "hygiene"
    COVERAGE = "coverage"
    STATUS = "status"


class CloudRecommendationKind(StrEnum):
    """Bounded observation-oriented recommendation kinds."""

    REVIEW_CLOUD_PLATFORM_SIGNALS = "review_cloud_platform_signals"
    REVIEW_MULTI_CLOUD_SIGNALS = "review_multi_cloud_signals"
    REVIEW_CONTAINERIZATION_SIGNALS = "review_containerization_signals"
    REVIEW_ORCHESTRATION_SIGNALS = "review_orchestration_signals"
    REVIEW_IAC_SIGNALS = "review_iac_signals"
    REVIEW_SERVERLESS_SIGNALS = "review_serverless_signals"
    REVIEW_MANAGED_SERVICE_SIGNALS = "review_managed_service_signals"
    REVIEW_DEPLOYMENT_PIPELINE_SIGNALS = "review_deployment_pipeline_signals"
    REVIEW_CLOUD_TECHNOLOGY_COVERAGE = "review_cloud_technology_coverage"
    REVIEW_DEPLOYMENT_WITHOUT_PLATFORM = "review_deployment_without_platform"
    ACKNOWLEDGE_NO_HYGIENE_FINDINGS_IN_SUPPORTED_SCOPE = (
        "acknowledge_no_hygiene_findings_in_supported_scope"
    )
    ACKNOWLEDGE_UNSUPPORTED_CLOUD_ANALYSIS_SCOPE = "acknowledge_unsupported_cloud_analysis_scope"


class CloudSynthesisStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    DISABLED = "disabled"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SUCCEEDED = "succeeded"
    EMPTY = "empty"
    FAILED = "failed"
