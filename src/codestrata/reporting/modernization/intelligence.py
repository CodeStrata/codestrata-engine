"""Build Modernization Assessment Intelligence (Epic 3 Slice 3.9).

Synthesis only: projects existing Findings → Recommendations → Priority Actions
→ Roadmap Initiatives. Does NOT import codestrata.reporting.html_v2 (circular
import). Duck-type entities with Any + getattr. Never invents Priority Actions
from Findings, never merges AI Advisor narrative, never creates a second roadmap.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from codestrata.reporting.modernization.intelligence_models import (
    ModernizationContributingHead,
    ModernizationCoverageRow,
    ModernizationInitiativeLink,
    ModernizationIntelligenceSection,
    ModernizationOverviewFact,
    ModernizationPhaseSummary,
    ModernizationPriorityActionLink,
    ModernizationThemeSummary,
)
from codestrata.reporting.roadmap.models import RoadmapReportSection

_BASE_LIMITATIONS = (
    "Modernization Assessment is derived from enabled assessment heads.",
    "Disabled or unavailable heads reduce completeness.",
    "No delivery estimate was produced.",
    "No cost estimate was produced.",
    "No staffing estimate was produced.",
    "No business-case or ROI analysis was performed.",
    "No runtime transformation validation was performed.",
    "Roadmap sequencing is deterministic guidance, not a delivery commitment.",
    "Legacy entities may have limited traceability.",
    "Absence of Priority Actions does not establish absence of modernization need.",
)

_SOFT_CLAIM_FRAGMENTS = (
    "modernization ready",
    "transformation ready",
    "transformation-ready",
    "easy to modernize",
    "low modernization risk",
    "strong modernization foundation",
    "clear path to transformation",
    "rapid migration",
    "rapid modernization",
    "high roi",
    "low effort",
    "transformation will succeed",
    "no modernization issues",
    "no modernization need",
    "no modernization needed",
    "guaranteed outcome",
    "easy migration",
)

_EMPTY_ACTIONS_MESSAGE = (
    "No deterministic modernization Priority Actions were produced from the "
    "assessed scope. Absence of Priority Actions does not establish absence of "
    "modernization need."
)

_SAFE_STATUS_SUMMARY = (
    "The modernization assessment synthesizes deterministic findings and "
    "recommendations from the enabled assessment heads. The roadmap is planning "
    "guidance, not a delivery commitment."
)

_CONFIDENCE_RANK = {
    "high": 3,
    "moderate": 2,
    "medium": 2,
    "limited": 1,
    "low": 1,
    "unavailable": 0,
    "unknown": 0,
    "legacy": 0,
}

# Structured head classification — mirrors Epic 3 Slice 3.1 maps without html_v2 import.
_CATEGORY_TO_HEAD: dict[str, tuple[str, str, str]] = {
    # head_id, title, anchor
    "security": (
        "security_intelligence",
        "Security Intelligence",
        "security-intelligence",
    ),
    "dependency": (
        "dependency_intelligence",
        "Dependency Intelligence",
        "dependency-intelligence",
    ),
    "technical_debt": (
        "technical_debt_intelligence",
        "Technical Debt Intelligence",
        "technical-debt-intelligence",
    ),
    "maintainability": (
        "technical_debt_intelligence",
        "Technical Debt Intelligence",
        "technical-debt-intelligence",
    ),
    "architecture": (
        "architecture_intelligence",
        "Architecture Intelligence",
        "architecture-intelligence",
    ),
    "cloud": ("cloud_readiness", "Cloud Readiness", "cloud-readiness"),
    "cloud_readiness": ("cloud_readiness", "Cloud Readiness", "cloud-readiness"),
    "ai_readiness": ("ai_readiness", "AI Readiness", "ai-readiness"),
    "modernization": (
        "modernization_assessment",
        "Modernization Assessment",
        "modernization-assessment",
    ),
    "technology": (
        "technology_inventory",
        "Technology Inventory",
        "technology-inventory",
    ),
}

_RULE_PREFIX_TO_HEAD: tuple[tuple[str, tuple[str, str, str]], ...] = (
    (
        "technical_debt.",
        (
            "technical_debt_intelligence",
            "Technical Debt Intelligence",
            "technical-debt-intelligence",
        ),
    ),
    (
        "ai_readiness.",
        ("ai_readiness", "AI Readiness", "ai-readiness"),
    ),
    (
        "ai-readiness.",
        ("ai_readiness", "AI Readiness", "ai-readiness"),
    ),
    (
        "architecture.",
        (
            "architecture_intelligence",
            "Architecture Intelligence",
            "architecture-intelligence",
        ),
    ),
    (
        "dependency.",
        (
            "dependency_intelligence",
            "Dependency Intelligence",
            "dependency-intelligence",
        ),
    ),
    (
        "security.",
        (
            "security_intelligence",
            "Security Intelligence",
            "security-intelligence",
        ),
    ),
    (
        "cloud.",
        ("cloud_readiness", "Cloud Readiness", "cloud-readiness"),
    ),
    (
        "modernization.",
        (
            "modernization_assessment",
            "Modernization Assessment",
            "modernization-assessment",
        ),
    ),
)

# Heads shown as modernization contributors / themes (spec examples).
_THEME_HEAD_ORDER: tuple[str, ...] = (
    "architecture_intelligence",
    "technical_debt_intelligence",
    "dependency_intelligence",
    "security_intelligence",
    "cloud_readiness",
    "ai_readiness",
)

_HEAD_META: dict[str, tuple[str, str]] = {
    "architecture_intelligence": (
        "Architecture Intelligence",
        "architecture-intelligence",
    ),
    "technical_debt_intelligence": (
        "Technical Debt Intelligence",
        "technical-debt-intelligence",
    ),
    "dependency_intelligence": (
        "Dependency Intelligence",
        "dependency-intelligence",
    ),
    "security_intelligence": ("Security Intelligence", "security-intelligence"),
    "cloud_readiness": ("Cloud Readiness", "cloud-readiness"),
    "ai_readiness": ("AI Readiness", "ai-readiness"),
    "modernization_assessment": (
        "Modernization Assessment",
        "modernization-assessment",
    ),
    "technology_inventory": ("Technology Inventory", "technology-inventory"),
}

_PHASE_ORDER = ("stabilize", "secure", "modernize", "optimize")


def build_modernization_intelligence(
    *,
    findings: Sequence[Any] = (),
    recommendations: Sequence[Any] = (),
    priority_actions: Sequence[Any] = (),
    roadmap_report: RoadmapReportSection | None = None,
) -> ModernizationIntelligenceSection:
    """Project Modernization Assessment from existing deterministic artifacts.

    Does not create Findings, Recommendations, Priority Actions, or Roadmap
    Initiatives. Does not consume AI Advisor / enrichment content.
    """

    finding_heads = {
        str(getattr(item, "finding_id", "") or ""): _classify_finding_head(item)
        for item in findings
        if str(getattr(item, "finding_id", "") or "").strip()
    }
    rec_heads = {
        str(getattr(item, "recommendation_id", "") or ""): _classify_recommendation_head(
            item, finding_heads=finding_heads
        )
        for item in recommendations
        if str(getattr(item, "recommendation_id", "") or "").strip()
    }

    pa_links = _priority_action_links(
        priority_actions,
        finding_heads=finding_heads,
        rec_heads=rec_heads,
    )
    phases, initiative_count, roadmap_is_legacy, uses_canonical = _roadmap_phases(
        roadmap_report
    )
    contributing = _contributing_heads(
        findings=findings,
        recommendations=recommendations,
        priority_actions=priority_actions,
        finding_heads=finding_heads,
        rec_heads=rec_heads,
    )
    themes = _themes(
        priority_actions=priority_actions,
        recommendations=recommendations,
        finding_heads=finding_heads,
        rec_heads=rec_heads,
    )

    supporting_finding_ids = _supporting_finding_ids(priority_actions, recommendations)
    supporting_rec_ids = _supporting_recommendation_ids(priority_actions, recommendations)

    overview = _overview(
        contributing=contributing,
        supporting_finding_count=len(supporting_finding_ids),
        supporting_recommendation_count=len(supporting_rec_ids),
        priority_action_count=len(pa_links),
        initiative_count=initiative_count,
        phases=phases,
        roadmap_is_legacy=roadmap_is_legacy,
    )
    coverage_rows = _coverage_rows(
        contributing=contributing,
        supporting_finding_count=len(supporting_finding_ids),
        supporting_recommendation_count=len(supporting_rec_ids),
        priority_action_count=len(pa_links),
        initiative_count=initiative_count,
        roadmap_report=roadmap_report,
        roadmap_is_legacy=roadmap_is_legacy,
    )
    limitations = _limitations(
        roadmap_report=roadmap_report,
        priority_action_count=len(pa_links),
        contributing=contributing,
        roadmap_is_legacy=roadmap_is_legacy,
    )
    confidence, confidence_label = _confidence(
        priority_actions=priority_actions,
        findings=findings,
        supporting_finding_ids=supporting_finding_ids,
        limitations=limitations,
        priority_action_count=len(pa_links),
    )
    status, status_label = _status(
        priority_action_count=len(pa_links),
        initiative_count=initiative_count,
        contributing=contributing,
        supporting_finding_count=len(supporting_finding_ids),
    )
    empty_message = _EMPTY_ACTIONS_MESSAGE if not pa_links else None

    return ModernizationIntelligenceSection(
        status=status,
        status_label=status_label,
        status_summary=_SAFE_STATUS_SUMMARY,
        confidence=confidence,
        confidence_label=confidence_label,
        overview_facts=overview,
        contributing_heads=contributing,
        priority_actions=pa_links,
        roadmap_phases=phases,
        themes=themes,
        coverage_rows=coverage_rows,
        limitations=limitations,
        supporting_finding_count=len(supporting_finding_ids),
        supporting_recommendation_count=len(supporting_rec_ids),
        priority_action_count=len(pa_links),
        roadmap_initiative_count=initiative_count,
        empty_actions_message=empty_message,
        roadmap_is_legacy=roadmap_is_legacy,
        uses_canonical_roadmap=uses_canonical,
    )


def scrub_soft_modernization_claims(text: str, *, fallback: str) -> str:
    """Replace soft modernization claims with a safe observational fallback."""

    if not text or not str(text).strip():
        return fallback
    if _contains_soft_claim(text):
        return fallback
    return str(text).strip()


def _contains_soft_claim(text: str) -> bool:
    lowered = str(text).lower()
    neutralized = (
        lowered.replace("does not establish absence of modernization need", "")
        .replace("do not establish absence of modernization need", "")
        .replace("absence of priority actions does not establish", "")
        .replace("not a delivery commitment", "")
        .replace("modernization assessment", "")
        .replace("modernization need", "")
    )
    return any(fragment in neutralized for fragment in _SOFT_CLAIM_FRAGMENTS)


def _normalize_category(category: str | None) -> str:
    return (category or "").strip().lower().replace(" ", "_").replace("-", "_")


def _classify_finding_head(item: Any) -> tuple[str, str, str] | None:
    category_head = _CATEGORY_TO_HEAD.get(
        _normalize_category(getattr(item, "category", None))
    )
    if category_head is not None:
        return category_head
    rid = (getattr(item, "rule_id", None) or "").strip().lower()
    for prefix, head in _RULE_PREFIX_TO_HEAD:
        if rid.startswith(prefix):
            return head
    return None


def _classify_recommendation_head(
    item: Any,
    *,
    finding_heads: dict[str, tuple[str, str, str] | None],
) -> tuple[str, str, str] | None:
    category_head = _CATEGORY_TO_HEAD.get(
        _normalize_category(getattr(item, "category", None))
    )
    if category_head is not None:
        return category_head
    primary = getattr(item, "primary_finding_id", None)
    if primary and primary in finding_heads and finding_heads[primary] is not None:
        return finding_heads[primary]
    for fid in getattr(item, "related_finding_ids", ()) or ():
        head = finding_heads.get(str(fid))
        if head is not None:
            return head
    return None


def _priority_action_links(
    priority_actions: Sequence[Any],
    *,
    finding_heads: dict[str, tuple[str, str, str] | None],
    rec_heads: dict[str, tuple[str, str, str] | None],
) -> tuple[ModernizationPriorityActionLink, ...]:
    rows: list[ModernizationPriorityActionLink] = []
    for item in priority_actions:
        action_id = str(
            getattr(item, "recommendation_id", None)
            or getattr(item, "action_id", None)
            or ""
        ).strip()
        title = str(getattr(item, "title", "") or "").strip()
        if not action_id or not title:
            continue
        # Reject presentation:finding synthesis IDs if somehow present.
        if action_id.startswith("presentation:finding:"):
            continue
        head = rec_heads.get(action_id)
        if head is None:
            head = _classify_recommendation_head(item, finding_heads=finding_heads)
        finding_ids = tuple(
            str(fid).strip()
            for fid in (getattr(item, "related_finding_ids", ()) or ())
            if str(fid).strip()
        )
        supporting_recs = tuple(
            str(rid).strip()
            for rid in (getattr(item, "supporting_recommendation_ids", ()) or ())
            if str(rid).strip()
        )
        # Canonical PA often equals its supporting recommendation id.
        rec_count = len(supporting_recs) if supporting_recs else (
            1 if getattr(item, "action_type", None) else 0
        )
        effort = getattr(item, "effort", None)
        effort_text = str(effort).strip() if effort is not None else None
        if effort_text and effort_text.lower() in {"unknown", "none", ""}:
            effort_text = None
        completeness = str(
            getattr(item, "evidence_completeness", "") or ""
        ).strip() or None
        limitations = tuple(
            str(note).strip()
            for note in (getattr(item, "limitations", ()) or ())
            if str(note).strip()
        )
        rows.append(
            ModernizationPriorityActionLink(
                action_id=action_id,
                title=title,
                priority=str(getattr(item, "priority", "") or "").strip() or None,
                presentation_bucket=(
                    str(getattr(item, "presentation_bucket", "") or "").strip() or None
                ),
                effort=effort_text,
                supporting_recommendation_count=rec_count,
                supporting_finding_count=len(finding_ids),
                evidence_completeness=completeness,
                limitations=limitations,
                head_id=head[0] if head else None,
                head_title=head[1] if head else None,
            )
        )
    rows.sort(
        key=lambda row: (
            _priority_rank(row.priority),
            row.title.lower(),
            row.action_id,
        )
    )
    return tuple(rows)


def _priority_rank(priority: str | None) -> int:
    order = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "moderate": 2,
        "low": 3,
        "informational": 4,
    }
    return order.get((priority or "").strip().lower(), 99)


def _roadmap_phases(
    roadmap_report: RoadmapReportSection | None,
) -> tuple[tuple[ModernizationPhaseSummary, ...], int, bool, bool]:
    if roadmap_report is None:
        return (), 0, False, False

    metadata = getattr(roadmap_report, "metadata", {}) or {}
    source = str(metadata.get("source", "") or "").strip().lower()
    phases_out: list[ModernizationPhaseSummary] = []
    total = 0
    any_legacy = False
    any_pa_backed = False

    phase_list = list(roadmap_report.phases)
    phase_list.sort(
        key=lambda phase: (
            _phase_rank(getattr(phase, "phase", None) or getattr(phase, "phase_id", "")),
            int(getattr(phase, "sequence", 0) or 0),
            str(getattr(phase, "title", "") or ""),
        )
    )

    for phase in phase_list:
        initiatives_raw = tuple(
            item
            for item in (getattr(phase, "initiatives", ()) or ())
            if getattr(item, "supporting_priority_action_ids", ())
            or getattr(item, "supporting_recommendation_ids", ())
        )
        if not initiatives_raw:
            continue
        initiative_links: list[ModernizationInitiativeLink] = []
        phase_has_legacy = False
        for item in initiatives_raw:
            initiative_type = str(
                getattr(item, "initiative_type", "legacy") or "legacy"
            ).strip().lower()
            is_legacy = initiative_type == "legacy"
            if is_legacy:
                phase_has_legacy = True
                any_legacy = True
            else:
                any_pa_backed = True
            pa_ids = tuple(
                str(pid).strip()
                for pid in (getattr(item, "supporting_priority_action_ids", ()) or ())
                if str(pid).strip()
            )
            # Never invent PA links for legacy initiatives.
            if is_legacy:
                pa_ids = ()
            title = _initiative_title(item, pa_ids=pa_ids)
            effort = str(getattr(item, "effort", "") or "").strip() or None
            if effort and effort.lower() in {"unknown", "none"}:
                effort = None
            initiative_links.append(
                ModernizationInitiativeLink(
                    initiative_id=str(getattr(item, "initiative_id", "") or "").strip(),
                    title=title,
                    sequence=int(getattr(item, "sequence", 0) or 0),
                    priority=str(getattr(item, "priority", "") or "").strip() or None,
                    effort=effort,
                    supporting_priority_action_ids=pa_ids,
                    depends_on_initiative_ids=tuple(
                        str(dep).strip()
                        for dep in (getattr(item, "depends_on_initiative_ids", ()) or ())
                        if str(dep).strip()
                    ),
                    evidence_completeness=(
                        str(getattr(item, "evidence_completeness", "") or "").strip()
                        or None
                    ),
                    limitations=tuple(
                        str(note).strip()
                        for note in (getattr(item, "limitations", ()) or ())
                        if str(note).strip()
                    ),
                    is_legacy=is_legacy,
                )
            )
        initiative_links.sort(key=lambda row: (row.sequence, row.title.lower()))
        total += len(initiative_links)
        phases_out.append(
            ModernizationPhaseSummary(
                phase_id=str(getattr(phase, "phase_id", "") or phase.phase),
                phase=str(getattr(phase, "phase", "") or ""),
                title=str(getattr(phase, "title", "") or ""),
                sequence=int(getattr(phase, "sequence", 0) or 0),
                initiative_count=len(initiative_links),
                initiatives=tuple(initiative_links),
                has_legacy=phase_has_legacy,
            )
        )

    uses_canonical = any_pa_backed or source == "priority_actions"
    roadmap_is_legacy = (not uses_canonical and any_legacy) or (
        source == "legacy" or (any_legacy and not any_pa_backed)
    )
    return tuple(phases_out), total, roadmap_is_legacy, uses_canonical


def _initiative_title(item: Any, *, pa_ids: tuple[str, ...]) -> str:
    summary = str(getattr(item, "summary", "") or "").strip()
    if summary:
        return summary
    raw = str(getattr(item, "title", "") or "").strip()
    if " — " in raw:
        raw = raw.split(" — ", 1)[-1].strip()
    if raw:
        return raw
    if pa_ids:
        return f"Initiative for {pa_ids[0]}"
    return "Modernization initiative"


def _phase_rank(phase: str | None) -> int:
    key = (phase or "").strip().lower()
    try:
        return _PHASE_ORDER.index(key)
    except ValueError:
        return 99


def _contributing_heads(
    *,
    findings: Sequence[Any],
    recommendations: Sequence[Any],
    priority_actions: Sequence[Any],
    finding_heads: dict[str, tuple[str, str, str] | None],
    rec_heads: dict[str, tuple[str, str, str] | None],
) -> tuple[ModernizationContributingHead, ...]:
    counts: dict[str, dict[str, int]] = {}
    meta: dict[str, tuple[str, str]] = {}

    def _bump(head: tuple[str, str, str] | None, field: str) -> None:
        if head is None:
            return
        head_id, title, anchor = head
        # Do not list Modernization Assessment as a contributing head to itself.
        if head_id == "modernization_assessment":
            return
        if head_id not in _THEME_HEAD_ORDER and head_id not in _HEAD_META:
            return
        bucket = counts.setdefault(
            head_id, {"finding_count": 0, "recommendation_count": 0, "priority_action_count": 0}
        )
        bucket[field] += 1
        meta[head_id] = (title, anchor)

    for item in findings:
        fid = str(getattr(item, "finding_id", "") or "")
        _bump(finding_heads.get(fid) or _classify_finding_head(item), "finding_count")
    for item in recommendations:
        rid = str(getattr(item, "recommendation_id", "") or "")
        _bump(
            rec_heads.get(rid)
            or _classify_recommendation_head(item, finding_heads=finding_heads),
            "recommendation_count",
        )
    for item in priority_actions:
        action_id = str(
            getattr(item, "recommendation_id", None)
            or getattr(item, "action_id", None)
            or ""
        ).strip()
        head = rec_heads.get(action_id)
        if head is None:
            head = _classify_recommendation_head(item, finding_heads=finding_heads)
        _bump(head, "priority_action_count")

    rows: list[ModernizationContributingHead] = []
    ordered = list(_THEME_HEAD_ORDER) + [
        key for key in counts if key not in _THEME_HEAD_ORDER
    ]
    for head_id in ordered:
        if head_id not in counts:
            continue
        title, anchor = meta.get(head_id) or _HEAD_META.get(
            head_id, (head_id.replace("_", " ").title(), head_id.replace("_", "-"))
        )
        bucket = counts[head_id]
        if not any(bucket.values()):
            continue
        rows.append(
            ModernizationContributingHead(
                head_id=head_id,
                title=title,
                anchor=anchor,
                finding_count=bucket["finding_count"],
                recommendation_count=bucket["recommendation_count"],
                priority_action_count=bucket["priority_action_count"],
            )
        )
    return tuple(rows)


def _themes(
    *,
    priority_actions: Sequence[Any],
    recommendations: Sequence[Any],
    finding_heads: dict[str, tuple[str, str, str] | None],
    rec_heads: dict[str, tuple[str, str, str] | None],
) -> tuple[ModernizationThemeSummary, ...]:
    """Bounded themes = assessment-head groups with counts and top deterministic titles."""

    by_head: dict[str, dict[str, Any]] = {}

    def _ensure(head: tuple[str, str, str]) -> dict[str, Any]:
        head_id, title, anchor = head
        if head_id == "modernization_assessment":
            # Themes prefer contributing intelligence heads; skip self.
            return {}
        if head_id not in _THEME_HEAD_ORDER:
            return {}
        bucket = by_head.setdefault(
            head_id,
            {
                "title": title,
                "anchor": anchor,
                "pa_count": 0,
                "rec_count": 0,
                "titles": [],
            },
        )
        return bucket

    for item in priority_actions:
        action_id = str(
            getattr(item, "recommendation_id", None)
            or getattr(item, "action_id", None)
            or ""
        ).strip()
        head = rec_heads.get(action_id)
        if head is None:
            head = _classify_recommendation_head(item, finding_heads=finding_heads)
        if head is None:
            continue
        bucket = _ensure(head)
        if not bucket:
            continue
        bucket["pa_count"] += 1
        title = str(getattr(item, "title", "") or "").strip()
        if title:
            bucket["titles"].append(title)

    for item in recommendations:
        rid = str(getattr(item, "recommendation_id", "") or "")
        head = rec_heads.get(rid) or _classify_recommendation_head(
            item, finding_heads=finding_heads
        )
        if head is None:
            continue
        bucket = _ensure(head)
        if not bucket:
            continue
        bucket["rec_count"] += 1
        # Prefer PA titles for theme tops; only add rec titles when no PAs yet.
        if bucket["pa_count"] == 0:
            title = str(getattr(item, "title", "") or "").strip()
            if title:
                bucket["titles"].append(title)

    rows: list[ModernizationThemeSummary] = []
    for head_id in _THEME_HEAD_ORDER:
        bucket = by_head.get(head_id)
        if not bucket:
            continue
        if bucket["pa_count"] == 0 and bucket["rec_count"] == 0:
            continue
        # Deduplicate titles preserving order; take top 3.
        seen: set[str] = set()
        top: list[str] = []
        for title in bucket["titles"]:
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            top.append(title)
            if len(top) >= 3:
                break
        rows.append(
            ModernizationThemeSummary(
                head_id=head_id,
                title=bucket["title"],
                anchor=bucket["anchor"],
                priority_action_count=bucket["pa_count"],
                recommendation_count=bucket["rec_count"],
                top_titles=tuple(top),
            )
        )
    return tuple(rows)


def _supporting_finding_ids(
    priority_actions: Sequence[Any],
    recommendations: Sequence[Any],
) -> set[str]:
    ids: set[str] = set()
    for item in priority_actions:
        for fid in getattr(item, "related_finding_ids", ()) or ():
            text = str(fid).strip()
            if text:
                ids.add(text)
    for item in recommendations:
        for fid in getattr(item, "related_finding_ids", ()) or ():
            text = str(fid).strip()
            if text:
                ids.add(text)
        primary = getattr(item, "primary_finding_id", None)
        if primary and str(primary).strip():
            ids.add(str(primary).strip())
    return ids


def _supporting_recommendation_ids(
    priority_actions: Sequence[Any],
    recommendations: Sequence[Any],
) -> set[str]:
    ids: set[str] = set()
    for item in recommendations:
        rid = str(getattr(item, "recommendation_id", "") or "").strip()
        if rid:
            ids.add(rid)
    for item in priority_actions:
        for rid in getattr(item, "supporting_recommendation_ids", ()) or ():
            text = str(rid).strip()
            if text:
                ids.add(text)
        # PA id often equals supporting recommendation id.
        action_id = str(
            getattr(item, "recommendation_id", None)
            or getattr(item, "action_id", None)
            or ""
        ).strip()
        if action_id and getattr(item, "action_type", None):
            ids.add(action_id)
    return ids


def _overview(
    *,
    contributing: Sequence[ModernizationContributingHead],
    supporting_finding_count: int,
    supporting_recommendation_count: int,
    priority_action_count: int,
    initiative_count: int,
    phases: Sequence[ModernizationPhaseSummary],
    roadmap_is_legacy: bool,
) -> tuple[ModernizationOverviewFact, ...]:
    facts: list[ModernizationOverviewFact] = [
        ModernizationOverviewFact(
            label="Contributing assessment heads",
            value=str(len(contributing)),
            note="Entities retain their original assessment-head classification",
        ),
        ModernizationOverviewFact(
            label="Supporting findings",
            value=str(supporting_finding_count),
        ),
        ModernizationOverviewFact(
            label="Deterministic recommendations",
            value=str(supporting_recommendation_count),
        ),
        ModernizationOverviewFact(
            label="Priority Actions",
            value=str(priority_action_count),
            note=(
                "Absence of Priority Actions does not establish absence of "
                "modernization need"
                if priority_action_count == 0
                else "Canonical Priority Actions only"
            ),
        ),
        ModernizationOverviewFact(
            label="Roadmap initiatives",
            value=str(initiative_count),
            note=(
                "Legacy roadmap items have limited traceability"
                if roadmap_is_legacy
                else "Planning guidance, not a delivery commitment"
            ),
        ),
        ModernizationOverviewFact(
            label="Roadmap phases represented",
            value=str(len(phases)),
        ),
    ]
    return tuple(facts)


def _coverage_rows(
    *,
    contributing: Sequence[ModernizationContributingHead],
    supporting_finding_count: int,
    supporting_recommendation_count: int,
    priority_action_count: int,
    initiative_count: int,
    roadmap_report: RoadmapReportSection | None,
    roadmap_is_legacy: bool,
) -> tuple[ModernizationCoverageRow, ...]:
    rows: list[ModernizationCoverageRow] = [
        ModernizationCoverageRow(
            label="Contributing heads",
            status="available" if contributing else "none_reported",
            display=str(len(contributing)),
            note="Coverage depends on which assessment heads were enabled and supported",
        ),
        ModernizationCoverageRow(
            label="Supporting findings",
            status="available" if supporting_finding_count else "none_reported",
            display=str(supporting_finding_count),
            note=None,
        ),
        ModernizationCoverageRow(
            label="Supporting recommendations",
            status="available" if supporting_recommendation_count else "none_reported",
            display=str(supporting_recommendation_count),
            note=None,
        ),
        ModernizationCoverageRow(
            label="Priority Actions",
            status="available" if priority_action_count else "none_reported",
            display=str(priority_action_count),
            note=(
                None
                if priority_action_count
                else "Zero Priority Actions do not mean no modernization need"
            ),
        ),
        ModernizationCoverageRow(
            label="Roadmap initiatives",
            status=(
                "legacy"
                if roadmap_is_legacy
                else ("available" if initiative_count else "none_reported")
            ),
            display=str(initiative_count),
            note=(
                "Legacy roadmap contributors have limited traceability"
                if roadmap_is_legacy
                else None
            ),
        ),
    ]
    if roadmap_report is not None:
        status = str(getattr(roadmap_report, "status", "") or "").strip()
        if status:
            rows.append(
                ModernizationCoverageRow(
                    label="Roadmap status",
                    status="available",
                    display=status,
                    note=None,
                )
            )
    return tuple(rows)


def _limitations(
    *,
    roadmap_report: RoadmapReportSection | None,
    priority_action_count: int,
    contributing: Sequence[ModernizationContributingHead],
    roadmap_is_legacy: bool,
) -> tuple[str, ...]:
    notes: list[str] = list(_BASE_LIMITATIONS)
    if roadmap_report is not None:
        for item in getattr(roadmap_report, "limitations", ()) or ():
            summary = str(item or "").strip()
            if not summary:
                continue
            if _contains_soft_claim(summary):
                continue
            notes.append(summary)
        for item in getattr(roadmap_report, "assumptions", ()) or ():
            summary = str(item or "").strip()
            if not summary or _contains_soft_claim(summary):
                continue
            notes.append(summary)
    if not contributing:
        notes.append(
            "Coverage depends on which assessment heads were enabled and supported."
        )
    if priority_action_count == 0:
        notes.append(_EMPTY_ACTIONS_MESSAGE)
    if roadmap_is_legacy:
        notes.append(
            "Legacy roadmap items are visibly marked and may have limited traceability."
        )

    seen: set[str] = set()
    out: list[str] = []
    for note in notes:
        key = note.strip()
        if not key or key.lower() in seen:
            continue
        seen.add(key.lower())
        out.append(key)
    return tuple(out)


def _confidence(
    *,
    priority_actions: Sequence[Any],
    findings: Sequence[Any],
    supporting_finding_ids: set[str],
    limitations: Sequence[str],
    priority_action_count: int,
) -> tuple[str, str]:
    ranks: list[int] = []
    for item in priority_actions:
        completeness = str(
            getattr(item, "evidence_completeness", "") or ""
        ).strip().lower()
        if completeness == "complete":
            ranks.append(3)
        elif completeness in {"partial", "incomplete"}:
            ranks.append(1)
        elif completeness == "moderate":
            ranks.append(2)
        elif completeness in {"legacy", "unavailable", "unknown", ""}:
            ranks.append(0)
        else:
            ranks.append(_CONFIDENCE_RANK.get(completeness, 0))

    finding_by_id = {
        str(getattr(item, "finding_id", "") or ""): item for item in findings
    }
    for fid in supporting_finding_ids:
        item = finding_by_id.get(fid)
        if item is None:
            ranks.append(0)
            continue
        direct = str(getattr(item, "confidence", "") or "").strip().lower()
        if direct in _CONFIDENCE_RANK:
            mapped = _CONFIDENCE_RANK[direct]
            ranks.append(3 if mapped == 3 else mapped)
            continue
        completeness = str(
            getattr(item, "evidence_completeness", "") or ""
        ).strip().lower()
        if completeness == "complete":
            ranks.append(3)
        elif completeness in {"partial", "incomplete"}:
            ranks.append(1)
        elif completeness == "moderate":
            ranks.append(2)
        else:
            ranks.append(0)

    if priority_action_count == 0:
        ranks.append(0)
    if limitations and priority_action_count == 0:
        ranks.append(0)

    if not ranks:
        return "unavailable", "Confidence unavailable"
    weakest = min(ranks)
    if weakest >= 3:
        return "high", "High confidence"
    if weakest == 2:
        return "moderate", "Moderate confidence"
    if weakest == 1:
        return "limited", "Limited confidence"
    return "unavailable", "Confidence unavailable"


def _status(
    *,
    priority_action_count: int,
    initiative_count: int,
    contributing: Sequence[ModernizationContributingHead],
    supporting_finding_count: int,
) -> tuple[str, str]:
    if priority_action_count or initiative_count:
        return "partially_assessed", "Partially assessed"
    if contributing or supporting_finding_count:
        return "partially_assessed", "Partially assessed"
    return "not_available", "Not available"
