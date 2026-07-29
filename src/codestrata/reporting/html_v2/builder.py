"""Build CustomerReportDocument from validated report input and Phase 3 artifacts."""

from __future__ import annotations

from collections import Counter

from codestrata import __version__ as ENGINE_VERSION
from codestrata.domain.ai_enrichment import AiEnrichmentResult
from codestrata.domain.findings import Finding as Phase3Finding
from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.recommendations import Recommendation as Phase3Recommendation
from codestrata.domain.recommendations import RecommendationResult
from codestrata.models import AnalysisResult
from codestrata.models import Finding as Phase1Finding
from codestrata.models import Recommendation as Phase1Recommendation
from codestrata.reporting.ai_status import (
    ai_execution_status_label,
    assessment_mode_display_label,
)
from codestrata.reporting.contract.constants import REPORT_HTML_VERSION
from codestrata.reporting.contract.identifiers import (
    build_finding_id_map,
    remap_related_finding_ids,
    stable_finding_id,
    stable_recommendation_id,
)
from codestrata.reporting.contract.ordering import (
    sorted_findings as contract_sorted_findings,
)
from codestrata.reporting.contract.ordering import (
    sorted_technologies as contract_sorted_technologies,
)
from codestrata.reporting.customer_universe import (
    CustomerFinding,
    CustomerRecommendation,
    resolve_customer_findings,
    resolve_customer_recommendations,
)
from codestrata.reporting.html_v2.leadership import (
    build_assessment_scope,
    build_engineering_risks,
    build_executive_summary_narrative,
    build_leadership_key_takeaways,
    build_leadership_roadmap,
    build_leadership_verdict,
    build_modernization_opportunities,
    build_priority_actions_for_leadership,
)
from codestrata.reporting.html_v2.models import (
    AiEnrichmentView,
    AiNextStepView,
    AiPriorityView,
    AiRiskView,
    AiThemeView,
    ArtifactRefView,
    AssessmentMetadataView,
    AssessmentScopeView,
    AssessmentSummaryView,
    CustomerReportDocument,
    DashboardMetrics,
    EngineeringRiskThemeView,
    EvidenceView,
    FindingView,
    RecommendationActionView,
    RecommendationView,
    ReportOutlineEntry,
    ReportSummary,
    RepositoryProfileView,
    TechnologyItemView,
    VersionHighlightView,
    priority_rank,
    severity_rank,
)
from codestrata.reporting.modernization_models import (
    AIExecutionStatus,
    AssessmentMode,
    HighlightedVersionInput,
    ModernizationReportInput,
    ReportArtifactInput,
)
from codestrata.reporting.modernization_view import repository_identifier, sanitize_display_path
from codestrata.security.redaction import redact_secrets


def build_customer_report_document(
    report_input: ModernizationReportInput,
) -> CustomerReportDocument:
    """Assemble the renderer-neutral customer presentation document."""

    analysis = report_input.analysis_result
    findings = _build_findings(report_input)
    recommendations = _build_recommendations(report_input)
    ai_view = _build_ai_enrichment(report_input.ai_enrichment)
    findings_by_severity = _count_sorted(
        [item.severity for item in findings],
        key_rank=severity_rank,
    )
    recommendations_by_priority = _count_sorted(
        [item.priority for item in recommendations],
        key_rank=priority_rank,
    )
    highest_priority = recommendations[0].priority if recommendations else None
    technologies = _technology_items(analysis)
    version_highlights = tuple(
        VersionHighlightView(
            label=item.label,
            value=item.value,
            kind=item.kind,
            detail=item.detail,
        )
        for item in report_input.highlighted_versions
    )
    artifacts = tuple(
        ArtifactRefView(label=item.label, relative_path=_safe_relative(item.relative_path))
        for item in report_input.report_artifacts
    )
    repo_name = repository_identifier(report_input)
    ai_status_label = _ai_enrichment_status(report_input, ai_view is not None)
    highest_severity = _highest_finding_severity(findings)
    metrics = _dashboard_metrics(
        analysis=analysis,
        technology_count=len(technologies),
        findings_count=len(findings),
        recommendations_count=len(recommendations),
        highest_finding_severity=highest_severity,
    )
    summary = ReportSummary(
        repository_name=repo_name,
        assessment_mode=report_input.assessment_mode.value,
        assessment_mode_label=assessment_mode_display_label(report_input),
        technologies=tuple(item.name for item in technologies),
        total_findings=len(findings),
        findings_by_severity=findings_by_severity,
        total_recommendations=len(recommendations),
        highest_recommendation_priority=highest_priority,
        ai_enrichment_status=ai_status_label,
        ai_enrichment_available=ai_view is not None,
        metrics=metrics,
        highest_finding_severity=highest_severity,
    )
    repository = RepositoryProfileView(
        name=analysis.repository.name,
        reference=_safe_optional_text(report_input.repository_reference),
        source_type="github" if analysis.repository.source_url else "local",
        file_count=analysis.repository.total_files or len(analysis.repository.files),
        default_branch=analysis.repository.default_branch,
    )
    rules_evaluated = 0
    if report_input.assessment_rule_evaluation is not None:
        rules_evaluated = len(report_input.assessment_rule_evaluation.rules_evaluated)
    assessment_summary = AssessmentSummaryView(
        rules_evaluated=rules_evaluated,
        findings_count=len(findings),
        recommendations_count=len(recommendations),
        findings_by_severity=findings_by_severity,
        recommendations_by_priority=recommendations_by_priority,
        summary_text=_assessment_summary_text(
            findings_count=len(findings),
            recommendations_count=len(recommendations),
            ai_available=ai_view is not None,
        ),
    )
    timing = report_input.timing
    advisor_version = None
    if ai_view is not None:
        advisor_version = ai_view.advisor_version
    metadata = AssessmentMetadataView(
        generated_at_utc=report_input.generated_at_utc.isoformat().replace("+00:00", "Z"),
        report_title=report_input.report_title,
        organization_name=report_input.organization_name,
        warnings=tuple(_safe_text(item) for item in report_input.warnings),
        timing_total_ms=timing.total_ms if timing else None,
        timing_scan_ms=timing.scan_ms if timing else None,
        timing_analysis_ms=timing.analysis_ms if timing else None,
        timing_ai_ms=timing.ai_ms if timing else None,
        timing_report_ms=timing.report_ms if timing else None,
        ai_status=report_input.ai_status.value,
        model_id=(
            report_input.ai_attempt.model_id
            if report_input.ai_attempt is not None
            else (
                report_input.assessment_result.model_metadata.model_id
                if report_input.assessment_result is not None
                else None
            )
        ),
        confidentiality_notice=_safe_optional_text(report_input.confidentiality_notice),
        report_version=REPORT_HTML_VERSION,
        engine_version=ENGINE_VERSION,
        advisor_version=advisor_version,
        repository_name=repo_name,
    )
    assessed, not_assessed = build_assessment_scope(report_input.assessment_activation)
    assessment_scope = (
        AssessmentScopeView(assessed_packs=assessed, not_assessed_packs=not_assessed)
        if assessed or not_assessed
        else None
    )
    priority_actions = build_priority_actions_for_leadership(
        findings=findings,
        recommendations=recommendations,
    )
    assessment_summary = assessment_summary.model_copy(
        update={
            "recommendations_count": len(priority_actions),
            "summary_text": _assessment_summary_text(
                findings_count=len(findings),
                recommendations_count=len(priority_actions),
                ai_available=ai_view is not None,
            ),
        }
    )
    key_takeaways = build_leadership_key_takeaways(
        findings=findings,
        recommendations=priority_actions,
        metrics=metrics,
        summary=summary,
        activation=report_input.assessment_activation,
        architecture_present=report_input.architecture_report is not None,
        cloud_present=report_input.cloud_report is not None,
        testing_present=report_input.testing_report is not None,
    )
    risk_themes = build_engineering_risks(findings)
    engineering_risks = tuple(
        EngineeringRiskThemeView(theme=theme, items=items) for theme, items in risk_themes
    )
    risk_titles = frozenset(
        item.rsplit(" (", 1)[0]
        for _theme, items in risk_themes
        for item in items
    )
    modernization_opportunities = build_modernization_opportunities(
        findings=findings,
        recommendations=priority_actions,
        risk_titles=risk_titles,
    )
    leadership_verdict = build_leadership_verdict(
        findings=findings,
        priority_actions=priority_actions,
        metrics=metrics,
        highest_severity=highest_severity,
    )
    executive_summary = build_executive_summary_narrative(
        findings=findings,
        priority_actions=priority_actions,
        metrics=metrics,
        highest_severity=highest_severity,
        technologies=tuple(item.name for item in technologies),
    )
    leadership_roadmap = build_leadership_roadmap(priority_actions)
    roadmap_report = leadership_roadmap or report_input.roadmap_report
    document = CustomerReportDocument(
        summary=summary,
        repository=repository,
        technologies=technologies,
        version_highlights=version_highlights,
        assessment_summary=assessment_summary,
        findings=findings,
        recommendations=recommendations,
        priority_actions=priority_actions,
        ai_enrichment=ai_view,
        architecture_report=report_input.architecture_report,
        technical_debt_report=report_input.technical_debt_report,
        dependency_report=report_input.dependency_report,
        security_report=report_input.security_report,
        testing_report=report_input.testing_report,
        cloud_report=report_input.cloud_report,
        ai_readiness_report=report_input.ai_readiness_report,
        performance_report=report_input.performance_report,
        roadmap_report=roadmap_report,
        artifacts=artifacts,
        metadata=metadata,
        leadership_verdict=leadership_verdict,
        executive_summary=executive_summary,
        key_takeaways=key_takeaways,
        engineering_risks=engineering_risks,
        modernization_opportunities=modernization_opportunities,
        assessment_scope=assessment_scope,
        outline=(),  # filled below once presence is known
    )
    outline = _build_outline(document)
    return document.model_copy(update={"outline": outline})


def build_html_report_view_model(report_input: ModernizationReportInput) -> CustomerReportDocument:
    """Backward-compatible alias for :func:`build_customer_report_document`."""

    return build_customer_report_document(report_input)


def _build_outline(document: CustomerReportDocument) -> tuple[ReportOutlineEntry, ...]:
    """Stable TOC entries for sections that will appear in the rendered report."""

    entries: list[ReportOutlineEntry] = [
        ReportOutlineEntry(section_id="executive-summary", title="Executive Summary"),
        ReportOutlineEntry(section_id="repository-overview", title="Repository Overview"),
        ReportOutlineEntry(section_id="assessment-summary", title="Assessment Summary"),
        ReportOutlineEntry(section_id="leadership-verdict", title="Leadership Verdict"),
        ReportOutlineEntry(section_id="key-takeaways", title="Key Takeaways"),
        ReportOutlineEntry(section_id="engineering-risks", title="Engineering Risks"),
    ]
    capability_packs = (
        ("architecture-assessment", "Architecture Assessment", document.architecture_report),
        ("technical-debt-assessment", "Technical Debt Assessment", document.technical_debt_report),
        ("dependency-assessment", "Dependency Assessment", document.dependency_report),
        ("security-assessment", "Security Assessment", document.security_report),
        ("testing-assessment", "Testing Assessment", document.testing_report),
        ("cloud-assessment", "Cloud Assessment", document.cloud_report),
        ("ai-readiness-assessment", "AI Readiness Assessment", document.ai_readiness_report),
        ("performance-assessment", "Performance Assessment", document.performance_report),
    )
    has_capability = any(present is not None for _, _, present in capability_packs)
    if has_capability:
        entries.append(
            ReportOutlineEntry(
                section_id="capability-assessments",
                title="Domain Intelligence",
            )
        )
    for section_id, title, present in capability_packs:
        if present is not None:
            entries.append(ReportOutlineEntry(section_id=section_id, title=title))
    entries.append(ReportOutlineEntry(section_id="findings", title="Findings"))
    entries.append(ReportOutlineEntry(section_id="recommendations", title="Recommendations"))
    entries.append(ReportOutlineEntry(section_id="priority-actions", title="Priority Actions"))
    entries.append(
        ReportOutlineEntry(
            section_id="modernization-opportunities",
            title="Modernization Opportunities",
        )
    )
    entries.append(
        ReportOutlineEntry(
            section_id="engineering-assessment-conclusion",
            title="Engineering Assessment Conclusion",
        )
    )
    if document.roadmap_report is not None:
        entries.append(
            ReportOutlineEntry(
                section_id="phased-modernization-plan",
                title="Implementation Sequence",
            )
        )
    if document.ai_enrichment is not None:
        entries.append(
            ReportOutlineEntry(
                section_id="modernization-advisor",
                title="Optional AI Enhancements",
            )
        )
    entries.append(
        ReportOutlineEntry(section_id="technical-appendix", title="Technical Appendix")
    )
    return tuple(entries)


def default_report_artifacts(
    *,
    include_ai_enrichment: bool,
    include_ai_execution: bool,
    include_architecture_assessment: bool = False,
) -> tuple[ReportArtifactInput, ...]:
    """Stable relative artifact list for Graph and Artifact References."""

    items = [
        ReportArtifactInput(label="Findings", relative_path="findings.json"),
        ReportArtifactInput(label="Recommendations", relative_path="recommendations.json"),
        ReportArtifactInput(label="Assessment JSON", relative_path="report.json"),
        ReportArtifactInput(
            label="Repository Graph",
            relative_path="graphs/repository-graph.json",
        ),
        ReportArtifactInput(
            label="Assessment Graph",
            relative_path="graphs/assessment-graph.json",
        ),
        ReportArtifactInput(
            label="Graph Summary",
            relative_path="graphs/graph-summary.json",
        ),
    ]
    if include_architecture_assessment:
        items.append(
            ReportArtifactInput(
                label="Architecture Assessment",
                relative_path="architecture-assessment.json",
            )
        )
    if include_ai_enrichment:
        items.append(
            ReportArtifactInput(
                label="Modernization Advisor",
                relative_path="advisor.json",
            )
        )
    if include_ai_execution:
        items.append(
            ReportArtifactInput(label="Advisor Execution", relative_path="advisor-execution.json")
        )
    return tuple(items)


def _build_findings(report_input: ModernizationReportInput) -> tuple[FindingView, ...]:
    return tuple(
        _customer_finding_view(item) for item in resolve_customer_findings(report_input)
    )


def _build_recommendations(
    report_input: ModernizationReportInput,
) -> tuple[RecommendationView, ...]:
    findings = resolve_customer_findings(report_input)
    finding_titles = {item.id: item.title for item in findings}
    finding_id_map = build_finding_id_map(list(report_input.analysis_result.findings))
    return tuple(
        _customer_recommendation_view(
            item,
            finding_id_map=finding_id_map,
            finding_titles=finding_titles,
        )
        for item in resolve_customer_recommendations(report_input)
    )


def _customer_finding_view(item: CustomerFinding) -> FindingView:
    if item.phase1 is not None:
        return _phase1_finding_view(item.phase1)
    return FindingView(
        finding_id=item.id,
        rule_id=item.rule_id,
        title=_safe_text(item.title),
        description=_safe_text(item.description),
        severity=item.severity,
        category=item.category,
        affected_nodes=(),
        evidence=tuple(
            EvidenceView(
                evidence_type=str(row.get("evidence_type") or "file"),
                source_id=str(row.get("source_id") or row.get("file_path") or ""),
                path=_safe_path(str(row.get("path") or row.get("file_path") or "")),
                excerpt=_safe_optional_text(
                    row.get("excerpt") if row.get("excerpt") is not None else row.get("description")
                ),
                node_id=str(row["node_id"]) if row.get("node_id") else None,
            )
            for row in item.evidence
            if isinstance(row, dict)
        ),
    )


def _customer_recommendation_view(
    item: CustomerRecommendation,
    *,
    finding_id_map: dict[str, str] | None = None,
    finding_titles: dict[str, str] | None = None,
) -> RecommendationView:
    titles = finding_titles or {}
    related_titles = tuple(
        titles[fid] for fid in item.related_finding_ids if fid in titles
    )
    if item.phase1 is not None:
        view = _phase1_recommendation_view(item.phase1, finding_id_map=finding_id_map or {})
        return view.model_copy(
            update={
                "related_finding_ids": tuple(item.related_finding_ids) or view.related_finding_ids,
                "related_finding_titles": related_titles or view.related_finding_titles,
                "effort": item.effort,
                "risk": item.risk,
                "dependencies": tuple(item.dependencies),
                "priority_score": item.priority_score,
                "presentation_bucket": item.presentation_bucket,
            }
        )
    return RecommendationView(
        recommendation_id=item.id,
        title=_safe_text(item.title),
        summary=_safe_text(item.description),
        rationale=_safe_text(item.rationale or item.description),
        priority=item.priority,
        category=item.category,
        related_finding_ids=tuple(item.related_finding_ids),
        related_finding_titles=related_titles,
        affected_nodes=(),
        actions=tuple(
            RecommendationActionView(
                order=index,
                title=_safe_text(action),
                description=_safe_text(action),
                command=None,
            )
            for index, action in enumerate(item.actions, start=1)
        ),
        evidence=tuple(
            EvidenceView(
                evidence_type=str(row.get("evidence_type") or "file"),
                source_id=str(row.get("source_id") or row.get("file_path") or ""),
                path=_safe_path(str(row.get("path") or row.get("file_path") or "")),
                excerpt=_safe_optional_text(
                    row.get("excerpt") if row.get("excerpt") is not None else row.get("description")
                ),
                node_id=None,
            )
            for row in item.evidence
            if isinstance(row, dict)
        ),
        effort=item.effort,
        risk=item.risk,
        dependencies=tuple(item.dependencies),
        priority_score=item.priority_score,
        presentation_bucket=item.presentation_bucket,
    )


def _sorted_phase3_findings(evaluation: RuleEvaluationResult) -> tuple[Phase3Finding, ...]:
    return tuple(
        sorted(
            evaluation.findings,
            key=lambda item: (
                severity_rank(item.severity.value),
                item.category.value,
                item.title.lower(),
                item.id,
            ),
        )
    )


def _sorted_phase3_recommendations(
    result: RecommendationResult,
) -> tuple[Phase3Recommendation, ...]:
    return tuple(
        sorted(
            result.recommendations,
            key=lambda item: (
                priority_rank(item.priority.value),
                item.category.value,
                item.title.lower(),
                item.id,
            ),
        )
    )


def _sorted_phase1_findings(analysis: AnalysisResult) -> tuple[Phase1Finding, ...]:
    return tuple(contract_sorted_findings(analysis.findings))


def _phase3_finding_view(finding: Phase3Finding) -> FindingView:
    return FindingView(
        finding_id=finding.id,
        rule_id=finding.rule_id,
        title=_safe_text(finding.title),
        description=_safe_text(finding.description),
        severity=finding.severity.value,
        category=finding.category.value,
        affected_nodes=tuple(str(node.root) for node in finding.affected_assessment_node_ids),
        evidence=tuple(
            EvidenceView(
                evidence_type=item.evidence_type,
                source_id=item.source_id,
                path=_safe_path(item.path),
                excerpt=_safe_optional_text(item.excerpt),
                node_id=str(item.node_id.root) if item.node_id is not None else None,
            )
            for item in finding.evidence
        ),
    )


def _phase1_finding_view(finding: Phase1Finding) -> FindingView:
    return FindingView(
        finding_id=stable_finding_id(finding),
        rule_id=finding.rule_id or "unknown",
        title=_safe_text(finding.title),
        description=_safe_text(finding.description),
        severity=str(getattr(finding.severity, "value", finding.severity)),
        category=str(getattr(finding.category, "value", finding.category)),
        affected_nodes=(),
        evidence=tuple(
            EvidenceView(
                evidence_type="file",
                source_id=item.file_path,
                path=_safe_path(item.file_path),
                excerpt=_safe_optional_text(item.snippet or item.description),
                node_id=None,
            )
            for item in finding.evidence
        ),
    )


def _phase3_recommendation_view(item: Phase3Recommendation) -> RecommendationView:
    return RecommendationView(
        recommendation_id=item.id,
        title=_safe_text(item.title),
        summary=_safe_text(item.summary),
        rationale=_safe_text(item.rationale),
        priority=item.priority.value,
        category=item.category.value,
        related_finding_ids=tuple(item.related_finding_ids),
        affected_nodes=tuple(str(node.root) for node in item.affected_node_ids),
        actions=tuple(
            RecommendationActionView(
                order=action.order,
                title=_safe_text(action.title),
                description=_safe_text(action.description),
                command=_safe_optional_text(action.command),
            )
            for action in sorted(item.actions, key=lambda row: (row.order, row.title))
        ),
        evidence=tuple(
            EvidenceView(
                evidence_type=ev.evidence_type,
                source_id=ev.source_id,
                path=_safe_path(ev.path),
                excerpt=_safe_optional_text(ev.excerpt),
                node_id=str(ev.node_id.root) if ev.node_id is not None else None,
            )
            for ev in item.evidence
        ),
    )


def _phase1_recommendation_view(
    item: Phase1Recommendation,
    *,
    finding_id_map: dict[str, str] | None = None,
) -> RecommendationView:
    id_map = finding_id_map or {}
    return RecommendationView(
        recommendation_id=stable_recommendation_id(item),
        title=_safe_text(item.title),
        summary=_safe_text(item.description),
        rationale=_safe_text(item.rationale or item.description),
        priority=str(getattr(item.priority, "value", item.priority)),
        category=str(getattr(item.category, "value", item.category)),
        related_finding_ids=remap_related_finding_ids(
            item.related_finding_ids, id_map
        ),
        affected_nodes=(),
        actions=tuple(
            RecommendationActionView(
                order=index,
                title=_safe_text(action),
                description=_safe_text(action),
                command=None,
            )
            for index, action in enumerate(item.actions or (), start=1)
        ),
        evidence=tuple(
            EvidenceView(
                evidence_type="file",
                source_id=ev.file_path,
                path=_safe_path(ev.file_path),
                excerpt=_safe_optional_text(ev.snippet or ev.description),
                node_id=None,
            )
            for ev in item.evidence
        ),
    )


def _build_ai_enrichment(result: AiEnrichmentResult | None) -> AiEnrichmentView | None:
    if result is None:
        return None
    return AiEnrichmentView(
        headline=_safe_text(result.executive_summary.headline),
        narrative=_safe_text(result.executive_summary.narrative),
        posture=_safe_optional_text(result.executive_summary.posture),
        themes=tuple(
            AiThemeView(
                title=_safe_text(theme.title),
                summary=_safe_text(theme.summary),
                related_finding_ids=tuple(theme.related_finding_ids),
                related_recommendation_ids=tuple(theme.related_recommendation_ids),
            )
            for theme in result.themes
        ),
        priorities=tuple(
            AiPriorityView(
                title=_safe_text(item.title),
                rationale=_safe_text(item.rationale),
                priority=item.priority.value,
                related_finding_ids=tuple(item.related_finding_ids),
                related_recommendation_ids=tuple(item.related_recommendation_ids),
            )
            for item in result.priorities
        ),
        risks=tuple(
            AiRiskView(
                title=_safe_text(item.title),
                summary=_safe_text(item.summary),
                severity=item.severity.value,
                related_finding_ids=tuple(item.related_finding_ids),
                related_recommendation_ids=tuple(item.related_recommendation_ids),
            )
            for item in result.risks
        ),
        suggested_next_steps=tuple(
            AiNextStepView(
                order=item.order,
                title=_safe_text(item.title),
                summary=_safe_text(item.summary),
                related_finding_ids=tuple(item.related_finding_ids),
                related_recommendation_ids=tuple(item.related_recommendation_ids),
            )
            for item in sorted(result.suggested_next_steps, key=lambda row: row.order)
        ),
        referenced_finding_ids=tuple(result.referenced_finding_ids),
        referenced_recommendation_ids=tuple(result.referenced_recommendation_ids),
        provider=_safe_text(result.provider_metadata.provider),
        model_id=_safe_text(result.provider_metadata.model_id),
        advisor_version=_safe_optional_text(result.provider_metadata.advisor_version),
        prompt_version=_safe_optional_text(result.provider_metadata.prompt_version),
        generated_at_utc=_safe_optional_text(result.provider_metadata.generated_at_utc),
        request_id=_safe_optional_text(result.provider_metadata.request_id),
        latency_ms=result.provider_metadata.latency_ms,
        input_tokens=result.provider_metadata.input_tokens,
        output_tokens=result.provider_metadata.output_tokens,
        limitations=tuple(_safe_text(item) for item in result.limitations),
    )


def _technology_items(analysis: AnalysisResult) -> tuple[TechnologyItemView, ...]:
    items = [
        TechnologyItemView(
            name=tech.name,
            category=str(getattr(tech.category, "value", tech.category))
            if tech.category is not None
            else None,
            version=tech.version,
        )
        for tech in contract_sorted_technologies(analysis.technologies)
    ]
    return tuple(items)


def _count_sorted(
    values: list[str] | tuple[str, ...],
    *,
    key_rank: object,
) -> tuple[tuple[str, int], ...]:
    counter: Counter[str] = Counter(values)
    return tuple(
        sorted(
            counter.items(),
            key=lambda pair: (key_rank(pair[0]), pair[0]),  # type: ignore[operator]
        )
    )


def _ai_enrichment_status(
    report_input: ModernizationReportInput,
    available: bool,
) -> str:
    if available:
        return "Available"
    if report_input.assessment_mode == AssessmentMode.DETERMINISTIC:
        return "Not requested"
    if report_input.ai_status == AIExecutionStatus.SUCCEEDED:
        return "Succeeded (artifact unavailable)"
    if report_input.ai_status == AIExecutionStatus.NOT_REQUESTED:
        return "Not requested"
    return ai_execution_status_label(report_input.ai_status)


def _assessment_summary_text(
    *,
    findings_count: int,
    recommendations_count: int,
    ai_available: bool,
) -> str:
    base = (
        f"{findings_count} finding(s) and "
        f"{recommendations_count} Priority Action(s) in this assessment."
    )
    if ai_available:
        return base + " Modernization Advisor narrative is included separately."
    return base


def _dashboard_metrics(
    *,
    analysis: AnalysisResult,
    technology_count: int,
    findings_count: int,
    recommendations_count: int,
    highest_finding_severity: str,
) -> DashboardMetrics:
    file_count = analysis.repository.total_files or len(analysis.repository.files)
    structure = analysis.facts.structure if analysis.facts is not None else None
    cicd = analysis.facts.cicd if analysis.facts is not None else None
    cloud = analysis.facts.cloud if analysis.facts is not None else None
    test_file_count = structure.test_file_count if structure is not None else None
    has_tests = structure.has_tests if structure is not None else None
    if has_tests is None and test_file_count is not None:
        has_tests = test_file_count > 0
    cicd_present: bool | None = None
    if cicd is not None:
        cicd_present = bool(cicd.has_ci) if cicd.has_ci is not None else bool(cicd.pipeline_count)
    cloud_count, cloud_primary, cloud_status = _cloud_enablement_signals(cloud)
    return DashboardMetrics(
        file_count=file_count,
        technology_count=technology_count,
        findings_count=findings_count,
        recommendations_count=recommendations_count,
        test_file_count=test_file_count,
        has_tests=has_tests,
        test_files_label=_test_files_label(
            test_file_count=test_file_count,
            has_tests=has_tests,
            structure_available=structure is not None,
        ),
        cicd_present=cicd_present,
        cicd_label=_cicd_label(cicd_present),
        cloud_signal_count=cloud_count,
        cloud_signals_primary=cloud_primary,
        cloud_signals_status=cloud_status,
        highest_finding_severity=highest_finding_severity,
        repository_size_label=f"{file_count} files",
    )


def _highest_finding_severity(findings: tuple[FindingView, ...]) -> str:
    """Return the highest severity among report findings, or None Detected."""

    if not findings:
        return "None Detected"
    order = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
        "informational": 4,
        "info": 4,
    }
    labels = {
        "critical": "Critical",
        "high": "High",
        "medium": "Medium",
        "low": "Low",
        "informational": "Informational",
        "info": "Informational",
    }
    best_key = min(
        (item.severity.lower() for item in findings),
        key=lambda key: order.get(key, 99),
    )
    return labels.get(best_key, "Unknown")


def _cloud_enablement_signals(cloud: object | None) -> tuple[int | None, str, str]:
    """Return (count, primary label, status) for the seven cloud enablement signals."""

    if cloud is None:
        return None, "Unknown", "Unknown"
    raw = (
        getattr(cloud, "has_docker", None),
        getattr(cloud, "has_kubernetes", None),
        getattr(cloud, "has_helm", None),
        getattr(cloud, "has_terraform", None),
        getattr(cloud, "has_cloudformation", None),
        getattr(cloud, "has_serverless", None),
        getattr(cloud, "has_docker_compose", None),
    )
    if all(value is None for value in raw):
        return None, "Unknown", "Unknown"
    count = sum(1 for value in raw if value is True)
    primary = f"{count} of 7"
    if count >= 2:
        status = "Established"
    elif count == 1:
        status = "Partial"
    else:
        status = "Not detected"
    return count, primary, status


def _cicd_label(present: bool | None) -> str:
    if present is True:
        return "Detected"
    if present is False:
        return "Not detected"
    return "Unknown"


def _test_files_label(
    *,
    test_file_count: int | None,
    has_tests: bool | None,
    structure_available: bool,
) -> str:
    if not structure_available:
        return "Unknown"
    if test_file_count is not None:
        return str(test_file_count)
    if has_tests is True:
        return "Detected"
    if has_tests is False:
        return "Not detected"
    return "Unknown"


def _safe_text(value: str) -> str:
    return redact_secrets(value.replace("\x00", ""))


def _safe_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    compact = value.strip()
    if not compact:
        return None
    return _safe_text(compact)


def _safe_path(value: str | None) -> str | None:
    if value is None:
        return None
    compact = value.strip()
    if not compact:
        return None
    return _safe_text(sanitize_display_path(compact))


def _safe_relative(path: str) -> str:
    compact = path.replace("\\", "/").strip().lstrip("/")
    if compact.startswith("..") or ":/" in compact or compact.startswith("/"):
        return _safe_text(sanitize_display_path(compact))
    return _safe_text(compact)


__all__ = [
    "HighlightedVersionInput",
    "ReportArtifactInput",
    "build_html_report_view_model",
    "default_report_artifacts",
]
