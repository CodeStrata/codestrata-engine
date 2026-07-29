"""Consolidate related recommendations for architecture conclusions."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.architecture.conclusions.identifiers import build_recommendation_group_id
from codestrata.domain.architecture.conclusions.models import (
    ArchitectureConclusion,
    ConsolidatedRecommendation,
)
from codestrata.domain.findings import Finding


def consolidate_recommendations(
    conclusions: Sequence[ArchitectureConclusion],
    findings: Sequence[Finding],
) -> tuple[ConsolidatedRecommendation, ...]:
    by_id = {finding.id: finding for finding in findings}
    groups: list[ConsolidatedRecommendation] = []
    for conclusion in sorted(conclusions, key=lambda item: item.conclusion_id):
        source_findings = [
            by_id[finding_id]
            for finding_id in conclusion.source_finding_ids
            if finding_id in by_id
        ]
        remediations = []
        source_rec_ids: list[str] = []
        for finding in source_findings:
            remediation = str(finding.metadata.get("remediation", "")).strip()
            if remediation:
                remediations.append(remediation)
            rec_key = str(finding.metadata.get("recommendation_id", "")).strip()
            if rec_key:
                source_rec_ids.append(rec_key)
            else:
                source_rec_ids.append(f"finding-remediation:{finding.id}")

        if not remediations:
            primary_action = (
                "Review the underlying architecture findings and regenerate the "
                "dependency graph after structural changes."
            )
        elif len(remediations) == 1:
            primary_action = remediations[0]
        else:
            primary_action = (
                "Address the related boundary and dependency conditions together: "
                + " ".join(remediations[:3])
            )

        group_id = build_recommendation_group_id(
            conclusion_id=conclusion.conclusion_id,
            primary_action_key=primary_action[:120],
        )
        groups.append(
            ConsolidatedRecommendation(
                recommendation_group_id=group_id,
                title=f"Respond to: {conclusion.title}",
                primary_action=primary_action,
                rationale=conclusion.summary,
                affected_scope=conclusion.affected_scope,
                source_recommendation_ids=tuple(sorted(set(source_rec_ids))),
                source_finding_ids=conclusion.source_finding_ids,
                prerequisites=(
                    "Confirm classification coverage is adequate for the affected units.",
                ),
                effort_band="medium",
                validation_steps=(
                    "Regenerate the architecture dependency graph.",
                    "Confirm related findings are resolved or intentionally accepted.",
                    "Re-run architecture conclusions and compare conclusion IDs.",
                ),
                sequencing_guidance=(
                    "Prefer resolving direct boundary violations before broad fan-out "
                    "cleanup when both exist in the same scope."
                ),
                modernization_wave=conclusion.modernization_relevance,
                confidence=conclusion.confidence,
                limitations=conclusion.limitations,
            )
        )
    # Attach group IDs back onto conclusions via rebuild in service.
    return tuple(sorted(groups, key=lambda item: item.recommendation_group_id))
