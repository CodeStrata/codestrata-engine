"""Dependency assessment inventory and hotspot projection (Phase 4.4.4)."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from collections.abc import Sequence

from codestrata.application.evidence.language.adapters import classify_source_path
from codestrata.domain.dependency.assessment.enums import DependencySourceRole
from codestrata.domain.dependency.assessment.identifiers import (
    build_hotspot_id,
    build_manifest_inventory_id,
)
from codestrata.domain.dependency.assessment.models import (
    DependencyAggregationInventory,
    DependencyCountBucket,
    DependencyDeclarationInventory,
    DependencyDiagnosticRecord,
    DependencyDiagnosticsSummary,
    DependencyEvidenceSummary,
    DependencyFindingInventory,
    DependencyFindingReference,
    DependencyHotspot,
    DependencyHotspotInventory,
    DependencyManifestInventory,
    DependencyManifestInventoryEntry,
    DependencyRoleDeclarationInventory,
    DependencyRoleFindingInventory,
)
from codestrata.domain.dependency.taxonomy import DependencyRole
from codestrata.domain.evidence.dependency.enums import (
    DependencyDeclarationKind,
    DependencyParseStatus,
    DependencyVersionResolutionStatus,
)
from codestrata.domain.evidence.dependency.identifiers import DEPENDENCY_EVIDENCE_SCHEMA_VERSION
from codestrata.domain.evidence.dependency.models import (
    AggregatedDependencyEvidence,
    DependencyDeclarationEvidence,
)
from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.domain.findings import Finding

_SEVERITY_RANK = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "informational": 1,
}

_ROLE_ORDER = {
    DependencySourceRole.PRODUCTION: 0,
    DependencySourceRole.TEST: 1,
    DependencySourceRole.UNKNOWN: 2,
}


def map_source_role(
    classification: str | SourceClassification | None,
    *,
    path: str | None = None,
) -> DependencySourceRole:
    """Map evidence classification / path heuristics to inventory source roles."""

    if isinstance(classification, SourceClassification):
        raw = classification.value
    else:
        raw = (classification or "").strip().lower()
    if raw in {"source", "production"}:
        return DependencySourceRole.PRODUCTION
    if raw == "test":
        return DependencySourceRole.TEST
    if raw in {"generated", "unknown"}:
        return DependencySourceRole.UNKNOWN
    if path:
        classified = classify_source_path(path)
        if classified is SourceClassification.SOURCE:
            return DependencySourceRole.PRODUCTION
        if classified is SourceClassification.TEST:
            return DependencySourceRole.TEST
        return DependencySourceRole.UNKNOWN
    return DependencySourceRole.UNKNOWN


def is_management_declaration(item: DependencyDeclarationEvidence) -> bool:
    return (
        item.is_dependency_management
        or item.declaration_kind is DependencyDeclarationKind.DEPENDENCY_MANAGEMENT
    )


def is_plugin_declaration(item: DependencyDeclarationEvidence) -> bool:
    return item.declaration_kind is DependencyDeclarationKind.PLUGIN


def is_active_declaration(item: DependencyDeclarationEvidence) -> bool:
    return not is_management_declaration(item) and not is_plugin_declaration(item)


def is_test_or_development(item: DependencyDeclarationEvidence) -> bool:
    return item.declaration_kind in {
        DependencyDeclarationKind.TEST,
        DependencyDeclarationKind.DEVELOPMENT,
    }


def enrich_finding_reference(finding: Finding) -> DependencyFindingReference:
    confidence = finding.metadata.get("confidence", "medium")
    path = finding.metadata.get("path")
    if not path and finding.evidence:
        path = finding.evidence[0].path
    path = path.replace("\\", "/") if path else None
    classification = finding.metadata.get("classification")
    source_role = map_source_role(classification, path=path)
    ids: list[str] = []
    meta_ids = finding.metadata.get("participating_evidence_ids", "")
    if meta_ids:
        ids.extend(part.strip() for part in meta_ids.split(",") if part.strip())
    if finding.metadata.get("evidence_id"):
        ids.append(finding.metadata["evidence_id"])
    for item in finding.evidence:
        if item.source_id:
            ids.append(item.source_id)
    evidence_ids = tuple(sorted(set(ids)))
    scope = tuple(item.path for item in finding.evidence if item.path) or tuple(
        part.strip()
        for part in finding.metadata.get("subject_keys", "").split(",")
        if part.strip()
    )
    return DependencyFindingReference(
        finding_id=finding.id,
        rule_id=finding.rule_id,
        title=finding.title,
        dependency_role=DependencyRole.UNKNOWN,
        source_role=source_role,
        affected_scope=scope,
        severity=finding.severity.value,
        confidence=str(confidence),
        status="visible",
        evidence_count=len(finding.evidence),
        suppression_state="unsuppressed",
        taxonomy_ids=(finding.metadata.get("taxonomy_id", "dependency.unknown"),),
        assessment_dimensions=("dependency",),
        path=path,
        ecosystem=finding.metadata.get("ecosystem"),
        normalized_identity=finding.metadata.get("normalized_identity"),
        evidence_ids=evidence_ids,
    )


def build_finding_references(
    findings: Sequence[Finding],
) -> tuple[DependencyFindingReference, ...]:
    refs = [enrich_finding_reference(finding) for finding in findings]
    return tuple(sorted(refs, key=lambda item: (item.rule_id, item.finding_id)))


def _role_finding_inventory(
    role: DependencySourceRole,
    refs: Sequence[DependencyFindingReference],
) -> DependencyRoleFindingInventory:
    subset = [item for item in refs if item.source_role is role]
    return DependencyRoleFindingInventory(
        source_role=role,
        finding_ids=tuple(item.finding_id for item in subset),
        finding_count=len(subset),
        unique_manifest_count=len({item.path for item in subset if item.path}),
        rule_counts=dict(sorted(Counter(item.rule_id for item in subset).items())),
        severity_counts=dict(
            sorted(Counter(item.severity for item in subset).items())
        ),
    )


def build_finding_inventory(
    refs: Sequence[DependencyFindingReference],
) -> DependencyFindingInventory:
    return DependencyFindingInventory(
        primary_source_role=DependencySourceRole.PRODUCTION,
        production=_role_finding_inventory(DependencySourceRole.PRODUCTION, refs),
        test=_role_finding_inventory(DependencySourceRole.TEST, refs),
        unknown=_role_finding_inventory(DependencySourceRole.UNKNOWN, refs),
        total_finding_count=len(refs),
    )


def _role_declaration_inventory(
    role: DependencySourceRole,
    declarations: Sequence[DependencyDeclarationEvidence],
) -> DependencyRoleDeclarationInventory:
    subset = [
        item
        for item in declarations
        if map_source_role(item.classification, path=item.source.path) is role
    ]
    return DependencyRoleDeclarationInventory(
        source_role=role,
        declaration_count=len(subset),
        active_declaration_count=sum(1 for item in subset if is_active_declaration(item)),
        dependency_management_count=sum(
            1 for item in subset if is_management_declaration(item)
        ),
        plugin_count=sum(1 for item in subset if is_plugin_declaration(item)),
        test_or_development_count=sum(
            1 for item in subset if is_test_or_development(item)
        ),
        local_or_editable_count=sum(
            1 for item in subset if item.is_local_path or item.is_editable
        ),
        kind_counts=dict(
            sorted(Counter(item.declaration_kind.value for item in subset).items())
        ),
        ecosystem_counts=dict(
            sorted(Counter(item.ecosystem.value for item in subset).items())
        ),
    )


def build_declaration_inventory(
    evidence: AggregatedDependencyEvidence | None,
) -> DependencyDeclarationInventory:
    declarations = evidence.declarations if evidence is not None else ()
    return DependencyDeclarationInventory(
        production=_role_declaration_inventory(
            DependencySourceRole.PRODUCTION, declarations
        ),
        test=_role_declaration_inventory(DependencySourceRole.TEST, declarations),
        unknown=_role_declaration_inventory(
            DependencySourceRole.UNKNOWN, declarations
        ),
        total_declaration_count=len(declarations),
    )


def build_evidence_summary(
    evidence: AggregatedDependencyEvidence | None,
) -> DependencyEvidenceSummary:
    if evidence is None:
        return DependencyEvidenceSummary()
    declarations = evidence.declarations
    role_counts = Counter(
        map_source_role(item.classification, path=item.source.path).value
        for item in declarations
    )
    unsupported_resolution = sum(
        1
        for item in declarations
        if item.version_resolution_status
        is DependencyVersionResolutionStatus.UNSUPPORTED_RESOLUTION
    )
    unsupported_messages: set[str] = set()
    for manifest in evidence.manifests:
        for item in (*manifest.unsupported_constructs, *manifest.diagnostics):
            if (
                "unsupported_version_resolution" in item
                or "version_resolution_unsupported" in item
            ):
                unsupported_messages.add(item)
    unsupported_resolution += len(unsupported_messages)
    proven = sum(
        1
        for item in declarations
        if item.version_resolution_status
        is DependencyVersionResolutionStatus.PROVEN_UNRESOLVED
    )
    return DependencyEvidenceSummary(
        schema_version=evidence.schema_version or DEPENDENCY_EVIDENCE_SCHEMA_VERSION,
        evidence_fingerprint=evidence.evidence_fingerprint,
        evidence_status=evidence.status.value,
        manifests_discovered=evidence.coverage.manifests_discovered,
        manifests_supported=evidence.coverage.manifests_supported,
        manifests_parsed=evidence.coverage.manifests_parsed,
        manifests_partially_parsed=evidence.coverage.manifests_partially_parsed,
        manifests_failed=evidence.coverage.manifests_failed,
        manifests_excluded=evidence.coverage.manifests_excluded,
        declarations_collected=evidence.coverage.declarations_collected,
        ecosystems=tuple(
            sorted({item.ecosystem.value for item in evidence.manifests})
            or sorted({item.ecosystem.value for item in declarations})
        ),
        unsupported_construct_count=evidence.coverage.unsupported_construct_count,
        proven_unresolved_count=proven,
        unsupported_resolution_count=unsupported_resolution,
        local_or_editable_count=sum(
            1 for item in declarations if item.is_local_path or item.is_editable
        ),
        production_declaration_count=role_counts.get(
            DependencySourceRole.PRODUCTION.value, 0
        ),
        test_declaration_count=role_counts.get(DependencySourceRole.TEST.value, 0),
        unknown_declaration_count=role_counts.get(
            DependencySourceRole.UNKNOWN.value, 0
        ),
    )


def _manifest_kind_counts(
    declarations: Sequence[DependencyDeclarationEvidence],
) -> dict[str, int]:
    return dict(
        sorted(Counter(item.declaration_kind.value for item in declarations).items())
    )


def build_manifest_inventory(
    *,
    evidence: AggregatedDependencyEvidence | None,
    finding_refs: Sequence[DependencyFindingReference],
) -> DependencyManifestInventory:
    if evidence is None:
        return DependencyManifestInventory()
    by_path: dict[str, list[DependencyDeclarationEvidence]] = defaultdict(list)
    for item in evidence.declarations:
        by_path[item.source.path].append(item)
    findings_by_path: dict[str, list[DependencyFindingReference]] = defaultdict(list)
    for ref in finding_refs:
        if ref.path:
            findings_by_path[ref.path].append(ref)

    entries: list[DependencyManifestInventoryEntry] = []
    for manifest in evidence.manifests:
        decls = by_path.get(manifest.path, [])
        findings = findings_by_path.get(manifest.path, [])
        role = map_source_role(manifest.classification, path=manifest.path)
        unsupported_resolution = len(
            {
                item
                for item in (*manifest.unsupported_constructs, *manifest.diagnostics)
                if "unsupported_version_resolution" in item
                or "version_resolution_unsupported" in item
            }
        )
        proven = sum(
            1
            for item in decls
            if item.version_resolution_status
            is DependencyVersionResolutionStatus.PROVEN_UNRESOLVED
        )
        diagnostics = tuple(
            sorted(
                {
                    *manifest.diagnostics,
                    *manifest.unsupported_constructs,
                    *manifest.unresolved_expressions,
                }
            )
        )
        entries.append(
            DependencyManifestInventoryEntry(
                manifest_inventory_id=build_manifest_inventory_id(
                    path=manifest.path, ecosystem=manifest.ecosystem.value
                ),
                path=manifest.path,
                source_role=role,
                ecosystem=manifest.ecosystem.value,
                manifest_type=manifest.manifest_type.value,
                parse_status=manifest.parse_status.value,
                evidence_id=manifest.evidence_id,
                declaration_count=len(decls),
                active_declaration_count=sum(
                    1 for item in decls if is_active_declaration(item)
                ),
                dependency_management_count=sum(
                    1 for item in decls if is_management_declaration(item)
                ),
                plugin_count=sum(1 for item in decls if is_plugin_declaration(item)),
                test_or_development_count=sum(
                    1 for item in decls if is_test_or_development(item)
                ),
                kind_counts=_manifest_kind_counts(decls),
                unsupported_construct_count=len(manifest.unsupported_constructs),
                proven_unresolved_count=proven,
                unsupported_resolution_count=unsupported_resolution,
                hygiene_finding_ids=tuple(
                    sorted({item.finding_id for item in findings})
                ),
                diagnostic_references=diagnostics,
            )
        )
    ordered = tuple(
        sorted(
            entries,
            key=lambda item: (
                _ROLE_ORDER.get(item.source_role, 9),
                item.path,
                item.manifest_inventory_id,
            ),
        )
    )
    return DependencyManifestInventory(entries=ordered)


def _buckets_from_counter(
    counter: Counter[str],
    *,
    prefix: str,
) -> tuple[DependencyCountBucket, ...]:
    return tuple(
        DependencyCountBucket(
            key=f"{prefix}:{key}",
            label=key,
            count=count,
        )
        for key, count in sorted(counter.items())
    )


def build_aggregation_inventory(
    evidence: AggregatedDependencyEvidence | None,
) -> DependencyAggregationInventory:
    if evidence is None:
        return DependencyAggregationInventory()
    declarations = evidence.declarations
    by_role: Counter[str] = Counter()
    by_ecosystem: Counter[str] = Counter()
    by_kind: Counter[str] = Counter()
    by_manifest_type: Counter[str] = Counter()
    by_resolution: Counter[str] = Counter()
    for item in declarations:
        role = map_source_role(item.classification, path=item.source.path)
        by_role[role.value] += 1
        by_ecosystem[item.ecosystem.value] += 1
        by_kind[item.declaration_kind.value] += 1
        by_manifest_type[item.manifest_type.value] += 1
        by_resolution[item.version_resolution_status.value] += 1
    return DependencyAggregationInventory(
        by_ecosystem=_buckets_from_counter(by_ecosystem, prefix="ecosystem"),
        by_manifest_type=_buckets_from_counter(
            by_manifest_type, prefix="manifest_type"
        ),
        by_declaration_kind=_buckets_from_counter(by_kind, prefix="kind"),
        by_source_role=_buckets_from_counter(by_role, prefix="source_role"),
        by_version_resolution_status=_buckets_from_counter(
            by_resolution, prefix="version_resolution"
        ),
    )


def _highest_severity(severities: Sequence[str]) -> str:
    if not severities:
        return "informational"
    return max(severities, key=lambda item: _SEVERITY_RANK.get(item, 0))


def _hotspot_sort_key(hotspot: DependencyHotspot) -> tuple[object, ...]:
    # Presentation ordering only — not a priority score.
    return (
        _ROLE_ORDER.get(hotspot.source_role, 9),
        -_SEVERITY_RANK.get(hotspot.highest_severity, 0),
        -len(hotspot.distinct_rule_ids),
        -hotspot.hygiene_finding_count,
        hotspot.path,
        hotspot.hotspot_id,
    )


def build_hotspot_inventory(
    *,
    manifest_inventory: DependencyManifestInventory,
    finding_refs: Sequence[DependencyFindingReference],
) -> DependencyHotspotInventory:
    findings_by_path: dict[str, list[DependencyFindingReference]] = defaultdict(list)
    for ref in finding_refs:
        if ref.path:
            findings_by_path[ref.path].append(ref)

    hotspots: list[DependencyHotspot] = []
    for entry in manifest_inventory.entries:
        findings = findings_by_path.get(entry.path, [])
        identities = tuple(
            sorted(
                {
                    item.normalized_identity
                    for item in findings
                    if item.normalized_identity
                }
            )
        )
        hotspots.append(
            DependencyHotspot(
                hotspot_id=build_hotspot_id(
                    path=entry.path, source_role=entry.source_role.value
                ),
                manifest_inventory_id=entry.manifest_inventory_id,
                path=entry.path,
                source_role=entry.source_role,
                ecosystem=entry.ecosystem,
                manifest_type=entry.manifest_type,
                declaration_count=entry.declaration_count,
                active_declaration_count=entry.active_declaration_count,
                dependency_management_count=entry.dependency_management_count,
                plugin_count=entry.plugin_count,
                hygiene_finding_count=len(entry.hygiene_finding_ids),
                distinct_rule_ids=tuple(sorted({item.rule_id for item in findings})),
                highest_severity=_highest_severity([item.severity for item in findings]),
                affected_package_identities=identities,
                finding_ids=entry.hygiene_finding_ids,
                diagnostics_count=len(entry.diagnostic_references),
                proven_unresolved_count=entry.proven_unresolved_count,
                unsupported_resolution_count=entry.unsupported_resolution_count,
            )
        )
    ordered = tuple(sorted(hotspots, key=_hotspot_sort_key))
    return DependencyHotspotInventory(
        production=tuple(
            item
            for item in ordered
            if item.source_role is DependencySourceRole.PRODUCTION
        ),
        test=tuple(
            item for item in ordered if item.source_role is DependencySourceRole.TEST
        ),
        unknown=tuple(
            item
            for item in ordered
            if item.source_role is DependencySourceRole.UNKNOWN
        ),
    )


def _diagnostic_id(*, code: str, path: str, message: str) -> str:
    payload = f"{code}|{path}|{message}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"dep-diagnostic:{digest}"


def _classify_diagnostic_code(text: str) -> str:
    lowered = text.lower()
    if "unsupported_version_resolution" in lowered or (
        "version_resolution_unsupported" in lowered
    ):
        return "unsupported_gradle_resolution"
    if ":dynamic:" in lowered:
        return "unsupported_dynamic_gradle"
    if "parent_not_fetched" in lowered:
        return "maven_parent_not_fetched"
    if "pluginmanagement" in lowered:
        return "maven_plugin_management"
    if "directive:" in lowered or "index-url" in lowered:
        return "requirements_directive_not_executed"
    if "parse_error" in lowered or "syntax" in lowered:
        return "malformed_manifest"
    if "proven" in lowered or "${" in text:
        return "unresolved_expression"
    return "other"


def build_diagnostics_summary(
    evidence: AggregatedDependencyEvidence | None,
    *,
    extra_diagnostics: Sequence[str] = (),
) -> DependencyDiagnosticsSummary:
    records: list[DependencyDiagnosticRecord] = []
    if evidence is not None:
        for manifest in evidence.manifests:
            role = map_source_role(manifest.classification, path=manifest.path)
            for message in (
                *manifest.diagnostics,
                *manifest.unsupported_constructs,
                *manifest.unresolved_expressions,
            ):
                code = _classify_diagnostic_code(message)
                records.append(
                    DependencyDiagnosticRecord(
                        diagnostic_id=_diagnostic_id(
                            code=code, path=manifest.path, message=message
                        ),
                        diagnostic_code=code,
                        message=message,
                        path=manifest.path,
                        source_role=role,
                        ecosystem=manifest.ecosystem.value,
                    )
                )
    for message in extra_diagnostics:
        text = str(message).strip()
        if not text:
            continue
        code = _classify_diagnostic_code(text)
        records.append(
            DependencyDiagnosticRecord(
                diagnostic_id=_diagnostic_id(code=code, path="", message=text),
                diagnostic_code=code,
                message=text,
                path=None,
                source_role=DependencySourceRole.UNKNOWN,
            )
        )
    unique = {
        item.diagnostic_id: item
        for item in sorted(
            records,
            key=lambda item: (
                item.path or "",
                item.diagnostic_code,
                item.message,
                item.diagnostic_id,
            ),
        )
    }
    ordered = tuple(unique.values())
    return DependencyDiagnosticsSummary(
        records=ordered,
        production_count=sum(
            1
            for item in ordered
            if item.source_role is DependencySourceRole.PRODUCTION
        ),
        test_count=sum(
            1 for item in ordered if item.source_role is DependencySourceRole.TEST
        ),
        unknown_count=sum(
            1
            for item in ordered
            if item.source_role is DependencySourceRole.UNKNOWN
        ),
    )


def parse_failure_counts(
    evidence: AggregatedDependencyEvidence | None,
) -> tuple[int, int, int]:
    """Return (production, test, unknown) failed-manifest counts."""

    if evidence is None:
        return 0, 0, 0
    production = test = unknown = 0
    for manifest in evidence.manifests:
        if manifest.parse_status is not DependencyParseStatus.FAILED:
            continue
        role = map_source_role(manifest.classification, path=manifest.path)
        if role is DependencySourceRole.PRODUCTION:
            production += 1
        elif role is DependencySourceRole.TEST:
            test += 1
        else:
            unknown += 1
    return production, test, unknown


def production_manifests_usable(
    evidence: AggregatedDependencyEvidence | None,
) -> bool:
    if evidence is None:
        return False
    production = [
        item
        for item in evidence.manifests
        if map_source_role(item.classification, path=item.path)
        is DependencySourceRole.PRODUCTION
    ]
    if not production:
        # No production manifests — usable only if any supported manifests exist
        # for inventory transparency; primary view stays empty.
        return evidence.coverage.manifests_supported > 0
    return any(
        item.parse_status
        in {
            DependencyParseStatus.SUCCEEDED,
            DependencyParseStatus.PARTIALLY_SUCCEEDED,
        }
        for item in production
    )
