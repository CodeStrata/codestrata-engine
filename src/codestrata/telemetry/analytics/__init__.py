"""Anonymous analytics (Epic 10): contract (10.1), identity (10.2), runtime (10.3),
assessment (10.4), repository aggregates (10.5), AI usage (10.6).

Assessment, runtime, repository-aggregate, and AI analytics may be constructed
locally. Analytics are not transmitted and are not persisted (only the anonymous
installation identity file may be written). AI analytics is construction-API
only — not wired into assess or AI execution.
"""

from __future__ import annotations

from codestrata.telemetry.analytics.assessment_analytics import (
    AssessmentAnalyticsEvent,
    build_assessment_analytics_event,
    classify_duration_bucket_ms,
    collect_assessment_analytics,
)
from codestrata.telemetry.analytics.assessment_analytics_compatibility import (
    AssessmentAnalyticsCompatibilityError,
    assert_assessment_analytics_schema_compatible,
    compatible_assessment_analytics_schema_versions,
)
from codestrata.telemetry.analytics.assessment_analytics_diagnostics import (
    AssessmentAnalyticsDiagnostics,
    empty_assessment_analytics_diagnostics,
)
from codestrata.telemetry.analytics.assessment_analytics_policy import (
    COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_URN,
    COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_URN,
    CommunityAssessmentAnalyticsPolicy,
    default_assessment_analytics_policy,
)
from codestrata.telemetry.analytics.assessment_analytics_projection import (
    AssessmentAnalyticsProjection,
    project_assessment_analytics_event,
    project_assessment_analytics_to_analytics_event,
)
from codestrata.telemetry.analytics.assessment_analytics_serialization import (
    assessment_analytics_event_to_stable_json,
    assessment_analytics_policy_to_stable_json,
)
from codestrata.telemetry.analytics.assessment_analytics_validation import (
    validate_assessment_analytics_event,
    validate_assessment_analytics_mapping,
)
from codestrata.telemetry.analytics.repository_aggregate import (
    RepositoryAggregateAnalyticsEvent,
    build_repository_aggregate_analytics_event,
    collect_repository_aggregate_analytics,
)
from codestrata.telemetry.analytics.repository_aggregate_compatibility import (
    RepositoryAggregateAnalyticsCompatibilityError,
    assert_repository_aggregate_schema_compatible,
    compatible_repository_aggregate_schema_versions,
)
from codestrata.telemetry.analytics.repository_aggregate_diagnostics import (
    RepositoryAggregateAnalyticsDiagnostics,
    empty_repository_aggregate_analytics_diagnostics,
)
from codestrata.telemetry.analytics.repository_aggregate_extractor import (
    extract_repository_aggregate_input,
)
from codestrata.telemetry.analytics.repository_aggregate_input import (
    RepositoryAggregateAnalyticsInput,
    build_repository_aggregate_input,
)
from codestrata.telemetry.analytics.repository_aggregate_models import (
    LanguageAggregate,
    RuleExecutionAggregate,
)
from codestrata.telemetry.analytics.repository_aggregate_policy import (
    COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_URN,
    COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_URN,
    CommunityRepositoryAggregateAnalyticsPolicy,
    default_repository_aggregate_analytics_policy,
)
from codestrata.telemetry.analytics.repository_aggregate_projection import (
    RepositoryAggregateAnalyticsProjection,
    project_repository_aggregate_analytics_event,
    project_repository_aggregate_to_analytics_event,
)
from codestrata.telemetry.analytics.repository_aggregate_serialization import (
    repository_aggregate_event_to_stable_json,
    repository_aggregate_policy_to_stable_json,
)
from codestrata.telemetry.analytics.repository_aggregate_validation import (
    validate_repository_aggregate_analytics_event,
    validate_repository_aggregate_analytics_mapping,
)
from codestrata.telemetry.analytics.compatibility import (
    AnalyticsCompatibilityError,
    assert_schema_compatible,
    compatible_schema_versions,
)
from codestrata.telemetry.analytics.diagnostics import (
    AnalyticsDiagnostics,
    empty_analytics_diagnostics,
)
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import (
    APPROVED_ANALYTICS_CATEGORIES,
    APPROVED_ANALYTICS_FIELD_NAMES,
    AnalyticsCategory,
    AnalyticsEvent,
    AnalyticsLifecycle,
)
from codestrata.telemetry.analytics.installation_identity import (
    AnonymousInstallationIdentity,
    diagnose_anonymous_installation_identity,
    ensure_anonymous_installation_identity,
    generate_anonymous_installation_id,
    is_uuid_v4,
    load_anonymous_installation_identity,
    new_anonymous_installation_identity,
)
from codestrata.telemetry.analytics.installation_identity_compatibility import (
    InstallationIdentityCompatibilityError,
    assert_identity_schema_compatible,
    compatible_identity_schema_versions,
    migrate_identity_mapping,
)
from codestrata.telemetry.analytics.installation_identity_diagnostics import (
    InstallationIdentityDiagnostics,
    empty_installation_identity_diagnostics,
)
from codestrata.telemetry.analytics.installation_identity_errors import (
    InstallationIdentityError,
    InstallationIdentityErrorCode,
)
from codestrata.telemetry.analytics.installation_identity_policy import (
    COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_URN,
    COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_URN,
    CommunityAnonymousInstallationIdentityPolicy,
    default_installation_identity_policy,
)
from codestrata.telemetry.analytics.installation_identity_serialization import (
    identity_policy_to_stable_json,
    identity_to_stable_json,
)
from codestrata.telemetry.analytics.installation_identity_storage import (
    installation_identity_path,
    read_identity_bytes,
    write_identity_atomic,
)
from codestrata.telemetry.analytics.installation_identity_validation import (
    parse_identity_bytes,
    parse_identity_mapping,
    validate_identity_record,
)
from codestrata.telemetry.analytics.policy import (
    COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_URN,
    COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_URN,
    CommunityAnonymousAnalyticsPolicy,
    default_analytics_policy,
)
from codestrata.telemetry.analytics.projection import (
    AnalyticsProjection,
    project_analytics_event,
    project_analytics_from_mapping,
)
from codestrata.telemetry.analytics.runtime_analytics import (
    COMMUNITY_RUNTIME_ANALYTICS_POLICY_URN,
    COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_URN,
    CommunityRuntimeAnalyticsPolicy,
    RuntimeAnalyticsEvent,
    build_runtime_analytics_event,
    collect_runtime_analytics,
    default_runtime_analytics_policy,
)
from codestrata.telemetry.analytics.runtime_analytics_compatibility import (
    RuntimeAnalyticsCompatibilityError,
    assert_runtime_analytics_schema_compatible,
    compatible_runtime_analytics_schema_versions,
)
from codestrata.telemetry.analytics.runtime_analytics_diagnostics import (
    RuntimeAnalyticsDiagnostics,
    empty_runtime_analytics_diagnostics,
)
from codestrata.telemetry.analytics.runtime_analytics_projection import (
    RuntimeAnalyticsProjection,
    project_runtime_analytics_event,
    project_runtime_analytics_to_analytics_event,
)
from codestrata.telemetry.analytics.runtime_analytics_serialization import (
    runtime_analytics_event_to_stable_json,
    runtime_analytics_policy_to_stable_json,
)
from codestrata.telemetry.analytics.runtime_analytics_validation import (
    validate_runtime_analytics_event,
    validate_runtime_analytics_mapping,
)
from codestrata.telemetry.analytics.serialization import (
    analytics_event_to_stable_json,
    analytics_policy_to_stable_json,
)
from codestrata.telemetry.analytics.validation import (
    validate_analytics_event,
    validate_analytics_mapping,
)
from codestrata.telemetry.analytics.ai_analytics import (
    collect_ai_analytics,
    project_from_typed_input,
)
from codestrata.telemetry.analytics.ai_analytics_compatibility import (
    AIAnalyticsCompatibilityError,
    assert_ai_analytics_schema_compatible,
    compatible_ai_analytics_schema_versions,
)
from codestrata.telemetry.analytics.ai_analytics_diagnostics import (
    AIAnalyticsDiagnostics,
    empty_ai_analytics_diagnostics,
)
from codestrata.telemetry.analytics.ai_analytics_input import (
    AIAnalyticsInput,
    build_ai_analytics_input,
)
from codestrata.telemetry.analytics.ai_analytics_mapping import (
    canonicalize_capability,
    map_model_id_to_family,
    map_provider_to_family,
)
from codestrata.telemetry.analytics.ai_analytics_models import (
    AIAnalyticsEvent,
    build_ai_analytics_event,
)
from codestrata.telemetry.analytics.ai_analytics_policy import (
    COMMUNITY_AI_ANALYTICS_POLICY_URN,
    COMMUNITY_AI_ANALYTICS_SCHEMA_URN,
    CommunityAIAnalyticsPolicy,
    default_ai_analytics_policy,
)
from codestrata.telemetry.analytics.ai_analytics_projection import (
    AIAnalyticsProjection,
    project_ai_analytics_event,
    project_ai_analytics_to_analytics_event,
)
from codestrata.telemetry.analytics.ai_analytics_serialization import (
    ai_analytics_event_to_stable_json,
    ai_analytics_policy_to_stable_json,
)
from codestrata.telemetry.analytics.ai_analytics_validation import (
    validate_ai_analytics_event,
    validate_ai_analytics_mapping,
)

__all__ = [
    "APPROVED_ANALYTICS_CATEGORIES",
    "APPROVED_ANALYTICS_FIELD_NAMES",
    "AnalyticsCategory",
    "AnalyticsCompatibilityError",
    "AnalyticsDiagnostics",
    "AnalyticsError",
    "AnalyticsErrorCode",
    "AnalyticsEvent",
    "AnalyticsLifecycle",
    "AnalyticsProjection",
    "AnonymousInstallationIdentity",
    "AssessmentAnalyticsCompatibilityError",
    "AssessmentAnalyticsDiagnostics",
    "AssessmentAnalyticsEvent",
    "AssessmentAnalyticsProjection",
    "COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_URN",
    "COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_URN",
    "COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_URN",
    "COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_URN",
    "COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_URN",
    "COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_URN",
    "COMMUNITY_RUNTIME_ANALYTICS_POLICY_URN",
    "COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_URN",
    "CommunityAnonymousAnalyticsPolicy",
    "CommunityAnonymousInstallationIdentityPolicy",
    "CommunityAssessmentAnalyticsPolicy",
    "CommunityRuntimeAnalyticsPolicy",
    "InstallationIdentityCompatibilityError",
    "InstallationIdentityDiagnostics",
    "InstallationIdentityError",
    "InstallationIdentityErrorCode",
    "RuntimeAnalyticsCompatibilityError",
    "RuntimeAnalyticsDiagnostics",
    "RuntimeAnalyticsEvent",
    "RuntimeAnalyticsProjection",
    "analytics_event_to_stable_json",
    "analytics_policy_to_stable_json",
    "assert_assessment_analytics_schema_compatible",
    "assert_identity_schema_compatible",
    "assert_runtime_analytics_schema_compatible",
    "assert_schema_compatible",
    "assessment_analytics_event_to_stable_json",
    "assessment_analytics_policy_to_stable_json",
    "build_assessment_analytics_event",
    "build_runtime_analytics_event",
    "classify_duration_bucket_ms",
    "collect_assessment_analytics",
    "collect_runtime_analytics",
    "compatible_assessment_analytics_schema_versions",
    "compatible_identity_schema_versions",
    "compatible_runtime_analytics_schema_versions",
    "compatible_schema_versions",
    "default_analytics_policy",
    "default_assessment_analytics_policy",
    "default_installation_identity_policy",
    "default_runtime_analytics_policy",
    "diagnose_anonymous_installation_identity",
    "empty_analytics_diagnostics",
    "empty_assessment_analytics_diagnostics",
    "empty_installation_identity_diagnostics",
    "empty_runtime_analytics_diagnostics",
    "ensure_anonymous_installation_identity",
    "generate_anonymous_installation_id",
    "identity_policy_to_stable_json",
    "identity_to_stable_json",
    "installation_identity_path",
    "is_uuid_v4",
    "load_anonymous_installation_identity",
    "migrate_identity_mapping",
    "new_anonymous_installation_identity",
    "parse_identity_bytes",
    "parse_identity_mapping",
    "project_analytics_event",
    "project_analytics_from_mapping",
    "project_assessment_analytics_event",
    "project_assessment_analytics_to_analytics_event",
    "project_runtime_analytics_event",
    "project_runtime_analytics_to_analytics_event",
    "read_identity_bytes",
    "runtime_analytics_event_to_stable_json",
    "runtime_analytics_policy_to_stable_json",
    "validate_analytics_event",
    "validate_analytics_mapping",
    "validate_assessment_analytics_event",
    "validate_assessment_analytics_mapping",
    "validate_identity_record",
    "validate_runtime_analytics_event",
    "validate_runtime_analytics_mapping",
    "COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_URN",
    "COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_URN",
    "CommunityRepositoryAggregateAnalyticsPolicy",
    "LanguageAggregate",
    "RepositoryAggregateAnalyticsCompatibilityError",
    "RepositoryAggregateAnalyticsDiagnostics",
    "RepositoryAggregateAnalyticsEvent",
    "RepositoryAggregateAnalyticsInput",
    "RepositoryAggregateAnalyticsProjection",
    "RuleExecutionAggregate",
    "assert_repository_aggregate_schema_compatible",
    "build_repository_aggregate_analytics_event",
    "build_repository_aggregate_input",
    "collect_repository_aggregate_analytics",
    "compatible_repository_aggregate_schema_versions",
    "default_repository_aggregate_analytics_policy",
    "empty_repository_aggregate_analytics_diagnostics",
    "extract_repository_aggregate_input",
    "project_repository_aggregate_analytics_event",
    "project_repository_aggregate_to_analytics_event",
    "repository_aggregate_event_to_stable_json",
    "repository_aggregate_policy_to_stable_json",
    "validate_repository_aggregate_analytics_event",
    "validate_repository_aggregate_analytics_mapping",
    "write_identity_atomic",
    "AIAnalyticsCompatibilityError",
    "AIAnalyticsDiagnostics",
    "AIAnalyticsEvent",
    "AIAnalyticsInput",
    "AIAnalyticsProjection",
    "COMMUNITY_AI_ANALYTICS_POLICY_URN",
    "COMMUNITY_AI_ANALYTICS_SCHEMA_URN",
    "CommunityAIAnalyticsPolicy",
    "ai_analytics_event_to_stable_json",
    "ai_analytics_policy_to_stable_json",
    "assert_ai_analytics_schema_compatible",
    "build_ai_analytics_event",
    "build_ai_analytics_input",
    "canonicalize_capability",
    "collect_ai_analytics",
    "compatible_ai_analytics_schema_versions",
    "default_ai_analytics_policy",
    "empty_ai_analytics_diagnostics",
    "map_model_id_to_family",
    "map_provider_to_family",
    "project_ai_analytics_event",
    "project_ai_analytics_to_analytics_event",
    "project_from_typed_input",
    "validate_ai_analytics_event",
    "validate_ai_analytics_mapping",
]
