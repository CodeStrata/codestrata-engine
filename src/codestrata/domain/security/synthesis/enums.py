"""Security synthesis enums (Phase 4.5.5)."""

from __future__ import annotations

from enum import StrEnum


class SecurityThemeKind(StrEnum):
    """Bounded theme kinds derived from Security assessment inventory."""

    SECURITY_HYGIENE_LANDSCAPE = "security_hygiene_landscape"
    CREDENTIAL_AND_SECRET_HYGIENE = "credential_and_secret_hygiene"
    PRIVATE_KEY_EXPOSURE = "private_key_exposure"
    TRANSPORT_SECURITY_CONFIGURATION = "transport_security_configuration"
    AUTHENTICATION_CONFIGURATION = "authentication_configuration"
    PERMISSIVE_CORS_CONFIGURATION = "permissive_cors_configuration"
    DEBUG_CONFIGURATION = "debug_configuration"
    PLACEHOLDER_CREDENTIALS = "placeholder_credentials"
    TEST_FIXTURE_OBSERVATIONS = "test_fixture_observations"
    UNKNOWN_ROLE_OBSERVATIONS = "unknown_role_observations"
    FINDING_CONCENTRATION = "finding_concentration"
    EVIDENCE_COVERAGE = "evidence_coverage"
    PARTIAL_EVIDENCE_COVERAGE = "partial_evidence_coverage"
    UNSUPPORTED_ANALYSIS_SCOPE = "unsupported_analysis_scope"
    NO_PRODUCTION_FINDINGS = "no_production_findings"


class SecurityThemeScope(StrEnum):
    PRODUCTION = "production"
    TEST_OBSERVATION = "test_observation"
    COVERAGE = "coverage"
    REPOSITORY = "repository"


class SecurityConclusionKind(StrEnum):
    """Bounded deterministic conclusion kinds."""

    PRODUCTION_SECURITY_FINDINGS_PRESENT = "production_security_findings_present"
    TEST_OR_FIXTURE_FINDINGS_ONLY = "test_or_fixture_findings_only"
    UNKNOWN_ROLE_FINDINGS_PRESENT = "unknown_role_findings_present"
    NO_PRODUCTION_FINDINGS_IN_SUPPORTED_SCOPE = (
        "no_production_findings_in_supported_scope"
    )
    PRIVATE_KEY_MATERIAL_DETECTED = "private_key_material_detected"
    LITERAL_CREDENTIALS_DETECTED = "literal_credentials_detected"
    PLACEHOLDER_CREDENTIALS_DETECTED = "placeholder_credentials_detected"
    TRANSPORT_VERIFICATION_DISABLED = "transport_verification_disabled"
    AUTHENTICATION_EXPLICITLY_DISABLED = "authentication_explicitly_disabled"
    PERMISSIVE_CORS_CONFIGURED = "permissive_cors_configured"
    DEBUG_ENABLED = "debug_enabled"
    FINDINGS_CONCENTRATED = "findings_concentrated"
    PARTIAL_EVIDENCE_COVERAGE = "partial_evidence_coverage"
    UNSUPPORTED_SECURITY_ANALYSIS_SCOPE = "unsupported_security_analysis_scope"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SYNTHESIS_DISABLED = "synthesis_disabled"
    SECURITY_HYGIENE_LANDSCAPE_IDENTIFIED = "security_hygiene_landscape_identified"


class SecurityConclusionAudience(StrEnum):
    PRODUCTION_HEALTH = "production_health"
    TEST_OBSERVATION = "test_observation"
    COVERAGE = "coverage"
    REPOSITORY = "repository"
    STATUS = "status"


class SecurityRecommendationKind(StrEnum):
    """Bounded recommendation kinds linked to conclusions."""

    REMOVE_COMMITTED_PRIVATE_KEY_MATERIAL = "remove_committed_private_key_material"
    ROTATE_AND_REPLACE_LITERAL_CREDENTIALS = "rotate_and_replace_literal_credentials"
    REPLACE_LITERAL_CREDENTIALS_WITH_EXTERNAL_SECRET_REFERENCE = (
        "replace_literal_credentials_with_external_secret_reference"
    )
    REPLACE_PLACEHOLDER_CREDENTIALS = "replace_placeholder_credentials"
    ENABLE_TLS_VERIFICATION = "enable_tls_verification"
    ENABLE_HOSTNAME_VERIFICATION = "enable_hostname_verification"
    ENABLE_AUTHENTICATION = "enable_authentication"
    RESTRICT_CORS_ORIGINS = "restrict_cors_origins"
    DISABLE_DEBUG_CONFIGURATION = "disable_debug_configuration"
    REVIEW_TEST_FIXTURE_SECURITY_OBSERVATIONS = (
        "review_test_fixture_security_observations"
    )
    CLASSIFY_UNKNOWN_ROLE_FILES = "classify_unknown_role_files"
    REVIEW_SECURITY_FINDING_HOTSPOTS = "review_security_finding_hotspots"
    CORRECT_MALFORMED_CONFIGURATION = "correct_malformed_configuration"
    EXPAND_SUPPORTED_EVIDENCE_COVERAGE = "expand_supported_evidence_coverage"
    ADD_RUNTIME_SECURITY_VALIDATION = "add_runtime_security_validation"
    ADD_GIT_HISTORY_SECRET_SCANNING = "add_git_history_secret_scanning"
    ADD_EXTERNAL_DEPENDENCY_VULNERABILITY_ANALYSIS = (
        "add_external_dependency_vulnerability_analysis"
    )
    ACKNOWLEDGE_NO_PRODUCTION_FINDINGS_IN_SUPPORTED_SCOPE = (
        "acknowledge_no_production_findings_in_supported_scope"
    )


class SecuritySynthesisStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    DISABLED = "disabled"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SUCCEEDED = "succeeded"
    EMPTY = "empty"
    FAILED = "failed"
