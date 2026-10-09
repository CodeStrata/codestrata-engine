"""Four-outcome Engineering Health projection helpers.

Maps canonical coverage/findings onto presentation labels. Does not add
canonical enums, compute a health score, or calculate rank/delta/lifecycle/
movement.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from codestrata.reporting.html_v2.assessment_heads import (
    AssessmentHeadRole,
    assessment_head_outcome_family,
    assessment_head_role,
    engineering_health_outcome_title,
)

# Presentation labels only — not OutcomeFamily / CoverageStatus / ResultStatus.
DISPLAY_NEEDS_ATTENTION = "Needs attention"
DISPLAY_NO_MATERIAL_ISSUES = "No material issues observed"
DISPLAY_INSUFFICIENT_EVIDENCE = "Insufficient evidence"
DISPLAY_NOT_APPLICABLE = "Not applicable"

# Git remains supporting context; there is no Git assessment head.
SUPPORTING_CONTEXT_GIT = "git"

_FORBIDDEN_COMPLETE_LABELS = frozenset(
    {
        "complete",
        "completed",
        "succeeded",
        "success",
        "healthy",
    }
)

_UNAVAILABLE_COVERAGE = frozenset(
    {
        "unavailable",
        "insufficient_evidence",
        "unknown",
        "error",
        "provisional",
        "",
    }
)
_NOT_APPLICABLE_COVERAGE = frozenset({"not_applicable", "disabled", "not_enabled"})
_PARTIAL_COVERAGE = frozenset({"partial", "partially_succeeded", "legacy"})
_COMPLETE_COVERAGE = frozenset({"complete", "succeeded", "inventory_generated"})
_FAILED_EXECUTION = frozenset({"failed", "error", "not_available"})
_BLOCK_CLEAN_REASONS = frozenset(
    {
        "feed_missing",
        "feed_stale",
        "no_exact_version",
        "cannot_prove_clean",
        "unknown",
        "error",
        "unavailable",
        "missing_git_history",
    }
)
_BLOCK_CLEAN_FRESHNESS = frozenset({"stale", "unknown", "unavailable", "error"})
_BLOCK_CLEAN_LIMITATIONS = frozenset(
    {"cannot_prove_clean", "feed_missing", "feed_stale", "missing_git_history"}
)
SECURITY_VULN_CAPABILITY = "security.m13.vulnerabilities"


def _coverage_status(payload: Mapping[str, Any] | None) -> str:
    if not isinstance(payload, Mapping):
        return ""
    return str(payload.get("status") or "").strip().lower()


def _payload_flag(payload: Mapping[str, Any] | None, key: str) -> bool:
    if not isinstance(payload, Mapping):
        return False
    value = payload.get(key)
    return value is True or str(value).strip().lower() in {"true", "1", "yes"}


def map_engineering_health_display_label(
    *,
    coverage_status: str | None,
    finding_count: int,
    execution_status: str | None = None,
    evidence_sufficient: bool | None = None,
    cannot_prove_clean: bool = False,
) -> str:
    """Map canonical coverage + findings to a presentation label.

    Partial/UNKNOWN coverage never becomes a clean/healthy claim.
    Execution success is not a health conclusion.
    """

    coverage = str(coverage_status or "").strip().lower()
    execution = str(execution_status or "").strip().lower()
    if coverage in _NOT_APPLICABLE_COVERAGE or execution == "not_enabled":
        return DISPLAY_NOT_APPLICABLE
    if execution in _FAILED_EXECUTION:
        return DISPLAY_INSUFFICIENT_EVIDENCE
    if cannot_prove_clean or evidence_sufficient is False:
        return DISPLAY_INSUFFICIENT_EVIDENCE
    if coverage in _UNAVAILABLE_COVERAGE:
        return DISPLAY_INSUFFICIENT_EVIDENCE
    if coverage in _COMPLETE_COVERAGE:
        if finding_count > 0:
            return DISPLAY_NEEDS_ATTENTION
        return DISPLAY_NO_MATERIAL_ISSUES
    if finding_count > 0:
        return DISPLAY_NEEDS_ATTENTION
    return DISPLAY_INSUFFICIENT_EVIDENCE


def display_label_for_section(section: Any) -> str:
    payload = getattr(section, "assessment_coverage", None)
    return map_engineering_health_display_label(
        coverage_status=_coverage_status(payload if isinstance(payload, Mapping) else None),
        finding_count=int(getattr(section, "findings_count", 0) or 0),
        execution_status=str(getattr(section, "status", "") or ""),
        evidence_sufficient=(
            None
            if not isinstance(payload, Mapping) or "evidence_sufficient" not in payload
            else bool(payload.get("evidence_sufficient"))
        ),
        cannot_prove_clean=_payload_flag(
            payload if isinstance(payload, Mapping) else None, "cannot_prove_clean"
        ),
    )


def _row_for_capability(
    rows: Sequence[Any], capability_id: str
) -> Mapping[str, Any] | None:
    for item in rows:
        if isinstance(item, Mapping) and str(item.get("capability_id") or "") == capability_id:
            return item
        capability = getattr(item, "capability_id", None)
        if capability == capability_id:
            dump = getattr(item, "model_dump", None)
            if callable(dump):
                payload = dump(mode="json")
                if isinstance(payload, Mapping):
                    return payload
    return None


def security_evidence_is_sufficient(
    *,
    coverage_rows: Sequence[Any] = (),
    freshness_rows: Sequence[Any] = (),
    limitations: Sequence[str] = (),
) -> bool | None:
    """True when required Security evidence can support a clean claim.

    ``None`` means no sealed vulnerability capability was attached.
    """

    limit_set = {str(item).strip() for item in limitations if str(item).strip()}
    row = _row_for_capability(coverage_rows, SECURITY_VULN_CAPABILITY)
    if row is None and not (limit_set & _BLOCK_CLEAN_LIMITATIONS):
        return None
    if limit_set & _BLOCK_CLEAN_LIMITATIONS:
        return False
    if row is None:
        return False
    execution = str(row.get("execution_state") or "").strip().lower()
    reason = str(row.get("coverage_reason") or "").strip().lower()
    row_limits = {str(item).strip() for item in (row.get("limitations") or ()) if str(item).strip()}
    if execution in _UNAVAILABLE_COVERAGE or execution in _FAILED_EXECUTION:
        return False
    if reason in _BLOCK_CLEAN_REASONS or row_limits & _BLOCK_CLEAN_LIMITATIONS:
        return False
    fresh = _row_for_capability(freshness_rows, SECURITY_VULN_CAPABILITY)
    if fresh is not None:
        state = str(fresh.get("state") or "").strip().lower()
        fresh_reason = str(fresh.get("reason_code") or "").strip().lower()
        if state in _BLOCK_CLEAN_FRESHNESS or fresh_reason in _BLOCK_CLEAN_REASONS:
            return False
    return True


def architecture_evidence_is_sufficient(architecture_report: Any | None) -> bool | None:
    """True/False from the architecture pack conclusion. None when no pack is present."""

    if architecture_report is None:
        return None
    status = str(getattr(architecture_report, "status", "") or "").strip().lower()
    if status in {"insufficient_evidence", "failed", "error", "not_available"}:
        return False
    conclusions = getattr(architecture_report, "conclusions", None) or ()
    for item in conclusions:
        payload = item if isinstance(item, Mapping) else getattr(item, "__dict__", {})
        if not isinstance(payload, Mapping):
            payload = {
                "category": getattr(item, "category", ""),
                "policy_id": getattr(item, "policy_id", ""),
                "conclusion_id": getattr(item, "conclusion_id", ""),
                "coverage": getattr(item, "coverage", None),
            }
        tokens = " ".join(
            str(payload.get(key) or "")
            for key in ("category", "policy_id", "conclusion_id")
        ).lower()
        if "insufficient-evidence" in tokens or "insufficient_evidence" in tokens:
            return False
        coverage = payload.get("coverage")
        if isinstance(coverage, Mapping):
            raw = coverage.get("classification_coverage")
        else:
            raw = getattr(coverage, "classification_coverage", None)
        try:
            if raw is not None and float(raw) <= 0.0:
                return False
        except (TypeError, ValueError):
            pass
    return True


def overlay_headline_evidence_coverage(
    sections: Sequence[Any],
    *,
    metadata: Mapping[str, Any] | None = None,
    architecture_report: Any | None = None,
) -> tuple[Any, ...]:
    """Copy sealed capability/conclusion honesty onto headline coverage payloads."""

    payload = metadata if isinstance(metadata, Mapping) else {}
    coverage_rows = payload.get("canonical_coverage") or ()
    freshness_rows = payload.get("canonical_freshness") or ()
    limitations = tuple(str(item) for item in (payload.get("canonical_limitations") or ()))
    security_ok = security_evidence_is_sufficient(
        coverage_rows=coverage_rows if isinstance(coverage_rows, Sequence) else (),
        freshness_rows=freshness_rows if isinstance(freshness_rows, Sequence) else (),
        limitations=limitations,
    )
    architecture_ok = architecture_evidence_is_sufficient(architecture_report)
    out: list[Any] = []
    for section in sections:
        head = str(getattr(section, "head", "") or "")
        coverage = getattr(section, "assessment_coverage", None)
        updated = dict(coverage) if isinstance(coverage, Mapping) else {}
        if head == "security_intelligence" and security_ok is False:
            updated["evidence_sufficient"] = False
            updated["cannot_prove_clean"] = True
            updated["status"] = "unknown"
        elif head == "architecture_intelligence" and architecture_ok is False:
            updated["evidence_sufficient"] = False
            updated["status"] = "insufficient_evidence"
        if updated != (dict(coverage) if isinstance(coverage, Mapping) else {}):
            out.append(section.model_copy(update={"assessment_coverage": updated}))
        else:
            out.append(section)
    return tuple(out)


def _label_implies_complete(label: str | None) -> bool:
    token = str(label or "").strip().lower()
    return token in _FORBIDDEN_COMPLETE_LABELS


def apply_engineering_health_projection(sections: Sequence[Any]) -> tuple[Any, ...]:
    """Attach role, outcome family, and reconciled display labels.

    When required evidence/rules are unavailable, customer-facing status cannot
    remain Complete/Succeeded.
    """

    out: list[Any] = []
    for section in sections:
        head = str(getattr(section, "head", "") or "")
        role = assessment_head_role(head)
        family = assessment_head_outcome_family(head)
        coverage = _coverage_status(getattr(section, "assessment_coverage", None))
        display_label = display_label_for_section(section)
        updates: dict[str, Any] = {
            "role": role,
            "display_label": display_label,
            "outcome_family": family,
        }
        status_label = str(getattr(section, "status_label", "") or "")
        status = str(getattr(section, "status", "") or "")
        if _label_implies_complete(status_label) and coverage not in _COMPLETE_COVERAGE:
            updates["status_label"] = display_label
        elif role == AssessmentHeadRole.HEADLINE:
            updates["status_label"] = display_label
        if status == "assessed" and coverage in _UNAVAILABLE_COVERAGE | _PARTIAL_COVERAGE:
            updates["status"] = "partially_assessed"
            updates.setdefault("status_label", display_label)
        out.append(section.model_copy(update=updates))
    return tuple(out)


def partition_assessment_heads(
    sections: Sequence[Any],
) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
    headlines = tuple(
        item.model_copy(update={"title": engineering_health_outcome_title(item.head)})
        for item in sections
        if getattr(item, "role", "") == AssessmentHeadRole.HEADLINE
    )
    supporting = tuple(
        item for item in sections if getattr(item, "role", "") == AssessmentHeadRole.SUPPORTING
    )
    appendix = tuple(
        item for item in sections if getattr(item, "role", "") == AssessmentHeadRole.APPENDIX
    )
    return headlines, supporting, appendix
