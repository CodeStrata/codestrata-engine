"""Deterministic AI Readiness synthesis from assessment inventory (Phase 4.8.5).

Consumes AI Readiness Assessment inventories, Findings, and rule-execution facts
only. Does not re-read repository files, recollect evidence, or reevaluate
hygiene rules.
"""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.ai_readiness.assessment.enums import AiReadinessAssessmentStatus
from codestrata.domain.ai_readiness.assessment.models import (
    AiReadinessCapabilityFamilyInventory,
    AiReadinessFindingInventory,
    AiReadinessLimitation,
    AiReadinessRuleInventory,
)
from codestrata.domain.ai_readiness.ids import (
    HYGIENE_RULE_IDS,
    RULE_AI_WITHOUT_OBSERVABILITY,
    RULE_API_BOUNDARIES,
    RULE_ARCHITECTURE_DOCS,
    RULE_BROAD_FOUNDATIONS,
    RULE_DATA_ACCESS,
    RULE_LIMITED_API_BOUNDARIES,
    RULE_LIMITED_DOCUMENTATION,
    RULE_LIMITED_FOUNDATIONS,
    RULE_LLM_SDK,
    RULE_MCP_TOOLS,
    RULE_OBSERVABILITY_GOVERNANCE,
    RULE_PROMPT_ASSETS,
    RULE_RAG_PIPELINE,
    RULE_SEARCH_RETRIEVAL,
    RULE_STRUCTURED_API_SPEC,
    RULE_VECTOR_EMBEDDINGS,
    RULE_WORKFLOW_AGENT,
)
from codestrata.domain.ai_readiness.synthesis.enums import (
    AiReadinessConclusionAudience,
    AiReadinessConclusionKind,
    AiReadinessRecommendationKind,
    AiReadinessSynthesisStatus,
    AiReadinessThemeKind,
    AiReadinessThemeScope,
)
from codestrata.domain.ai_readiness.synthesis.identifiers import (
    POLICY_AI_INTEGRATION,
    POLICY_API_BOUNDARIES,
    POLICY_BROAD,
    POLICY_DATA_RETRIEVAL,
    POLICY_DISABLED,
    POLICY_DOCUMENTATION,
    POLICY_INSUFFICIENT,
    POLICY_LANDSCAPE,
    POLICY_LIMITED,
    POLICY_MCP_TOOLS,
    POLICY_NO_FINDINGS,
    POLICY_OBSERVABILITY,
    POLICY_RULE_EXECUTION,
    POLICY_UNSUPPORTED_SCOPE,
    POLICY_WORKFLOW_AGENT,
    SYNTHESIS_VERSION,
    build_conclusion_id,
    build_recommendation_id,
    build_theme_id,
)
from codestrata.domain.ai_readiness.synthesis.models import (
    AiReadinessConclusion,
    AiReadinessRecommendation,
    AiReadinessSynthesisResult,
    AiReadinessTheme,
)
from codestrata.domain.findings.models import Finding

_FINDING_REF_LIMIT = 32

_FORBIDDEN_WORDS = (
    "ai ready",
    "is ai ready",
    "are ai ready",
    "agent ready",
    "agent-ready",
    "rag ready",
    "rag-ready",
    "fully ai-enabled",
    "fully ai enabled",
    "production ready",
    "modernize",
    "modernisation",
    "modernization path",
    "readiness score",
    "readiness grade",
    "implement rag",
    "migrate to",
    "no ai issues",
)


def _bound_ids(values: Sequence[str], limit: int) -> tuple[str, ...]:
    return tuple(sorted({item for item in values if item}))[:limit]


def _assert_safe_text(*parts: str) -> None:
    joined = " ".join(parts).lower()
    sanitized = (
        joined.replace("does not establish that the repository is ai ready", "")
        .replace("do not establish that the repository is ai ready", "")
        .replace("does not mean the repository is ai ready", "")
        .replace("the repository is ai ready", "")
        .replace("does not establish ai readiness", "")
        .replace("do not establish ai readiness", "")
        .replace("without claiming ai readiness", "")
        .replace("from claiming ai readiness", "")
        .replace("claiming ai readiness", "")
        .replace("not readiness scores", "")
        .replace("readiness scoring", "")
        .replace("readiness scores", "")
        .replace("zero findings does not mean", "")
        .replace("does not claim ai usage is absent", "")
        .replace("suitable for rag", "")
        .replace("is ai ready", "")
        .replace("are ai ready", "")
        .replace("not ai ready", "")
        .replace("ai readiness", "")
        .replace("agent ready", "")
        .replace("agent-ready", "")
    )
    for phrase in _FORBIDDEN_WORDS:
        if phrase in sanitized:
            raise ValueError(f"forbidden synthesis wording: {phrase}")


def _make_conclusion(
    *,
    repository_id: str,
    policy_id: str,
    kind: AiReadinessConclusionKind,
    audience: AiReadinessConclusionAudience,
    title: str,
    summary: str,
    technical_interpretation: str,
    theme_ids: Sequence[str] = (),
    finding_ids: Sequence[str] = (),
    rule_ids: Sequence[str] = (),
    confidence: str = "high",
    metadata: dict[str, str] | None = None,
) -> AiReadinessConclusion:
    _assert_safe_text(title, summary, technical_interpretation)
    support = tuple(theme_ids) + tuple(finding_ids) + tuple(rule_ids)
    return AiReadinessConclusion(
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
    kind: AiReadinessRecommendationKind,
    action_key: str,
    title: str,
    action: str,
    rationale: str,
    conclusion_ids: Sequence[str],
    audience: AiReadinessConclusionAudience,
    theme_ids: Sequence[str] = (),
    finding_ids: Sequence[str] = (),
    rule_ids: Sequence[str] = (),
) -> AiReadinessRecommendation:
    _assert_safe_text(title, action, rationale)
    return AiReadinessRecommendation(
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


def _findings_for_rules(
    findings: Sequence[Finding],
    rule_ids: Sequence[str],
) -> tuple[Finding, ...]:
    wanted = set(rule_ids)
    return tuple(item for item in findings if item.rule_id in wanted)


def _rule_theme(
    *,
    kind: AiReadinessThemeKind,
    title: str,
    description: str,
    findings: Sequence[Finding],
    ordering_key: str,
) -> AiReadinessTheme | None:
    if not findings:
        return None
    _assert_safe_text(title, description)
    finding_ids = tuple(item.id for item in findings)
    rule_ids = tuple(sorted({item.rule_id for item in findings}))
    return AiReadinessTheme(
        theme_id=build_theme_id(
            kind=kind.value,
            scope=AiReadinessThemeScope.HYGIENE.value,
            subject=rule_ids[0] if rule_ids else "",
        ),
        kind=kind,
        title=title,
        description=description,
        scope=AiReadinessThemeScope.HYGIENE,
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
    families_observed: int,
) -> str:
    if findings_count == 0:
        text = (
            f"{rules_executed} AI Readiness Hygiene rules executed with zero "
            "findings in the supported repository evidence scope. This "
            "summarizes capability signals only and does not establish that "
            "the repository is ai ready."
        )
    else:
        text = (
            f"AI Readiness Hygiene inventory shows {findings_count} finding"
            f"{'' if findings_count == 1 else 's'} across {rules_matched} matched "
            f"rule{'s' if rules_matched != 1 else ''} of {rules_executed} executed"
            f" ({families_observed} capability famil"
            f"{'y' if families_observed == 1 else 'ies'} observed). "
            "Implications remain informational to low and do not establish "
            "ai readiness."
        )
    _assert_safe_text(text)
    return text


def _link_recommendations(
    conclusions: list[AiReadinessConclusion],
    recommendations: Sequence[AiReadinessRecommendation],
) -> list[AiReadinessConclusion]:
    by_conclusion: dict[str, list[str]] = {}
    for item in recommendations:
        for conclusion_id in item.conclusion_ids:
            by_conclusion.setdefault(conclusion_id, []).append(item.recommendation_id)
    linked: list[AiReadinessConclusion] = []
    for conclusion in conclusions:
        ids = tuple(sorted(set(by_conclusion.get(conclusion.conclusion_id, ()))))
        if not ids:
            linked.append(conclusion)
            continue
        linked.append(conclusion.model_copy(update={"recommendation_ids": ids}))
    return linked


def _emit_finding_theme(
    *,
    repository_id: str,
    themes: list[AiReadinessTheme],
    conclusions: list[AiReadinessConclusion],
    recommendations: list[AiReadinessRecommendation],
    findings: Sequence[Finding],
    theme_kind: AiReadinessThemeKind,
    conclusion_kind: AiReadinessConclusionKind,
    recommendation_kind: AiReadinessRecommendationKind,
    policy_id: str,
    title: str,
    description: str,
    conclusion_title: str,
    technical_interpretation: str,
    recommendation_title: str,
    recommendation_action: str,
    recommendation_rationale: str,
    action_key: str,
    rule_ids: Sequence[str],
    ordering_key: str,
    confidence: str = "high",
    audience: AiReadinessConclusionAudience = AiReadinessConclusionAudience.HYGIENE,
) -> None:
    theme = _rule_theme(
        kind=theme_kind,
        title=title,
        description=description,
        findings=findings,
        ordering_key=ordering_key,
    )
    if theme is None:
        return
    themes.append(theme)
    conclusion = _make_conclusion(
        repository_id=repository_id,
        policy_id=policy_id,
        kind=conclusion_kind,
        audience=audience,
        title=conclusion_title,
        summary=theme.description,
        technical_interpretation=technical_interpretation,
        theme_ids=(theme.theme_id,),
        finding_ids=theme.finding_ids,
        rule_ids=rule_ids,
        confidence=confidence,
    )
    conclusions.append(conclusion)
    recommendations.append(
        _make_recommendation(
            kind=recommendation_kind,
            action_key=action_key,
            title=recommendation_title,
            action=recommendation_action,
            rationale=recommendation_rationale,
            conclusion_ids=(conclusion.conclusion_id,),
            audience=audience,
            theme_ids=(theme.theme_id,),
            finding_ids=theme.finding_ids,
            rule_ids=rule_ids,
        )
    )


def synthesize_ai_readiness(
    *,
    repository_id: str,
    pack_enabled: bool,
    section_status: AiReadinessAssessmentStatus,
    findings: Sequence[Finding] = (),
    finding_inventory: AiReadinessFindingInventory | None = None,
    rule_inventory: AiReadinessRuleInventory | None = None,
    capability_family_inventory: AiReadinessCapabilityFamilyInventory | None = None,
    limitations: Sequence[AiReadinessLimitation] = (),
    evidence_status: str = "",
    include_synthesis: bool = True,
) -> AiReadinessSynthesisResult:
    """Build deterministic AI Readiness synthesis from inventory facts."""

    if not include_synthesis:
        return AiReadinessSynthesisResult(
            status=AiReadinessSynthesisStatus.NOT_REQUESTED,
            synthesis_version=SYNTHESIS_VERSION,
            diagnostics=("synthesis_not_requested",),
        )

    if (
        not pack_enabled
        or section_status is AiReadinessAssessmentStatus.DISABLED
        or section_status is AiReadinessAssessmentStatus.NOT_REQUESTED
    ):
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_DISABLED,
            kind=AiReadinessConclusionKind.SYNTHESIS_DISABLED,
            audience=AiReadinessConclusionAudience.STATUS,
            title="AI Readiness synthesis disabled",
            summary=(
                "AI Readiness synthesis was not generated because the AI "
                "Readiness pack or analysis section is disabled."
            ),
            technical_interpretation=(
                "Enable rules.ai_readiness and analysis.ai_readiness to produce "
                "inventory-derived synthesis."
            ),
        )
        return AiReadinessSynthesisResult(
            status=AiReadinessSynthesisStatus.DISABLED,
            synthesis_version=SYNTHESIS_VERSION,
            conclusions=(conclusion,),
            conclusion_ids=(conclusion.conclusion_id,),
            diagnostics=("synthesis_disabled",),
        )

    if section_status in {
        AiReadinessAssessmentStatus.INSUFFICIENT_EVIDENCE,
        AiReadinessAssessmentStatus.FAILED,
        AiReadinessAssessmentStatus.NOT_APPLICABLE,
    }:
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_INSUFFICIENT,
            kind=AiReadinessConclusionKind.INSUFFICIENT_EVIDENCE,
            audience=AiReadinessConclusionAudience.STATUS,
            title="Insufficient AI Readiness evidence for synthesis",
            summary=(
                "AI Readiness synthesis could not be fully generated because "
                f"the assessment status is {section_status.value}."
            ),
            technical_interpretation=(
                "Provide usable repository-ai-readiness evidence and successful "
                "rule evaluation before interpreting AI Readiness synthesis."
            ),
        )
        return AiReadinessSynthesisResult(
            status=AiReadinessSynthesisStatus.INSUFFICIENT_EVIDENCE,
            synthesis_version=SYNTHESIS_VERSION,
            conclusions=(conclusion,),
            conclusion_ids=(conclusion.conclusion_id,),
            diagnostics=("synthesis_insufficient_evidence",),
        )

    ordered = tuple(sorted(findings, key=lambda item: (item.rule_id, item.id, item.title)))
    inventory = finding_inventory or AiReadinessFindingInventory(
        finding_ids=tuple(item.id for item in ordered),
        finding_count=len(ordered),
    )
    rules = rule_inventory or AiReadinessRuleInventory()
    families = capability_family_inventory or AiReadinessCapabilityFamilyInventory()
    rules_executed = rules.rules_executed or sum(1 for item in rules.entries if item.executed)
    if rules_executed == 0 and pack_enabled:
        rules_executed = len(HYGIENE_RULE_IDS)
    rules_matched = rules.rules_matched or sum(
        1 for item in rules.entries if item.evaluation_status == "matched"
    )
    rules_not_matched = rules.rules_not_matched
    finding_ids = tuple(inventory.finding_ids) or tuple(item.id for item in ordered)
    findings_count = inventory.finding_count or len(ordered)
    families_observed = families.families_observed

    themes: list[AiReadinessTheme] = []
    conclusions: list[AiReadinessConclusion] = []
    recommendations: list[AiReadinessRecommendation] = []

    if findings_count == 0:
        landscape_desc = (
            f"{rules_executed} AI Readiness Hygiene rules executed and produced "
            "no findings within the supported repository evidence scope."
        )
    else:
        landscape_desc = (
            f"The supported AI Readiness Hygiene rules produced {findings_count} "
            f"finding{'' if findings_count == 1 else 's'} across "
            f"{rules_matched} matched rule{'s' if rules_matched != 1 else ''}."
        )
    _assert_safe_text(landscape_desc)
    landscape = AiReadinessTheme(
        theme_id=build_theme_id(
            kind=AiReadinessThemeKind.AI_READINESS_HYGIENE_LANDSCAPE.value,
            scope=AiReadinessThemeScope.REPOSITORY.value,
        ),
        kind=AiReadinessThemeKind.AI_READINESS_HYGIENE_LANDSCAPE,
        title="AI readiness hygiene landscape",
        description=landscape_desc,
        scope=AiReadinessThemeScope.REPOSITORY,
        finding_ids=_bound_ids(finding_ids, _FINDING_REF_LIMIT),
        rule_ids=tuple(HYGIENE_RULE_IDS),
        counts={
            "finding_count": findings_count,
            "rules_executed": rules_executed,
            "rules_matched": rules_matched,
            "families_observed": families_observed,
        },
        ordering_key="00_landscape",
    )
    themes.append(landscape)
    conclusions.append(
        _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_LANDSCAPE,
            kind=AiReadinessConclusionKind.AI_READINESS_HYGIENE_LANDSCAPE_IDENTIFIED,
            audience=AiReadinessConclusionAudience.REPOSITORY,
            title="AI readiness hygiene landscape identified",
            summary=landscape_desc,
            technical_interpretation=(
                "This conclusion summarizes supported AI Readiness Hygiene "
                "rule execution and finding counts only."
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
    coverage_theme = AiReadinessTheme(
        theme_id=build_theme_id(
            kind=AiReadinessThemeKind.RULE_EXECUTION_COVERAGE.value,
            scope=AiReadinessThemeScope.COVERAGE.value,
        ),
        kind=AiReadinessThemeKind.RULE_EXECUTION_COVERAGE,
        title="Rule execution coverage",
        description=coverage_desc,
        scope=AiReadinessThemeScope.COVERAGE,
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
            kind=AiReadinessConclusionKind.RULE_EXECUTION_SUMMARY,
            audience=AiReadinessConclusionAudience.COVERAGE,
            title="AI Readiness Hygiene rule execution summary",
            summary=coverage_desc,
            technical_interpretation=(
                "Applicable registered hygiene rules versus matched outcomes "
                "are inventory facts, not readiness scores."
            ),
            theme_ids=(coverage_theme.theme_id,),
            rule_ids=list(HYGIENE_RULE_IDS),
        )
    )

    api_findings = _findings_for_rules(
        ordered,
        (RULE_API_BOUNDARIES, RULE_STRUCTURED_API_SPEC, RULE_LIMITED_API_BOUNDARIES),
    )
    docs_findings = _findings_for_rules(
        ordered,
        (RULE_ARCHITECTURE_DOCS, RULE_LIMITED_DOCUMENTATION),
    )
    data_findings = _findings_for_rules(
        ordered,
        (RULE_DATA_ACCESS, RULE_SEARCH_RETRIEVAL, RULE_VECTOR_EMBEDDINGS),
    )
    ai_findings = _findings_for_rules(
        ordered,
        (RULE_LLM_SDK, RULE_PROMPT_ASSETS, RULE_RAG_PIPELINE),
    )
    mcp_findings = _findings_for_rules(ordered, (RULE_MCP_TOOLS,))
    workflow_findings = _findings_for_rules(ordered, (RULE_WORKFLOW_AGENT,))
    observability_findings = _findings_for_rules(
        ordered,
        (RULE_OBSERVABILITY_GOVERNANCE, RULE_AI_WITHOUT_OBSERVABILITY),
    )
    broad_findings = _findings_for_rules(ordered, (RULE_BROAD_FOUNDATIONS,))
    limited_findings = _findings_for_rules(ordered, (RULE_LIMITED_FOUNDATIONS,))

    if api_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=api_findings,
            theme_kind=AiReadinessThemeKind.API_AND_SERVICE_BOUNDARIES,
            conclusion_kind=AiReadinessConclusionKind.API_AND_SERVICE_BOUNDARIES_OBSERVED,
            recommendation_kind=AiReadinessRecommendationKind.REVIEW_API_AND_SERVICE_BOUNDARY_SIGNALS,
            policy_id=POLICY_API_BOUNDARIES,
            title="API and service boundaries",
            description=(
                f"{len(api_findings)} finding"
                f"{'' if len(api_findings) == 1 else 's'} report API or service "
                "boundary signals in repository evidence."
            ),
            conclusion_title="API and service boundaries observed",
            technical_interpretation=(
                "API boundary markers are repository-observable capability "
                "signals. They do not establish that the repository is ai ready."
            ),
            recommendation_title="Review API and service boundary signals",
            recommendation_action=(
                "Review the linked AI Readiness Hygiene findings and confirm "
                "the observed API and service boundary markers remain intentional."
            ),
            recommendation_rationale=(
                "AI-001/002/003 matched on API boundary signals; review keeps "
                "inventory signals actionable without claiming ai readiness."
            ),
            action_key="review-api-and-service-boundary-signals",
            rule_ids=tuple(sorted({item.rule_id for item in api_findings})),
            ordering_key="10_api_boundaries",
        )

    if docs_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=docs_findings,
            theme_kind=AiReadinessThemeKind.DOCUMENTATION_MATURITY,
            conclusion_kind=AiReadinessConclusionKind.DOCUMENTATION_MATURITY_OBSERVED,
            recommendation_kind=AiReadinessRecommendationKind.REVIEW_DOCUMENTATION_MATURITY_SIGNALS,
            policy_id=POLICY_DOCUMENTATION,
            title="Documentation maturity",
            description=(
                f"{len(docs_findings)} finding"
                f"{'' if len(docs_findings) == 1 else 's'} report architecture "
                "or capability documentation signals."
            ),
            conclusion_title="Documentation maturity observed",
            technical_interpretation=(
                "Documentation markers describe repository metadata signals. "
                "They do not establish that the repository is ai ready."
            ),
            recommendation_title="Review documentation maturity signals",
            recommendation_action=(
                "Review the linked documentation findings and confirm each "
                "observed marker remains intentional for this repository."
            ),
            recommendation_rationale=(
                "AI-010/011 matched on documentation signals; review is "
                "observation-oriented without claiming ai readiness."
            ),
            action_key="review-documentation-maturity-signals",
            rule_ids=tuple(sorted({item.rule_id for item in docs_findings})),
            ordering_key="11_documentation",
        )

    if data_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=data_findings,
            theme_kind=AiReadinessThemeKind.DATA_AND_RETRIEVAL_FOUNDATIONS,
            conclusion_kind=AiReadinessConclusionKind.DATA_AND_RETRIEVAL_FOUNDATIONS_OBSERVED,
            recommendation_kind=AiReadinessRecommendationKind.REVIEW_DATA_AND_RETRIEVAL_SIGNALS,
            policy_id=POLICY_DATA_RETRIEVAL,
            title="Data and retrieval foundations",
            description=(
                f"{len(data_findings)} finding"
                f"{'' if len(data_findings) == 1 else 's'} report data access, "
                "search, or embedding retrieval signals."
            ),
            conclusion_title="Data and retrieval foundations observed",
            technical_interpretation=(
                "Data and retrieval markers are repository signals only. They "
                "do not establish RAG suitability or that the repository is "
                "ai ready."
            ),
            recommendation_title="Review data and retrieval signals",
            recommendation_action=(
                "Review the linked data and retrieval findings and confirm "
                "observed markers remain intentional."
            ),
            recommendation_rationale=(
                "AI-020/021/022 matched on data or retrieval signals; review "
                "stays observation-oriented."
            ),
            action_key="review-data-and-retrieval-signals",
            rule_ids=tuple(sorted({item.rule_id for item in data_findings})),
            ordering_key="12_data_retrieval",
        )

    if ai_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=ai_findings,
            theme_kind=AiReadinessThemeKind.AI_INTEGRATION_MATURITY,
            conclusion_kind=AiReadinessConclusionKind.AI_INTEGRATION_MATURITY_OBSERVED,
            recommendation_kind=AiReadinessRecommendationKind.REVIEW_AI_INTEGRATION_SIGNALS,
            policy_id=POLICY_AI_INTEGRATION,
            title="AI integration maturity",
            description=(
                f"{len(ai_findings)} finding"
                f"{'' if len(ai_findings) == 1 else 's'} report LLM SDK, prompt, "
                "or RAG pipeline signals."
            ),
            conclusion_title="AI integration maturity observed",
            technical_interpretation=(
                "AI integration markers describe declared tooling. They do "
                "not establish production operation or that the repository is "
                "ai ready."
            ),
            recommendation_title="Review AI integration signals",
            recommendation_action=(
                "Review the linked AI integration findings and confirm each "
                "observed marker remains intentional."
            ),
            recommendation_rationale=(
                "AI-030/031/032 matched on AI integration signals; review does "
                "not prescribe architecture changes."
            ),
            action_key="review-ai-integration-signals",
            rule_ids=tuple(sorted({item.rule_id for item in ai_findings})),
            ordering_key="13_ai_integration",
        )

    if mcp_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=mcp_findings,
            theme_kind=AiReadinessThemeKind.MCP_AND_TOOL_ECOSYSTEM,
            conclusion_kind=AiReadinessConclusionKind.MCP_AND_TOOL_ECOSYSTEM_OBSERVED,
            recommendation_kind=AiReadinessRecommendationKind.REVIEW_MCP_AND_TOOL_SIGNALS,
            policy_id=POLICY_MCP_TOOLS,
            title="MCP and tool ecosystem",
            description=(
                f"{len(mcp_findings)} finding"
                f"{'' if len(mcp_findings) == 1 else 's'} report MCP or tool "
                "ecosystem signals."
            ),
            conclusion_title="MCP and tool ecosystem observed",
            technical_interpretation=(
                "MCP and tool markers are repository signals only and do not "
                "establish that the repository is ai ready."
            ),
            recommendation_title="Review MCP and tool signals",
            recommendation_action=(
                "Review the linked MCP and tool findings and confirm packaging "
                "artifacts remain intentional."
            ),
            recommendation_rationale=(
                "AI-040 matched on MCP or tool signals; review stays observation-oriented."
            ),
            action_key="review-mcp-and-tool-signals",
            rule_ids=(RULE_MCP_TOOLS,),
            ordering_key="14_mcp_tools",
        )

    if workflow_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=workflow_findings,
            theme_kind=AiReadinessThemeKind.WORKFLOW_AND_AGENT_FOUNDATIONS,
            conclusion_kind=AiReadinessConclusionKind.WORKFLOW_AND_AGENT_FOUNDATIONS_OBSERVED,
            recommendation_kind=AiReadinessRecommendationKind.REVIEW_WORKFLOW_AND_AGENT_SIGNALS,
            policy_id=POLICY_WORKFLOW_AGENT,
            title="Workflow and agent foundations",
            description=(
                f"{len(workflow_findings)} finding"
                f"{'' if len(workflow_findings) == 1 else 's'} report workflow "
                "or agent foundation signals."
            ),
            conclusion_title="Workflow and agent foundations observed",
            technical_interpretation=(
                "Workflow and agent markers describe declared automation "
                "signals. They do not establish that the repository is ai ready."
            ),
            recommendation_title="Review workflow and agent signals",
            recommendation_action=(
                "Review the linked workflow and agent findings and confirm "
                "observed markers remain intentional."
            ),
            recommendation_rationale=(
                "AI-041 matched on workflow or agent signals; review does not "
                "prescribe agent architecture."
            ),
            action_key="review-workflow-and-agent-signals",
            rule_ids=(RULE_WORKFLOW_AGENT,),
            ordering_key="15_workflow_agent",
        )

    if observability_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=observability_findings,
            theme_kind=AiReadinessThemeKind.OBSERVABILITY_AND_GOVERNANCE,
            conclusion_kind=AiReadinessConclusionKind.OBSERVABILITY_AND_GOVERNANCE_OBSERVED,
            recommendation_kind=(
                AiReadinessRecommendationKind.REVIEW_OBSERVABILITY_AND_GOVERNANCE_SIGNALS
            ),
            policy_id=POLICY_OBSERVABILITY,
            title="Observability and governance",
            description=(
                f"{len(observability_findings)} finding"
                f"{'' if len(observability_findings) == 1 else 's'} report "
                "observability or governance signals for AI-related assets."
            ),
            conclusion_title="Observability and governance observed",
            technical_interpretation=(
                "Observability and governance markers are inventory signals. "
                "They do not establish that the repository is ai ready."
            ),
            recommendation_title="Review observability and governance signals",
            recommendation_action=(
                "Review the linked observability and governance findings and "
                "confirm each marker remains intentional."
            ),
            recommendation_rationale=(
                "AI-050/051 matched on observability or governance signals; "
                "review stays observation-oriented."
            ),
            action_key="review-observability-and-governance-signals",
            rule_ids=tuple(sorted({item.rule_id for item in observability_findings})),
            ordering_key="16_observability",
        )

    if broad_findings or families_observed >= 3:
        if broad_findings:
            desc = (
                f"{len(broad_findings)} finding"
                f"{'' if len(broad_findings) == 1 else 's'} report broad AI "
                "enablement foundations across multiple capability families."
            )
            finding_ids_for_theme = tuple(item.id for item in broad_findings)
            rule_ids_for_theme: tuple[str, ...] = (RULE_BROAD_FOUNDATIONS,)
        else:
            desc = (
                f"Capability family inventory observes {families_observed} "
                "distinct AI readiness capability families from Findings metadata."
            )
            finding_ids_for_theme = finding_ids
            rule_ids_for_theme = tuple(sorted({item.rule_id for item in ordered})) or tuple(
                HYGIENE_RULE_IDS
            )
        _assert_safe_text(desc)
        theme = AiReadinessTheme(
            theme_id=build_theme_id(
                kind=AiReadinessThemeKind.BROAD_AI_ENABLEMENT.value,
                scope=AiReadinessThemeScope.COVERAGE.value,
                subject="families",
            ),
            kind=AiReadinessThemeKind.BROAD_AI_ENABLEMENT,
            title="Broad AI enablement",
            description=desc,
            scope=AiReadinessThemeScope.COVERAGE,
            finding_ids=_bound_ids(finding_ids_for_theme, _FINDING_REF_LIMIT),
            rule_ids=rule_ids_for_theme,
            counts={
                "finding_count": len(broad_findings),
                "families_observed": families_observed,
            },
            ordering_key="17_broad_enablement",
        )
        themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_BROAD,
            kind=AiReadinessConclusionKind.BROAD_AI_ENABLEMENT_OBSERVED,
            audience=AiReadinessConclusionAudience.COVERAGE,
            title="Broad AI enablement observed",
            summary=theme.description,
            technical_interpretation=(
                "Family coverage summarizes distinct capability signal groups. "
                "It does not establish that the repository is ai ready."
            ),
            theme_ids=(theme.theme_id,),
            finding_ids=theme.finding_ids,
            rule_ids=rule_ids_for_theme,
            confidence="medium",
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=AiReadinessRecommendationKind.REVIEW_BROAD_AI_ENABLEMENT,
                action_key="review-broad-ai-enablement",
                title="Review broad AI enablement signals",
                action=(
                    "Review the linked Findings and confirm the observed "
                    "capability families remain intentional for this repository."
                ),
                rationale=(
                    "Broad enablement themes summarize inventory facts without "
                    "claiming ai readiness."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=AiReadinessConclusionAudience.COVERAGE,
                theme_ids=(theme.theme_id,),
                finding_ids=theme.finding_ids,
                rule_ids=rule_ids_for_theme,
            )
        )

    if limited_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=limited_findings,
            theme_kind=AiReadinessThemeKind.LIMITED_SUPPORTING_FOUNDATIONS,
            conclusion_kind=AiReadinessConclusionKind.LIMITED_SUPPORTING_FOUNDATIONS_OBSERVED,
            recommendation_kind=AiReadinessRecommendationKind.REVIEW_LIMITED_SUPPORTING_FOUNDATIONS,
            policy_id=POLICY_LIMITED,
            title="Limited supporting foundations",
            description=(
                f"{len(limited_findings)} finding"
                f"{'' if len(limited_findings) == 1 else 's'} report limited "
                "supporting AI readiness foundations."
            ),
            conclusion_title="Limited supporting foundations observed",
            technical_interpretation=(
                "Limited foundation markers describe sparse capability signals. "
                "They do not establish that the repository is ai ready."
            ),
            recommendation_title="Review limited supporting foundations",
            recommendation_action=(
                "Review the linked findings and confirm whether limited "
                "foundation markers are expected for this repository."
            ),
            recommendation_rationale=(
                "AI-061 matched on limited supporting foundations; review "
                "stays observation-oriented."
            ),
            action_key="review-limited-supporting-foundations",
            rule_ids=(RULE_LIMITED_FOUNDATIONS,),
            ordering_key="18_limited_foundations",
            confidence="medium",
        )

    if findings_count == 0 and rules_executed > 0:
        theme = AiReadinessTheme(
            theme_id=build_theme_id(
                kind=AiReadinessThemeKind.NO_HYGIENE_FINDINGS.value,
                scope=AiReadinessThemeScope.STATUS.value,
            ),
            kind=AiReadinessThemeKind.NO_HYGIENE_FINDINGS,
            title="No hygiene findings in supported scope",
            description=(
                f"No AI Readiness Hygiene findings were emitted by the "
                f"{rules_executed} enabled rules within the supported "
                "repository evidence scope."
            ),
            scope=AiReadinessThemeScope.STATUS,
            rule_ids=tuple(HYGIENE_RULE_IDS),
            counts={"rules_executed": rules_executed, "finding_count": 0},
            ordering_key="20_no_findings",
        )
        _assert_safe_text(theme.description)
        themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_NO_FINDINGS,
            kind=AiReadinessConclusionKind.NO_HYGIENE_FINDINGS_IN_SUPPORTED_SCOPE,
            audience=AiReadinessConclusionAudience.STATUS,
            title="No hygiene findings in supported scope",
            summary=theme.description,
            technical_interpretation=(
                "Zero findings is a neutral inventory outcome for enabled "
                "hygiene rules. It does not establish that the repository is "
                "ai ready."
            ),
            theme_ids=(theme.theme_id,),
            rule_ids=list(HYGIENE_RULE_IDS),
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=AiReadinessRecommendationKind.ACKNOWLEDGE_NO_HYGIENE_FINDINGS_IN_SUPPORTED_SCOPE,
                action_key="acknowledge-no-hygiene-findings",
                title="Acknowledge zero hygiene findings in supported scope",
                action=(
                    "Treat zero AI Readiness Hygiene findings as a bounded "
                    "inventory outcome for the supported evidence and rule pack "
                    "only."
                ),
                rationale=(
                    "Neutral acknowledgment prevents overstating risk or "
                    "claiming ai readiness from an empty finding set."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=AiReadinessConclusionAudience.STATUS,
                theme_ids=(theme.theme_id,),
                rule_ids=list(HYGIENE_RULE_IDS),
            )
        )

    if limitations:
        theme = AiReadinessTheme(
            theme_id=build_theme_id(
                kind=AiReadinessThemeKind.UNSUPPORTED_ANALYSIS_SCOPE.value,
                scope=AiReadinessThemeScope.STATUS.value,
            ),
            kind=AiReadinessThemeKind.UNSUPPORTED_ANALYSIS_SCOPE,
            title="Unsupported AI readiness analysis scope",
            description=(
                f"{len(limitations)} documented limitation"
                f"{'' if len(limitations) == 1 else 's'} bound this assessment: "
                "readiness scoring, AI/LLM execution, and report presentation "
                "remain out of scope."
            ),
            scope=AiReadinessThemeScope.STATUS,
            counts={"limitation_count": len(limitations)},
            ordering_key="30_unsupported_scope",
        )
        _assert_safe_text(theme.description)
        themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_UNSUPPORTED_SCOPE,
            kind=AiReadinessConclusionKind.UNSUPPORTED_AI_READINESS_ANALYSIS_SCOPE,
            audience=AiReadinessConclusionAudience.STATUS,
            title="Unsupported AI readiness analysis scope acknowledged",
            summary=theme.description,
            technical_interpretation=(
                "Synthesis uses repository-observable AI Readiness Hygiene "
                "evidence only. Readiness scores and AI execution are not "
                "evaluated."
            ),
            theme_ids=(theme.theme_id,),
            metadata={"limitation_count": str(len(limitations))},
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=AiReadinessRecommendationKind.ACKNOWLEDGE_UNSUPPORTED_AI_READINESS_ANALYSIS_SCOPE,
                action_key="acknowledge-unsupported-ai-readiness-analysis-scope",
                title="Acknowledge unsupported AI readiness analysis scope",
                action=(
                    "Interpret AI Readiness synthesis as hygiene inventory only "
                    "until additional analysis capabilities exist."
                ),
                rationale=(
                    "Documented limitations keep conclusions from claiming "
                    "ai readiness or prescribing enablement paths."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=AiReadinessConclusionAudience.STATUS,
                theme_ids=(theme.theme_id,),
            )
        )

    themes_sorted = tuple(sorted(themes, key=lambda item: (item.ordering_key, item.theme_id)))
    recommendations_sorted = tuple(
        sorted(recommendations, key=lambda item: (item.kind.value, item.recommendation_id))
    )
    deduped: list[AiReadinessRecommendation] = []
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
        families_observed=families_observed,
    )
    status = (
        AiReadinessSynthesisStatus.EMPTY
        if findings_count == 0
        else AiReadinessSynthesisStatus.SUCCEEDED
    )
    return AiReadinessSynthesisResult(
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
