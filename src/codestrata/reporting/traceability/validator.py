"""Validate the canonical assessment report.json traceability chain.

Policy (Epic 2 Slice 2.6): fail report construction on unresolved core
references. Do not silently discard unknown Evidence / Finding /
Recommendation / Priority Action / Roadmap dependency IDs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class AssessmentTraceabilityError(ValueError):
    """Raised when the canonical report.json chain cannot be resolved."""


def validate_assessment_traceability(assessment: Mapping[str, Any]) -> None:
    """Validate the Evidence → Finding → Recommendation → PA → Roadmap chain.

    Raises:
        AssessmentTraceabilityError: on any unresolved or inconsistent reference.
    """

    evidence_by_id = _index_by_id(assessment.get("evidence") or [], id_key="evidence_id")
    findings = list(assessment.get("findings") or [])
    findings_by_id = _index_by_id(findings, id_key="id")
    recommendations = list(assessment.get("deterministic_recommendations") or [])
    recommendations_by_id = _index_by_id(recommendations, id_key="id")
    priority_actions = list(assessment.get("priority_actions") or [])
    actions_by_id = _index_by_id(priority_actions, id_key="action_id")

    _validate_evidence_unique(assessment.get("evidence") or [])
    _validate_findings(findings, evidence_by_id)
    _validate_recommendations(recommendations, findings_by_id)
    _validate_priority_actions(priority_actions, recommendations_by_id, findings_by_id)

    roadmap = assessment.get("roadmap")
    if isinstance(roadmap, dict):
        _validate_roadmap(roadmap, actions_by_id, recommendations_by_id, findings_by_id)


def _index_by_id(items: Sequence[Any], *, id_key: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        raw = item.get(id_key)
        if raw is None:
            continue
        key = str(raw)
        if key in indexed:
            raise AssessmentTraceabilityError(f"duplicate {id_key}={key!r}")
        indexed[key] = item
    return indexed


def _validate_evidence_unique(evidence: Sequence[Any]) -> None:
    seen: set[str] = set()
    for item in evidence:
        if not isinstance(item, dict):
            raise AssessmentTraceabilityError("assessment.evidence entries must be objects")
        eid = item.get("evidence_id")
        if not eid:
            raise AssessmentTraceabilityError("assessment.evidence entry missing evidence_id")
        key = str(eid)
        if key in seen:
            raise AssessmentTraceabilityError(f"duplicate evidence_id={key!r}")
        seen.add(key)
        path = item.get("path") or (item.get("location") or {}).get("path")
        if isinstance(path, str) and (path.startswith("/") or path.startswith("file://")):
            raise AssessmentTraceabilityError(
                f"evidence_id={key!r} has non-repository-relative path"
            )


def _finding_evidence_ids(finding: Mapping[str, Any]) -> list[str]:
    ids: list[str] = []
    for ref in finding.get("evidence_refs") or []:
        if isinstance(ref, dict):
            eid = ref.get("evidence_id")
            if eid:
                ids.append(str(eid))
        elif ref:
            ids.append(str(ref))
    return ids


def _validate_findings(
    findings: Sequence[Any],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
) -> None:
    for finding in findings:
        if not isinstance(finding, dict):
            raise AssessmentTraceabilityError("finding entries must be objects")
        fid = str(finding.get("id") or "")
        evidence_ids = _finding_evidence_ids(finding)
        for eid in evidence_ids:
            if eid not in evidence_by_id:
                raise AssessmentTraceabilityError(
                    f"finding {fid!r} references unknown evidence_id={eid!r}"
                )
        primary = finding.get("primary_evidence_id")
        if primary is not None:
            primary_s = str(primary)
            if primary_s not in evidence_by_id:
                raise AssessmentTraceabilityError(
                    f"finding {fid!r} primary_evidence_id={primary_s!r} unresolved"
                )
            if evidence_ids and primary_s not in evidence_ids:
                raise AssessmentTraceabilityError(
                    f"finding {fid!r} primary_evidence_id not in evidence_refs"
                )
        for eid in finding.get("synthesized_from_evidence_ids") or []:
            key = str(eid)
            if key and key not in evidence_by_id:
                raise AssessmentTraceabilityError(
                    f"finding {fid!r} synthesized_from unknown evidence_id={key!r}"
                )


def _validate_recommendations(
    recommendations: Sequence[Any],
    findings_by_id: Mapping[str, Mapping[str, Any]],
) -> None:
    for rec in recommendations:
        if not isinstance(rec, dict):
            raise AssessmentTraceabilityError("recommendation entries must be objects")
        rid = str(rec.get("id") or "")
        supporting = [str(x) for x in (rec.get("supporting_finding_ids") or [])]
        related = [str(x) for x in (rec.get("related_finding_ids") or [])]
        if supporting != related:
            # Compatibility window: fields must remain equivalent.
            if sorted(supporting) != sorted(related):
                raise AssessmentTraceabilityError(
                    f"recommendation {rid!r} supporting_finding_ids != related_finding_ids"
                )
        for fid in supporting:
            if fid not in findings_by_id:
                raise AssessmentTraceabilityError(
                    f"recommendation {rid!r} references unknown finding_id={fid!r}"
                )
        primary = rec.get("primary_finding_id")
        if primary is not None:
            primary_s = str(primary)
            if primary_s not in findings_by_id:
                raise AssessmentTraceabilityError(
                    f"recommendation {rid!r} primary_finding_id={primary_s!r} unresolved"
                )
            if supporting and primary_s not in supporting:
                raise AssessmentTraceabilityError(
                    f"recommendation {rid!r} primary_finding_id not in supporting_finding_ids"
                )


def _validate_priority_actions(
    actions: Sequence[Any],
    recommendations_by_id: Mapping[str, Mapping[str, Any]],
    findings_by_id: Mapping[str, Mapping[str, Any]],
) -> None:
    for action in actions:
        if not isinstance(action, dict):
            raise AssessmentTraceabilityError("priority_action entries must be objects")
        aid = str(action.get("action_id") or "")
        if aid.startswith("presentation:finding:"):
            raise AssessmentTraceabilityError(
                f"priority action {aid!r} must not be finding-synthesized"
            )
        supporting_recs = [str(x) for x in (action.get("supporting_recommendation_ids") or [])]
        for rid in supporting_recs:
            if rid not in recommendations_by_id:
                raise AssessmentTraceabilityError(
                    f"priority action {aid!r} references unknown recommendation_id={rid!r}"
                )
        primary = action.get("primary_recommendation_id")
        if primary is not None:
            primary_s = str(primary)
            if primary_s not in recommendations_by_id:
                raise AssessmentTraceabilityError(
                    f"priority action {aid!r} primary_recommendation_id unresolved"
                )
            if supporting_recs and primary_s not in supporting_recs:
                raise AssessmentTraceabilityError(
                    f"priority action {aid!r} primary_recommendation_id not in supporting"
                )
        expected_findings: set[str] = set()
        for rid in supporting_recs:
            rec = recommendations_by_id[rid]
            expected_findings.update(
                str(x) for x in (rec.get("supporting_finding_ids") or rec.get("related_finding_ids") or [])
            )
        actual_findings = {str(x) for x in (action.get("supporting_finding_ids") or [])}
        if actual_findings != expected_findings:
            raise AssessmentTraceabilityError(
                f"priority action {aid!r} supporting_finding_ids mismatch derived union"
            )
        for fid in actual_findings:
            if fid not in findings_by_id:
                raise AssessmentTraceabilityError(
                    f"priority action {aid!r} references unknown finding_id={fid!r}"
                )


def _validate_roadmap(
    roadmap: Mapping[str, Any],
    actions_by_id: Mapping[str, Mapping[str, Any]],
    recommendations_by_id: Mapping[str, Mapping[str, Any]],
    findings_by_id: Mapping[str, Mapping[str, Any]],
) -> None:
    initiatives = list(roadmap.get("initiatives") or [])
    initiative_ids = {
        str(item.get("initiative_id"))
        for item in initiatives
        if isinstance(item, dict) and item.get("initiative_id")
    }
    for item in initiatives:
        if not isinstance(item, dict):
            raise AssessmentTraceabilityError("roadmap initiative entries must be objects")
        iid = str(item.get("initiative_id") or "")
        initiative_type = str(item.get("initiative_type") or "legacy").lower()
        supporting_pas = [str(x) for x in (item.get("supporting_priority_action_ids") or [])]
        primary_pa = item.get("primary_priority_action_id")

        if initiative_type in {"priority_action_backed", "merged"}:
            if not supporting_pas:
                raise AssessmentTraceabilityError(
                    f"roadmap initiative {iid!r} claims PA backing without supporting_priority_action_ids"
                )
            for paid in supporting_pas:
                if paid not in actions_by_id:
                    raise AssessmentTraceabilityError(
                        f"roadmap initiative {iid!r} unknown priority_action_id={paid!r}"
                    )
            if primary_pa is not None:
                primary_s = str(primary_pa)
                if primary_s not in actions_by_id:
                    raise AssessmentTraceabilityError(
                        f"roadmap initiative {iid!r} primary_priority_action_id unresolved"
                    )
                if primary_s not in supporting_pas:
                    raise AssessmentTraceabilityError(
                        f"roadmap initiative {iid!r} primary_priority_action_id not in supporting"
                    )
            expected_recs: set[str] = set()
            expected_findings: set[str] = set()
            for paid in supporting_pas:
                action = actions_by_id[paid]
                expected_recs.update(
                    str(x) for x in (action.get("supporting_recommendation_ids") or [])
                )
                expected_findings.update(
                    str(x) for x in (action.get("supporting_finding_ids") or [])
                )
            actual_recs = {str(x) for x in (item.get("supporting_recommendation_ids") or [])}
            actual_findings = {str(x) for x in (item.get("supporting_finding_ids") or [])}
            if actual_recs != expected_recs:
                raise AssessmentTraceabilityError(
                    f"roadmap initiative {iid!r} supporting_recommendation_ids mismatch derived union"
                )
            if actual_findings != expected_findings:
                raise AssessmentTraceabilityError(
                    f"roadmap initiative {iid!r} supporting_finding_ids mismatch derived union"
                )
        elif initiative_type == "legacy":
            # Legacy path must not fabricate Priority Action IDs.
            if supporting_pas or primary_pa:
                raise AssessmentTraceabilityError(
                    f"legacy roadmap initiative {iid!r} must not claim Priority Action IDs"
                )
            for rid in item.get("supporting_recommendation_ids") or []:
                if str(rid) not in recommendations_by_id:
                    raise AssessmentTraceabilityError(
                        f"legacy roadmap initiative {iid!r} unknown recommendation_id={rid!r}"
                    )
            for fid in item.get("supporting_finding_ids") or []:
                if str(fid) not in findings_by_id:
                    raise AssessmentTraceabilityError(
                        f"legacy roadmap initiative {iid!r} unknown finding_id={fid!r}"
                    )

        for dep in item.get("depends_on_initiative_ids") or []:
            dep_s = str(dep)
            if dep_s not in initiative_ids:
                raise AssessmentTraceabilityError(
                    f"roadmap initiative {iid!r} depends_on unresolved initiative_id={dep_s!r}"
                )
