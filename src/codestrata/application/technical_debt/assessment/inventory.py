"""Technical Debt complexity inventory and hotspot projection (Phase 4.3.4A)."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import PurePosixPath

from codestrata.application.evidence.language.adapters import classify_source_path
from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.domain.findings import Finding
from codestrata.domain.technical_debt.assessment.enums import TechnicalDebtSourceRole
from codestrata.domain.technical_debt.assessment.identifiers import build_hotspot_id
from codestrata.domain.technical_debt.assessment.models import (
    TechnicalDebtFindingInventory,
    TechnicalDebtFindingReference,
    TechnicalDebtHotspot,
    TechnicalDebtHotspotInventory,
    TechnicalDebtObservedMetric,
    TechnicalDebtRoleInventory,
)
from codestrata.domain.technical_debt.taxonomy import TechnicalDebtCategory

_SEVERITY_RANK = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "informational": 1,
}


def map_source_role(
    classification: str | None,
    *,
    path: str | None = None,
) -> TechnicalDebtSourceRole:
    """Map evidence classification / path heuristics to inventory source roles."""

    raw = (classification or "").strip().lower()
    if raw in {"source", "production"}:
        return TechnicalDebtSourceRole.PRODUCTION
    if raw in {"test", "fixture"}:
        return TechnicalDebtSourceRole.TEST
    if raw in {"generated", "unknown", "example", "vendor", "documentation", "docs"}:
        # Non-production content must not drive the primary production inventory.
        return TechnicalDebtSourceRole.UNKNOWN
    if path:
        classified = classify_source_path(path)
        if classified is SourceClassification.SOURCE:
            return TechnicalDebtSourceRole.PRODUCTION
        if classified in {SourceClassification.TEST, SourceClassification.FIXTURE}:
            return TechnicalDebtSourceRole.TEST
        return TechnicalDebtSourceRole.UNKNOWN
    return TechnicalDebtSourceRole.UNKNOWN


def package_from_path(path: str | None) -> str:
    if not path:
        return "(unknown)"
    normalized = path.replace("\\", "/")
    parent = str(PurePosixPath(normalized).parent)
    return parent if parent not in {"", "."} else "(root)"


def source_unit_from_finding(finding: Finding, *, path: str | None) -> str:
    meta_unit = finding.metadata.get("subject_keys", "")
    parts = [part.strip() for part in str(meta_unit).split(",") if part.strip()]
    # Prefer symbol-like keys (not the path itself).
    for part in parts:
        if path and part.replace("\\", "/") == path.replace("\\", "/"):
            continue
        return part
    if finding.evidence and finding.evidence[0].source_id:
        return finding.evidence[0].source_id
    return path or "repository"


def enrich_finding_reference(finding: Finding) -> TechnicalDebtFindingReference:
    taxonomy = finding.metadata.get("taxonomy_id", TechnicalDebtCategory.COMPLEXITY.value)
    confidence = finding.metadata.get("confidence", "medium")
    dimensions = tuple(
        part.strip()
        for part in finding.metadata.get("assessment_dimensions", "technical-debt").split(",")
        if part.strip()
    ) or ("technical-debt",)
    scope = tuple(
        part.strip()
        for part in finding.metadata.get("subject_keys", "").split(",")
        if part.strip()
    )
    path = finding.metadata.get("path")
    if not path and finding.evidence:
        path = finding.evidence[0].path
    if not path and scope:
        path = next(
            (
                item
                for item in scope
                if "/" in item or item.endswith((".py", ".java"))
            ),
            None,
        )
    path = path.replace("\\", "/") if path else None
    source_unit = source_unit_from_finding(finding, path=path)
    if not scope:
        scope = tuple(item for item in (path, source_unit) if item)
    classification = finding.metadata.get("classification")
    source_role = map_source_role(classification, path=path)
    language = finding.metadata.get("language")
    package = finding.metadata.get("package") or package_from_path(path)
    return TechnicalDebtFindingReference(
        finding_id=finding.id,
        rule_id=finding.rule_id,
        title=finding.title,
        debt_category=TechnicalDebtCategory.COMPLEXITY,
        affected_scope=scope,
        severity=finding.severity.value,
        confidence=str(confidence),
        evidence_count=len(finding.evidence),
        taxonomy_ids=(str(taxonomy),),
        assessment_dimensions=dimensions,
        source_role=source_role,
        language=language,
        path=path,
        package=package,
        source_unit=source_unit,
        metric=finding.metadata.get("metric"),
        metric_value=finding.metadata.get("value"),
        threshold=finding.metadata.get("threshold"),
        severity_basis=finding.metadata.get("severity_basis"),
    )


def build_finding_references(
    findings: Sequence[Finding],
) -> tuple[TechnicalDebtFindingReference, ...]:
    refs = [enrich_finding_reference(finding) for finding in findings]
    return tuple(sorted(refs, key=lambda item: (item.rule_id, item.finding_id)))


def _role_inventory(
    role: TechnicalDebtSourceRole,
    refs: Sequence[TechnicalDebtFindingReference],
) -> TechnicalDebtRoleInventory:
    subset = [item for item in refs if item.source_role is role]
    rule_counts = Counter(item.rule_id for item in subset)
    severity_counts = Counter(item.severity for item in subset)
    files = {item.path for item in subset if item.path}
    units = {(item.path or "", item.source_unit or "") for item in subset}
    return TechnicalDebtRoleInventory(
        source_role=role,
        finding_ids=tuple(item.finding_id for item in subset),
        finding_count=len(subset),
        unique_file_count=len(files),
        unique_source_unit_count=len(units),
        rule_counts=dict(sorted(rule_counts.items())),
        severity_counts=dict(sorted(severity_counts.items())),
    )


def build_finding_inventory(
    refs: Sequence[TechnicalDebtFindingReference],
) -> TechnicalDebtFindingInventory:
    production = _role_inventory(TechnicalDebtSourceRole.PRODUCTION, refs)
    test = _role_inventory(TechnicalDebtSourceRole.TEST, refs)
    unknown = _role_inventory(TechnicalDebtSourceRole.UNKNOWN, refs)
    unit_rules: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for item in refs:
        key = (
            item.source_role.value,
            item.path or "",
            item.source_unit or "",
        )
        unit_rules[key].add(item.rule_id)
    overlapping = sum(1 for rules in unit_rules.values() if len(rules) > 1)
    return TechnicalDebtFindingInventory(
        primary_source_role=TechnicalDebtSourceRole.PRODUCTION,
        production=production,
        test=test,
        unknown=unknown,
        total_finding_count=len(refs),
        overlapping_source_unit_count=overlapping,
    )


def _highest_severity(severities: Sequence[str]) -> str:
    if not severities:
        return "informational"
    return max(severities, key=lambda item: _SEVERITY_RANK.get(item, 0))


def _hotspot_sort_key(hotspot: TechnicalDebtHotspot) -> tuple[object, ...]:
    return (
        -_SEVERITY_RANK.get(hotspot.highest_severity, 0),
        -hotspot.finding_count,
        hotspot.path,
        hotspot.source_unit,
        hotspot.hotspot_id,
    )


def build_hotspots(
    refs: Sequence[TechnicalDebtFindingReference],
) -> tuple[TechnicalDebtHotspot, ...]:
    groups: dict[tuple[str, str, str, str], list[TechnicalDebtFindingReference]] = defaultdict(list)
    for item in refs:
        path = item.path or "(unknown)"
        unit = item.source_unit or "(unknown)"
        language = item.language or "unknown"
        key = (item.source_role.value, path, unit, language)
        groups[key].append(item)

    hotspots: list[TechnicalDebtHotspot] = []
    for (role_value, path, unit, language), items in groups.items():
        role = TechnicalDebtSourceRole(role_value)
        finding_ids = tuple(sorted(item.finding_id for item in items))
        rule_ids = tuple(sorted({item.rule_id for item in items}))
        metrics = tuple(
            sorted(
                (
                    TechnicalDebtObservedMetric(
                        metric=item.metric or "unknown",
                        value=item.metric_value or "unknown",
                        threshold=item.threshold,
                        rule_id=item.rule_id,
                        finding_id=item.finding_id,
                    )
                    for item in items
                ),
                key=lambda metric: (metric.rule_id, metric.metric, metric.finding_id),
            )
        )
        hotspot = TechnicalDebtHotspot(
            hotspot_id=build_hotspot_id(path=path, source_unit=unit, source_role=role.value),
            source_unit_key=f"{path}|{unit}",
            path=path,
            package=package_from_path(path),
            source_unit=unit,
            source_role=role,
            language=language,
            finding_ids=finding_ids,
            rule_ids=rule_ids,
            finding_count=len(finding_ids),
            highest_severity=_highest_severity([item.severity for item in items]),
            observed_metrics=metrics,
        )
        hotspots.append(hotspot)
    return tuple(sorted(hotspots, key=_hotspot_sort_key))


def build_hotspot_inventory(
    refs: Sequence[TechnicalDebtFindingReference],
) -> TechnicalDebtHotspotInventory:
    hotspots = build_hotspots(refs)
    return TechnicalDebtHotspotInventory(
        production=tuple(
            item for item in hotspots if item.source_role is TechnicalDebtSourceRole.PRODUCTION
        ),
        test=tuple(
            item for item in hotspots if item.source_role is TechnicalDebtSourceRole.TEST
        ),
        unknown=tuple(
            item for item in hotspots if item.source_role is TechnicalDebtSourceRole.UNKNOWN
        ),
    )


def parse_failure_paths(diagnostics: Sequence[str]) -> tuple[str, ...]:
    """Extract relative paths from complexity parse-failure diagnostics."""

    paths: list[str] = []
    for item in diagnostics:
        text = str(item).strip()
        if not text:
            continue
        # Formats: python_syntax_error:path:msg  |  java_parse_error:path:...
        if ":" not in text:
            continue
        kind, rest = text.split(":", 1)
        if "syntax_error" not in kind and "parse_error" not in kind and "failed" not in kind:
            continue
        path = rest.split(":", 1)[0].strip().replace("\\", "/")
        if path:
            paths.append(path)
    return tuple(sorted(set(paths)))


def material_production_parse_failures(diagnostics: Sequence[str]) -> int:
    """Count parse failures that affect production sources.

    Test/fixture/generated parse failures remain diagnostics and coverage
    signals but do not degrade section status to partially_succeeded.
    Unsupported languages and unavailable optional metrics never appear here.
    """

    count = 0
    for path in parse_failure_paths(diagnostics):
        if map_source_role(None, path=path) is TechnicalDebtSourceRole.PRODUCTION:
            count += 1
    return count
