"""Initial architecture conclusion policies (Phase 4.2.3)."""

from __future__ import annotations

from codestrata.application.architecture.conclusions.helpers import (
    build_severity_summary,
    coverage_map,
    default_limitations,
    derive_confidence,
    derive_materiality,
    derive_status,
    scope_from_findings,
    wave_for_category,
)
from codestrata.application.architecture.conclusions.registry import (
    ConclusionPolicyContext,
    ConclusionPolicyMetadata,
    ConclusionPolicyResult,
)
from codestrata.domain.architecture.conclusions.enums import ConclusionStatus
from codestrata.domain.architecture.conclusions.identifiers import (
    CAT_BOUNDARY_INTEGRITY,
    CAT_COUPLING,
    CAT_DEPENDENCY_STRUCTURE,
    CAT_ENTERPRISE_CONFORMANCE,
    CAT_FRAMEWORK_INDEPENDENCE,
    CAT_INSUFFICIENT_EVIDENCE,
    POLICY_BOUNDARY_INTEGRITY,
    POLICY_BROAD_DEPENDENCY,
    POLICY_CYCLIC_DEPENDENCY,
    POLICY_ENTERPRISE_NONCONFORMANCE,
    POLICY_FRAMEWORK_EROSION,
    POLICY_INSUFFICIENT_EVIDENCE,
    POLICY_POSITIVE_BOUNDARY,
    build_conclusion_id,
)
from codestrata.domain.architecture.conclusions.models import ArchitectureConclusion
from codestrata.domain.findings import Finding
from codestrata.domain.rules.architecture.ids import (
    RULE_COMPONENT_CONCENTRATION,
    RULE_DEPENDENCY_CYCLE,
    RULE_ENTERPRISE_STANDARD_MISMATCH,
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
    RULE_FRAMEWORK_LEAKAGE,
    RULE_INVALID_DEPENDENCY_DIRECTION,
    RULE_LAYER_BOUNDARY_VIOLATION,
)


def _findings_for_rules(
    findings: tuple[Finding, ...],
    rule_ids: set[str],
) -> list[Finding]:
    return [item for item in findings if item.rule_id in rule_ids]


def _build_conclusion(
    *,
    policy_id: str,
    category: str,
    title: str,
    summary: str,
    technical: str,
    executive: str,
    findings: list[Finding],
    repository_id: str,
    extraction_coverage: float | None,
    classification_coverage: float | None,
    taxonomy_ids: tuple[str, ...] = (),
) -> ArchitectureConclusion:
    from codestrata.application.architecture.conclusions.clustering import select_primary_finding

    primary = select_primary_finding(findings)
    related = tuple(sorted(item.id for item in findings if item.id != primary.id))
    scope = scope_from_findings(findings)
    confidence = derive_confidence(
        findings,
        classification_coverage=classification_coverage,
        essential_finding_ids=[primary.id],
    )
    materiality = derive_materiality(findings, reinforcing_count=max(0, len(findings) - 1))
    status = derive_status(
        confidence=confidence,
        classification_coverage=classification_coverage,
    )
    conclusion_id = build_conclusion_id(
        policy_id=policy_id,
        policy_version="1.0.0",
        repository_id=repository_id,
        affected_scope=scope,
        source_finding_ids=[item.id for item in findings],
    )
    return ArchitectureConclusion(
        conclusion_id=conclusion_id,
        policy_id=policy_id,
        category=category,
        title=title,
        summary=summary,
        technical_interpretation=technical,
        executive_interpretation=executive,
        affected_scope=scope,
        taxonomy_ids=taxonomy_ids,
        source_finding_ids=tuple(sorted(item.id for item in findings)),
        primary_finding_id=primary.id,
        related_finding_ids=related,
        severity_summary=build_severity_summary(findings),
        business_impact="unknown",
        confidence=confidence,
        coverage=coverage_map(
            extraction_coverage=extraction_coverage,
            classification_coverage=classification_coverage,
        ),
        materiality=materiality,
        modernization_relevance=wave_for_category(category),
        limitations=default_limitations(),
        status=status,
        metadata={"primary_rule_id": primary.rule_id},
    )


class BoundaryIntegrityPolicy:
    def __init__(self) -> None:
        self._metadata = ConclusionPolicyMetadata(
            policy_id=POLICY_BOUNDARY_INTEGRITY,
            category=CAT_BOUNDARY_INTEGRITY,
            title="Boundary Integrity Concern",
            description=(
                "Groups direction, boundary, and related cycle findings that indicate "
                "incomplete architectural isolation between layers or modules."
            ),
            source_rule_ids=(
                RULE_INVALID_DEPENDENCY_DIRECTION,
                RULE_LAYER_BOUNDARY_VIOLATION,
                RULE_DEPENDENCY_CYCLE,
                RULE_FRAMEWORK_LEAKAGE,
            ),
            documentation_reference=(
                "docs/analysis-intelligence/architecture-conclusions/policies.md"
            ),
        )

    @property
    def metadata(self) -> ConclusionPolicyMetadata:
        return self._metadata

    def evaluate(self, context: ConclusionPolicyContext) -> ConclusionPolicyResult:
        cluster = context.cluster
        if cluster is None or cluster.category != CAT_BOUNDARY_INTEGRITY:
            return ConclusionPolicyResult.not_applicable("cluster_not_boundary_integrity")
        members = [item for item in context.findings if item.id in set(cluster.finding_ids)]
        direct = _findings_for_rules(
            tuple(members),
            {
                RULE_INVALID_DEPENDENCY_DIRECTION,
                RULE_LAYER_BOUNDARY_VIOLATION,
                RULE_FRAMEWORK_LEAKAGE,
            },
        )
        cycles = [item for item in members if item.rule_id == RULE_DEPENDENCY_CYCLE]
        if not members:
            return ConclusionPolicyResult.not_applicable("empty_cluster")
        # Cycle-only clusters are owned by CyclicDependencyPolicy.
        if cycles and not direct:
            return ConclusionPolicyResult.not_applicable("cycle_only_use_cyclic_policy")
        if not direct:
            return ConclusionPolicyResult.not_applicable("no_direct_boundary_finding")
        if (
            context.classification_coverage is not None
            and context.classification_coverage < 0.1
        ):
            return ConclusionPolicyResult.not_applicable("insufficient_classification_coverage")

        aspects: list[str] = []
        if any(item.rule_id == RULE_INVALID_DEPENDENCY_DIRECTION for item in members):
            aspects.append("wrong dependency direction")
        if any(item.rule_id == RULE_LAYER_BOUNDARY_VIOLATION for item in members):
            aspects.append("bypassed layer boundary")
        if any(item.rule_id == RULE_DEPENDENCY_CYCLE for item in members):
            aspects.append("cyclical boundary coupling")
        if any(item.rule_id == RULE_FRAMEWORK_LEAKAGE for item in members):
            aspects.append("framework leakage across an independent boundary")
        aspect_text = "; ".join(aspects)
        scope = scope_from_findings(members)
        scope_text = ", ".join(scope[:6]) or "related architectural units"
        title = "Architectural boundary integrity is incomplete"
        summary = (
            f"Related findings indicate incomplete isolation among {scope_text} "
            f"({aspect_text})."
        )
        technical = (
            "Static dependency analysis shows one or more boundary-related conditions "
            f"across the same architectural scope: {aspect_text}. Underlying findings "
            "remain individually valid and are not merged away."
        )
        executive = (
            f"The units {scope_text} participate in related boundary concerns "
            f"({aspect_text}). This can increase coordination cost for architectural "
            "change and should be reviewed before major module extraction. "
            "This conclusion is based on static analysis and does not establish "
            "business impact or production reliability."
        )
        conclusion = _build_conclusion(
            policy_id=POLICY_BOUNDARY_INTEGRITY,
            category=CAT_BOUNDARY_INTEGRITY,
            title=title,
            summary=summary,
            technical=technical,
            executive=executive,
            findings=members,
            repository_id=context.repository_id,
            extraction_coverage=context.extraction_coverage,
            classification_coverage=context.classification_coverage,
            taxonomy_ids=("boundary-integrity",),
        )
        return ConclusionPolicyResult.succeeded(conclusion)


class CyclicDependencyPolicy:
    def __init__(self) -> None:
        self._metadata = ConclusionPolicyMetadata(
            policy_id=POLICY_CYCLIC_DEPENDENCY,
            category=CAT_DEPENDENCY_STRUCTURE,
            title="Cyclic Dependency Structure",
            description="Standalone cycle conclusion when no boundary cluster absorbs it.",
            source_rule_ids=(RULE_DEPENDENCY_CYCLE,),
        )

    @property
    def metadata(self) -> ConclusionPolicyMetadata:
        return self._metadata

    def evaluate(self, context: ConclusionPolicyContext) -> ConclusionPolicyResult:
        cluster = context.cluster
        if cluster is None:
            return ConclusionPolicyResult.not_applicable("no_cluster")
        members = [item for item in context.findings if item.id in set(cluster.finding_ids)]
        cycles = [item for item in members if item.rule_id == RULE_DEPENDENCY_CYCLE]
        if not cycles:
            return ConclusionPolicyResult.not_applicable("no_cycle_finding")
        # Skip when already covered by boundary-integrity with reinforcing findings.
        if cluster.category == CAT_BOUNDARY_INTEGRITY and len(members) > 1:
            return ConclusionPolicyResult.skipped("absorbed_by_boundary_integrity")
        if any(
            item.rule_id
            in {
                RULE_INVALID_DEPENDENCY_DIRECTION,
                RULE_LAYER_BOUNDARY_VIOLATION,
                RULE_FRAMEWORK_LEAKAGE,
            }
            for item in members
        ):
            return ConclusionPolicyResult.skipped("absorbed_by_boundary_integrity")
        if cluster.category not in {CAT_DEPENDENCY_STRUCTURE, CAT_BOUNDARY_INTEGRITY}:
            return ConclusionPolicyResult.not_applicable("wrong_category")

        scope = scope_from_findings(cycles)
        scope_text = ", ".join(scope[:6]) or "architectural units"
        conclusion = _build_conclusion(
            policy_id=POLICY_CYCLIC_DEPENDENCY,
            category=CAT_DEPENDENCY_STRUCTURE,
            title="Directed dependency cycle among architectural units",
            summary=f"A dependency cycle was observed among {scope_text}.",
            technical=(
                "A directed cycle remains in the normalized primary dependency graph. "
                "Cycle resolution typically requires introducing a stable abstraction "
                "or inverting at least one dependency."
            ),
            executive=(
                f"Units {scope_text} form a dependency cycle. Cycles increase change "
                "coordination risk. This observation is limited to static analysis."
            ),
            findings=cycles,
            repository_id=context.repository_id,
            extraction_coverage=context.extraction_coverage,
            classification_coverage=context.classification_coverage,
            taxonomy_ids=("dependency-cycle",),
        )
        return ConclusionPolicyResult.succeeded(conclusion)


class BroadDependencySurfacePolicy:
    def __init__(self) -> None:
        self._metadata = ConclusionPolicyMetadata(
            policy_id=POLICY_BROAD_DEPENDENCY,
            category=CAT_COUPLING,
            title="Broad Dependency Surface",
            description="Coupling and concentration findings indicating wide dependency fan-out.",
            source_rule_ids=(
                RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
                RULE_COMPONENT_CONCENTRATION,
            ),
        )

    @property
    def metadata(self) -> ConclusionPolicyMetadata:
        return self._metadata

    def evaluate(self, context: ConclusionPolicyContext) -> ConclusionPolicyResult:
        cluster = context.cluster
        if cluster is None or cluster.category != CAT_COUPLING:
            return ConclusionPolicyResult.not_applicable("cluster_not_coupling")
        members = [item for item in context.findings if item.id in set(cluster.finding_ids)]
        if not members:
            return ConclusionPolicyResult.not_applicable("empty_cluster")
        scope = scope_from_findings(members)
        scope_text = ", ".join(scope[:6]) or "an architectural module"
        conclusion = _build_conclusion(
            policy_id=POLICY_BROAD_DEPENDENCY,
            category=CAT_COUPLING,
            title="Broad architectural dependency surface",
            summary=(
                f"One or more modules around {scope_text} show elevated coupling "
                "or concentration in the normalized dependency graph."
            ),
            technical=(
                "Outgoing cross-module edges and/or incident-edge concentration exceed "
                "configured thresholds for comparable primary units. This does not by "
                "itself prove poor maintainability."
            ),
            executive=(
                f"Module scope {scope_text} presents a broad dependency surface. "
                "Reducing fan-out can simplify future structural changes. "
                "No business impact is asserted from repository-only evidence."
            ),
            findings=members,
            repository_id=context.repository_id,
            extraction_coverage=context.extraction_coverage,
            classification_coverage=context.classification_coverage,
            taxonomy_ids=("coupling",),
        )
        return ConclusionPolicyResult.succeeded(conclusion)


class FrameworkBoundaryErosionPolicy:
    def __init__(self) -> None:
        self._metadata = ConclusionPolicyMetadata(
            policy_id=POLICY_FRAMEWORK_EROSION,
            category=CAT_FRAMEWORK_INDEPENDENCE,
            title="Framework Boundary Erosion",
            description="Framework leakage, optionally reinforced by boundary findings.",
            source_rule_ids=(RULE_FRAMEWORK_LEAKAGE, RULE_LAYER_BOUNDARY_VIOLATION),
        )

    @property
    def metadata(self) -> ConclusionPolicyMetadata:
        return self._metadata

    def evaluate(self, context: ConclusionPolicyContext) -> ConclusionPolicyResult:
        cluster = context.cluster
        if cluster is None:
            return ConclusionPolicyResult.not_applicable("no_cluster")
        members = [item for item in context.findings if item.id in set(cluster.finding_ids)]
        leakage = [item for item in members if item.rule_id == RULE_FRAMEWORK_LEAKAGE]
        if not leakage:
            return ConclusionPolicyResult.not_applicable("no_framework_leakage")
        if cluster.category == CAT_BOUNDARY_INTEGRITY and len(members) > len(leakage):
            return ConclusionPolicyResult.skipped("absorbed_by_boundary_integrity")
        scope_text = ", ".join(cluster.affected_scope[:6]) or "domain units"
        conclusion = _build_conclusion(
            policy_id=POLICY_FRAMEWORK_EROSION,
            category=CAT_FRAMEWORK_INDEPENDENCE,
            title="Framework types appear in an independent boundary",
            summary=f"Framework-specific usage was observed in {scope_text}.",
            technical=(
                "Framework annotation or type usage was detected in a layer expected "
                "to remain framework-independent under current heuristics."
            ),
            executive=(
                f"Framework-specific types appear within {scope_text}. "
                "This may hinder future isolation of domain logic from infrastructure "
                "frameworks. Evidence is static and heuristic."
            ),
            findings=members if cluster.category == CAT_FRAMEWORK_INDEPENDENCE else leakage,
            repository_id=context.repository_id,
            extraction_coverage=context.extraction_coverage,
            classification_coverage=context.classification_coverage,
            taxonomy_ids=("framework-independence",),
        )
        return ConclusionPolicyResult.succeeded(conclusion)


class EnterpriseNonconformancePolicy:
    def __init__(self) -> None:
        self._metadata = ConclusionPolicyMetadata(
            policy_id=POLICY_ENTERPRISE_NONCONFORMANCE,
            category=CAT_ENTERPRISE_CONFORMANCE,
            title="Enterprise Architecture Nonconformance",
            description="Enterprise-standard mismatch findings (enterprise context only).",
            source_rule_ids=(RULE_ENTERPRISE_STANDARD_MISMATCH,),
            enterprise_only=True,
        )

    @property
    def metadata(self) -> ConclusionPolicyMetadata:
        return self._metadata

    def evaluate(self, context: ConclusionPolicyContext) -> ConclusionPolicyResult:
        if not context.enterprise_context_present:
            return ConclusionPolicyResult.not_applicable("enterprise_context_absent")
        members = _findings_for_rules(
            context.findings, {RULE_ENTERPRISE_STANDARD_MISMATCH}
        )
        if not members:
            return ConclusionPolicyResult.not_applicable("no_enterprise_mismatch")
        conclusion = _build_conclusion(
            policy_id=POLICY_ENTERPRISE_NONCONFORMANCE,
            category=CAT_ENTERPRISE_CONFORMANCE,
            title="Declared enterprise architecture standard is not met",
            summary="Repository evidence conflicts with a declared enterprise standard.",
            technical=(
                "An enterprise-standard mismatch finding cites a declared standard. "
                "Enterprise context increases organizational relevance; it does not "
                "automatically raise technical severity."
            ),
            executive=(
                "Declared enterprise architecture expectations are not met for this "
                "repository. Review ownership and governing standards before structural "
                "change. Business impact remains unknown unless criticality is declared."
            ),
            findings=members,
            repository_id=context.repository_id,
            extraction_coverage=context.extraction_coverage,
            classification_coverage=context.classification_coverage,
            taxonomy_ids=("enterprise-conformance",),
        )
        return ConclusionPolicyResult.succeeded(conclusion)


class PositiveBoundaryConformancePolicy:
    """Domain support present; generation disabled until positive evidence is reliable."""

    def __init__(self) -> None:
        self._metadata = ConclusionPolicyMetadata(
            policy_id=POLICY_POSITIVE_BOUNDARY,
            category=CAT_BOUNDARY_INTEGRITY,
            title="Positive Boundary Conformance",
            description=(
                "Reserved for explicit positive boundary evidence. Disabled by default "
                "because absence of findings is not positive evidence."
            ),
            source_rule_ids=(),
            enabled_by_default=False,
        )

    @property
    def metadata(self) -> ConclusionPolicyMetadata:
        return self._metadata

    def evaluate(self, context: ConclusionPolicyContext) -> ConclusionPolicyResult:
        _ = context
        return ConclusionPolicyResult.skipped(
            "positive_conclusions_disabled_until_explicit_positive_evidence"
        )


class InsufficientEvidencePolicy:
    def __init__(self) -> None:
        self._metadata = ConclusionPolicyMetadata(
            policy_id=POLICY_INSUFFICIENT_EVIDENCE,
            category=CAT_INSUFFICIENT_EVIDENCE,
            title="Insufficient Architecture Evidence",
            description="Aggregates meaningful coverage limitations when assessment was requested.",
            source_rule_ids=(),
        )

    @property
    def metadata(self) -> ConclusionPolicyMetadata:
        return self._metadata

    def evaluate(self, context: ConclusionPolicyContext) -> ConclusionPolicyResult:
        # Only emit when architecture findings were expected but coverage is too low
        # and no other conclusions will speak to limitations.
        if context.cluster is not None:
            return ConclusionPolicyResult.not_applicable("cluster_present")
        classification = context.classification_coverage
        extraction = context.extraction_coverage
        if classification is None and extraction is None:
            return ConclusionPolicyResult.not_applicable("no_coverage_metrics")
        low_classification = classification is not None and classification < 0.2
        low_extraction = extraction is not None and extraction < 0.2
        if not (low_classification or low_extraction):
            return ConclusionPolicyResult.not_applicable("coverage_adequate")
        if context.findings:
            # Findings already convey concerns; avoid duplicate insufficient-evidence noise.
            return ConclusionPolicyResult.skipped("findings_present")

        from codestrata.domain.architecture.conclusions.enums import ConclusionMateriality
        from codestrata.domain.architecture.conclusions.relationships import SeveritySummary
        from codestrata.domain.rules.enums import RuleConfidence

        conclusion_id = build_conclusion_id(
            policy_id=POLICY_INSUFFICIENT_EVIDENCE,
            policy_version="1.0.0",
            repository_id=context.repository_id,
            affected_scope=("repository",),
            source_finding_ids=(),
        )
        conclusion = ArchitectureConclusion(
            conclusion_id=conclusion_id,
            policy_id=POLICY_INSUFFICIENT_EVIDENCE,
            category=CAT_INSUFFICIENT_EVIDENCE,
            title="Architecture evidence is insufficient for strong conclusions",
            summary=(
                "Architecture assessment was requested, but coverage is too limited "
                "to establish strong architectural conclusions."
            ),
            technical_interpretation=(
                "Extraction and/or classification coverage is below the threshold for "
                "confident boundary or coupling conclusions."
            ),
            executive_interpretation=(
                "Available static evidence is insufficient for a confident architecture "
                "judgment. Improve source coverage or layer classification before "
                "treating architecture as assessed."
            ),
            affected_scope=("repository",),
            source_finding_ids=(),
            severity_summary=SeveritySummary(
                highest_severity="informational",
                severity_counts={"informational": 0},
                source_finding_count=0,
            ),
            business_impact="unknown",
            confidence=RuleConfidence.LOW,
            coverage=coverage_map(
                extraction_coverage=extraction,
                classification_coverage=classification,
            ),
            materiality=ConclusionMateriality.INFORMATIONAL,
            modernization_relevance=wave_for_category(CAT_INSUFFICIENT_EVIDENCE),
            limitations=default_limitations(),
            status=ConclusionStatus.INSUFFICIENT_EVIDENCE,
        )
        return ConclusionPolicyResult.succeeded(conclusion)


def default_conclusion_policies() -> tuple[object, ...]:
    return (
        BoundaryIntegrityPolicy(),
        CyclicDependencyPolicy(),
        BroadDependencySurfacePolicy(),
        FrameworkBoundaryErosionPolicy(),
        EnterpriseNonconformancePolicy(),
        PositiveBoundaryConformancePolicy(),
        InsufficientEvidencePolicy(),
    )
