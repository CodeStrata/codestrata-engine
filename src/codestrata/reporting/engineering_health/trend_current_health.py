"""Current-health projection for a trend slot.

Uses the same assessment-head contract as the baseline report. Comparison
lifecycle stays on AnalysisResult identities and is not counted here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codestrata.application.assessment_heads.coverage import build_assessment_coverage_map
from codestrata.reporting.engineering_health.projection import (
    apply_engineering_health_projection,
    overlay_headline_evidence_coverage,
)
from codestrata.reporting.html_v2.assessment_head_grouping import (
    build_assessment_head_sections,
)
from codestrata.reporting.html_v2.assessment_heads import (
    ENGINEERING_HEALTH_HEADLINES,
    assessment_head_outcome_family,
    engineering_health_outcome_title,
)
from codestrata.reporting.html_v2.models import AssessmentHeadSectionView, FindingView
from codestrata.reporting.prioritization import BUCKET_LABELS

_HEAD_PACK_FILES: dict[str, str] = {
    "architecture": "architecture.json",
    "technical_debt": "technical-debt.json",
    "dependency": "dependencies.json",
    "security": "security.json",
    "testing": "testing.json",
    "cloud": "cloud.json",
    "ai_readiness": "ai.json",
}

# family, title, label, finding count, coverage status
HeadlineOutcome = tuple[str, str, str, int, str | None]


def project_slot_headline_outcomes(slot_directory: Path) -> tuple[HeadlineOutcome, ...] | None:
    """Project the four baseline headlines from customer findings and head packs.

    Returns None when the customer finding record is absent. Callers must
    show UNKNOWN rather than counting AnalysisResult findings.
    """

    findings = _load_findings(slot_directory / "findings.json")
    if findings is None:
        return None
    packs = _load_packs(slot_directory / "heads")
    head_rows, _unclassified, _recommendations = build_assessment_head_sections(
        findings=findings,
        recommendations=(),
        priority_actions=(),
        technologies_present=False,
        architecture_present="architecture" in packs,
        technical_debt_present="technical_debt" in packs,
        dependency_present="dependency" in packs,
        security_present="security" in packs,
        cloud_present="cloud" in packs,
        ai_readiness_present="ai_readiness" in packs,
        testing_present="testing" in packs,
    )
    sections = tuple(AssessmentHeadSectionView(**row) for row in head_rows)
    coverage = build_assessment_coverage_map(pack_sections=packs)
    attached = tuple(
        section.model_copy(update={"assessment_coverage": coverage.get(section.head)})
        for section in sections
    )
    overlaid = overlay_headline_evidence_coverage(
        attached,
        metadata=_analysis_metadata(slot_directory),
        architecture_report=_architecture_report(packs.get("architecture")),
    )
    projected = apply_engineering_health_projection(overlaid)
    by_head = {str(section.head): section for section in projected}
    outcomes: list[HeadlineOutcome] = []
    for head in ENGINEERING_HEALTH_HEADLINES:
        section = by_head.get(head.value)
        if section is None:
            continue
        coverage = section.assessment_coverage
        payload = coverage if isinstance(coverage, dict) else {}
        outcomes.append(
            (
                assessment_head_outcome_family(head) or head.value,
                engineering_health_outcome_title(head),
                str(section.display_label or "UNKNOWN"),
                int(section.findings_count),
                str(payload.get("status") or "") or None,
            )
        )
    return tuple(outcomes)


_HORIZON_ORDER = {"immediate": 0, "near_term": 1, "future": 2}


def load_priority_actions(slot_directory: Path) -> tuple[tuple[str, str, str, str], ...] | None:
    """Return supplied HEAD recommendations as title, priority, horizon, category.

    ``None`` means the recommendation record is absent. An empty tuple means
    the record was supplied with no actions. Order follows the existing
    presentation horizon, then the supplied record order. Scores are not copied.
    """

    path = slot_directory / "recommendations.json"
    if not path.is_file():
        return None
    payload = _read_object(path)
    if payload is None:
        return None
    raw = payload.get("recommendations")
    if not isinstance(raw, list):
        return ()
    ordered: list[tuple[int, int, tuple[str, str, str, str]]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        bucket = str(item.get("presentation_bucket") or "").strip().lower()
        horizon = BUCKET_LABELS.get(bucket, "UNKNOWN")
        priority = str(item.get("priority") or "").strip() or "UNKNOWN"
        category = str(item.get("category") or "").strip() or "UNKNOWN"
        ordered.append(
            (
                _HORIZON_ORDER.get(bucket, 9),
                index,
                (title, priority, horizon, category),
            )
        )
    ordered.sort(key=lambda row: (row[0], row[1]))
    return tuple(row[2] for row in ordered)


def slot_file_populations(
    slot_directory: Path,
    inventory_paths: list[Any] | None,
) -> tuple[int | None, int | None]:
    """Return committed-scope inventory and scan-admitted assessed file counts.

    These are different populations. Neither count is inferred from the other.
    """

    inventory = len(inventory_paths) if isinstance(inventory_paths, list) else None
    assessed = _included_files(slot_directory / "scan-boundary-diagnostics.json")
    if assessed is None:
        assessed = _repository_total_files(slot_directory / "analysis-result.json")
    return inventory, assessed


def _load_findings(path: Path) -> tuple[FindingView, ...] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    raw = payload.get("findings") if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        return None
    findings: list[FindingView] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        finding_id = str(item.get("finding_id") or item.get("id") or "").strip()
        if not finding_id:
            continue
        findings.append(
            FindingView(
                finding_id=finding_id,
                rule_id=str(item.get("rule_id") or ""),
                title=str(item.get("title") or finding_id),
                description=str(item.get("description") or item.get("title") or finding_id),
                severity=str(item.get("severity") or "info"),
                category=str(item.get("category") or ""),
            )
        )
    return tuple(findings)


def _load_packs(heads: Path) -> dict[str, dict[str, Any]]:
    packs: dict[str, dict[str, Any]] = {}
    for pack_id, filename in _HEAD_PACK_FILES.items():
        path = heads / filename
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict):
            packs[pack_id] = payload
    return packs


def _analysis_metadata(slot_directory: Path) -> dict[str, Any]:
    path = slot_directory / "analysis-result.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    metadata = payload.get("metadata") if isinstance(payload, dict) else None
    return dict(metadata) if isinstance(metadata, dict) else {}


class _ArchitectureReport:
    """Attribute view used by architecture evidence sufficiency."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.status = payload.get("status")
        self.conclusions = payload.get("conclusions") or ()


def _architecture_report(payload: dict[str, Any] | None) -> _ArchitectureReport | None:
    if not isinstance(payload, dict):
        return None
    return _ArchitectureReport(payload)


def _included_files(path: Path) -> int | None:
    payload = _read_object(path)
    value = payload.get("included_files") if payload else None
    return value if isinstance(value, int) else None


def _repository_total_files(path: Path) -> int | None:
    payload = _read_object(path)
    repository = payload.get("repository") if payload else None
    if not isinstance(repository, dict):
        return None
    value = repository.get("total_files")
    return value if isinstance(value, int) else None


def _read_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None
