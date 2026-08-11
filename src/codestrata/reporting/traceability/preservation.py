"""Canonical report.json traceability preservation (Epic 2 Slice 2.8).

``report.json`` is the authoritative interchange contract. MCP and Platform
boundaries must preserve these fields without regenerating relationships.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from codestrata.reporting.traceability.validator import (
    AssessmentTraceabilityError,
    validate_assessment_traceability,
)

# Compatibility matrix — schema 1.2 additive fields that must survive transport.
TRACEABILITY_ASSESSMENT_COLLECTIONS: tuple[str, ...] = (
    "evidence",
    "findings",
    "deterministic_recommendations",
    "priority_actions",
    "roadmap",
    "assessment_head_confidence",
    "assessment_coverage",
)

FINDING_TRACEABILITY_FIELDS: tuple[str, ...] = (
    "evidence_refs",
    "primary_evidence_id",
    "synthesized_from_evidence_ids",
    "evidence_completeness",
    "limitations",
)

RECOMMENDATION_TRACEABILITY_FIELDS: tuple[str, ...] = (
    "supporting_finding_ids",
    "related_finding_ids",
    "primary_finding_id",
    "recommendation_type",
    "evidence_completeness",
    "limitations",
)

PRIORITY_ACTION_TRACEABILITY_FIELDS: tuple[str, ...] = (
    "action_id",
    "supporting_recommendation_ids",
    "primary_recommendation_id",
    "supporting_finding_ids",
    "evidence_completeness",
    "limitations",
    "action_type",
)

ROADMAP_INITIATIVE_TRACEABILITY_FIELDS: tuple[str, ...] = (
    "initiative_id",
    "supporting_priority_action_ids",
    "primary_priority_action_id",
    "supporting_recommendation_ids",
    "supporting_finding_ids",
    "initiative_type",
    "evidence_completeness",
    "limitations",
    "depends_on_initiative_ids",
)

SUMMARY_TRACEABILITY_FIELDS: tuple[str, ...] = (
    "evidence_count",
    "priority_action_count",
    "roadmap_initiative_count",
)


class CanonicalReportLoadError(ValueError):
    """Raised when a report document cannot be loaded or validated."""


def extract_assessment(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return the assessment object from a report envelope or bare assessment."""

    if not isinstance(document, Mapping):
        raise CanonicalReportLoadError("report document must be an object")
    if "assessment" in document and isinstance(document["assessment"], Mapping):
        return dict(document["assessment"])
    # Accept a bare assessment object for convenience.
    if "findings" in document or "deterministic_recommendations" in document:
        return dict(document)
    raise CanonicalReportLoadError("report document missing assessment")


def load_report_document(source: str | Path | bytes | Mapping[str, Any]) -> dict[str, Any]:
    """Load a report.json document without mutating it."""

    if isinstance(source, Mapping):
        return dict(copy.deepcopy(source))
    if isinstance(source, bytes):
        try:
            payload = json.loads(source.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CanonicalReportLoadError("invalid report.json bytes") from error
        if not isinstance(payload, dict):
            raise CanonicalReportLoadError("report.json root must be an object")
        return payload
    path = Path(source)
    try:
        text = path.read_text(encoding="utf-8")
        payload = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CanonicalReportLoadError(f"unable to load report from {path}") from error
    if not isinstance(payload, dict):
        raise CanonicalReportLoadError("report.json root must be an object")
    return payload


def schema_version_of(document: Mapping[str, Any]) -> str:
    raw = document.get("schema_version")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    manifest = document.get("manifest")
    if isinstance(manifest, Mapping):
        nested = manifest.get("schema_version")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    return ASSESSMENT_JSON_SCHEMA_VERSION


def classify_traceability_state(assessment: Mapping[str, Any]) -> str:
    """Classify completeness without fabricating missing fields.

    Returns:
        ``complete`` — evidence + priority_actions present (roadmap optional empty)
        ``incomplete`` — schema 1.2 shape with some Epic 2 collections missing
        ``legacy`` — older / partial shape without Epic 2 collections
    """

    has_evidence = isinstance(assessment.get("evidence"), list)
    has_pas = isinstance(assessment.get("priority_actions"), list)
    has_findings = isinstance(assessment.get("findings"), list)
    if has_evidence and has_pas and has_findings:
        return "complete"
    if has_findings and (
        has_evidence
        or has_pas
        or isinstance(assessment.get("roadmap"), dict)
        or any(
            isinstance(item, dict)
            and (
                "evidence_refs" in item
                or "evidence_completeness" in item
                or "supporting_finding_ids" in item
            )
            for item in (
                *(assessment.get("findings") or []),
                *(assessment.get("deterministic_recommendations") or []),
            )
        )
    ):
        return "incomplete"
    return "legacy"


def validate_canonical_assessment(
    assessment: Mapping[str, Any],
    *,
    require_full_chain: bool = False,
) -> str:
    """Validate assessment traceability.

    For ``complete`` reports, runs the Slice 2.6 fail-closed validator.
    For legacy/incomplete reports, skips full-chain validation unless required.
    """

    state = classify_traceability_state(assessment)
    if state == "complete" or require_full_chain:
        # Ensure collections exist so validator can run.
        normalized = dict(assessment)
        normalized.setdefault("evidence", [])
        normalized.setdefault("priority_actions", [])
        try:
            validate_assessment_traceability(normalized)
        except AssessmentTraceabilityError as error:
            raise CanonicalReportLoadError(str(error)) from error
    return state


def traceability_snapshot(assessment: Mapping[str, Any]) -> dict[str, Any]:
    """Extract only canonical IDs and supporting lists for round-trip comparison."""

    findings = [
        {
            "id": item.get("id"),
            **{key: item.get(key) for key in FINDING_TRACEABILITY_FIELDS},
        }
        for item in (assessment.get("findings") or [])
        if isinstance(item, dict)
    ]
    recommendations = [
        {
            "id": item.get("id"),
            **{key: item.get(key) for key in RECOMMENDATION_TRACEABILITY_FIELDS},
        }
        for item in (assessment.get("deterministic_recommendations") or [])
        if isinstance(item, dict)
    ]
    priority_actions = [
        {key: item.get(key) for key in PRIORITY_ACTION_TRACEABILITY_FIELDS}
        for item in (assessment.get("priority_actions") or [])
        if isinstance(item, dict)
    ]
    roadmap = assessment.get("roadmap") if isinstance(assessment.get("roadmap"), dict) else {}
    initiatives = [
        {key: item.get(key) for key in ROADMAP_INITIATIVE_TRACEABILITY_FIELDS}
        for item in (roadmap.get("initiatives") or [])
        if isinstance(item, dict)
    ]
    evidence = [
        {"evidence_id": item.get("evidence_id")}
        for item in (assessment.get("evidence") or [])
        if isinstance(item, dict)
    ]
    summary = assessment.get("summary") if isinstance(assessment.get("summary"), dict) else {}
    return {
        "evidence": evidence,
        "findings": findings,
        "deterministic_recommendations": recommendations,
        "priority_actions": priority_actions,
        "roadmap_initiatives": initiatives,
        "summary": {key: summary.get(key) for key in SUMMARY_TRACEABILITY_FIELDS},
        "traceability_status": classify_traceability_state(assessment),
    }


def assert_traceability_equivalent(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> None:
    """Assert two assessments preserve identical canonical traceability fields."""

    a = traceability_snapshot(left)
    b = traceability_snapshot(right)
    if a != b:
        raise AssertionError(
            "traceability snapshot mismatch between reports "
            f"(left_status={a['traceability_status']}, "
            f"right_status={b['traceability_status']})"
        )


def lookup_entity(
    assessment: Mapping[str, Any],
    *,
    kind: str,
    entity_id: str,
) -> dict[str, Any] | None:
    """Exact-ID lookup into canonical assessment collections. No fuzzy matching."""

    key = str(entity_id or "").strip()
    if not key:
        return None
    kind_l = kind.strip().lower()
    if kind_l == "evidence":
        for item in assessment.get("evidence") or []:
            if isinstance(item, dict) and str(item.get("evidence_id")) == key:
                return dict(item)
        return None
    if kind_l == "finding":
        for item in assessment.get("findings") or []:
            if isinstance(item, dict) and str(item.get("id")) == key:
                return dict(item)
        return None
    if kind_l in {"recommendation", "deterministic_recommendation"}:
        for item in assessment.get("deterministic_recommendations") or []:
            if isinstance(item, dict) and str(item.get("id")) == key:
                return dict(item)
        return None
    if kind_l in {"priority_action", "action"}:
        for item in assessment.get("priority_actions") or []:
            if isinstance(item, dict) and str(item.get("action_id")) == key:
                return dict(item)
        return None
    if kind_l in {"roadmap_initiative", "initiative"}:
        roadmap = assessment.get("roadmap")
        if not isinstance(roadmap, dict):
            return None
        for item in roadmap.get("initiatives") or []:
            if isinstance(item, dict) and str(item.get("initiative_id")) == key:
                return dict(item)
        return None
    raise CanonicalReportLoadError(f"unsupported entity kind: {kind}")


def preserve_assessment_collections(assessment: Mapping[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of assessment with canonical collections preserved."""

    out = dict(assessment)
    for key in TRACEABILITY_ASSESSMENT_COLLECTIONS:
        if key in assessment:
            out[key] = copy.deepcopy(assessment[key])
    return out


def counts_from_assessment(assessment: Mapping[str, Any]) -> dict[str, int]:
    roadmap = assessment.get("roadmap") if isinstance(assessment.get("roadmap"), dict) else {}
    initiatives = roadmap.get("initiatives") if isinstance(roadmap, dict) else []
    return {
        "evidence_count": len(assessment.get("evidence") or []),
        "finding_count": len(assessment.get("findings") or []),
        "recommendation_count": len(assessment.get("deterministic_recommendations") or []),
        "priority_action_count": len(assessment.get("priority_actions") or []),
        "roadmap_initiative_count": len(initiatives or []),
    }
