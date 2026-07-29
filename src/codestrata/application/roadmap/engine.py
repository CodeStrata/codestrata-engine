"""Deterministic Modernization Roadmap Engine (Phase 5.10).

Consumes existing findings and recommendations only. Does not rerun
assessment packs, rules, or analyzers.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from codestrata.application.roadmap.mapping import (
    RoadmapSourceEvidence,
    RoadmapSourceFinding,
    RoadmapSourceRecommendation,
    map_effort,
    map_phase,
    map_priority,
    map_risk,
    max_effort,
    max_priority,
    max_risk,
    normalize_category,
    prerequisite_phases,
    priority_rank,
)
from codestrata.domain.roadmap.constants import (
    PHASE_OBJECTIVES,
    PHASE_OUTCOMES,
    PHASE_SEQUENCE,
    PHASE_TITLES,
)
from codestrata.domain.roadmap.enums import (
    RoadmapConfidence,
    RoadmapPhaseName,
    RoadmapStatus,
)
from codestrata.domain.roadmap.identifiers import (
    ENGINE_VERSION,
    build_initiative_id,
    build_phase_id,
)
from codestrata.domain.roadmap.models import (
    RoadmapAssessmentSection,
    RoadmapEvidenceReference,
    RoadmapInitiative,
    RoadmapPhasePlan,
)

_ASSUMPTIONS = (
    "Roadmap initiatives are derived only from existing assessment findings "
    "and recommendations; assessments are not re-run.",
    "Phase assignment is deterministic from recommendation category "
    "(stabilize / secure / modernize / optimize).",
    "Priority, effort, and risk are mapped from recommendation and finding "
    "attributes using fixed rules (no AI estimation).",
    "Cross-phase dependencies follow Stabilize → Secure → Modernize → Optimize.",
)

_BASE_LIMITATIONS = (
    "Does not produce schedules, dates, cost estimates, or portfolio plans.",
    "Does not mutate repositories or create external tracker tickets.",
    "Does not invent findings or recommendations beyond the provided inputs.",
)


class ModernizationRoadmapEngine:
    """Group recommendations into phased initiatives with stable IDs."""

    def generate(
        self,
        *,
        recommendations: Sequence[RoadmapSourceRecommendation] = (),
        findings: Sequence[RoadmapSourceFinding] = (),
    ) -> RoadmapAssessmentSection:
        finding_by_id = {item.id: item for item in findings}
        # Deduplicate recommendations by id (first occurrence wins; inputs should
        # already be stable-ordered by callers).
        unique_recs: dict[str, RoadmapSourceRecommendation] = {}
        for rec in recommendations:
            unique_recs.setdefault(rec.id, rec)
        ordered_recs = tuple(
            sorted(
                unique_recs.values(),
                key=lambda item: (
                    priority_rank(map_priority(item.priority)),
                    normalize_category(item.category),
                    item.id,
                ),
            )
        )

        if not ordered_recs:
            limitations = list(_BASE_LIMITATIONS)
            if findings:
                limitations.insert(
                    0,
                    "Findings were present but no recommendations were available; "
                    "initiatives are recommendation-driven.",
                )
            else:
                limitations.insert(
                    0,
                    "No findings or recommendations were available for roadmap generation.",
                )
            return RoadmapAssessmentSection.empty(
                status=RoadmapStatus.EMPTY,
                summary="No modernization initiatives could be derived.",
                limitations=limitations,
            )

        groups: dict[tuple[RoadmapPhaseName, str], list[RoadmapSourceRecommendation]] = (
            defaultdict(list)
        )
        for rec in ordered_recs:
            phase = map_phase(rec.category)
            category = normalize_category(rec.category)
            groups[(phase, category)].append(rec)

        initiatives: list[RoadmapInitiative] = []
        for phase in PHASE_SEQUENCE:
            phase_groups = sorted(
                ((cat, recs) for (ph, cat), recs in groups.items() if ph == phase),
                key=lambda item: item[0],
            )
            for category, recs in phase_groups:
                initiatives.append(
                    self._build_initiative(
                        phase=phase,
                        category=category,
                        recommendations=tuple(recs),
                        finding_by_id=finding_by_id,
                    )
                )

        # Attach cross-phase dependencies after all IDs exist.
        by_phase: dict[RoadmapPhaseName, list[str]] = defaultdict(list)
        for item in initiatives:
            by_phase[item.phase].append(item.initiative_id)

        linked: list[RoadmapInitiative] = []
        for index, item in enumerate(initiatives):
            deps: list[str] = []
            for prior in prerequisite_phases(item.phase):
                deps.extend(by_phase.get(prior, ()))
            linked.append(
                item.model_copy(
                    update={
                        "depends_on_initiative_ids": tuple(sorted(set(deps))),
                        "sequence": index,
                    }
                )
            )

        phases = self._build_phases(linked)
        confidence = self._confidence(linked, finding_by_id)
        uncovered = sorted(
            {
                finding.id
                for finding in findings
                if not any(finding.id in init.supporting_finding_ids for init in linked)
            }
        )
        limitations = list(_BASE_LIMITATIONS)
        if uncovered:
            limitations.insert(
                0,
                f"{len(uncovered)} finding(s) are not referenced by any roadmap "
                "initiative recommendation.",
            )
        if any(not init.supporting_finding_ids for init in linked):
            limitations.insert(
                0,
                "Some initiatives lack supporting finding IDs because source "
                "recommendations were not finding-grounded.",
            )

        summary = (
            f"{len(linked)} initiative(s) across {len(phases)} phase(s) derived "
            f"from {len(ordered_recs)} recommendation(s)."
        )
        return RoadmapAssessmentSection(
            status=RoadmapStatus.SUCCEEDED,
            summary=summary,
            phases=phases,
            initiatives=tuple(linked),
            assumptions=_ASSUMPTIONS,
            limitations=tuple(limitations),
            confidence=confidence,
            metadata={
                "engine_version": ENGINE_VERSION,
                "initiative_count": str(len(linked)),
                "phase_count": str(len(phases)),
                "recommendation_count": str(len(ordered_recs)),
                "finding_count": str(len(finding_by_id)),
                "uncovered_finding_count": str(len(uncovered)),
            },
        )

    def generate_from_artifacts(
        self,
        *,
        recommendation_result: Any | None = None,
        rule_evaluation: Any | None = None,
        analysis_result: Any | None = None,
    ) -> RoadmapAssessmentSection:
        """Build a roadmap from Phase 3 and/or Phase 1 assessment artifacts."""

        recommendations = list(
            _recommendations_from_phase3(recommendation_result)
            or _recommendations_from_phase1(analysis_result)
            or ()
        )
        findings = list(
            _findings_from_phase3(rule_evaluation)
            or _findings_from_phase1(analysis_result)
            or ()
        )
        return self.generate(recommendations=recommendations, findings=findings)

    def _build_initiative(
        self,
        *,
        phase: RoadmapPhaseName,
        category: str,
        recommendations: Sequence[RoadmapSourceRecommendation],
        finding_by_id: Mapping[str, RoadmapSourceFinding],
    ) -> RoadmapInitiative:
        rec_ids = tuple(sorted({item.id for item in recommendations}))
        # Keep finding IDs referenced by recommendations (traceability even when
        # the finding object itself was not supplied).
        finding_ids = tuple(
            sorted({fid for item in recommendations for fid in item.related_finding_ids})
        )
        severities = tuple(
            finding_by_id[fid].severity for fid in finding_ids if fid in finding_by_id
        )
        priorities = tuple(map_priority(item.priority) for item in recommendations)
        efforts = tuple(
            map_effort(item.effort, action_count=item.action_count) for item in recommendations
        )
        risks = tuple(
            map_risk(
                item.risk,
                priority=map_priority(item.priority),
                finding_severities=tuple(
                    finding_by_id[fid].severity
                    for fid in item.related_finding_ids
                    if fid in finding_by_id
                )
                or severities,
            )
            for item in recommendations
        )
        evidence = _collect_evidence(recommendations, finding_by_id, finding_ids)
        titles = [item.title for item in recommendations]
        if len(titles) == 1:
            summary = titles[0]
        else:
            preview = "; ".join(titles[:3])
            extra = len(titles) - 3
            summary = preview if extra <= 0 else f"{preview}; +{extra} more"
        title = f"{PHASE_TITLES[phase]} — {_category_label(category)}"
        confidence = (
            RoadmapConfidence.HIGH
            if finding_ids and all(item.related_finding_ids for item in recommendations)
            else (
                RoadmapConfidence.MEDIUM
                if finding_ids
                else RoadmapConfidence.LOW
            )
        )
        return RoadmapInitiative(
            initiative_id=build_initiative_id(
                phase=phase.value,
                category=category,
                recommendation_ids=rec_ids,
            ),
            title=title,
            summary=summary,
            phase=phase,
            priority=max_priority(priorities),
            effort=max_effort(efforts),
            risk=max_risk(risks),
            expected_outcome=PHASE_OUTCOMES[phase],
            depends_on_initiative_ids=(),
            supporting_finding_ids=finding_ids,
            supporting_recommendation_ids=rec_ids,
            evidence_references=evidence,
            confidence=confidence,
            category=category,
            sequence=0,
        )

    def _build_phases(
        self, initiatives: Sequence[RoadmapInitiative]
    ) -> tuple[RoadmapPhasePlan, ...]:
        by_phase: dict[RoadmapPhaseName, list[str]] = defaultdict(list)
        for item in initiatives:
            by_phase[item.phase].append(item.initiative_id)
        plans: list[RoadmapPhasePlan] = []
        for index, phase in enumerate(PHASE_SEQUENCE):
            ids = tuple(by_phase.get(phase, ()))
            if not ids:
                continue
            plans.append(
                RoadmapPhasePlan(
                    phase_id=build_phase_id(phase.value),
                    phase=phase,
                    title=PHASE_TITLES[phase],
                    objective=PHASE_OBJECTIVES[phase],
                    sequence=index,
                    initiative_ids=ids,
                )
            )
        return tuple(plans)

    def _confidence(
        self,
        initiatives: Sequence[RoadmapInitiative],
        finding_by_id: Mapping[str, RoadmapSourceFinding],
    ) -> RoadmapConfidence:
        if not initiatives:
            return RoadmapConfidence.NONE
        grounded = sum(1 for item in initiatives if item.supporting_finding_ids)
        if grounded == len(initiatives) and finding_by_id:
            return RoadmapConfidence.HIGH
        if grounded:
            return RoadmapConfidence.MEDIUM
        return RoadmapConfidence.LOW


def _category_label(category: str) -> str:
    return category.replace("_", " ").strip().title() or "Unknown"


def _collect_evidence(
    recommendations: Sequence[RoadmapSourceRecommendation],
    finding_by_id: Mapping[str, RoadmapSourceFinding],
    finding_ids: Sequence[str],
) -> tuple[RoadmapEvidenceReference, ...]:
    refs: list[RoadmapEvidenceReference] = []
    seen: set[tuple[str, str, str | None]] = set()
    for rec in recommendations:
        for item in rec.evidence:
            key = (item.evidence_type, item.source_id, item.path)
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                RoadmapEvidenceReference(
                    evidence_type=item.evidence_type,
                    source_id=item.source_id,
                    path=item.path,
                    excerpt=item.excerpt,
                )
            )
    for fid in finding_ids:
        finding = finding_by_id.get(fid)
        if finding is None:
            continue
        for item in finding.evidence:
            key = (item.evidence_type, item.source_id, item.path)
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                RoadmapEvidenceReference(
                    evidence_type=item.evidence_type,
                    source_id=item.source_id,
                    path=item.path,
                    excerpt=item.excerpt,
                )
            )
    return tuple(
        sorted(refs, key=lambda item: (item.evidence_type, item.source_id, item.path or ""))
    )


def _recommendations_from_phase3(
    result: Any | None,
) -> tuple[RoadmapSourceRecommendation, ...] | None:
    if result is None:
        return None
    items = getattr(result, "recommendations", None)
    if not items:
        return None
    out: list[RoadmapSourceRecommendation] = []
    for rec in items:
        evidence = tuple(
            RoadmapSourceEvidence(
                evidence_type=str(ev.evidence_type),
                source_id=str(ev.source_id),
                path=getattr(ev, "path", None),
                excerpt=getattr(ev, "excerpt", None),
            )
            for ev in getattr(rec, "evidence", ()) or ()
        )
        actions = getattr(rec, "actions", ()) or ()
        out.append(
            RoadmapSourceRecommendation(
                id=str(rec.id),
                title=str(rec.title),
                summary=str(getattr(rec, "summary", None) or rec.title),
                priority=str(getattr(rec.priority, "value", rec.priority)),
                category=str(getattr(rec.category, "value", rec.category)),
                related_finding_ids=tuple(str(x) for x in getattr(rec, "related_finding_ids", ())),
                evidence=evidence,
                action_count=len(actions),
            )
        )
    return tuple(out)


def _findings_from_phase3(result: Any | None) -> tuple[RoadmapSourceFinding, ...] | None:
    if result is None:
        return None
    items = getattr(result, "findings", None)
    if not items:
        return None
    out: list[RoadmapSourceFinding] = []
    for finding in items:
        evidence = tuple(
            RoadmapSourceEvidence(
                evidence_type=str(ev.evidence_type),
                source_id=str(ev.source_id),
                path=getattr(ev, "path", None),
                excerpt=getattr(ev, "excerpt", None),
            )
            for ev in getattr(finding, "evidence", ()) or ()
        )
        out.append(
            RoadmapSourceFinding(
                id=str(finding.id),
                title=str(finding.title),
                severity=str(getattr(finding.severity, "value", finding.severity)),
                category=str(getattr(finding.category, "value", finding.category)),
                evidence=evidence,
            )
        )
    return tuple(out)


def _recommendations_from_phase1(
    result: Any | None,
) -> tuple[RoadmapSourceRecommendation, ...] | None:
    if result is None:
        return None
    items = getattr(result, "recommendations", None)
    if not items:
        return None
    out: list[RoadmapSourceRecommendation] = []
    for rec in items:
        evidence_raw = getattr(rec, "evidence", ()) or ()
        evidence = tuple(
            RoadmapSourceEvidence(
                evidence_type=str(getattr(ev, "kind", None) or getattr(ev, "type", "evidence")),
                source_id=str(
                    getattr(ev, "source", None)
                    or getattr(ev, "path", None)
                    or getattr(ev, "id", "evidence")
                ),
                path=str(getattr(ev, "path", None) or "") or None,
                excerpt=str(getattr(ev, "excerpt", None) or getattr(ev, "snippet", None) or "")
                or None,
            )
            for ev in evidence_raw
        )
        actions = getattr(rec, "actions", ()) or ()
        out.append(
            RoadmapSourceRecommendation(
                id=str(rec.id),
                title=str(rec.title),
                summary=str(getattr(rec, "description", None) or rec.title),
                priority=str(getattr(rec.priority, "value", rec.priority)),
                category=str(getattr(rec.category, "value", rec.category)),
                related_finding_ids=tuple(
                    str(x) for x in getattr(rec, "related_finding_ids", ()) or ()
                ),
                evidence=evidence,
                action_count=len(actions),
                effort=(
                    str(
                        getattr(
                            getattr(rec, "effort", None),
                            "value",
                            getattr(rec, "effort", None),
                        )
                    )
                    if getattr(rec, "effort", None) is not None
                    else None
                ),
                risk=(
                    str(
                        getattr(
                            getattr(rec, "risk", None),
                            "value",
                            getattr(rec, "risk", None),
                        )
                    )
                    if getattr(rec, "risk", None) is not None
                    else None
                ),
            )
        )
    return tuple(out)


def _findings_from_phase1(result: Any | None) -> tuple[RoadmapSourceFinding, ...] | None:
    if result is None:
        return None
    items = getattr(result, "findings", None)
    if not items:
        return None
    out: list[RoadmapSourceFinding] = []
    for finding in items:
        evidence_raw = getattr(finding, "evidence", ()) or ()
        evidence = tuple(
            RoadmapSourceEvidence(
                evidence_type=str(getattr(ev, "kind", None) or getattr(ev, "type", "evidence")),
                source_id=str(
                    getattr(ev, "source", None)
                    or getattr(ev, "path", None)
                    or getattr(ev, "id", "evidence")
                ),
                path=str(getattr(ev, "path", None) or "") or None,
                excerpt=str(getattr(ev, "excerpt", None) or getattr(ev, "snippet", None) or "")
                or None,
            )
            for ev in evidence_raw
        )
        out.append(
            RoadmapSourceFinding(
                id=str(finding.id),
                title=str(finding.title),
                severity=str(getattr(finding.severity, "value", finding.severity)),
                category=str(getattr(finding.category, "value", finding.category)),
                evidence=evidence,
            )
        )
    return tuple(out)
