"""Dependency synthesis enums (Phase 4.4.5)."""

from __future__ import annotations

from enum import StrEnum


class DependencyThemeKind(StrEnum):
    """Bounded theme kinds derived from inventory facts."""

    DEPENDENCY_LANDSCAPE = "dependency_landscape"
    MANIFEST_DISTRIBUTION = "manifest_distribution"
    DECLARATION_HYGIENE = "declaration_hygiene"
    VERSION_RESOLUTION_COVERAGE = "version_resolution_coverage"
    MUTABLE_VERSION_USAGE = "mutable_version_usage"
    UNBOUNDED_PYTHON_REQUIREMENTS = "unbounded_python_requirements"
    DUPLICATE_DECLARATIONS = "duplicate_declarations"
    CONFLICTING_EXACT_VERSIONS = "conflicting_exact_versions"
    UNRESOLVED_VERSIONS = "unresolved_versions"
    TEST_FIXTURE_HYGIENE = "test_fixture_hygiene"
    BUILD_PLUGIN_LANDSCAPE = "build_plugin_landscape"
    PARTIAL_ECOSYSTEM_COVERAGE = "partial_ecosystem_coverage"


class DependencyThemeScope(StrEnum):
    PRODUCTION = "production"
    TEST_OBSERVATION = "test_observation"
    COVERAGE = "coverage"
    REPOSITORY = "repository"


class DependencyConclusionKind(StrEnum):
    """Bounded deterministic conclusion kinds."""

    DEPENDENCY_LANDSCAPE_IDENTIFIED = "dependency_landscape_identified"
    NO_PRODUCTION_HYGIENE_FINDINGS = "no_production_hygiene_findings"
    PRODUCTION_HYGIENE_FINDINGS_PRESENT = "production_hygiene_findings_present"
    TEST_FIXTURE_FINDINGS_PRESENT = "test_fixture_findings_present"
    MUTABLE_VERSIONS_PRESENT = "mutable_versions_present"
    UNBOUNDED_REQUIREMENTS_PRESENT = "unbounded_requirements_present"
    DUPLICATE_DECLARATIONS_PRESENT = "duplicate_declarations_present"
    CONFLICTING_EXACT_VERSIONS_PRESENT = "conflicting_exact_versions_present"
    UNRESOLVED_VERSIONS_PRESENT = "unresolved_versions_present"
    UNSUPPORTED_RESOLUTION_COVERAGE = "unsupported_resolution_coverage"
    PRODUCTION_COLLECTION_PARTIAL = "production_collection_partial"
    DECLARED_DEPENDENCIES_ONLY = "declared_dependencies_only"
    UNSUPPORTED_ECOSYSTEM_COVERAGE = "unsupported_ecosystem_coverage"
    DISABLED = "disabled"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class DependencyConclusionAudience(StrEnum):
    PRODUCTION_HEALTH = "production_health"
    TEST_OBSERVATION = "test_observation"
    COVERAGE = "coverage"
    REPOSITORY = "repository"
    STATUS = "status"


class DependencyRecommendationKind(StrEnum):
    """Bounded recommendation kinds linked to conclusions."""

    REVIEW_DEPENDENCY_HYGIENE_FINDINGS = "review_dependency_hygiene_findings"
    REMOVE_DUPLICATE_DECLARATIONS = "remove_duplicate_declarations"
    DEFINE_UNRESOLVED_LOCAL_VERSION = "define_unresolved_local_version"
    REPLACE_MUTABLE_VERSION_DECLARATION = "replace_mutable_version_declaration"
    CONSTRAIN_PYTHON_REQUIREMENT = "constrain_python_requirement"
    RECONCILE_CONFLICTING_EXACT_VERSIONS = "reconcile_conflicting_exact_versions"
    REVIEW_TEST_FIXTURE_DECLARATIONS = "review_test_fixture_declarations"
    EXPAND_GRADLE_RESOLUTION_COVERAGE = "expand_gradle_resolution_coverage"
    ADD_RESOLVED_GRAPH_ANALYSIS = "add_resolved_graph_analysis"
    ADD_UNSUPPORTED_ECOSYSTEM_COVERAGE = "add_unsupported_ecosystem_coverage"
    ACKNOWLEDGE_NO_PRODUCTION_FINDINGS = "acknowledge_no_production_findings"


class DependencySynthesisStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    DISABLED = "disabled"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SUCCEEDED = "succeeded"
    EMPTY = "empty"
