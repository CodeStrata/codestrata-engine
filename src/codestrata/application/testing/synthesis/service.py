"""Deterministic Test synthesis from assessment inventory (Phase 4.6.5).

Consumes Test Assessment inventories, Findings, and rule-execution facts only.
Does not re-read repository files, recollect evidence, execute tests, or
reevaluate hygiene rules.
"""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.findings.models import Finding
from codestrata.domain.testing.assessment.enums import TestAssessmentStatus
from codestrata.domain.testing.assessment.models import (
    TestFindingInventory,
    TestLimitation,
    TestRuleInventory,
)
from codestrata.domain.testing.ids import (
    HYGIENE_RULE_IDS,
    RULE_COVERAGE_WITHOUT_CI_INVOCATION,
    RULE_DECLARED_WITHOUT_OBSERVATION,
    RULE_DISABLED_OR_SKIPPED,
    RULE_UNCONFIRMED_CANDIDATES,
)
from codestrata.domain.testing.synthesis.enums import (
    TestConclusionAudience,
    TestConclusionKind,
    TestRecommendationKind,
    TestSynthesisStatus,
    TestThemeKind,
    TestThemeScope,
)
from codestrata.domain.testing.synthesis.identifiers import (
    POLICY_COVERAGE_CI,
    POLICY_DISABLED,
    POLICY_DISABLED_SKIPPED,
    POLICY_DISCOVERY,
    POLICY_FRAMEWORK,
    POLICY_INSUFFICIENT,
    POLICY_LANDSCAPE,
    POLICY_NO_FINDINGS,
    POLICY_RULE_EXECUTION,
    POLICY_UNSUPPORTED_SCOPE,
    SYNTHESIS_VERSION,
    build_conclusion_id,
    build_recommendation_id,
    build_theme_id,
)
from codestrata.domain.testing.synthesis.models import (
    TestConclusion,
    TestingSynthesisResult,
    TestRecommendation,
    TestTheme,
)

_FINDING_REF_LIMIT = 32

_FORBIDDEN_WORDS = (
    "well tested",
    "testing passed",
    "tests passed",
    "release ready",
    "no testing issues",
    "tests are sufficient",
    "fully tested",
    "test coverage is adequate",
)


def _bound_ids(values: Sequence[str], limit: int) -> tuple[str, ...]:
    return tuple(sorted({item for item in values if item}))[:limit]


def _assert_safe_text(*parts: str) -> None:
    joined = " ".join(parts).lower()
    sanitized = (
        joined.replace("does not mean the repository is well tested", "")
        .replace("does not establish that the repository is well tested", "")
        .replace("does not establish that tests are sufficient", "")
        .replace("does not establish release readiness", "")
        .replace("or release ready", "")
        .replace("not release ready", "")
        .replace("zero findings does not mean", "")
        .replace("do not establish release readiness", "")
    )
    for phrase in _FORBIDDEN_WORDS:
        if phrase in sanitized:
            raise ValueError(f"forbidden synthesis wording: {phrase}")


def _make_conclusion(
    *,
    repository_id: str,
    policy_id: str,
    kind: TestConclusionKind,
    audience: TestConclusionAudience,
    title: str,
    summary: str,
    technical_interpretation: str,
    theme_ids: Sequence[str] = (),
    finding_ids: Sequence[str] = (),
    rule_ids: Sequence[str] = (),
    confidence: str = "high",
    metadata: dict[str, str] | None = None,
) -> TestConclusion:
    _assert_safe_text(title, summary, technical_interpretation)
    support = tuple(theme_ids) + tuple(finding_ids) + tuple(rule_ids)
    return TestConclusion(
        conclusion_id=build_conclusion_id(
            policy_id=policy_id,
            repository_id=repository_id,
            supporting_ids=support,
        ),
        policy_id=policy_id,
        kind=kind,
        audience=audience,
        title=title,
        summary=summary,
        technical_interpretation=technical_interpretation,
        theme_ids=_bound_ids(theme_ids, _FINDING_REF_LIMIT),
        finding_ids=_bound_ids(finding_ids, _FINDING_REF_LIMIT),
        rule_ids=_bound_ids(rule_ids, _FINDING_REF_LIMIT),
        confidence=confidence,
        metadata=metadata or {},
    )


def _make_recommendation(
    *,
    kind: TestRecommendationKind,
    action_key: str,
    title: str,
    action: str,
    rationale: str,
    conclusion_ids: Sequence[str],
    audience: TestConclusionAudience,
    theme_ids: Sequence[str] = (),
    finding_ids: Sequence[str] = (),
    rule_ids: Sequence[str] = (),
) -> TestRecommendation:
    _assert_safe_text(title, action, rationale)
    return TestRecommendation(
        recommendation_id=build_recommendation_id(
            conclusion_ids=conclusion_ids,
            action_key=action_key,
        ),
        kind=kind,
        title=title,
        action=action,
        rationale=rationale,
        conclusion_ids=_bound_ids(conclusion_ids, _FINDING_REF_LIMIT),
        theme_ids=_bound_ids(theme_ids, _FINDING_REF_LIMIT),
        finding_ids=_bound_ids(finding_ids, _FINDING_REF_LIMIT),
        rule_ids=_bound_ids(rule_ids, _FINDING_REF_LIMIT),
        audience=audience,
    )


def _findings_for_rule(
    findings: Sequence[Finding],
    rule_id: str,
) -> tuple[Finding, ...]:
    return tuple(item for item in findings if item.rule_id == rule_id)


def _rule_theme(
    *,
    kind: TestThemeKind,
    title: str,
    description: str,
    findings: Sequence[Finding],
    ordering_key: str,
) -> TestTheme | None:
    if not findings:
        return None
    _assert_safe_text(title, description)
    finding_ids = tuple(item.id for item in findings)
    rule_ids = tuple(sorted({item.rule_id for item in findings}))
    return TestTheme(
        theme_id=build_theme_id(
            kind=kind.value,
            scope=TestThemeScope.HYGIENE.value,
            subject=rule_ids[0] if rule_ids else "",
        ),
        kind=kind,
        title=title,
        description=description,
        scope=TestThemeScope.HYGIENE,
        finding_ids=_bound_ids(finding_ids, _FINDING_REF_LIMIT),
        rule_ids=rule_ids,
        counts={"finding_count": len(findings)},
        ordering_key=ordering_key,
    )


def _posture_summary(
    *,
    findings_count: int,
    rules_executed: int,
    rules_matched: int,
) -> str:
    if findings_count == 0:
        text = (
            f"{rules_executed} Test Hygiene rules executed with zero findings in "
            "the supported repository evidence scope. This summarizes hygiene "
            "signals only and does not establish release readiness."
        )
    else:
        text = (
            f"Test Hygiene inventory shows {findings_count} finding"
            f"{'' if findings_count == 1 else 's'} across {rules_matched} matched "
            f"rule{'s' if rules_matched != 1 else ''} of {rules_executed} executed. "
            "Implications remain informational to medium and do not establish "
            "release readiness."
        )
    _assert_safe_text(text)
    return text


def _link_recommendations(
    conclusions: list[TestConclusion],
    recommendations: Sequence[TestRecommendation],
) -> list[TestConclusion]:
    by_conclusion: dict[str, list[str]] = {}
    for item in recommendations:
        for conclusion_id in item.conclusion_ids:
            by_conclusion.setdefault(conclusion_id, []).append(item.recommendation_id)
    linked: list[TestConclusion] = []
    for conclusion in conclusions:
        ids = tuple(sorted(set(by_conclusion.get(conclusion.conclusion_id, ()))))
        if not ids:
            linked.append(conclusion)
            continue
        linked.append(conclusion.model_copy(update={"recommendation_ids": ids}))
    return linked


def synthesize_testing(
    *,
    repository_id: str,
    pack_enabled: bool,
    section_status: TestAssessmentStatus,
    findings: Sequence[Finding] = (),
    finding_inventory: TestFindingInventory | None = None,
    rule_inventory: TestRuleInventory | None = None,
    limitations: Sequence[TestLimitation] = (),
    evidence_status: str = "",
    include_synthesis: bool = True,
) -> TestingSynthesisResult:
    """Build deterministic Test synthesis from inventory facts."""

    if not include_synthesis:
        return TestingSynthesisResult(
            status=TestSynthesisStatus.NOT_REQUESTED,
            synthesis_version=SYNTHESIS_VERSION,
            diagnostics=("synthesis_not_requested",),
        )

    if (
        not pack_enabled
        or section_status is TestAssessmentStatus.DISABLED
        or section_status is TestAssessmentStatus.NOT_REQUESTED
    ):
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_DISABLED,
            kind=TestConclusionKind.SYNTHESIS_DISABLED,
            audience=TestConclusionAudience.STATUS,
            title="Test synthesis disabled",
            summary=(
                "Test synthesis was not generated because the Test pack or "
                "assessment section is disabled."
            ),
            technical_interpretation=(
                "Enable rules.testing and assessment.sections.testing to produce "
                "inventory-derived synthesis."
            ),
        )
        return TestingSynthesisResult(
            status=TestSynthesisStatus.DISABLED,
            synthesis_version=SYNTHESIS_VERSION,
            conclusions=(conclusion,),
            conclusion_ids=(conclusion.conclusion_id,),
            diagnostics=("synthesis_disabled",),
        )

    if section_status in {
        TestAssessmentStatus.INSUFFICIENT_EVIDENCE,
        TestAssessmentStatus.FAILED,
        TestAssessmentStatus.NOT_APPLICABLE,
    }:
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_INSUFFICIENT,
            kind=TestConclusionKind.INSUFFICIENT_EVIDENCE,
            audience=TestConclusionAudience.STATUS,
            title="Insufficient Test evidence for synthesis",
            summary=(
                "Test synthesis could not be fully generated because the "
                f"assessment status is {section_status.value}."
            ),
            technical_interpretation=(
                "Provide usable repository-testing evidence and successful rule "
                "evaluation before interpreting Test synthesis."
            ),
        )
        return TestingSynthesisResult(
            status=TestSynthesisStatus.INSUFFICIENT_EVIDENCE,
            synthesis_version=SYNTHESIS_VERSION,
            conclusions=(conclusion,),
            conclusion_ids=(conclusion.conclusion_id,),
            diagnostics=("synthesis_insufficient_evidence",),
        )

    ordered = tuple(sorted(findings, key=lambda item: (item.rule_id, item.id, item.title)))
    inventory = finding_inventory or TestFindingInventory(
        finding_ids=tuple(item.id for item in ordered),
        finding_count=len(ordered),
    )
    rules = rule_inventory or TestRuleInventory()
    rules_executed = rules.rules_executed or sum(1 for item in rules.entries if item.executed)
    if rules_executed == 0 and pack_enabled:
        rules_executed = len(HYGIENE_RULE_IDS)
    rules_matched = rules.rules_matched or sum(
        1 for item in rules.entries if item.evaluation_status == "matched"
    )
    rules_not_matched = rules.rules_not_matched
    finding_ids = tuple(inventory.finding_ids) or tuple(item.id for item in ordered)
    findings_count = inventory.finding_count or len(ordered)

    themes: list[TestTheme] = []
    conclusions: list[TestConclusion] = []
    recommendations: list[TestRecommendation] = []

    if findings_count == 0:
        landscape_desc = (
            f"{rules_executed} Test Hygiene rules executed and produced no "
            "findings within the supported repository evidence scope."
        )
    else:
        landscape_desc = (
            f"The supported Test Hygiene rules produced {findings_count} finding"
            f"{'' if findings_count == 1 else 's'} across "
            f"{rules_matched} matched rule{'s' if rules_matched != 1 else ''}."
        )
    _assert_safe_text(landscape_desc)
    landscape = TestTheme(
        theme_id=build_theme_id(
            kind=TestThemeKind.TESTING_HYGIENE_LANDSCAPE.value,
            scope=TestThemeScope.REPOSITORY.value,
        ),
        kind=TestThemeKind.TESTING_HYGIENE_LANDSCAPE,
        title="Testing hygiene landscape",
        description=landscape_desc,
        scope=TestThemeScope.REPOSITORY,
        finding_ids=_bound_ids(finding_ids, _FINDING_REF_LIMIT),
        rule_ids=tuple(HYGIENE_RULE_IDS),
        counts={
            "finding_count": findings_count,
            "rules_executed": rules_executed,
            "rules_matched": rules_matched,
        },
        ordering_key="00_landscape",
    )
    themes.append(landscape)
    conclusions.append(
        _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_LANDSCAPE,
            kind=TestConclusionKind.TESTING_HYGIENE_LANDSCAPE_IDENTIFIED,
            audience=TestConclusionAudience.REPOSITORY,
            title="Testing hygiene landscape identified",
            summary=landscape_desc,
            technical_interpretation=(
                "This conclusion summarizes supported Test Hygiene rule "
                "execution and finding counts only."
            ),
            theme_ids=(landscape.theme_id,),
            finding_ids=finding_ids,
            rule_ids=list(HYGIENE_RULE_IDS),
        )
    )

    coverage_desc = (
        f"Rule execution coverage: {rules_executed} executed, "
        f"{rules_matched} matched, {rules_not_matched} not matched"
        + (
            f"; evidence status {evidence_status}."
            if evidence_status
            else " within the registered hygiene pack."
        )
    )
    _assert_safe_text(coverage_desc)
    coverage_theme = TestTheme(
        theme_id=build_theme_id(
            kind=TestThemeKind.RULE_EXECUTION_COVERAGE.value,
            scope=TestThemeScope.COVERAGE.value,
        ),
        kind=TestThemeKind.RULE_EXECUTION_COVERAGE,
        title="Rule execution coverage",
        description=coverage_desc,
        scope=TestThemeScope.COVERAGE,
        rule_ids=tuple(HYGIENE_RULE_IDS),
        counts={
            "rules_planned": rules.rules_planned or len(HYGIENE_RULE_IDS),
            "rules_executed": rules_executed,
            "rules_matched": rules_matched,
            "rules_not_matched": rules_not_matched,
            "rules_not_applicable": rules.rules_not_applicable,
            "rules_failed": rules.rules_failed,
        },
        ordering_key="01_rule_execution",
    )
    themes.append(coverage_theme)
    conclusions.append(
        _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_RULE_EXECUTION,
            kind=TestConclusionKind.RULE_EXECUTION_SUMMARY,
            audience=TestConclusionAudience.COVERAGE,
            title="Test Hygiene rule execution summary",
            summary=coverage_desc,
            technical_interpretation=(
                "Applicable registered hygiene rules versus matched outcomes "
                "are inventory facts, not test-quality scores."
            ),
            theme_ids=(coverage_theme.theme_id,),
            rule_ids=list(HYGIENE_RULE_IDS),
        )
    )

    disabled_findings = _findings_for_rule(ordered, RULE_DISABLED_OR_SKIPPED)
    discovery_findings = _findings_for_rule(ordered, RULE_UNCONFIRMED_CANDIDATES)
    framework_findings = _findings_for_rule(ordered, RULE_DECLARED_WITHOUT_OBSERVATION)
    coverage_findings = _findings_for_rule(ordered, RULE_COVERAGE_WITHOUT_CI_INVOCATION)

    if disabled_findings:
        theme = _rule_theme(
            kind=TestThemeKind.DISABLED_OR_SKIPPED_TESTS,
            title="Disabled or skipped tests",
            description=(
                f"{len(disabled_findings)} finding"
                f"{'' if len(disabled_findings) == 1 else 's'} report disabled, "
                "skipped, or ignored test markers in repository evidence."
            ),
            findings=disabled_findings,
            ordering_key="10_disabled_skipped",
        )
        if theme is not None:
            themes.append(theme)
            conclusion = _make_conclusion(
                repository_id=repository_id,
                policy_id=POLICY_DISABLED_SKIPPED,
                kind=TestConclusionKind.DISABLED_OR_SKIPPED_TESTS_OBSERVED,
                audience=TestConclusionAudience.HYGIENE,
                title="Disabled or skipped tests observed",
                summary=theme.description,
                technical_interpretation=(
                    "Disabled markers are repository-local hygiene signals. "
                    "Severity implications stay informational to medium and do "
                    "not judge whether skips are justified."
                ),
                theme_ids=(theme.theme_id,),
                finding_ids=theme.finding_ids,
                rule_ids=(RULE_DISABLED_OR_SKIPPED,),
                confidence="high",
            )
            conclusions.append(conclusion)
            recommendations.append(
                _make_recommendation(
                    kind=TestRecommendationKind.REVIEW_DISABLED_OR_SKIPPED_TESTS,
                    action_key="review-disabled-or-skipped-tests",
                    title="Review disabled or skipped tests",
                    action=(
                        "Review disabled, skipped, or ignored markers referenced "
                        "by the linked findings and confirm each remains intentional."
                    ),
                    rationale=(
                        "TEST-001 matched on repository-observable markers; "
                        "review keeps hygiene signals actionable without "
                        "claiming test failure."
                    ),
                    conclusion_ids=(conclusion.conclusion_id,),
                    audience=TestConclusionAudience.HYGIENE,
                    theme_ids=(theme.theme_id,),
                    finding_ids=theme.finding_ids,
                    rule_ids=(RULE_DISABLED_OR_SKIPPED,),
                )
            )

    if discovery_findings:
        theme = _rule_theme(
            kind=TestThemeKind.TEST_DISCOVERY_CONFIDENCE,
            title="Test discovery confidence",
            description=(
                f"{len(discovery_findings)} finding"
                f"{'' if len(discovery_findings) == 1 else 's'} indicate material "
                "unconfirmed test-file candidates under discovery heuristics."
            ),
            findings=discovery_findings,
            ordering_key="11_discovery",
        )
        if theme is not None:
            themes.append(theme)
            conclusion = _make_conclusion(
                repository_id=repository_id,
                policy_id=POLICY_DISCOVERY,
                kind=TestConclusionKind.TEST_DISCOVERY_UNCERTAINTY_OBSERVED,
                audience=TestConclusionAudience.HYGIENE,
                title="Test discovery uncertainty observed",
                summary=theme.description,
                technical_interpretation=(
                    "Unconfirmed candidates describe discovery uncertainty, not "
                    "missing tests or failed execution."
                ),
                theme_ids=(theme.theme_id,),
                finding_ids=theme.finding_ids,
                rule_ids=(RULE_UNCONFIRMED_CANDIDATES,),
                confidence="medium",
            )
            conclusions.append(conclusion)
            recommendations.append(
                _make_recommendation(
                    kind=TestRecommendationKind.IMPROVE_TEST_DISCOVERY_SIGNALING,
                    action_key="improve-test-discovery-signaling",
                    title="Improve test discovery signaling",
                    action=(
                        "Strengthen naming, layout, or framework markers so "
                        "candidate test files are confirmed by repository evidence."
                    ),
                    rationale=(
                        "TEST-002 matched on unconfirmed candidates; clearer "
                        "signals reduce discovery ambiguity."
                    ),
                    conclusion_ids=(conclusion.conclusion_id,),
                    audience=TestConclusionAudience.HYGIENE,
                    theme_ids=(theme.theme_id,),
                    finding_ids=theme.finding_ids,
                    rule_ids=(RULE_UNCONFIRMED_CANDIDATES,),
                )
            )

    if framework_findings:
        theme = _rule_theme(
            kind=TestThemeKind.FRAMEWORK_DECLARATION_CONSISTENCY,
            title="Framework declaration consistency",
            description=(
                f"{len(framework_findings)} finding"
                f"{'' if len(framework_findings) == 1 else 's'} report declared "
                "test frameworks without matching structural observation."
            ),
            findings=framework_findings,
            ordering_key="12_framework",
        )
        if theme is not None:
            themes.append(theme)
            conclusion = _make_conclusion(
                repository_id=repository_id,
                policy_id=POLICY_FRAMEWORK,
                kind=TestConclusionKind.FRAMEWORK_DECLARATION_GAP_OBSERVED,
                audience=TestConclusionAudience.HYGIENE,
                title="Framework declaration gap observed",
                summary=theme.description,
                technical_interpretation=(
                    "Declaration-without-observation is a consistency signal "
                    "within supported evidence; it is not a runtime test result."
                ),
                theme_ids=(theme.theme_id,),
                finding_ids=theme.finding_ids,
                rule_ids=(RULE_DECLARED_WITHOUT_OBSERVATION,),
                confidence="high",
            )
            conclusions.append(conclusion)
            recommendations.append(
                _make_recommendation(
                    kind=TestRecommendationKind.ALIGN_FRAMEWORK_DECLARATION_AND_OBSERVATION,
                    action_key="align-framework-declaration-and-observation",
                    title="Align framework declaration and observation",
                    action=(
                        "Reconcile declared test frameworks with observed test "
                        "structure, or remove stale declarations."
                    ),
                    rationale=(
                        "TEST-003 matched on declaration/observation mismatch "
                        "in repository-testing evidence."
                    ),
                    conclusion_ids=(conclusion.conclusion_id,),
                    audience=TestConclusionAudience.HYGIENE,
                    theme_ids=(theme.theme_id,),
                    finding_ids=theme.finding_ids,
                    rule_ids=(RULE_DECLARED_WITHOUT_OBSERVATION,),
                )
            )

    if coverage_findings:
        theme = _rule_theme(
            kind=TestThemeKind.COVERAGE_AND_CI_ALIGNMENT,
            title="Coverage and CI alignment",
            description=(
                f"{len(coverage_findings)} finding"
                f"{'' if len(coverage_findings) == 1 else 's'} report coverage "
                "configuration without a matching CI test invocation signal."
            ),
            findings=coverage_findings,
            ordering_key="13_coverage_ci",
        )
        if theme is not None:
            themes.append(theme)
            conclusion = _make_conclusion(
                repository_id=repository_id,
                policy_id=POLICY_COVERAGE_CI,
                kind=TestConclusionKind.COVERAGE_WITHOUT_CI_OBSERVED,
                audience=TestConclusionAudience.COVERAGE,
                title="Coverage configuration without CI invocation observed",
                summary=theme.description,
                technical_interpretation=(
                    "This compares coverage configuration facts to CI invocation "
                    "facts only. Runtime coverage percentages are not measured."
                ),
                theme_ids=(theme.theme_id,),
                finding_ids=theme.finding_ids,
                rule_ids=(RULE_COVERAGE_WITHOUT_CI_INVOCATION,),
                confidence="medium",
            )
            conclusions.append(conclusion)
            recommendations.append(
                _make_recommendation(
                    kind=TestRecommendationKind.ALIGN_COVERAGE_CONFIG_WITH_CI,
                    action_key="align-coverage-config-with-ci",
                    title="Align coverage configuration with CI",
                    action=(
                        "Ensure CI workflows invoke tests in a way that matches "
                        "declared coverage tooling, or adjust coverage config "
                        "to match actual CI practice."
                    ),
                    rationale=(
                        "TEST-005 matched on coverage configuration without CI "
                        "invocation alignment in repository evidence."
                    ),
                    conclusion_ids=(conclusion.conclusion_id,),
                    audience=TestConclusionAudience.COVERAGE,
                    theme_ids=(theme.theme_id,),
                    finding_ids=theme.finding_ids,
                    rule_ids=(RULE_COVERAGE_WITHOUT_CI_INVOCATION,),
                )
            )

    if findings_count == 0 and rules_executed > 0:
        theme = TestTheme(
            theme_id=build_theme_id(
                kind=TestThemeKind.NO_HYGIENE_FINDINGS.value,
                scope=TestThemeScope.STATUS.value,
            ),
            kind=TestThemeKind.NO_HYGIENE_FINDINGS,
            title="No hygiene findings in supported scope",
            description=(
                f"No Test Hygiene findings were emitted by the {rules_executed} "
                "enabled rules within the supported repository evidence scope."
            ),
            scope=TestThemeScope.STATUS,
            rule_ids=tuple(HYGIENE_RULE_IDS),
            counts={"rules_executed": rules_executed, "finding_count": 0},
            ordering_key="20_no_findings",
        )
        _assert_safe_text(theme.description)
        themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_NO_FINDINGS,
            kind=TestConclusionKind.NO_HYGIENE_FINDINGS_IN_SUPPORTED_SCOPE,
            audience=TestConclusionAudience.STATUS,
            title="No hygiene findings in supported scope",
            summary=theme.description,
            technical_interpretation=(
                "Zero findings is a neutral inventory outcome for enabled "
                "hygiene rules. It does not establish that tests are sufficient."
            ),
            theme_ids=(theme.theme_id,),
            rule_ids=list(HYGIENE_RULE_IDS),
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=TestRecommendationKind.ACKNOWLEDGE_NO_HYGIENE_FINDINGS_IN_SUPPORTED_SCOPE,
                action_key="acknowledge-no-hygiene-findings",
                title="Acknowledge zero hygiene findings in supported scope",
                action=(
                    "Treat zero Test Hygiene findings as a bounded inventory "
                    "outcome for the supported evidence and rule pack only."
                ),
                rationale=(
                    "Neutral acknowledgment prevents overstating risk or "
                    "quality from an empty finding set."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=TestConclusionAudience.STATUS,
                theme_ids=(theme.theme_id,),
                rule_ids=list(HYGIENE_RULE_IDS),
            )
        )

    if limitations:
        limitation_ids = tuple(item.limitation_id for item in limitations)
        theme = TestTheme(
            theme_id=build_theme_id(
                kind=TestThemeKind.UNSUPPORTED_ANALYSIS_SCOPE.value,
                scope=TestThemeScope.STATUS.value,
            ),
            kind=TestThemeKind.UNSUPPORTED_ANALYSIS_SCOPE,
            title="Unsupported test analysis scope",
            description=(
                f"{len(limitations)} documented limitation"
                f"{'' if len(limitations) == 1 else 's'} bound this assessment: "
                "test execution and runtime coverage measurement remain out of scope."
            ),
            scope=TestThemeScope.STATUS,
            counts={"limitation_count": len(limitations)},
            ordering_key="30_unsupported_scope",
        )
        _assert_safe_text(theme.description)
        themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_UNSUPPORTED_SCOPE,
            kind=TestConclusionKind.UNSUPPORTED_TEST_ANALYSIS_SCOPE,
            audience=TestConclusionAudience.STATUS,
            title="Unsupported test analysis scope acknowledged",
            summary=theme.description,
            technical_interpretation=(
                "Synthesis uses repository-observable hygiene evidence only. "
                "Pass/fail execution and runtime coverage percentages are not "
                "evaluated in this phase."
            ),
            theme_ids=(theme.theme_id,),
            metadata={"limitation_count": str(len(limitation_ids))},
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=TestRecommendationKind.ACKNOWLEDGE_UNSUPPORTED_TEST_ANALYSIS_SCOPE,
                action_key="acknowledge-unsupported-test-analysis-scope",
                title="Acknowledge unsupported test analysis scope",
                action=(
                    "Interpret Test synthesis as hygiene inventory only until "
                    "execution and runtime coverage capabilities exist."
                ),
                rationale=(
                    "Documented limitations keep conclusions from overstating "
                    "test quality or release readiness."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=TestConclusionAudience.STATUS,
                theme_ids=(theme.theme_id,),
            )
        )

    themes_sorted = tuple(sorted(themes, key=lambda item: (item.ordering_key, item.theme_id)))
    recommendations_sorted = tuple(
        sorted(recommendations, key=lambda item: (item.kind.value, item.recommendation_id))
    )
    # Dedupe recommendations by kind (keep first after sort).
    deduped: list[TestRecommendation] = []
    seen_kinds: set[str] = set()
    for item in recommendations_sorted:
        if item.kind.value in seen_kinds:
            continue
        seen_kinds.add(item.kind.value)
        deduped.append(item)
    conclusions_linked = _link_recommendations(conclusions, deduped)
    conclusions_sorted = tuple(
        sorted(
            conclusions_linked,
            key=lambda item: (item.kind.value, item.conclusion_id),
        )
    )
    posture = _posture_summary(
        findings_count=findings_count,
        rules_executed=rules_executed,
        rules_matched=rules_matched,
    )
    status = TestSynthesisStatus.EMPTY if findings_count == 0 else TestSynthesisStatus.SUCCEEDED
    return TestingSynthesisResult(
        status=status,
        synthesis_version=SYNTHESIS_VERSION,
        overall_posture_summary=posture,
        themes=themes_sorted,
        theme_ids=tuple(item.theme_id for item in themes_sorted),
        conclusions=conclusions_sorted,
        conclusion_ids=tuple(item.conclusion_id for item in conclusions_sorted),
        recommendations=tuple(deduped),
        recommendation_ids=tuple(item.recommendation_id for item in deduped),
    )
