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
from codestrata.reporting.html_v2.assessment_head_grouping import (
    UNCLASSIFIED_LIMITATION,
    build_assessment_head_sections,
)
from codestrata.reporting.html_v2.assessment_heads import (
    ASSESSMENT_RESULT_HEADS,
    ASSESSMENT_RESULTS_ANCHOR,
    ASSESSMENT_RESULTS_TITLE,
    AssessmentHead,
    assessment_head_anchor,
    assessment_head_title,
)
from codestrata.reporting.html_v2.evidence_presentation import evidence_ref_view_from_domain
from codestrata.reporting.html_v2.leadership import (
    build_assessment_scope,
    build_engineering_risks,
    build_executive_summary_narrative,
    build_leadership_key_takeaways,
    build_leadership_priority_actions,
    build_leadership_roadmap,
    build_leadership_verdict,
    build_modernization_opportunities,
    customer_title,
)
from codestrata.reporting.html_v2.models import (
    AiEnrichmentView,
    AiNextStepView,
    AiPriorityView,
    AiRiskView,
    AiThemeView,
    ArtifactRefView,
    AssessmentHeadSectionView,
    AssessmentMetadataView,
    AssessmentScopeView,
    AssessmentSummaryView,
    CustomerReportDocument,
    DashboardMetrics,
    EngineeringRiskThemeView,
    EvidenceRefView,
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
from codestrata.reporting.ai_readiness.intelligence import (
    build_ai_readiness_intelligence,
)
from codestrata.reporting.architecture import build_architecture_intelligence
from codestrata.reporting.cloud.intelligence import build_cloud_intelligence
from codestrata.reporting.dependency.intelligence import build_dependency_intelligence
from codestrata.reporting.engineering_intelligence import build_engineering_intelligence
from codestrata.reporting.modernization.intelligence import (
    build_modernization_intelligence,
)
from codestrata.reporting.security.intelligence import build_security_intelligence
from codestrata.reporting.technical_debt.intelligence import (
    build_technical_debt_intelligence,
)
from codestrata.reporting.technology import build_technology_inventory
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
    technology_inventory = build_technology_inventory(
        analysis,
        highlighted_versions=report_input.highlighted_versions,
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
    priority_actions_canonical = build_leadership_priority_actions(
        findings=findings,
        recommendations=recommendations,
        max_actions=10_000,
    )
    from codestrata.application.priority_actions import priority_action_to_recommendation_view

    finding_by_id = {item.finding_id: item for item in findings}
    recommendation_by_id = {item.recommendation_id: item for item in recommendations}
    priority_actions = tuple(
        priority_action_to_recommendation_view(
            action,
            related_finding_titles=tuple(
                customer_title(finding_by_id[fid].title)
                if fid in finding_by_id
                else fid
                for fid in action.supporting_finding_ids
            ),
            supporting_recommendation_titles=tuple(
                recommendation_by_id[rid].title
                if rid in recommendation_by_id
                else rid
                for rid in action.supporting_recommendation_ids
            ),
        )
        for action in priority_actions_canonical
    )
    findings = _attach_finding_reverse_links(
        findings,
        recommendations=recommendations,
        priority_actions=priority_actions,
    )
    evidence_index = _collect_evidence_index(findings)
    assessment_summary = assessment_summary.model_copy(
        update={
            "recommendations_count": min(len(priority_actions), 8)
            if priority_actions
            else 0,
            "summary_text": _assessment_summary_text(
                findings_count=len(findings),
                recommendations_count=len(priority_actions),
                ai_available=ai_view is not None,
            ),
        }
    )
    # Leadership surfaces show a prioritized subset; full set remains on the document.
    leadership_actions = priority_actions[:8]
    key_takeaways = build_leadership_key_takeaways(
        findings=findings,
        recommendations=leadership_actions,
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
        recommendations=leadership_actions,
        risk_titles=risk_titles,
    )
    leadership_verdict = build_leadership_verdict(
        findings=findings,
        priority_actions=leadership_actions,
        metrics=metrics,
        highest_severity=highest_severity,
    )
    executive_summary = build_executive_summary_narrative(
        findings=findings,
        priority_actions=leadership_actions,
        metrics=metrics,
        highest_severity=highest_severity,
        technologies=tuple(item.name for item in technologies),
    )
    leadership_roadmap = build_leadership_roadmap(
        leadership_actions,
        canonical_actions=priority_actions_canonical,
    )
    roadmap_report = leadership_roadmap or report_input.roadmap_report
    assessed_packs = assessment_scope.assessed_packs if assessment_scope else ()
    not_assessed_packs = assessment_scope.not_assessed_packs if assessment_scope else ()
    head_rows, unclassified_findings, unclassified_recommendations = (
        build_assessment_head_sections(
            findings=findings,
            recommendations=recommendations,
            priority_actions=priority_actions,
            technologies_present=bool(technologies) or technology_inventory.fact_count > 0,
            architecture_present=report_input.architecture_report is not None,
            technical_debt_present=report_input.technical_debt_report is not None,
            dependency_present=report_input.dependency_report is not None,
            security_present=report_input.security_report is not None,
            cloud_present=report_input.cloud_report is not None,
            ai_readiness_present=report_input.ai_readiness_report is not None,
            assessed_packs=assessed_packs,
            not_assessed_packs=not_assessed_packs,
        )
    )
    architecture_intelligence = build_architecture_intelligence(
        report_input.architecture_report,
        findings=findings,
        recommendations=recommendations,
    )
    technical_debt_intelligence = build_technical_debt_intelligence(
        report_input.technical_debt_report,
        findings=findings,
        recommendations=recommendations,
    )
    dependency_intelligence = build_dependency_intelligence(
        report_input.dependency_report,
        findings=findings,
        recommendations=recommendations,
    )
    security_intelligence = build_security_intelligence(
        report_input.security_report,
        findings=findings,
        recommendations=recommendations,
    )
    cloud_intelligence = build_cloud_intelligence(
        report_input.cloud_report,
        findings=findings,
        recommendations=recommendations,
    )
    ai_readiness_intelligence = build_ai_readiness_intelligence(
        report_input.ai_readiness_report,
        findings=findings,
        recommendations=recommendations,
    )
    modernization_intelligence = build_modernization_intelligence(
        findings=findings,
        recommendations=recommendations,
        priority_actions=priority_actions,
        roadmap_report=roadmap_report,
    )
    assessment_heads = tuple(
        _enrich_modernization_assessment_head(
            _enrich_ai_readiness_head(
                _enrich_cloud_readiness_head(
                    _enrich_security_intelligence_head(
                        _enrich_dependency_intelligence_head(
                            _enrich_technical_debt_intelligence_head(
                                _enrich_architecture_intelligence_head(
                                    _enrich_technology_inventory_head(
                                        AssessmentHeadSectionView(**row),
                                        technology_inventory,
                                    ),
                                    architecture_intelligence,
                                ),
                                technical_debt_intelligence,
                            ),
                            dependency_intelligence,
                        ),
                        security_intelligence,
                    ),
                    cloud_intelligence,
                ),
                ai_readiness_intelligence,
            ),
            modernization_intelligence,
        )
        for row in head_rows
    )
    assessment_heads = _apply_modernization_head_confidence(assessment_heads)
    assessment_heads = _attach_assessment_coverage(
        assessment_heads,
        report_input=report_input,
        technologies_present=bool(technologies) or technology_inventory.fact_count > 0,
        assessed_packs=assessed_packs,
        not_assessed_packs=not_assessed_packs,
    )
    engineering_intelligence = build_engineering_intelligence(
        assessment_heads=assessment_heads,
        priority_actions=priority_actions,
        priority_actions_total=len(priority_actions),
        roadmap_report=roadmap_report,
        assessment_summary=assessment_summary,
        highest_finding_severity=summary.highest_finding_severity,
        unclassified_limitation=UNCLASSIFIED_LIMITATION,
        has_unclassified=bool(unclassified_findings or unclassified_recommendations),
    )
    document = CustomerReportDocument(
        summary=summary,
        repository=repository,
        technologies=technologies,
        version_highlights=version_highlights,
        assessment_summary=assessment_summary,
        findings=findings,
        recommendations=recommendations,
        priority_actions=priority_actions,
        priority_actions_total=len(priority_actions),
        evidence=evidence_index,
        ai_enrichment=ai_view,
        architecture_report=report_input.architecture_report,
        architecture_intelligence=architecture_intelligence,
        technical_debt_report=report_input.technical_debt_report,
        technical_debt_intelligence=technical_debt_intelligence,
        dependency_report=report_input.dependency_report,
        dependency_intelligence=dependency_intelligence,
        security_report=report_input.security_report,
        security_intelligence=security_intelligence,
        testing_report=report_input.testing_report,
        cloud_report=report_input.cloud_report,
        cloud_intelligence=cloud_intelligence,
        ai_readiness_report=report_input.ai_readiness_report,
        ai_readiness_intelligence=ai_readiness_intelligence,
        modernization_intelligence=modernization_intelligence,
        engineering_intelligence=engineering_intelligence,
        performance_report=report_input.performance_report,
        technology_inventory=technology_inventory,
        roadmap_report=roadmap_report,
        artifacts=artifacts,
        metadata=metadata,
        leadership_verdict=leadership_verdict,
        executive_summary=executive_summary,
        key_takeaways=key_takeaways,
        engineering_risks=engineering_risks,
        modernization_opportunities=modernization_opportunities,
        assessment_scope=assessment_scope,
        assessment_heads=assessment_heads,
        unclassified_findings=unclassified_findings,
        unclassified_recommendations=unclassified_recommendations,
        unclassified_limitation=UNCLASSIFIED_LIMITATION,
        outline=(),  # filled below once presence is known
    )
    outline = _build_outline(document)
    return document.model_copy(update={"outline": outline})


def build_html_report_view_model(report_input: ModernizationReportInput) -> CustomerReportDocument:
    """Backward-compatible alias for :func:`build_customer_report_document`."""

    return build_customer_report_document(report_input)


def _build_outline(document: CustomerReportDocument) -> tuple[ReportOutlineEntry, ...]:
    """Stable TOC entries for the Epic 3 assessment-head report hierarchy.

    Entries are presence-driven: an outline entry is emitted only when the
    renderer emits the matching section, so contents links never resolve to a
    missing anchor.
    """

    entries: list[ReportOutlineEntry] = []
    if (document.leadership_verdict or "").strip():
        entries.append(
            ReportOutlineEntry(section_id="leadership-verdict", title="Leadership Verdict")
        )
    entries.append(
        ReportOutlineEntry(section_id="executive-summary", title="Executive Summary")
    )
    entries.extend([
        ReportOutlineEntry(
            section_id=assessment_head_anchor(AssessmentHead.ENGINEERING_INTELLIGENCE),
            title=assessment_head_title(AssessmentHead.ENGINEERING_INTELLIGENCE),
        ),
        ReportOutlineEntry(section_id="key-takeaways", title="Key Takeaways"),
        ReportOutlineEntry(section_id="priority-actions", title="Priority Actions"),
        ReportOutlineEntry(section_id="engineering-risks", title="Engineering Risks"),
        ReportOutlineEntry(
            section_id=ASSESSMENT_RESULTS_ANCHOR,
            title=ASSESSMENT_RESULTS_TITLE,
        ),
    ])
    rendered_heads = {section.head for section in document.assessment_heads}
    head_anchors = {
        section.head: (section.anchor or assessment_head_anchor(section.head))
        for section in document.assessment_heads
    }
    for head in ASSESSMENT_RESULT_HEADS:
        if head.value not in rendered_heads:
            continue
        entries.append(
            ReportOutlineEntry(
                section_id=head_anchors.get(head.value) or assessment_head_anchor(head),
                title=assessment_head_title(head),
            )
        )
    if document.roadmap_report is not None:
        entries.append(
            ReportOutlineEntry(
                section_id="phased-modernization-plan",
                title="Roadmap",
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
    findings = resolve_customer_findings(report_input)
    finding_titles = {item.id: item.title for item in findings}
    correlation_labels = _correlation_relationship_labels(report_input)
    return tuple(
        _customer_finding_view(
            item,
            finding_titles=finding_titles,
            correlation_labels=correlation_labels.get(item.id, {}),
        )
        for item in findings
    )


_SEVERITY_BASIS_LABELS = {
    "direct_secret_exposure": "Direct secret exposure signal",
    "explicit_security_control_disabled": "Explicit configuration state",
    "exploitable_configuration_pattern": "Configuration hygiene concern",
    "architectural_boundary_violation": "Architectural boundary relationship",
    "architectural_cycle": "Architectural dependency cycle",
    "dependency_declaration_instability": "Dependency declaration semantics",
    "deterministic_threshold_exceedance": "Configured threshold exceeded",
    "threshold_magnitude": "Measurement magnitude above threshold",
    "production_context": "Production-context repository evidence",
    "test_or_fixture_context": "Test, fixture, or documentation context",
    "runtime_impact_unverified": "Static runtime impact unverified",
    "business_impact_unverified": "Business impact unverified",
    "static_signal_only": "Static repository signal",
    "readiness_inventory_signal": "Repository readiness inventory signal",
    "context_cap": "Repository context severity cap",
    "measurement_band": "Typed measurement severity band",
    "explicit_rule_policy": "Explicit rule severity policy",
    "rule_default": "Rule default severity",
    "legacy_rule": "Legacy rule severity",
}


def _severity_basis_labels(item: CustomerFinding) -> tuple[str, ...]:
    assessment = item.severity_assessment if isinstance(item.severity_assessment, dict) else {}
    raw = assessment.get("basis") if assessment else None
    if not raw:
        meta = str(
            (item.metadata or {}).get("severity_calibration_basis")
            or (item.metadata or {}).get("severity_basis")
            or ""
        )
        raw = [part for part in meta.split(",") if part.strip()]
    labels: list[str] = []
    for basis in raw or ():
        key = str(getattr(basis, "value", basis)).strip().lower()
        label = _SEVERITY_BASIS_LABELS.get(key)
        if label and label not in labels:
            labels.append(label)
    return tuple(labels[:5])


def _correlation_relationship_labels(
    report_input: ModernizationReportInput,
) -> dict[str, dict[str, str]]:
    """Map finding_id -> {related_finding_id: customer-safe relationship label}."""

    from codestrata.reporting.assessment_json import _finding_correlations_payload

    labels: dict[str, dict[str, str]] = {}
    type_labels = {
        "configuration_cluster": "Same configuration subject",
        "dependency_cluster": "Same dependency identity",
        "architecture_cluster": "Same architecture subject",
        "complexity_cluster": "Same measurement subject",
        "shared_evidence": "Shared evidence",
        "shared_subject": "Same repository subject",
        "deployment_cluster": "Same deployment artifact",
        "ai_integration_cluster": "Same AI integration boundary",
        "cross_head_modernization": "Related modernization condition",
    }
    for item in _finding_correlations_payload(report_input):
        if not isinstance(item, dict):
            continue
        ctype = str(item.get("correlation_type") or "")
        label = type_labels.get(ctype, "Related repository condition")
        members = [str(fid) for fid in (item.get("finding_ids") or []) if fid]
        for fid in members:
            bucket = labels.setdefault(fid, {})
            for other in members:
                if other != fid:
                    bucket[other] = label
    return labels


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


def _customer_finding_view(
    item: CustomerFinding,
    *,
    finding_titles: dict[str, str] | None = None,
    correlation_labels: dict[str, str] | None = None,
) -> FindingView:
    evidence_refs = tuple(
        evidence_ref_view_from_domain(ref)
        for ref in item.evidence_refs
        if getattr(ref, "evidence_id", None)
    )
    # Drop absolute / file:// paths from projected EvidenceRef views.
    sanitized_refs: list[EvidenceRefView] = []
    for ref in evidence_refs:
        path = ref.path
        if path and (path.startswith("/") or path.startswith("file:")):
            path = _safe_path(path)
            if path and (path.startswith("/") or path.startswith("file:")):
                path = None
            ref = ref.model_copy(update={"path": path})
        sanitized_refs.append(ref)
    titles = finding_titles or {}
    labels = correlation_labels or {}
    related_ids = tuple(item.correlated_finding_ids)
    related_titles = tuple(titles.get(fid, fid) for fid in related_ids)
    related_labels = tuple(
        labels.get(fid, "Related repository condition") for fid in related_ids
    )
    base_kwargs = {
        "evidence_refs": tuple(sanitized_refs),
        "primary_evidence_id": item.primary_evidence_id,
        "synthesized_from_evidence_ids": tuple(item.synthesized_from_evidence_ids),
        "evidence_completeness": item.evidence_completeness or "legacy",
        "limitations": tuple(item.limitations),
        "finding_confidence_level": _finding_confidence_level(item),
        "rule_confidence_level": _rule_confidence_level(item),
        "correlated_finding_ids": related_ids,
        "correlated_finding_titles": related_titles,
        "correlation_relationship_labels": related_labels,
        "severity_basis_labels": _severity_basis_labels(item),
    }
    if item.phase1 is not None:
        view = _phase1_finding_view(item.phase1)
        return view.model_copy(update=base_kwargs)
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
        **base_kwargs,
    )


def _customer_recommendation_view(
    item: CustomerRecommendation,
    *,
    finding_id_map: dict[str, str] | None = None,
    finding_titles: dict[str, str] | None = None,
) -> RecommendationView:
    titles = finding_titles or {}
    supporting = tuple(item.supporting_finding_ids or item.related_finding_ids)
    related = tuple(item.related_finding_ids or item.supporting_finding_ids)
    # Compatibility: keep dual fields equivalent without duplicating in UI.
    finding_ids = tuple(sorted(set(supporting) | set(related)))
    related_titles = tuple(titles[fid] for fid in finding_ids if fid in titles)
    primary = item.primary_finding_id
    if primary is not None and primary not in finding_ids:
        primary = finding_ids[0] if finding_ids else None
    elif primary is None and finding_ids:
        primary = finding_ids[0]
    confidence_limits: tuple[str, ...] = ()
    confidence = getattr(item, "recommendation_confidence", None)
    if confidence is not None:
        raw_limits = getattr(confidence, "limitations", None)
        if raw_limits is None and isinstance(confidence, dict):
            raw_limits = confidence.get("limitations")
        if raw_limits:
            confidence_limits = tuple(str(note) for note in raw_limits if str(note).strip())
    limitations = tuple(dict.fromkeys((*item.limitations, *confidence_limits)))
    trace_kwargs = {
        "related_finding_ids": finding_ids,
        "related_finding_titles": related_titles,
        "primary_finding_id": primary,
        "recommendation_type": item.recommendation_type or "legacy",
        "evidence_completeness": item.evidence_completeness or "legacy",
        "limitations": limitations,
        "recommendation_confidence_level": _recommendation_confidence_level(item),
        "priority_basis_labels": _priority_basis_labels(item),
        "effort": item.effort,
        "risk": item.risk,
        "dependencies": tuple(item.dependencies),
        "priority_score": item.priority_score,
        "presentation_bucket": item.presentation_bucket,
    }
    if item.phase1 is not None:
        view = _phase1_recommendation_view(item.phase1, finding_id_map=finding_id_map or {})
        return view.model_copy(update=trace_kwargs)
    return RecommendationView(
        recommendation_id=item.id,
        title=_safe_text(item.title),
        summary=_safe_text(item.description),
        rationale=_safe_text(item.rationale or item.description),
        priority=item.priority,
        category=item.category,
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
        **trace_kwargs,
    )


def _collect_evidence_index(findings: tuple[FindingView, ...]) -> tuple[EvidenceRefView, ...]:
    by_id: dict[str, EvidenceRefView] = {}
    for finding in findings:
        for ref in finding.evidence_refs:
            existing = by_id.get(ref.evidence_id)
            if existing is None:
                by_id[ref.evidence_id] = ref
    return tuple(sorted(by_id.values(), key=lambda item: item.evidence_id))


def _attach_finding_reverse_links(
    findings: tuple[FindingView, ...],
    *,
    recommendations: tuple[RecommendationView, ...],
    priority_actions: tuple[RecommendationView, ...],
) -> tuple[FindingView, ...]:
    recs_by_finding: dict[str, list[RecommendationView]] = {}
    for rec in recommendations:
        for fid in rec.related_finding_ids:
            recs_by_finding.setdefault(fid, []).append(rec)
    actions_by_finding: dict[str, list[RecommendationView]] = {}
    for action in priority_actions:
        for fid in action.related_finding_ids:
            actions_by_finding.setdefault(fid, []).append(action)
    updated: list[FindingView] = []
    for finding in findings:
        recs = recs_by_finding.get(finding.finding_id, [])
        actions = actions_by_finding.get(finding.finding_id, [])
        updated.append(
            finding.model_copy(
                update={
                    "driven_recommendation_ids": tuple(item.recommendation_id for item in recs),
                    "driven_recommendation_titles": tuple(item.title for item in recs),
                    "influenced_priority_action_ids": tuple(
                        item.recommendation_id for item in actions
                    ),
                    "influenced_priority_action_titles": tuple(item.title for item in actions),
                }
            )
        )
    return tuple(updated)


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
        finding_confidence_level=finding.finding_confidence.level.value,
        rule_confidence_level=(
            str(finding.metadata.get("rule_confidence_level") or "") or None
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
            confidence=tech.confidence,
            source=tech.source,
        )
        for tech in contract_sorted_technologies(analysis.technologies)
    ]
    return tuple(items)


def _enrich_technology_inventory_head(
    section: AssessmentHeadSectionView,
    inventory,
) -> AssessmentHeadSectionView:
    """Overlay Slice 3.2 inventory status/limitations; confidence is canonical."""

    if section.head != AssessmentHead.TECHNOLOGY_INVENTORY.value:
        return section
    from codestrata.application.assessment_heads.confidence import (
        apply_canonical_head_confidence,
    )

    status_map = {
        "inventory_generated": "assessed",
        "partial_inventory": "partially_assessed",
        "inventory_unavailable": "not_available",
        "legacy_inventory": "legacy_assessment",
    }
    status = status_map.get(inventory.status, section.status)
    limitations = tuple(
        dict.fromkeys((*section.limitations, *inventory.limitations))
    )
    updated = section.model_copy(
        update={
            "status": status,
            "status_label": inventory.status_label,
            "limitations": limitations,
            "pack_content_available": True,
            "placeholder_message": (
                None
                if inventory.fact_count or inventory.composition is not None
                else "No supported technology evidence was available."
            ),
        }
    )
    coverage = {
        "assessed": "complete",
        "partially_assessed": "partial",
        "not_available": "unavailable",
        "legacy_assessment": "legacy",
    }.get(status, "unavailable")
    return apply_canonical_head_confidence(
        updated,
        coverage_state=coverage,
        inventory_confidence=getattr(inventory, "confidence", None),
    )


_PACK_STATUS_MAP = {
    "succeeded": "assessed",
    "partially_succeeded": "partially_assessed",
    "insufficient_evidence": "partially_assessed",
    "disabled": "not_enabled",
    "not_applicable": "not_available",
    "failed": "not_available",
    "not_requested": "not_available",
}


def _finalize_pack_head(
    section: AssessmentHeadSectionView,
    intelligence,
    *,
    placeholder: str | None,
) -> AssessmentHeadSectionView:
    from codestrata.application.assessment_heads.confidence import (
        apply_canonical_head_confidence,
    )

    status = _PACK_STATUS_MAP.get(intelligence.status, section.status)
    limitations = tuple(dict.fromkeys((*section.limitations, *intelligence.limitations)))
    updated = section.model_copy(
        update={
            "status": status,
            "status_label": intelligence.status_label,
            "limitations": limitations,
            "pack_content_available": True,
            "placeholder_message": placeholder,
            "findings_count": max(section.findings_count, intelligence.finding_count),
            "recommendations_count": max(
                section.recommendations_count, intelligence.recommendation_count
            ),
        }
    )
    coverage = {
        "succeeded": "complete",
        "partially_succeeded": "partial",
        "insufficient_evidence": "insufficient",
        "disabled": "unavailable",
        "not_applicable": "unsupported",
        "failed": "unavailable",
        "not_requested": "unavailable",
    }.get(str(intelligence.status), None)
    return apply_canonical_head_confidence(
        updated,
        pack_assessment_status=str(intelligence.status),
        coverage_state=coverage,
    )


def _enrich_architecture_intelligence_head(
    section: AssessmentHeadSectionView,
    intelligence,
) -> AssessmentHeadSectionView:
    """Overlay Slice 3.3 Architecture Intelligence status/limitations; confidence is canonical."""

    if intelligence is None:
        return section
    if section.head != AssessmentHead.ARCHITECTURE_INTELLIGENCE.value:
        return section
    placeholder = None
    if intelligence.status in {"disabled", "not_requested"}:
        placeholder = "Architecture analysis was not enabled for this assessment."
    elif intelligence.status in {"not_applicable", "failed"}:
        placeholder = "Architecture assessment is not available for this repository."
    elif intelligence.finding_count == 0 and intelligence.status == "insufficient_evidence":
        placeholder = "Architecture coverage was partial; conclusions could not be established safely."
    return _finalize_pack_head(section, intelligence, placeholder=placeholder)


def _enrich_technical_debt_intelligence_head(
    section: AssessmentHeadSectionView,
    intelligence,
) -> AssessmentHeadSectionView:
    """Overlay Technical Debt status/limitations; confidence is canonical."""

    if intelligence is None:
        return section
    if section.head != AssessmentHead.TECHNICAL_DEBT_INTELLIGENCE.value:
        return section
    placeholder = None
    if intelligence.status in {"disabled", "not_requested"}:
        placeholder = "Technical debt analysis was not enabled for this assessment."
    elif intelligence.status in {"not_applicable", "failed"}:
        placeholder = "Technical debt assessment is not available for this repository."
    elif intelligence.finding_count == 0 and intelligence.status == "insufficient_evidence":
        placeholder = (
            "Technical debt coverage was partial; conclusions could not be "
            "established safely."
        )
    return _finalize_pack_head(section, intelligence, placeholder=placeholder)


def _enrich_dependency_intelligence_head(
    section: AssessmentHeadSectionView,
    intelligence,
) -> AssessmentHeadSectionView:
    """Overlay Dependency status/limitations; confidence is canonical."""

    if intelligence is None:
        return section
    if section.head != AssessmentHead.DEPENDENCY_INTELLIGENCE.value:
        return section
    placeholder = None
    if intelligence.status in {"disabled", "not_requested"}:
        placeholder = "Dependency analysis was not enabled for this assessment."
    elif intelligence.status in {"not_applicable", "failed"}:
        placeholder = "Dependency assessment is not available for this repository."
    elif intelligence.finding_count == 0 and intelligence.status == "insufficient_evidence":
        placeholder = (
            "Dependency coverage was partial; conclusions could not be "
            "established safely."
        )
    return _finalize_pack_head(section, intelligence, placeholder=placeholder)


def _enrich_security_intelligence_head(
    section: AssessmentHeadSectionView,
    intelligence,
) -> AssessmentHeadSectionView:
    """Overlay Security status/limitations; confidence is canonical."""

    if intelligence is None:
        return section
    if section.head != AssessmentHead.SECURITY_INTELLIGENCE.value:
        return section
    placeholder = None
    if intelligence.status in {"disabled", "not_requested"}:
        placeholder = "Security analysis was not enabled for this assessment."
    elif intelligence.status in {"not_applicable", "failed"}:
        placeholder = "Security assessment is not available for this repository."
    elif intelligence.finding_count == 0 and intelligence.status == "insufficient_evidence":
        placeholder = (
            "Security coverage was partial; conclusions could not be "
            "established safely."
        )
    return _finalize_pack_head(section, intelligence, placeholder=placeholder)


def _enrich_cloud_readiness_head(
    section: AssessmentHeadSectionView,
    intelligence,
) -> AssessmentHeadSectionView:
    """Overlay Cloud Readiness status/limitations; confidence is canonical."""

    if intelligence is None:
        return section
    if section.head != AssessmentHead.CLOUD_READINESS.value:
        return section
    placeholder = None
    if intelligence.status in {"disabled", "not_requested"}:
        placeholder = "Cloud analysis was not enabled for this assessment."
    elif intelligence.status in {"not_applicable", "failed"}:
        placeholder = "Cloud assessment is not available for this repository."
    elif intelligence.finding_count == 0 and intelligence.status == "insufficient_evidence":
        placeholder = (
            "Cloud coverage was partial; conclusions could not be "
            "established safely."
        )
    return _finalize_pack_head(section, intelligence, placeholder=placeholder)


def _enrich_ai_readiness_head(
    section: AssessmentHeadSectionView,
    intelligence,
) -> AssessmentHeadSectionView:
    """Overlay AI Readiness status/limitations; confidence is canonical."""

    if intelligence is None:
        return section
    if section.head != AssessmentHead.AI_READINESS.value:
        return section
    placeholder = None
    if intelligence.status in {"disabled", "not_requested"}:
        placeholder = "AI readiness analysis was not enabled for this assessment."
    elif intelligence.status in {"not_applicable", "failed"}:
        placeholder = "AI readiness assessment is not available for this repository."
    elif intelligence.finding_count == 0 and intelligence.status == "insufficient_evidence":
        placeholder = (
            "AI readiness coverage was partial; conclusions could not be "
            "established safely."
        )
    return _finalize_pack_head(section, intelligence, placeholder=placeholder)


def _enrich_modernization_assessment_head(
    section: AssessmentHeadSectionView,
    intelligence,
) -> AssessmentHeadSectionView:
    """Overlay Modernization status/limitations; confidence recomputed later."""

    if intelligence is None:
        return section
    if section.head != AssessmentHead.MODERNIZATION_ASSESSMENT.value:
        return section
    retained = tuple(
        note
        for note in section.limitations
        if "scheduled for a later release" not in note.lower()
    )
    limitations = tuple(dict.fromkeys((*retained, *intelligence.limitations)))
    placeholder = None
    if intelligence.status == "not_available" and intelligence.priority_action_count == 0:
        placeholder = intelligence.empty_actions_message
    return section.model_copy(
        update={
            "status": intelligence.status,
            "status_label": intelligence.status_label,
            "limitations": limitations,
            "pack_content_available": True,
            "placeholder_message": placeholder,
        }
    )


def _apply_modernization_head_confidence(
    sections: tuple[AssessmentHeadSectionView, ...],
) -> tuple[AssessmentHeadSectionView, ...]:
    """Bound modernization confidence by contributing assessment heads."""

    from codestrata.application.assessment_heads.confidence import (
        apply_canonical_head_confidence,
    )

    contributing = tuple(
        item.confidence
        for item in sections
        if item.head != AssessmentHead.MODERNIZATION_ASSESSMENT.value
        and item.status not in {"not_enabled", "not_available"}
    )
    out: list[AssessmentHeadSectionView] = []
    for section in sections:
        if section.head != AssessmentHead.MODERNIZATION_ASSESSMENT.value:
            out.append(section)
            continue
        out.append(
            apply_canonical_head_confidence(
                section,
                coverage_state=(
                    "partial"
                    if section.status == "partially_assessed"
                    else "unavailable"
                    if section.status == "not_available"
                    else "complete"
                ),
                contributing_head_levels=contributing,
                assessment_coverage=section.assessment_coverage,
            )
        )
    return tuple(out)


def _attach_assessment_coverage(
    sections: tuple[AssessmentHeadSectionView, ...],
    *,
    report_input,
    technologies_present: bool,
    assessed_packs,
    not_assessed_packs,
) -> tuple[AssessmentHeadSectionView, ...]:
    """Attach canonical AssessmentCoverage and refresh head confidence from it."""

    from codestrata.application.assessment_heads.confidence import (
        apply_canonical_head_confidence,
    )
    from codestrata.application.assessment_heads.coverage import (
        build_assessment_coverage_map,
        derive_assessment_coverage,
    )
    from codestrata.domain.assessment_heads.assessment_coverage import (
        AssessmentCoverage,
    )

    def _dump(section) -> dict | None:
        if section is None:
            return None
        if hasattr(section, "model_dump"):
            return section.model_dump(mode="json")
        if isinstance(section, dict):
            return section
        return None

    pack_sections = {
        "architecture": _dump(report_input.architecture_report),
        "technical_debt": _dump(report_input.technical_debt_report),
        "dependency": _dump(report_input.dependency_report),
        "security": _dump(report_input.security_report),
        "testing": _dump(report_input.testing_report),
        "cloud": _dump(report_input.cloud_report),
        "ai_readiness": _dump(report_input.ai_readiness_report),
        "performance": _dump(getattr(report_input, "performance_report", None)),
        "roadmap": _dump(report_input.roadmap_report),
    }
    activation = {
        "assessed_packs": tuple(assessed_packs or ()),
        "not_assessed_packs": tuple(not_assessed_packs or ()),
    }
    coverage_map = build_assessment_coverage_map(
        pack_sections=pack_sections,
        technologies_present=technologies_present,
        activation=activation,
    )
    out: list[AssessmentHeadSectionView] = []
    for section in sections:
        payload = coverage_map.get(section.head)
        if payload is None:
            coverage = derive_assessment_coverage(
                head_id=section.head,
                activated=section.status not in {"not_enabled", "not_available"},
                pack_status=(
                    "disabled"
                    if section.status == "not_enabled"
                    else "failed"
                    if section.status == "not_available"
                    else "succeeded"
                    if section.status == "assessed"
                    else "partially_succeeded"
                    if section.status == "partially_assessed"
                    else None
                ),
            )
            payload = coverage.model_dump(mode="json") if isinstance(coverage, AssessmentCoverage) else None
        updated = section.model_copy(update={"assessment_coverage": payload})
        out.append(
            apply_canonical_head_confidence(
                updated,
                assessment_coverage=payload,
            )
        )
    # Re-bound modernization after contributor confidence refresh.
    return _apply_modernization_head_confidence(tuple(out))



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


def _finding_confidence_level(item: CustomerFinding) -> str | None:
    confidence = getattr(item, "finding_confidence", None)
    if confidence is None:
        return None
    level = getattr(confidence, "level", None)
    if level is None and isinstance(confidence, dict):
        level = confidence.get("level")
    if level is None:
        return None
    return str(getattr(level, "value", level))


def _recommendation_confidence_level(item: CustomerRecommendation) -> str | None:
    confidence = getattr(item, "recommendation_confidence", None)
    if confidence is None:
        return None
    level = getattr(confidence, "level", None)
    if level is None and isinstance(confidence, dict):
        level = confidence.get("level")
    if level is None:
        return None
    return str(getattr(level, "value", level))


def _priority_basis_labels(item: CustomerRecommendation) -> tuple[str, ...]:
    assessment = getattr(item, "priority_assessment", None)
    if assessment is None:
        return ()
    basis = getattr(assessment, "basis", None)
    summary = getattr(assessment, "component_summary", None)
    if basis is None and isinstance(assessment, dict):
        basis = assessment.get("basis")
        summary = assessment.get("component_summary")
    if not basis:
        return ()
    highest = None
    if summary is not None:
        highest = getattr(summary, "highest_finding_severity", None)
        if highest is None and isinstance(summary, dict):
            highest = summary.get("highest_finding_severity")
    severity_label = "Supported Finding severity"
    if highest:
        severity_label = f"{str(highest).replace('_', ' ').title()}-severity supported Finding"

    labels_by_key = {
        "calibrated_finding_severity": severity_label,
        "recommendation_confidence": "Recommendation confidence",
        "direct_security_exposure": "Direct production configuration remediation",
        "deterministic_scope": "Broad deterministic scope",
        "correlated_supporting_findings": "Correlated supporting Findings",
        "evidence_completeness": "Evidence completeness constraint",
        "static_only_limitation": "Static runtime effect not validated",
        "legacy_recommendation": "Legacy Recommendation",
        "confidence_cap": "Confidence-bounded urgency",
        "context_cap": "Non-production context",
    }
    labels: list[str] = []
    for item_basis in basis:
        key = str(getattr(item_basis, "value", item_basis)).strip().lower()
        label = labels_by_key.get(key)
        if label and label not in labels:
            labels.append(label)
    return tuple(labels[:4])


def _rule_confidence_level(item: CustomerFinding) -> str | None:
    raw = item.metadata.get("rule_confidence_level")
    if raw:
        return str(raw)
    block = item.metadata.get("rule_confidence")
    if isinstance(block, dict) and block.get("level"):
        return str(block["level"])
    return None


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
