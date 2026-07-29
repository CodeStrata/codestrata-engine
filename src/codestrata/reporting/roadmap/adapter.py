"""Adapt RoadmapAssessmentSection into presentation RoadmapReportSection.

Phase 5.10 — presentation only. Does not regenerate findings, recommendations,
or re-run assessment packs.
"""

from __future__ import annotations

from codestrata.domain.roadmap.constants import PHASE_TITLES
from codestrata.domain.roadmap.enums import RoadmapPhaseName, RoadmapStatus
from codestrata.domain.roadmap.models import RoadmapAssessmentSection, RoadmapInitiative
from codestrata.reporting.roadmap.models import (
    EVIDENCE_DISPLAY_LIMIT,
    INITIATIVE_DISPLAY_LIMIT,
    LIMITATION_DISPLAY_LIMIT,
    ROADMAP_REPORT_SECTION_ID,
    ROADMAP_REPORT_SECTION_VERSION,
    RoadmapReportEvidenceView,
    RoadmapReportInitiativeView,
    RoadmapReportPhaseView,
    RoadmapReportSection,
)

_STATUS_LABELS = {
    RoadmapStatus.SUCCEEDED: "Succeeded",
    RoadmapStatus.EMPTY: "Empty",
    RoadmapStatus.DISABLED: "Disabled",
    RoadmapStatus.FAILED: "Failed",
}


class RoadmapReportAdapter:
    """Map domain roadmap section to report presentation models."""

    def adapt(
        self,
        section: RoadmapAssessmentSection,
        *,
        include_assumptions: bool = True,
        include_limitations: bool = True,
        include_evidence: bool = True,
    ) -> RoadmapReportSection:
        initiatives = tuple(
            self._initiative(item, include_evidence=include_evidence)
            for item in section.initiatives[:INITIATIVE_DISPLAY_LIMIT]
        )
        by_id = {item.initiative_id: item for item in initiatives}
        phases = tuple(
            RoadmapReportPhaseView(
                phase_id=phase.phase_id,
                phase=phase.phase.value,
                title=phase.title,
                objective=phase.objective,
                sequence=phase.sequence,
                initiative_ids=phase.initiative_ids,
                initiatives=tuple(
                    by_id[iid] for iid in phase.initiative_ids if iid in by_id
                ),
            )
            for phase in section.phases
        )
        assumptions = section.assumptions if include_assumptions else ()
        limitations = (
            section.limitations[:LIMITATION_DISPLAY_LIMIT]
            if include_limitations
            else ()
        )
        status = (
            section.status
            if isinstance(section.status, RoadmapStatus)
            else RoadmapStatus(str(section.status))
        )
        return RoadmapReportSection(
            section_id=ROADMAP_REPORT_SECTION_ID,
            section_version=ROADMAP_REPORT_SECTION_VERSION,
            schema_name=section.schema_name,
            engine_version=section.engine_version,
            status=status.value,
            status_label=_STATUS_LABELS.get(status, status.value.title()),
            summary=section.summary,
            phases=phases,
            initiatives=initiatives,
            initiatives_total=len(section.initiatives),
            initiatives_displayed=len(initiatives),
            assumptions=assumptions,
            limitations=limitations,
            confidence=section.confidence.value,
            metadata=dict(section.metadata),
        )

    def _initiative(
        self,
        item: RoadmapInitiative,
        *,
        include_evidence: bool,
    ) -> RoadmapReportInitiativeView:
        phase = item.phase if isinstance(item.phase, RoadmapPhaseName) else RoadmapPhaseName(
            str(item.phase)
        )
        evidence: tuple[RoadmapReportEvidenceView, ...] = ()
        if include_evidence:
            evidence = tuple(
                RoadmapReportEvidenceView(
                    evidence_type=ref.evidence_type,
                    source_id=ref.source_id,
                    path=ref.path,
                    excerpt=ref.excerpt,
                )
                for ref in item.evidence_references[:EVIDENCE_DISPLAY_LIMIT]
            )
        return RoadmapReportInitiativeView(
            initiative_id=item.initiative_id,
            title=item.title,
            summary=item.summary,
            phase=phase.value,
            phase_label=PHASE_TITLES.get(phase, phase.value.title()),
            priority=item.priority.value,
            effort=item.effort.value,
            risk=item.risk.value,
            expected_outcome=item.expected_outcome,
            depends_on_initiative_ids=item.depends_on_initiative_ids,
            supporting_finding_ids=item.supporting_finding_ids,
            supporting_recommendation_ids=item.supporting_recommendation_ids,
            evidence_references=evidence,
            confidence=item.confidence.value,
            category=item.category,
            sequence=item.sequence,
        )
