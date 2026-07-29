"""Test Hygiene SharedRules (Phase 4.6.3).

Rules consume AggregatedRepositoryTestingEvidence only. They never re-read
repository files, execute tests, or invent runtime coverage conclusions.
"""

from __future__ import annotations

from collections import Counter

from codestrata.application.rules.testing.helpers import (
    TEST001_HOTSPOT_MAX_PATHS,
    TEST001_HOTSPOT_MIN_COUNT,
    TEST001_MAX_MARKER_EVIDENCE,
    TEST002_MIN_CONSIDERED,
    TEST002_MIN_RATIO,
    TEST002_MIN_UNCONFIRMED,
    _sorted_matches,
    evidence_candidate,
    evidence_coverage,
    evidence_framework,
    evidence_is_usable,
    evidence_marker,
    frameworks_equivalent,
    is_considered_candidate,
    is_coverage_configuration,
    is_declared_test_framework,
    is_disabled_or_skipped_marker,
    is_observed_test_framework,
    is_unconfirmed_candidate,
    language_support_present,
    make_metadata,
    match,
    repository_testing_evidence,
    severity_for_marker_count,
    severity_for_unconfirmed_ratio,
)
from codestrata.domain.evidence.repository_testing.models import (
    FrameworkFactEvidence,
    MarkerFactEvidence,
)
from codestrata.domain.rules.applicability import RuleApplicability
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import (
    RuleConfidence,
    RuleEvidenceKind,
    RuleSeverity,
    RuleSkipReason,
)
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.metadata import RuleMetadata
from codestrata.domain.rules.results import SharedRuleEvaluationResult
from codestrata.domain.testing.ids import (
    RULE_COVERAGE_WITHOUT_CI_INVOCATION,
    RULE_DECLARED_WITHOUT_OBSERVATION,
    RULE_DISABLED_OR_SKIPPED,
    RULE_UNCONFIRMED_CANDIDATES,
)
from codestrata.domain.testing.taxonomy import TestCategory


def _testing_applicability(context: RuleExecutionContext) -> RuleApplicability:
    evidence = repository_testing_evidence(context)
    if evidence is None:
        return RuleApplicability.not_applicable(
            reason_code=RuleSkipReason.OTHER,
            message="Repository-testing evidence unavailable",
        )
    if not evidence_is_usable(evidence):
        return RuleApplicability.not_applicable(
            reason_code=RuleSkipReason.OTHER,
            message=(
                f"Repository-testing evidence status is {evidence.status.value}"
            ),
        )
    return RuleApplicability.applicable()


class DisabledOrSkippedMarkersRule:
    """Flags confirmed disabled/skipped/quarantined marker observations."""

    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_DISABLED_OR_SKIPPED,
            title="Disabled or skipped tests detected",
            description=(
                "Detects repository-observable disabled, ignored, skipped, "
                "conditional-skip, quarantined, or expected-failure markers. "
                "Does not claim tests are obsolete, failing, or unjustified."
            ),
            remediation=(
                "Review disabled or skipped markers and restore or remove them "
                "intentionally."
            ),
            severity=severity_for_marker_count(1),
        )

    def evaluate_applicability(
        self, context: RuleExecutionContext
    ) -> RuleApplicability:
        return _testing_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_testing_evidence(context)
        assert evidence is not None
        by_id: dict[str, MarkerFactEvidence] = {}
        for item in evidence.marker_facts:
            if not is_disabled_or_skipped_marker(item):
                continue
            by_id.setdefault(item.evidence_id, item)
        markers = sorted(
            by_id.values(),
            key=lambda item: (item.path, item.marker_type.value, item.evidence_id),
        )
        if not markers:
            return SharedRuleEvaluationResult.not_matched()

        count = len(markers)
        type_counts = Counter(item.marker_type.value for item in markers)
        path_counts = Counter(item.path for item in markers)
        hotspots = [
            (path, path_count)
            for path, path_count in sorted(
                path_counts.items(),
                key=lambda pair: (-pair[1], pair[0]),
            )
            if path_count >= TEST001_HOTSPOT_MIN_COUNT
        ][:TEST001_HOTSPOT_MAX_PATHS]

        hotspot_text = "; ".join(
            f"{path} ({path_count})" for path, path_count in hotspots
        )
        type_text = ", ".join(
            f"{name}={value}"
            for name, value in sorted(type_counts.items(), key=lambda pair: pair[0])
        )
        summary = (
            f"Observed {count} disabled or skipped test marker"
            f"{'' if count == 1 else 's'}"
            f" ({type_text})."
        )
        if hotspot_text:
            summary = f"{summary} Concentrated paths: {hotspot_text}."

        category = TestCategory.DISABLED_TEST
        evidence_items: list[RuleEvidence] = [
            RuleEvidence(
                kind=RuleEvidenceKind.REPOSITORY_FACT,
                subject_reference=f"{RULE_DISABLED_OR_SKIPPED}:markers",
                message=f"disabled_or_skipped_marker_count={count}",
                attributes={
                    "marker_count": str(count),
                    "marker_types": type_text,
                    "hotspot_paths": hotspot_text,
                    "testing_category": category.value,
                },
                provenance="aggregated_repository_testing_evidence",
            )
        ]
        for path, path_count in hotspots:
            evidence_items.append(
                RuleEvidence(
                    kind=RuleEvidenceKind.FILE_LOCATION,
                    subject_reference=f"{RULE_DISABLED_OR_SKIPPED}:hotspot:{path}",
                    message=f"marker_count={path_count}",
                    safe_location=path,
                    attributes={
                        "path": path,
                        "marker_count": str(path_count),
                        "testing_category": category.value,
                    },
                    provenance="aggregated_repository_testing_evidence",
                )
            )
        for item in markers[:TEST001_MAX_MARKER_EVIDENCE]:
            evidence_items.append(
                evidence_marker(
                    item=item,
                    message=(
                        f"marker_type={item.marker_type.value}; "
                        f"marker_text={item.marker_text}"
                    ),
                    testing_category=category,
                )
            )

        return _sorted_matches(
            [
                match(
                    rule_id=RULE_DISABLED_OR_SKIPPED,
                    title="Disabled or skipped tests detected",
                    summary=summary,
                    severity=severity_for_marker_count(count),
                    confidence=RuleConfidence.HIGH,
                    evidence=tuple(evidence_items),
                    subject_keys=(
                        RULE_DISABLED_OR_SKIPPED,
                        "markers",
                        str(count),
                    ),
                )
            ]
        )


class UnconfirmedCandidatesRule:
    """Flags material unconfirmed test-candidate ratios (not small-repo noise)."""

    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_UNCONFIRMED_CANDIDATES,
            title="Material test candidates lack structural confirmation",
            description=(
                "Detects when a material portion of discovered test candidates "
                "could not be structurally confirmed. Excludes fixtures, "
                "support, configuration, reports, and non-test candidates."
            ),
            remediation=(
                "Review ambiguous candidates and strengthen structural test "
                "markers where tests are intended."
            ),
        )

    def evaluate_applicability(
        self, context: RuleExecutionContext
    ) -> RuleApplicability:
        return _testing_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_testing_evidence(context)
        assert evidence is not None
        considered = [
            item
            for item in evidence.file_candidates
            if is_considered_candidate(item)
        ]
        unconfirmed = [
            item for item in considered if is_unconfirmed_candidate(item)
        ]
        considered_count = len(considered)
        unconfirmed_count = len(unconfirmed)
        if considered_count < TEST002_MIN_CONSIDERED:
            return SharedRuleEvaluationResult.not_matched()
        if unconfirmed_count < TEST002_MIN_UNCONFIRMED:
            return SharedRuleEvaluationResult.not_matched()
        ratio = unconfirmed_count / considered_count
        if ratio < TEST002_MIN_RATIO:
            return SharedRuleEvaluationResult.not_matched()

        category = TestCategory.TEST_STRUCTURE
        sample = sorted(
            unconfirmed,
            key=lambda item: (item.path, item.evidence_id),
        )[:10]
        evidence_items: list[RuleEvidence] = [
            RuleEvidence(
                kind=RuleEvidenceKind.REPOSITORY_FACT,
                subject_reference=f"{RULE_UNCONFIRMED_CANDIDATES}:ratio",
                message=(
                    f"unconfirmed={unconfirmed_count}; "
                    f"considered={considered_count}; "
                    f"ratio={ratio:.4f}"
                ),
                attributes={
                    "considered_count": str(considered_count),
                    "unconfirmed_count": str(unconfirmed_count),
                    "unconfirmed_ratio": f"{ratio:.4f}",
                    "testing_category": category.value,
                },
                provenance="aggregated_repository_testing_evidence",
            )
        ]
        for item in sample:
            evidence_items.append(
                evidence_candidate(
                    item=item,
                    message=(
                        f"confirmation_level={item.confirmation_level.value}; "
                        f"role={item.role.value}"
                    ),
                    testing_category=category,
                )
            )

        return _sorted_matches(
            [
                match(
                    rule_id=RULE_UNCONFIRMED_CANDIDATES,
                    title="Material test candidates lack structural confirmation",
                    summary=(
                        "A material portion of discovered test candidates could "
                        "not be structurally confirmed as tests."
                    ),
                    severity=severity_for_unconfirmed_ratio(ratio),
                    confidence=RuleConfidence.MEDIUM,
                    evidence=tuple(evidence_items),
                    subject_keys=(
                        RULE_UNCONFIRMED_CANDIDATES,
                        "unconfirmed",
                        str(unconfirmed_count),
                        str(considered_count),
                    ),
                )
            ]
        )


class DeclaredWithoutObservationRule:
    """Flags declared test frameworks without matching structural observation."""

    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_DECLARED_WITHOUT_OBSERVATION,
            title="Declared test framework lacks structural observation",
            description=(
                "Detects test frameworks declared or configured in build/"
                "dependency manifests without a corresponding structurally "
                "observed usage of the same framework family. Does not claim "
                "the framework is unused."
            ),
            remediation=(
                "Confirm whether declared frameworks remain needed or whether "
                "tests exist outside inspected boundaries."
            ),
        )

    def evaluate_applicability(
        self, context: RuleExecutionContext
    ) -> RuleApplicability:
        return _testing_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_testing_evidence(context)
        assert evidence is not None
        if evidence.coverage.candidate_files_inspected == 0:
            return SharedRuleEvaluationResult.not_matched()

        declared_items = [
            item
            for item in evidence.framework_facts
            if is_declared_test_framework(item)
        ]
        observed_frameworks = [
            item.framework
            for item in evidence.framework_facts
            if is_observed_test_framework(item)
        ]
        declared_by_framework: dict[str, FrameworkFactEvidence] = {}
        for item in declared_items:
            declared_by_framework.setdefault(item.framework.value, item)

        unmatched: list[FrameworkFactEvidence] = []
        for framework_value in sorted(declared_by_framework):
            item = declared_by_framework[framework_value]
            framework = item.framework
            if any(
                frameworks_equivalent(framework, observed)
                for observed in observed_frameworks
            ):
                continue
            if not language_support_present(
                framework=framework,
                languages_represented=evidence.coverage.languages_represented,
                file_candidates=evidence.file_candidates,
            ):
                continue
            unmatched.append(item)

        if not unmatched:
            return SharedRuleEvaluationResult.not_matched()

        framework_names = sorted({item.framework.value for item in unmatched})
        category = TestCategory.FRAMEWORK
        evidence_items = [
            evidence_framework(
                item=item,
                message=(
                    f"framework={item.framework.value}; basis={item.basis.value}; "
                    "no matching structural observation"
                ),
                testing_category=category,
            )
            for item in sorted(
                unmatched,
                key=lambda entry: (
                    entry.framework.value,
                    entry.path,
                    entry.evidence_id,
                ),
            )
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_DECLARED_WITHOUT_OBSERVATION,
                    title="Declared test framework lacks structural observation",
                    summary=(
                        "Declared test framework(s) without corresponding "
                        "structural observation: "
                        + ", ".join(framework_names)
                        + "."
                    ),
                    severity=RuleSeverity.LOW,
                    confidence=RuleConfidence.MEDIUM,
                    evidence=tuple(evidence_items),
                    subject_keys=(
                        RULE_DECLARED_WITHOUT_OBSERVATION,
                        "declared_without_observation",
                        ",".join(framework_names),
                    ),
                )
            ]
        )


class CoverageWithoutCiInvocationRule:
    """Flags coverage configuration when CI was inspected without invocations."""

    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_COVERAGE_WITHOUT_CI_INVOCATION,
            title="Coverage configuration without CI test invocation",
            description=(
                "Detects coverage configuration when CI files were inspected "
                "but no test or coverage invocation fact was observed. Does "
                "not claim CI never runs tests or that coverage is uncollected."
            ),
            remediation=(
                "Add an explicit test or coverage command to CI when coverage "
                "configuration is intended to be enforced."
            ),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(
        self, context: RuleExecutionContext
    ) -> RuleApplicability:
        return _testing_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_testing_evidence(context)
        assert evidence is not None
        coverage_items = [
            item for item in evidence.coverage_facts if is_coverage_configuration(item)
        ]
        has_coverage = bool(coverage_items) or (
            evidence.coverage.coverage_configurations > 0
        )
        if not has_coverage:
            return SharedRuleEvaluationResult.not_matched()
        if evidence.coverage.ci_files_inspected == 0:
            return SharedRuleEvaluationResult.not_matched()
        if evidence.ci_test_invocation_facts:
            return SharedRuleEvaluationResult.not_matched()

        category = TestCategory.COVERAGE_CONFIGURATION
        if coverage_items:
            evidence_items = tuple(
                evidence_coverage(
                    item=item,
                    message=(
                        f"fact_type={item.fact_type.value}; "
                        "no CI test/coverage invocation observed"
                    ),
                    testing_category=category,
                )
                for item in sorted(
                    coverage_items,
                    key=lambda entry: (entry.path, entry.evidence_id),
                )
            )
        else:
            evidence_items = (
                RuleEvidence(
                    kind=RuleEvidenceKind.REPOSITORY_FACT,
                    subject_reference=(
                        f"{RULE_COVERAGE_WITHOUT_CI_INVOCATION}:coverage_config"
                    ),
                    message=(
                        "coverage_configurations="
                        f"{evidence.coverage.coverage_configurations}"
                    ),
                    attributes={
                        "coverage_configurations": str(
                            evidence.coverage.coverage_configurations
                        ),
                        "ci_files_inspected": str(
                            evidence.coverage.ci_files_inspected
                        ),
                        "testing_category": category.value,
                    },
                    provenance="aggregated_repository_testing_evidence",
                ),
            )

        return _sorted_matches(
            [
                match(
                    rule_id=RULE_COVERAGE_WITHOUT_CI_INVOCATION,
                    title="Coverage configuration without CI test invocation",
                    summary=(
                        "Coverage configuration was detected, but no "
                        "corresponding test or coverage command was observed "
                        "in the inspected CI configuration."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=RuleConfidence.MEDIUM,
                    evidence=evidence_items,
                    subject_keys=(
                        RULE_COVERAGE_WITHOUT_CI_INVOCATION,
                        "coverage_without_ci",
                        str(evidence.coverage.coverage_configurations),
                        str(evidence.coverage.ci_files_inspected),
                    ),
                )
            ]
        )
