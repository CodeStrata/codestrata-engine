"""Shared helpers for Test Hygiene SharedRules (Phase 4.6.3)."""

from __future__ import annotations

from codestrata.domain.evidence.repository_testing.enums import (
    CoverageFactType,
    EvidenceConfirmationLevel,
    FrameworkEvidenceBasis,
    RepositoryTestingParseStatus,
    TestFileRole,
    TestFrameworkFamily,
    TestMarkerType,
)
from codestrata.domain.evidence.repository_testing.models import (
    AggregatedRepositoryTestingEvidence,
    CiTestInvocationFactEvidence,
    CoverageFactEvidence,
    FrameworkFactEvidence,
    MarkerFactEvidence,
    TestFileCandidateEvidence,
)
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import (
    RuleCategory,
    RuleConfidence,
    RuleEvidenceKind,
    RuleIncrementalBehavior,
    RuleSeverity,
)
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.identifiers import RuleId
from codestrata.domain.rules.metadata import RuleMetadata, RuleVersion
from codestrata.domain.rules.results import RuleMatch, SharedRuleEvaluationResult
from codestrata.domain.testing.ids import (
    PACK_ID,
    PACK_VERSION,
    RULE_COVERAGE_WITHOUT_CI_INVOCATION,
    RULE_DECLARED_WITHOUT_OBSERVATION,
    RULE_DISABLED_OR_SKIPPED,
    RULE_UNCONFIRMED_CANDIDATES,
    RULE_VERSION,
)
from codestrata.domain.testing.taxonomy import TestCategory

# TEST-001 thresholds
TEST001_SEVERITY_LOW_MIN = 3
TEST001_SEVERITY_MEDIUM_MIN = 10
TEST001_HOTSPOT_MAX_PATHS = 5
TEST001_HOTSPOT_MIN_COUNT = 2
TEST001_MAX_MARKER_EVIDENCE = 20

# TEST-002 thresholds
TEST002_MIN_CONSIDERED = 20
TEST002_MIN_UNCONFIRMED = 10
TEST002_MIN_RATIO = 0.25
TEST002_INFORMATIONAL_RATIO_LT = 0.35

DISABLED_OR_SKIPPED_MARKER_TYPES: frozenset[TestMarkerType] = frozenset(
    {
        TestMarkerType.DISABLED,
        TestMarkerType.IGNORED,
        TestMarkerType.SKIPPED,
        TestMarkerType.CONDITIONAL_SKIP,
        TestMarkerType.QUARANTINED,
        TestMarkerType.EXPECTED_FAILURE,
    }
)

EXCLUDED_CANDIDATE_ROLES: frozenset[TestFileRole] = frozenset(
    {
        TestFileRole.TEST_FIXTURE,
        TestFileRole.TEST_SUPPORT,
        TestFileRole.TEST_CONFIGURATION,
        TestFileRole.COVERAGE_CONFIGURATION,
        TestFileRole.TEST_REPORT,
        TestFileRole.NON_TEST_CANDIDATE,
    }
)

TEST_FRAMEWORKS: frozenset[TestFrameworkFamily] = frozenset(
    {
        TestFrameworkFamily.PYTEST,
        TestFrameworkFamily.UNITTEST,
        TestFrameworkFamily.JUNIT,
        TestFrameworkFamily.JUNIT_JUPITER,
        TestFrameworkFamily.TESTNG,
        TestFrameworkFamily.JEST,
        TestFrameworkFamily.VITEST,
        TestFrameworkFamily.MOCHA,
        TestFrameworkFamily.PLAYWRIGHT,
        TestFrameworkFamily.CYPRESS,
        TestFrameworkFamily.XUNIT,
        TestFrameworkFamily.NUNIT,
        TestFrameworkFamily.MSTEST,
        TestFrameworkFamily.SPOCK,
        TestFrameworkFamily.KOTEST,
    }
)

_FRAMEWORK_LANGUAGES: dict[TestFrameworkFamily, frozenset[str]] = {
    TestFrameworkFamily.PYTEST: frozenset({"python"}),
    TestFrameworkFamily.UNITTEST: frozenset({"python"}),
    TestFrameworkFamily.JUNIT: frozenset({"java", "kotlin", "groovy"}),
    TestFrameworkFamily.JUNIT_JUPITER: frozenset({"java", "kotlin", "groovy"}),
    TestFrameworkFamily.TESTNG: frozenset({"java", "kotlin", "groovy"}),
    TestFrameworkFamily.SPOCK: frozenset({"groovy", "java"}),
    TestFrameworkFamily.KOTEST: frozenset({"kotlin"}),
    TestFrameworkFamily.JEST: frozenset({"javascript", "typescript"}),
    TestFrameworkFamily.VITEST: frozenset({"javascript", "typescript"}),
    TestFrameworkFamily.MOCHA: frozenset({"javascript", "typescript"}),
    TestFrameworkFamily.PLAYWRIGHT: frozenset({"javascript", "typescript"}),
    TestFrameworkFamily.CYPRESS: frozenset({"javascript", "typescript"}),
    TestFrameworkFamily.XUNIT: frozenset({"csharp", "fsharp", "vb"}),
    TestFrameworkFamily.NUNIT: frozenset({"csharp", "fsharp", "vb"}),
    TestFrameworkFamily.MSTEST: frozenset({"csharp", "fsharp", "vb"}),
}

_JUNIT_FAMILY = frozenset(
    {TestFrameworkFamily.JUNIT, TestFrameworkFamily.JUNIT_JUPITER}
)

_RECOMMENDATIONS: dict[str, str] = {
    RULE_DISABLED_OR_SKIPPED: (
        "Review disabled, ignored, skipped, quarantined, or expected-failure "
        "markers and restore or remove them intentionally."
    ),
    RULE_UNCONFIRMED_CANDIDATES: (
        "Review naming-only or ambiguous test candidates and strengthen "
        "structural markers where tests are intended."
    ),
    RULE_DECLARED_WITHOUT_OBSERVATION: (
        "Confirm whether declared test frameworks are still needed, or whether "
        "tests exist outside inspected boundaries."
    ),
    RULE_COVERAGE_WITHOUT_CI_INVOCATION: (
        "Add an explicit test or coverage command to CI when coverage "
        "configuration is intended to be enforced in the pipeline."
    ),
}

_PROVENANCE = "aggregated_repository_testing_evidence"


def repository_testing_evidence(
    context: RuleExecutionContext,
) -> AggregatedRepositoryTestingEvidence | None:
    raw = context.repository_testing_evidence
    if isinstance(raw, AggregatedRepositoryTestingEvidence):
        return raw
    return None


def evidence_is_usable(
    evidence: AggregatedRepositoryTestingEvidence | None,
) -> bool:
    if evidence is None:
        return False
    if evidence.status in {
        RepositoryTestingParseStatus.NOT_APPLICABLE,
        RepositoryTestingParseStatus.SKIPPED,
        RepositoryTestingParseStatus.FAILED,
        RepositoryTestingParseStatus.INSUFFICIENT_EVIDENCE,
    }:
        return False
    if evidence.status not in {
        RepositoryTestingParseStatus.SUCCEEDED,
        RepositoryTestingParseStatus.PARTIALLY_SUCCEEDED,
    }:
        return False
    return bool(
        evidence.file_candidates
        or evidence.structural_test_facts
        or evidence.framework_facts
        or evidence.test_type_facts
        or evidence.build_configuration_facts
        or evidence.marker_facts
        or evidence.fixture_facts
        or evidence.coverage_facts
        or evidence.ci_test_invocation_facts
    )


def make_metadata(
    *,
    rule_id: str,
    title: str,
    description: str,
    remediation: str,
    severity: RuleSeverity = RuleSeverity.LOW,
) -> RuleMetadata:
    return RuleMetadata(
        rule_id=RuleId(rule_id),
        version=RuleVersion.parse(RULE_VERSION),
        title=title,
        description=description,
        category=RuleCategory.TESTING,
        default_severity=severity,
        supported_languages=(
            "java",
            "python",
            "javascript",
            "typescript",
            "kotlin",
            "groovy",
            "csharp",
            "php",
        ),
        tags=("testing", PACK_ID, "hygiene", "dimension:testing"),
        remediation_summary=remediation,
        documentation_reference=(
            "docs/analysis-intelligence/shared-rule-platform.md"
        ),
        enabled_by_default=True,
        experimental=False,
        requires_enterprise_context=False,
        incremental_behaviors=(
            RuleIncrementalBehavior.AFFECTED_BY_SOURCE_CHANGES,
            RuleIncrementalBehavior.REQUIRES_FULL_CONTEXT,
        ),
    )


def recommendation_for(rule_id: str) -> str:
    return _RECOMMENDATIONS.get(
        rule_id,
        "Review the repository-testing evidence fact and remediate the "
        "hygiene condition.",
    )


def match(
    *,
    rule_id: str,
    title: str,
    summary: str,
    severity: RuleSeverity,
    confidence: RuleConfidence,
    evidence: tuple[RuleEvidence, ...],
    subject_keys: tuple[str, ...],
    remediation: str | None = None,
) -> RuleMatch:
    return RuleMatch(
        rule_id=RuleId(rule_id),
        rule_version=RuleVersion.parse(RULE_VERSION),
        severity=severity,
        confidence=confidence,
        title=title,
        summary=summary,
        evidence=evidence,
        remediation=remediation or recommendation_for(rule_id),
        affected_entities=subject_keys,
        provenance=PACK_ID,
        subject_keys=subject_keys,
    )


def evidence_marker(
    *,
    item: MarkerFactEvidence,
    message: str,
    testing_category: TestCategory,
) -> RuleEvidence:
    line = item.line_start
    return RuleEvidence(
        kind=RuleEvidenceKind.FILE_LOCATION,
        subject_reference=item.evidence_id,
        message=message,
        safe_location=item.path,
        line_start=line,
        line_end=line,
        attributes={
            "evidence_id": item.evidence_id,
            "path": item.path,
            "marker_type": item.marker_type.value,
            "marker_text": item.marker_text,
            "testing_category": testing_category.value,
        },
        provenance=_PROVENANCE,
    )


def evidence_candidate(
    *,
    item: TestFileCandidateEvidence,
    message: str,
    testing_category: TestCategory,
) -> RuleEvidence:
    return RuleEvidence(
        kind=RuleEvidenceKind.FILE_LOCATION,
        subject_reference=item.evidence_id,
        message=message,
        safe_location=item.path,
        attributes={
            "evidence_id": item.evidence_id,
            "path": item.path,
            "role": item.role.value,
            "confirmation_level": item.confirmation_level.value,
            "language_hint": item.language_hint or "",
            "testing_category": testing_category.value,
        },
        provenance=_PROVENANCE,
    )


def evidence_framework(
    *,
    item: FrameworkFactEvidence,
    message: str,
    testing_category: TestCategory,
) -> RuleEvidence:
    return RuleEvidence(
        kind=RuleEvidenceKind.CONFIGURATION_KEY,
        subject_reference=item.evidence_id,
        message=message,
        safe_location=item.path,
        attributes={
            "evidence_id": item.evidence_id,
            "path": item.path,
            "framework": item.framework.value,
            "basis": item.basis.value,
            "declared_version": item.declared_version or "",
            "detail": (item.detail or "")[:200],
            "testing_category": testing_category.value,
        },
        provenance=_PROVENANCE,
    )


def evidence_coverage(
    *,
    item: CoverageFactEvidence,
    message: str,
    testing_category: TestCategory,
) -> RuleEvidence:
    return RuleEvidence(
        kind=RuleEvidenceKind.CONFIGURATION_KEY,
        subject_reference=item.evidence_id,
        message=message,
        safe_location=item.path,
        attributes={
            "evidence_id": item.evidence_id,
            "path": item.path,
            "fact_type": item.fact_type.value,
            "tool": item.tool.value if item.tool is not None else "",
            "detail": (item.detail or "")[:200],
            "testing_category": testing_category.value,
        },
        provenance=_PROVENANCE,
    )


def evidence_ci(
    *,
    item: CiTestInvocationFactEvidence,
    message: str,
    testing_category: TestCategory,
) -> RuleEvidence:
    return RuleEvidence(
        kind=RuleEvidenceKind.CONFIGURATION_KEY,
        subject_reference=item.evidence_id,
        message=message,
        safe_location=item.path,
        attributes={
            "evidence_id": item.evidence_id,
            "path": item.path,
            "job_or_step": item.job_or_step,
            "tool": item.tool,
            "command_projection": item.command_projection,
            "testing_category": testing_category.value,
        },
        provenance=_PROVENANCE,
    )


def framework_family_key(framework: TestFrameworkFamily) -> str:
    if framework in _JUNIT_FAMILY:
        return "junit_family"
    return framework.value


def frameworks_equivalent(
    left: TestFrameworkFamily, right: TestFrameworkFamily
) -> bool:
    return framework_family_key(left) == framework_family_key(right)


def languages_for_framework(framework: TestFrameworkFamily) -> frozenset[str]:
    return _FRAMEWORK_LANGUAGES.get(framework, frozenset())


def language_support_present(
    *,
    framework: TestFrameworkFamily,
    languages_represented: tuple[str, ...],
    file_candidates: tuple[TestFileCandidateEvidence, ...],
) -> bool:
    expected = languages_for_framework(framework)
    if not expected:
        return True
    represented = {item.strip().lower() for item in languages_represented if item}
    if represented & expected:
        return True
    for candidate in file_candidates:
        hint = (candidate.language_hint or "").strip().lower()
        if hint and hint in expected:
            return True
    return False


def is_disabled_or_skipped_marker(item: MarkerFactEvidence) -> bool:
    return item.marker_type in DISABLED_OR_SKIPPED_MARKER_TYPES


def is_considered_candidate(item: TestFileCandidateEvidence) -> bool:
    return item.role not in EXCLUDED_CANDIDATE_ROLES


def is_unconfirmed_candidate(item: TestFileCandidateEvidence) -> bool:
    return (
        item.confirmation_level
        is not EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
    )


def is_declared_test_framework(item: FrameworkFactEvidence) -> bool:
    if item.framework not in TEST_FRAMEWORKS:
        return False
    return item.basis in {
        FrameworkEvidenceBasis.DECLARED,
        FrameworkEvidenceBasis.CONFIGURED,
    }


def is_observed_test_framework(item: FrameworkFactEvidence) -> bool:
    if item.framework not in TEST_FRAMEWORKS:
        return False
    return item.basis is FrameworkEvidenceBasis.STRUCTURALLY_OBSERVED


def is_coverage_configuration(item: CoverageFactEvidence) -> bool:
    return item.fact_type is CoverageFactType.COVERAGE_CONFIGURATION


def severity_for_marker_count(count: int) -> RuleSeverity:
    if count >= TEST001_SEVERITY_MEDIUM_MIN:
        return RuleSeverity.MEDIUM
    if count >= TEST001_SEVERITY_LOW_MIN:
        return RuleSeverity.LOW
    return RuleSeverity.INFORMATIONAL


def severity_for_unconfirmed_ratio(ratio: float) -> RuleSeverity:
    if ratio < TEST002_INFORMATIONAL_RATIO_LT:
        return RuleSeverity.INFORMATIONAL
    return RuleSeverity.LOW


def enrich_finding_metadata(rule_id: str) -> dict[str, str]:
    category = category_for_rule(rule_id)
    return {
        "taxonomy_id": category.value,
        "testing_category": category.value,
        "assessment_dimensions": "testing",
        "business_impact": "unknown",
        "pack_id": PACK_ID,
        "pack_version": PACK_VERSION,
        "recommendation_effort_band": "unknown",
        "recommendation_validation": "static_evidence_only",
        "recommendation_rationale": recommendation_for(rule_id),
        "recommendation_expected_outcome": (
            "Improve repository-local test hygiene using typed evidence facts"
        ),
    }


def category_for_rule(rule_id: str) -> TestCategory:
    mapping = {
        RULE_DISABLED_OR_SKIPPED: TestCategory.DISABLED_TEST,
        RULE_UNCONFIRMED_CANDIDATES: TestCategory.TEST_STRUCTURE,
        RULE_DECLARED_WITHOUT_OBSERVATION: TestCategory.FRAMEWORK,
        RULE_COVERAGE_WITHOUT_CI_INVOCATION: TestCategory.COVERAGE_CONFIGURATION,
    }
    return mapping.get(rule_id, TestCategory.UNKNOWN)


def _sorted_matches(matches: list[RuleMatch]) -> SharedRuleEvaluationResult:
    if not matches:
        return SharedRuleEvaluationResult.not_matched()
    return SharedRuleEvaluationResult.matched(
        tuple(
            sorted(
                matches,
                key=lambda item: (
                    item.subject_keys,
                    str(item.rule_id),
                    item.summary,
                ),
            )
        )
    )
