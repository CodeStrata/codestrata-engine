"""Conservative reuse eligibility decisions for incremental planning."""

from __future__ import annotations

import logging

from codestrata.application.incremental.models import (
    CompatibilityResult,
    ImpactAnalysis,
    RepositoryChangeSet,
    ReuseAssessment,
    ReuseDecision,
)
from codestrata.application.incremental.policies import IncrementalPlanningPolicy

logger = logging.getLogger(__name__)

_SUBJECTS = (
    "inventory",
    "technology_detection",
    "repository_graph",
    "engineering_knowledge_graph",
    "assessment_graph",
    "findings",
    "recommendations",
    "modernization_roadmap",
    "ai_execution",
    "ai_enrichment",
)


class ReusePolicy:
    """Produce explicit reuse decisions rather than scattered booleans."""

    def evaluate(
        self,
        *,
        changes: RepositoryChangeSet,
        impact: ImpactAnalysis,
        compatibility: CompatibilityResult,
        policy: IncrementalPlanningPolicy | None = None,
        previous_artifacts_complete: bool = True,
        missing_artifacts: tuple[str, ...] = (),
        has_stable_findings: bool = True,
        ai_inputs_unchanged: bool = False,
        ai_config_unchanged: bool = False,
    ) -> tuple[ReuseAssessment, ...]:
        policy = policy or IncrementalPlanningPolicy()
        assessments: list[ReuseAssessment] = []

        if impact.requires_full_rebuild or not compatibility.compatible:
            extra_reasons: list[str] = []
            if missing_artifacts:
                extra_reasons.append("missing_required_artifacts")
            if not previous_artifacts_complete:
                extra_reasons.append("incomplete_previous_artifacts")
            reasons = tuple(
                dict.fromkeys(
                    (
                        *impact.full_rebuild_reasons,
                        *compatibility.blocking_reasons,
                        *extra_reasons,
                    )
                )
            )
            for subject in _SUBJECTS:
                assessments.append(
                    ReuseAssessment(
                        subject_kind=subject,
                        subject_id=subject,
                        decision=ReuseDecision.FULL_REBUILD,
                        reasons=reasons or ("full_rebuild_required",),
                        missing_fingerprints=missing_artifacts,
                        compatibility_failures=compatibility.blocking_reasons,
                        confidence="high",
                    )
                )
            return tuple(assessments)

        no_content = changes.change_count == 0
        doc_only = changes.has_documentation_only_changes and not (
            changes.has_source_changes
            or changes.has_build_changes
            or changes.has_configuration_changes
            or changes.has_dependency_manifest_changes
        )
        metadata_only = (
            bool(changes.metadata_changed)
            and not changes.added
            and not changes.modified
            and not changes.deleted
            and not changes.unknown
        )

        inventory_decision = ReuseDecision.REUSABLE
        inventory_reasons: list[str] = ["manifest_unchanged"]
        if not no_content and not (doc_only or (metadata_only and policy.allow_metadata_only_noop)):
            inventory_decision = ReuseDecision.RECOMPUTE
            inventory_reasons = ["inventory_changed"]

        tech_decision = (
            ReuseDecision.REUSABLE
            if inventory_decision is ReuseDecision.REUSABLE
            else ReuseDecision.RECOMPUTE
        )

        graph_decision = ReuseDecision.REUSABLE
        graph_reasons: list[str] = ["no_source_or_build_impact"]
        graph_invalidated = (
            changes.has_source_changes
            or changes.has_build_changes
            or changes.has_dependency_manifest_changes
        )
        if graph_invalidated:
            if impact.impacted_components and not impact.requires_full_rebuild:
                graph_decision = ReuseDecision.RECOMPUTE
                graph_reasons = ["impacted_graph_region"]
            else:
                graph_decision = ReuseDecision.RECOMPUTE
                graph_reasons = ["source_or_build_changed"]

        if doc_only or (metadata_only and policy.allow_metadata_only_noop) or no_content:
            graph_decision = ReuseDecision.REUSABLE
            graph_reasons = ["documentation_or_noop"]

        findings_decision = ReuseDecision.REUSABLE
        findings_reasons: list[str] = ["findings_unaffected"]
        if not has_stable_findings:
            findings_decision = ReuseDecision.UNSUPPORTED
            findings_reasons = ["phase1_uuid_findings_not_authoritative"]
        elif graph_decision is not ReuseDecision.REUSABLE:
            if impact.impacted_findings:
                findings_decision = ReuseDecision.RECOMPUTE
                findings_reasons = ["impacted_findings"]
            else:
                findings_decision = ReuseDecision.RECOMPUTE
                findings_reasons = ["graph_region_changed"]
        if doc_only or no_content or (metadata_only and policy.allow_metadata_only_noop):
            findings_decision = ReuseDecision.REUSABLE
            findings_reasons = ["no_assessment_impact"]

        rec_decision = ReuseDecision.REUSABLE
        rec_reasons: list[str] = ["recommendations_unaffected"]
        if findings_decision is ReuseDecision.RECOMPUTE:
            rec_decision = ReuseDecision.RECOMPUTE
            rec_reasons = ["findings_require_recompute"]
        elif impact.impacted_recommendations:
            rec_decision = ReuseDecision.RECOMPUTE
            rec_reasons = ["impacted_recommendations"]
        if findings_decision is ReuseDecision.UNSUPPORTED:
            rec_decision = ReuseDecision.UNSUPPORTED
            rec_reasons = ["findings_unsupported"]
        if findings_decision is ReuseDecision.REUSABLE:
            rec_decision = ReuseDecision.REUSABLE
            rec_reasons = ["findings_reusable"]

        roadmap_decision = rec_decision
        roadmap_reasons = ("follows_recommendations",)

        # AI: never reusable unless deterministic inputs + AI config are proven unchanged.
        ai_decision = ReuseDecision.RECOMPUTE
        ai_reasons = ["ai_reuse_requires_proven_unchanged_inputs"]
        if (
            inventory_decision is ReuseDecision.REUSABLE
            and graph_decision is ReuseDecision.REUSABLE
            and findings_decision is ReuseDecision.REUSABLE
            and rec_decision is ReuseDecision.REUSABLE
            and ai_inputs_unchanged
            and ai_config_unchanged
        ):
            ai_decision = ReuseDecision.REUSABLE
            ai_reasons = ["deterministic_inputs_and_ai_config_unchanged"]

        mapping: dict[str, tuple[ReuseDecision, tuple[str, ...]]] = {
            "inventory": (inventory_decision, tuple(inventory_reasons)),
            "technology_detection": (tech_decision, ("follows_inventory",)),
            "repository_graph": (graph_decision, tuple(graph_reasons)),
            "engineering_knowledge_graph": (graph_decision, tuple(graph_reasons)),
            "assessment_graph": (graph_decision, tuple(graph_reasons)),
            "findings": (findings_decision, tuple(findings_reasons)),
            "recommendations": (rec_decision, tuple(rec_reasons)),
            "modernization_roadmap": (roadmap_decision, roadmap_reasons),
            "ai_execution": (ai_decision, tuple(ai_reasons)),
            "ai_enrichment": (ai_decision, tuple(ai_reasons)),
        }

        for subject in _SUBJECTS:
            decision, reasons = mapping[subject]
            confidence = "high"
            if "structural_hash_unavailable" in impact.unknown_impacts:
                confidence = "medium"
            assessments.append(
                ReuseAssessment(
                    subject_kind=subject,
                    subject_id=subject,
                    decision=decision,
                    reasons=reasons,
                    impacted_by=tuple(impact.directly_changed_files[:20]),
                    confidence=confidence,
                )
            )

        reusable = sum(1 for item in assessments if item.decision is ReuseDecision.REUSABLE)
        recompute = sum(1 for item in assessments if item.decision is ReuseDecision.RECOMPUTE)
        full_rebuild = sum(1 for item in assessments if item.decision is ReuseDecision.FULL_REBUILD)
        logger.info(
            "incremental.reuse_evaluated",
            extra={
                "reusable": reusable,
                "recompute": recompute,
                "full_rebuild": full_rebuild,
            },
        )
        return tuple(assessments)
