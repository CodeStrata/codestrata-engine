"""Serialize assessment.roadmap from Priority Actions (canonical) or legacy fallback."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from codestrata.domain.priority_actions import PriorityAction
from codestrata.domain.roadmap.constants import PHASE_TITLES
from codestrata.domain.roadmap.enums import RoadmapInitiativeType, RoadmapPhaseName
from codestrata.domain.roadmap.models import RoadmapAssessmentSection, RoadmapInitiative

_LEGACY_FALLBACK_LIMITATION = (
    "assessment.roadmap used the legacy recommendation-grouped builder because "
    "no canonical Priority Actions were available. Initiatives are marked "
    "initiative_type=legacy and do not claim Priority Action backing."
)


def serialize_initiative_for_assessment(item: RoadmapInitiative) -> dict[str, Any]:
    """Serialize a domain initiative with full Epic 2.5/2.6 traceability fields."""

    phase = (
        item.phase
        if isinstance(item.phase, RoadmapPhaseName)
        else RoadmapPhaseName(str(item.phase))
    )
    initiative_type = item.initiative_type
    if isinstance(initiative_type, RoadmapInitiativeType):
        initiative_type_value = initiative_type.value
    else:
        initiative_type_value = str(initiative_type)
    completeness = item.evidence_completeness
    completeness_value = (
        completeness.value if hasattr(completeness, "value") else str(completeness)
    )
    return {
        "initiative_id": item.initiative_id,
        "title": item.title,
        "summary": item.summary,
        "phase": phase.value,
        "phase_label": PHASE_TITLES.get(phase, phase.value.title()),
        "priority": item.priority.value,
        "effort": item.effort.value,
        "risk": item.risk.value,
        "expected_outcome": item.expected_outcome,
        "depends_on_initiative_ids": list(item.depends_on_initiative_ids),
        "supporting_finding_ids": list(item.supporting_finding_ids),
        "supporting_recommendation_ids": list(item.supporting_recommendation_ids),
        "supporting_priority_action_ids": list(item.supporting_priority_action_ids),
        "primary_priority_action_id": item.primary_priority_action_id,
        "initiative_type": initiative_type_value,
        "evidence_completeness": completeness_value,
        "limitations": list(item.limitations),
        "evidence_references": [
            {
                "evidence_type": ref.evidence_type,
                "source_id": ref.source_id,
                **({"path": ref.path} if ref.path else {}),
                **({"excerpt": ref.excerpt} if ref.excerpt else {}),
            }
            for ref in item.evidence_references
        ],
        "confidence": item.confidence.value,
        "category": item.category,
        "sequence": item.sequence,
    }


def serialize_roadmap_section(section: RoadmapAssessmentSection) -> dict[str, Any]:
    """Serialize a domain roadmap section for assessment.roadmap."""

    initiatives = tuple(section.initiatives)
    by_id = {item.initiative_id: item for item in initiatives}
    phases_payload: list[dict[str, Any]] = []
    for phase in section.phases:
        nested = [
            serialize_initiative_for_assessment(by_id[iid])
            for iid in phase.initiative_ids
            if iid in by_id
        ]
        phases_payload.append(
            {
                "phase_id": phase.phase_id,
                "phase": phase.phase.value,
                "title": phase.title,
                "objective": phase.objective,
                "sequence": phase.sequence,
                "initiative_ids": list(phase.initiative_ids),
                "initiatives": nested,
            }
        )
    status = section.status.value if hasattr(section.status, "value") else str(section.status)
    return {
        "section_id": section.section_id,
        "section_version": section.section_version,
        "schema_name": section.schema_name,
        "engine_version": section.engine_version,
        "status": status,
        "status_label": status.replace("_", " ").title(),
        "summary": section.summary,
        "phases": phases_payload,
        "initiatives": [serialize_initiative_for_assessment(item) for item in initiatives],
        "initiatives_total": len(initiatives),
        "initiatives_displayed": len(initiatives),
        "assumptions": list(section.assumptions),
        "limitations": list(section.limitations),
        "confidence": section.confidence.value,
        "metadata": dict(section.metadata),
    }


def build_assessment_roadmap_payload(
    actions: Sequence[PriorityAction],
    *,
    legacy_roadmap: Any | None = None,
) -> dict[str, Any] | None:
    """Build assessment.roadmap from Priority Actions when available.

    Fallback: when no Priority Actions exist, serialize the legacy presentation
    roadmap (if any) and mark initiatives as ``legacy``. Never fabricates
    Priority Action IDs on the legacy path.

    Fallback condition: ``not actions`` (no recommendation-backed Priority
    Actions in the canonical universe).
    """

    if actions:
        # Lazy import avoids reporting ↔ application circular import at package load.
        from codestrata.application.roadmap.from_priority_actions import (
            build_roadmap_from_priority_actions,
        )

        section = build_roadmap_from_priority_actions(actions)
        if not section.initiatives:
            return None
        return serialize_roadmap_section(section)

    if legacy_roadmap is None:
        return None
    if isinstance(legacy_roadmap, RoadmapAssessmentSection):
        payload = serialize_roadmap_section(legacy_roadmap)
        payload = _mark_legacy_initiatives(payload)
    elif hasattr(legacy_roadmap, "model_dump"):
        payload = _mark_legacy_initiatives(legacy_roadmap.model_dump(mode="json"))
    else:
        return None
    if not (payload.get("initiatives") or []):
        if int(payload.get("initiatives_total") or 0) == 0:
            return None
    limitations = list(payload.get("limitations") or [])
    if _LEGACY_FALLBACK_LIMITATION not in limitations:
        limitations.append(_LEGACY_FALLBACK_LIMITATION)
    payload["limitations"] = limitations
    metadata = dict(payload.get("metadata") or {})
    metadata.setdefault("source", "legacy_recommendation_grouped")
    metadata.setdefault("priority_action_backed", "false")
    payload["metadata"] = metadata
    return payload


def _mark_legacy_initiatives(payload: dict[str, Any]) -> dict[str, Any]:
    def _mark(item: dict[str, Any]) -> None:
        item["supporting_priority_action_ids"] = []
        item["primary_priority_action_id"] = None
        item["initiative_type"] = RoadmapInitiativeType.LEGACY.value
        item.setdefault("evidence_completeness", "legacy")
        item.setdefault("limitations", [])

    for item in payload.get("initiatives") or []:
        if isinstance(item, dict):
            _mark(item)
    for phase in payload.get("phases") or []:
        if not isinstance(phase, dict):
            continue
        for item in phase.get("initiatives") or []:
            if isinstance(item, dict):
                _mark(item)
    return payload
