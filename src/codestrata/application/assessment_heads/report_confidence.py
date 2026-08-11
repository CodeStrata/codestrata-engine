"""Build additive Assessment-Head Confidence map for report.json (Slice 5.4)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from codestrata.application.assessment_heads.confidence import (
    derive_assessment_head_confidence,
)
from codestrata.domain.assessment_heads import assessment_head_confidence_to_json
from codestrata.reporting.html_v2.assessment_head_grouping import (
    classify_finding_head,
    normalize_category,
)
from codestrata.reporting.html_v2.assessment_heads import (
    ASSESSMENT_RESULT_HEADS,
    AssessmentHead,
)
from codestrata.reporting.html_v2.models import FindingView


def build_assessment_head_confidence_map(
    *,
    findings: Sequence[Mapping[str, Any]] = (),
    pack_sections: Mapping[str, Mapping[str, Any] | None] | None = None,
    technologies_present: bool = False,
    activation: Mapping[str, Any] | None = None,
    assessment_coverage_map: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Derive additive ``assessment.assessment_head_confidence`` keyed by head id."""

    by_head = _group_finding_levels(findings)
    packs = pack_sections or {}
    coverage_map = assessment_coverage_map or {}
    assessed = {
        str(item).strip().lower()
        for item in (activation or {}).get("assessed_packs") or ()
        if str(item).strip()
    }
    not_assessed = {
        str(item[0] if isinstance(item, (list, tuple)) else item).strip().lower()
        for item in (activation or {}).get("not_assessed_packs") or ()
        if item
    }

    out: dict[str, dict[str, Any]] = {}

    # Canonical HTML assessment-result heads.
    for head in ASSESSMENT_RESULT_HEADS:
        head_id = head.value
        pack_key = _head_to_pack_key(head)
        section = packs.get(pack_key) if pack_key else None
        pack_status = None
        if isinstance(section, Mapping):
            pack_status = str(section.get("status") or "").strip().lower() or None
        status = _assessment_status_for_head(
            head=head,
            finding_count=len(by_head.get(head_id, ())),
            pack_status=pack_status,
            pack_present=section is not None
            or (head is AssessmentHead.TECHNOLOGY_INVENTORY and technologies_present),
            pack_enabled=_pack_enabled(pack_key, assessed, not_assessed),
            technologies_present=technologies_present,
        )
        levels = by_head.get(head_id, ())
        completeness = by_head.get(f"{head_id}__completeness", ())
        limitations: list[str] = []
        if isinstance(section, Mapping):
            for note in section.get("limitations") or ():
                if str(note).strip():
                    limitations.append(str(note).strip())
        # Deferred EvidenceRef packs stay honest when Finding Confidence is unavailable.
        if head_id in {
            AssessmentHead.CLOUD_READINESS.value,
            AssessmentHead.AI_READINESS.value,
            "testing",
            "performance",
        } and levels and all(item == "unavailable" for item in levels):
            limitations.append(
                "EvidenceRef mapping for this assessment head is deferred; "
                "Finding Confidence remains Unavailable."
            )
        contributing: tuple[str, ...] = ()
        if head is AssessmentHead.MODERNIZATION_ASSESSMENT:
            contributing = tuple(
                out[other.value]["level"]
                for other in ASSESSMENT_RESULT_HEADS
                if other is not AssessmentHead.MODERNIZATION_ASSESSMENT
                and other.value in out
                and out[other.value]
                .get("component_summary", {})
                .get("assessment_status")
                not in {"not_enabled", "not_available", None, ""}
            )
        coverage_payload = coverage_map.get(head_id)
        confidence = derive_assessment_head_confidence(
            head_id=head_id,
            assessment_status=status,
            finding_confidence_levels=levels,
            evidence_completeness_values=completeness,
            limitations=limitations,
            activated=status in {"assessed", "partially_assessed", "legacy_assessment"},
            pack_assessment_status=pack_status,
            synthesized=head is AssessmentHead.MODERNIZATION_ASSESSMENT,
            contributing_head_levels=contributing,
            inventory_confidence=(
                str(section.get("confidence") or "").strip().lower()
                if head is AssessmentHead.TECHNOLOGY_INVENTORY
                and isinstance(section, Mapping)
                else None
            ),
            assessment_coverage=coverage_payload,
        )
        out[head_id] = assessment_head_confidence_to_json(confidence)

    # Optional pack-only heads (testing / performance) when sections exist.
    for pack_key in ("testing", "performance"):
        section = packs.get(pack_key)
        if not isinstance(section, Mapping):
            continue
        head_id = pack_key
        pack_status = str(section.get("status") or "").strip().lower() or None
        status = _status_from_pack(pack_status)
        levels = by_head.get(head_id, ())
        limitations = [
            str(note).strip()
            for note in section.get("limitations") or ()
            if str(note).strip()
        ]
        limitations.append(
            "EvidenceRef mapping for this assessment head is deferred; "
            "Finding Confidence remains Unavailable."
        )
        confidence = derive_assessment_head_confidence(
            head_id=head_id,
            assessment_status=status,
            finding_confidence_levels=levels
            or (("unavailable",) if int(section.get("finding_count") or 0) > 0 else ()),
            evidence_completeness_values=(),
            limitations=limitations,
            activated=status in {"assessed", "partially_assessed"},
            pack_assessment_status=pack_status,
            assessment_coverage=coverage_map.get(head_id),
        )
        out[head_id] = assessment_head_confidence_to_json(confidence)

    return dict(sorted(out.items(), key=lambda pair: pair[0]))


def _group_finding_levels(
    findings: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[str, ...]]:
    buckets: dict[str, list[str]] = {}
    completeness: dict[str, list[str]] = {}
    seen_ids: set[str] = set()
    for raw in findings:
        if not isinstance(raw, Mapping):
            continue
        finding_id = str(raw.get("id") or raw.get("finding_id") or "").strip()
        if finding_id and finding_id in seen_ids:
            continue
        if finding_id:
            seen_ids.add(finding_id)
        category = normalize_category(str(raw.get("category") or ""))
        # Skip AI advisory / unclassified appendix material.
        if category in {"ai", "ai_advisor", "advisory"}:
            continue
        view = FindingView(
            finding_id=finding_id or f"tmp:{len(seen_ids)}",
            rule_id=str(raw.get("rule_id") or "") or "unknown",
            title=str(raw.get("title") or "finding"),
            description=str(raw.get("description") or "finding"),
            severity=str(raw.get("severity") or "info"),
            category=str(raw.get("category") or "unknown"),
            finding_confidence_level=_finding_level(raw),
            evidence_completeness=str(raw.get("evidence_completeness") or "") or "legacy",
        )
        head = classify_finding_head(view)
        if head is None:
            # testing / performance via category aliases
            if category in {"testing", "test", "quality"}:
                head_id = "testing"
            elif category in {"performance", "perf"}:
                head_id = "performance"
            else:
                continue
        else:
            head_id = head.value
        buckets.setdefault(head_id, []).append(view.finding_confidence_level or "unavailable")
        completeness.setdefault(head_id, []).append(view.evidence_completeness)
    out: dict[str, tuple[str, ...]] = {
        key: tuple(values) for key, values in buckets.items()
    }
    for key, values in completeness.items():
        out[f"{key}__completeness"] = tuple(values)
    return out


def _finding_level(raw: Mapping[str, Any]) -> str:
    block = raw.get("finding_confidence")
    if isinstance(block, Mapping) and block.get("level"):
        return str(block["level"]).strip().lower()
    direct = raw.get("finding_confidence_level")
    if direct:
        return str(direct).strip().lower()
    return "unavailable"


def _head_to_pack_key(head: AssessmentHead) -> str | None:
    mapping = {
        AssessmentHead.ARCHITECTURE_INTELLIGENCE: "architecture",
        AssessmentHead.TECHNICAL_DEBT_INTELLIGENCE: "technical_debt",
        AssessmentHead.DEPENDENCY_INTELLIGENCE: "dependency",
        AssessmentHead.SECURITY_INTELLIGENCE: "security",
        AssessmentHead.CLOUD_READINESS: "cloud",
        AssessmentHead.AI_READINESS: "ai_readiness",
        AssessmentHead.MODERNIZATION_ASSESSMENT: "roadmap",
    }
    return mapping.get(head)


def _pack_enabled(
    pack_key: str | None,
    assessed: set[str],
    not_assessed: set[str],
) -> bool | None:
    if not pack_key:
        return None
    if pack_key in assessed:
        return True
    if pack_key in not_assessed:
        return False
    return None


def _status_from_pack(pack_status: str | None) -> str:
    mapping = {
        "succeeded": "assessed",
        "partially_succeeded": "partially_assessed",
        "insufficient_evidence": "partially_assessed",
        "disabled": "not_enabled",
        "not_applicable": "not_available",
        "failed": "not_available",
        "not_requested": "not_available",
        "inventory_generated": "assessed",
        "partial_inventory": "partially_assessed",
        "inventory_unavailable": "not_available",
        "legacy_inventory": "legacy_assessment",
    }
    if not pack_status:
        return "not_available"
    return mapping.get(pack_status, "partially_assessed")


def _assessment_status_for_head(
    *,
    head: AssessmentHead,
    finding_count: int,
    pack_status: str | None,
    pack_present: bool,
    pack_enabled: bool | None,
    technologies_present: bool,
) -> str:
    if pack_status:
        return _status_from_pack(pack_status)
    if pack_enabled is False:
        return "not_enabled"
    if head is AssessmentHead.TECHNOLOGY_INVENTORY:
        if technologies_present:
            return "assessed"
        return "not_available"
    if head is AssessmentHead.MODERNIZATION_ASSESSMENT:
        if finding_count:
            return "partially_assessed"
        return "not_available" if not pack_present else "partially_assessed"
    if pack_present or finding_count:
        return "assessed" if finding_count or pack_present else "not_available"
    if pack_enabled is True:
        return "assessed"
    return "not_available"
