"""Project sealed baseline records into customer HTML view models.

Copies assess-time M22/M25/M26 and trust metadata. Does not rank, subtract,
or invent comparison/movement.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from codestrata import RULESET_VERSION
from codestrata import __version__ as ENGINE_VERSION
from codestrata.domain.contracts.hotspot import EngineeringHotspot, OwnershipConcentration
from codestrata.reporting.engineering_health.models import (
    AttentionOutcomeView,
    AttentionSummaryView,
    CochangePairView,
    CochangeSectionView,
    CoverageTrustRowView,
    CoverageTrustView,
    EngineeringHotspotView,
    HotspotContributorView,
    HotspotSectionView,
    OwnershipConcentrationView,
    OwnershipSectionView,
)
from codestrata.reporting.engineering_health.projection import (
    DISPLAY_INSUFFICIENT_EVIDENCE,
    DISPLAY_NEEDS_ATTENTION,
    DISPLAY_NOT_APPLICABLE,
)
from codestrata.reporting.html_v2.assessment_heads import (
    AssessmentHeadRole,
    engineering_health_outcome_title,
)

CANONICAL_COCHANGE_KEY = "canonical_cochange"
CANONICAL_COVERAGE_KEY = "canonical_coverage"
CANONICAL_FRESHNESS_KEY = "canonical_freshness"
CANONICAL_HOTSPOTS_KEY = "canonical_hotspots"
CANONICAL_LIMITATIONS_KEY = "canonical_limitations"
CANONICAL_OWNERSHIP_KEY = "canonical_ownership"
DIRTY_KEY = "dirty"
EVALUATION_TIME_KEY = "evaluation_time"
FEED_DIGEST_KEY = "feed_digest"
GIT_HEAD_KEY = "git_head"
GIT_HISTORY_COVERAGE_KEY = "git_history_coverage"
SOURCE_REVISION_KEY = "source_revision"
WORKING_STATE_DIGEST_KEY = "working_state_digest"
WORKING_STATE_DIGEST_KIND_KEY = "working_state_digest_kind"
GIT_WORKING_STATE_KIND = "git_working_state"
COMMITTED_SNAPSHOT_KIND = "committed_snapshot"
GIT_WORKING_STATE_DIGEST_LABEL = "Git working-state digest"
COMMITTED_SNAPSHOT_DIGEST_LABEL = "Committed-snapshot digest"
UNSPECIFIED_CHECKOUT_DIGEST_LABEL = "Sealed checkout digest"
CHECKOUT_DIGEST_NOTE = (
    "Git working-state digest identifies the live Git checkout (HEAD, index, and worktree). "
    "Committed-snapshot digest is sealed when history is replayed from a pinned commit. "
    "Neither value is the canonical file-inventory digest, which is SHA-256 of the sorted "
    "assessed file-path list and does not prove file-content equality."
)

_NO_COMPARISON = "No comparison or trend was requested for this baseline assessment."
_HOTSPOTS_UNAVAILABLE = "Engineering Hotspots unavailable: m22_records_not_attached."
_OWNERSHIP_UNAVAILABLE = "Ownership concentration unavailable: records were not attached."
_COCHANGE_UNAVAILABLE = (
    "Temporal co-change unavailable. No pair, support, or union denominator was supplied."
)


def _as_mapping(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        payload = dump(mode="json")
        if isinstance(payload, Mapping):
            return payload
    return None


def _hotspot_view(item: Any) -> EngineeringHotspotView | None:
    payload = _as_mapping(item)
    if payload is None:
        return None
    try:
        record = (
            item
            if isinstance(item, EngineeringHotspot)
            else EngineeringHotspot.model_validate(payload)
        )
    except Exception:
        record = None
    source = record.model_dump(mode="json") if record is not None else dict(payload)
    contributors = []
    for part in source.get("contributors") or ():
        if not isinstance(part, Mapping):
            continue
        name = str(part.get("name") or "").strip()
        role = str(part.get("role") or "").strip()
        if not name or not role:
            continue
        contributors.append(
            HotspotContributorView(
                name=name,
                role=role,
                value=None if part.get("value") is None else str(part.get("value")),
                measurement_id=(
                    None if part.get("measurement_id") is None else str(part.get("measurement_id"))
                ),
                coverage_reason=(
                    None
                    if part.get("coverage_reason") is None
                    else str(part.get("coverage_reason"))
                ),
                evidence_ids=tuple(str(eid) for eid in part.get("evidence_ids") or ()),
            )
        )
    record_id = str(source.get("record_id") or "").strip()
    subject_id = str(source.get("subject_id") or "").strip()
    list_kind = str(source.get("list_kind") or "").strip()
    if not record_id or not subject_id or not list_kind:
        return None
    ranking = source.get("ranking_value")
    return EngineeringHotspotView(
        record_id=record_id,
        subject_id=subject_id,
        list_kind=list_kind,
        ranking_value=None if ranking is None else str(ranking),
        history_profile_id=(
            None
            if source.get("history_profile_id") is None
            else str(source.get("history_profile_id"))
        ),
        history_window=(
            None if source.get("history_window") is None else str(source.get("history_window"))
        ),
        priority_explanation=(
            None
            if source.get("priority_explanation") is None
            else str(source.get("priority_explanation"))
        ),
        contributors=tuple(contributors),
        active_finding_ids=tuple(str(fid) for fid in source.get("active_finding_ids") or ()),
        evidence_ids=tuple(str(eid) for eid in source.get("evidence_ids") or ()),
    )


def project_hotspot_section(metadata: Mapping[str, Any] | None) -> HotspotSectionView:
    records = () if not isinstance(metadata, Mapping) else metadata.get(CANONICAL_HOTSPOTS_KEY)
    if records is None:
        return HotspotSectionView(available=False, unavailable_reason=_HOTSPOTS_UNAVAILABLE)
    items = tuple(item for raw in records if (item := _hotspot_view(raw)) is not None)
    if not items:
        return HotspotSectionView(
            available=False, unavailable_reason=_HOTSPOTS_UNAVAILABLE, items=()
        )
    return HotspotSectionView(available=True, items=items)


def _ownership_view(item: Any) -> OwnershipConcentrationView | None:
    payload = _as_mapping(item)
    if payload is None:
        return None
    try:
        record = (
            item
            if isinstance(item, OwnershipConcentration)
            else OwnershipConcentration.model_validate(payload)
        )
        source = record.model_dump(mode="json")
    except Exception:
        source = dict(payload)
    subject_id = str(source.get("subject_id") or "").strip()
    scope = str(source.get("scope") or "").strip()
    if not subject_id or not scope:
        return None
    return OwnershipConcentrationView(
        scope=scope,
        subject_id=subject_id,
        numerator=source.get("numerator"),
        denominator=source.get("denominator"),
        serialized_ratio=(
            None if source.get("serialized_ratio") is None else str(source.get("serialized_ratio"))
        ),
        history_profile_id=(
            None
            if source.get("history_profile_id") is None
            else str(source.get("history_profile_id"))
        ),
        history_window=None
        if source.get("history_window") is None
        else str(source.get("history_window")),
        status=None if source.get("status") is None else str(source.get("status")),
        notes=None if source.get("notes") is None else str(source.get("notes")),
        evidence_ids=tuple(str(eid) for eid in source.get("evidence_ids") or ()),
    )


def project_ownership_section(metadata: Mapping[str, Any] | None) -> OwnershipSectionView:
    records = () if not isinstance(metadata, Mapping) else metadata.get(CANONICAL_OWNERSHIP_KEY)
    if records is None:
        return OwnershipSectionView(available=False, unavailable_reason=_OWNERSHIP_UNAVAILABLE)
    items = tuple(item for raw in records if (item := _ownership_view(raw)) is not None)
    if not items:
        return OwnershipSectionView(
            available=False,
            unavailable_reason=_OWNERSHIP_UNAVAILABLE,
            items=(),
        )
    return OwnershipSectionView(available=True, items=items)


def _cochange_view(item: Any) -> CochangePairView | None:
    payload = _as_mapping(item)
    if payload is None:
        return None
    left = str(payload.get("left") or "").strip()
    right = str(payload.get("right") or "").strip()
    scope = str(payload.get("scope") or "repository").strip() or "repository"
    if not left or not right:
        return None
    support = payload.get("support")
    union = payload.get("union")
    jaccard = payload.get("jaccard")
    return CochangePairView(
        scope=scope,
        left=left,
        right=right,
        support=None if support is None else int(support),
        union=None if union is None else int(union),
        jaccard=None if jaccard is None else str(jaccard),
        supported_relation=(
            None
            if payload.get("supported_relation") is None
            else bool(payload.get("supported_relation"))
        ),
        qualified_incomplete_window=bool(payload.get("qualified_incomplete_window")),
        unavailable_reason=(
            None
            if payload.get("unavailable_reason") is None
            else str(payload.get("unavailable_reason"))
        ),
    )


def project_cochange_section(metadata: Mapping[str, Any] | None) -> CochangeSectionView:
    records = () if not isinstance(metadata, Mapping) else metadata.get(CANONICAL_COCHANGE_KEY)
    if records is None:
        return CochangeSectionView(available=False, unavailable_reason=_COCHANGE_UNAVAILABLE)
    items = tuple(item for raw in records if (item := _cochange_view(raw)) is not None)
    if not items:
        return CochangeSectionView(
            available=False, unavailable_reason=_COCHANGE_UNAVAILABLE, items=()
        )
    return CochangeSectionView(available=True, items=items)


def _checkout_digest_label(kind: object) -> str:
    """Label the sealed checkout digest without renaming the stored value."""

    if kind == GIT_WORKING_STATE_KIND:
        return GIT_WORKING_STATE_DIGEST_LABEL
    if kind == COMMITTED_SNAPSHOT_KIND:
        return COMMITTED_SNAPSHOT_DIGEST_LABEL
    return UNSPECIFIED_CHECKOUT_DIGEST_LABEL


def _meta_text(metadata: Mapping[str, Any], key: str) -> str:
    value = metadata.get(key)
    if value is None or str(value).strip() == "":
        return "UNKNOWN"
    return str(value)


def project_coverage_trust(
    metadata: Mapping[str, Any] | None,
    *,
    engine_version: str | None = None,
    report_version: str | None = None,
) -> CoverageTrustView:
    payload = metadata if isinstance(metadata, Mapping) else {}
    dirty = payload.get(DIRTY_KEY)
    if dirty is True:
        working_state = "dirty"
    elif dirty is False:
        working_state = "clean"
    else:
        working_state = "UNKNOWN"
    rows = [
        CoverageTrustRowView(label="Engine version", value=engine_version or ENGINE_VERSION),
        CoverageTrustRowView(label="Rule package version", value=RULESET_VERSION),
        CoverageTrustRowView(label="Report version", value=report_version or "unknown"),
        CoverageTrustRowView(
            label="Source revision", value=_meta_text(payload, SOURCE_REVISION_KEY)
        ),
        CoverageTrustRowView(label="Git HEAD", value=_meta_text(payload, GIT_HEAD_KEY)),
        CoverageTrustRowView(label="Working state", value=working_state),
        CoverageTrustRowView(
            label=_checkout_digest_label(payload.get(WORKING_STATE_DIGEST_KIND_KEY)),
            value=_meta_text(payload, WORKING_STATE_DIGEST_KEY),
        ),
        CoverageTrustRowView(
            label="Evaluation time", value=_meta_text(payload, EVALUATION_TIME_KEY)
        ),
        CoverageTrustRowView(
            label="Vulnerability feed digest", value=_meta_text(payload, FEED_DIGEST_KEY)
        ),
        CoverageTrustRowView(
            label="Git history coverage",
            value=_meta_text(payload, GIT_HISTORY_COVERAGE_KEY),
        ),
    ]
    capability_rows: list[dict[str, Any]] = []
    freshness = {
        str(item.get("capability_id")): item
        for item in payload.get(CANONICAL_FRESHNESS_KEY) or ()
        if isinstance(item, Mapping)
    }
    for item in payload.get(CANONICAL_COVERAGE_KEY) or ():
        if not isinstance(item, Mapping):
            dump = _as_mapping(item)
            if dump is None:
                continue
            item = dump
        capability_id = str(item.get("capability_id") or "")
        fresh = freshness.get(capability_id, {})
        capability_rows.append(
            {
                "capability_id": capability_id,
                "scope": item.get("scope"),
                "execution_state": item.get("execution_state"),
                "coverage_ratio": item.get("coverage_ratio"),
                "coverage_reason": item.get("coverage_reason"),
                "freshness": fresh.get("state") if isinstance(fresh, Mapping) else None,
                "freshness_reason": fresh.get("reason_code")
                if isinstance(fresh, Mapping)
                else None,
                "feed_provider": fresh.get("feed_provider") if isinstance(fresh, Mapping) else None,
            }
        )
    limitations = tuple(
        str(item) for item in payload.get(CANONICAL_LIMITATIONS_KEY) or () if str(item).strip()
    )
    return CoverageTrustView(
        rows=tuple(rows),
        capability_rows=tuple(capability_rows),
        material_limitations=limitations[:8],
        comparison_state=_NO_COMPARISON,
        identity_note=CHECKOUT_DIGEST_NOTE,
    )


def project_attention_summary(
    *,
    headline_outcomes: Sequence[Any],
    leadership_verdict: str,
    key_takeaways: Sequence[str],
    priority_action_ids: Sequence[str],
) -> AttentionSummaryView:
    verdict = (leadership_verdict or "").strip()
    takeaway = next((str(item).strip() for item in key_takeaways if str(item).strip()), "")
    headline = verdict or takeaway or "Review the four outcomes and attached evidence."
    needing: list[AttentionOutcomeView] = []
    unavailable: list[AttentionOutcomeView] = []
    for section in headline_outcomes:
        label = str(getattr(section, "display_label", "") or "")
        row = AttentionOutcomeView(
            head=str(getattr(section, "head", "") or ""),
            title=engineering_health_outcome_title(getattr(section, "head", "")),
            display_label=label or "Insufficient evidence",
            findings_count=int(getattr(section, "findings_count", 0) or 0),
            anchor=str(getattr(section, "anchor", "") or ""),
        )
        if label == DISPLAY_NEEDS_ATTENTION:
            needing.append(row)
        elif label in {DISPLAY_INSUFFICIENT_EVIDENCE, DISPLAY_NOT_APPLICABLE}:
            unavailable.append(row)
        elif str(getattr(section, "role", "") or "") == AssessmentHeadRole.HEADLINE:
            coverage = getattr(section, "assessment_coverage", None)
            status = ""
            if isinstance(coverage, Mapping):
                status = str(coverage.get("status") or "").strip().lower()
            if status in {"unavailable", "unknown", "insufficient_evidence", "error", ""}:
                unavailable.append(row)
    return AttentionSummaryView(
        headline=headline,
        outcomes_needing_attention=tuple(needing),
        unavailable_evidence=tuple(unavailable),
        top_priority_action_ids=tuple(str(item) for item in priority_action_ids[:3]),
        comparison_state=_NO_COMPARISON,
    )


def overlay_subjects_from_hotspots(
    section: HotspotSectionView,
) -> dict[str, tuple[str, ...]]:
    mapping: dict[str, list[str]] = {}
    for item in section.items:
        mapping.setdefault(item.subject_id, []).append(item.record_id)
    return {key: tuple(values) for key, values in mapping.items()}


def overlay_subjects_from_ownership(
    section: OwnershipSectionView,
) -> dict[str, tuple[str, ...]]:
    mapping: dict[str, list[str]] = {}
    for item in section.items:
        mapping.setdefault(item.subject_id, []).append(item.subject_id)
    return {key: tuple(values) for key, values in mapping.items()}
