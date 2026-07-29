"""Aggregate Dependency Evidence bundles."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from codestrata.domain.evidence.dependency.enums import DependencyParseStatus
from codestrata.domain.evidence.dependency.models import (
    AggregatedDependencyEvidence,
    DependencyEvidenceBundle,
    DependencyEvidenceCoverage,
)


def _fingerprint(
    *,
    repository_id: str,
    bundles: Sequence[DependencyEvidenceBundle],
) -> str:
    parts = [repository_id]
    for bundle in sorted(bundles, key=lambda item: item.provider_id):
        parts.append(bundle.provider_id)
        for manifest in bundle.manifests:
            parts.append(manifest.evidence_id)
        for declaration in bundle.declarations:
            parts.append(declaration.evidence_id)
    payload = "\n".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _merge_coverage(
    bundles: Sequence[DependencyEvidenceBundle],
) -> DependencyEvidenceCoverage:
    return DependencyEvidenceCoverage(
        manifests_discovered=sum(item.coverage.manifests_discovered for item in bundles),
        manifests_supported=sum(item.coverage.manifests_supported for item in bundles),
        manifests_parsed=sum(item.coverage.manifests_parsed for item in bundles),
        manifests_partially_parsed=sum(
            item.coverage.manifests_partially_parsed for item in bundles
        ),
        manifests_failed=sum(item.coverage.manifests_failed for item in bundles),
        manifests_excluded=sum(item.coverage.manifests_excluded for item in bundles),
        declarations_collected=sum(
            item.coverage.declarations_collected for item in bundles
        ),
        unsupported_construct_count=sum(
            item.coverage.unsupported_construct_count for item in bundles
        ),
        unresolved_expression_count=sum(
            item.coverage.unresolved_expression_count for item in bundles
        ),
    )


def _aggregate_status(
    bundles: Sequence[DependencyEvidenceBundle],
    coverage: DependencyEvidenceCoverage,
) -> DependencyParseStatus:
    if not bundles or coverage.manifests_supported == 0:
        return DependencyParseStatus.NOT_APPLICABLE
    statuses = {bundle.status for bundle in bundles}
    if statuses == {DependencyParseStatus.FAILED}:
        return DependencyParseStatus.FAILED
    if (
        DependencyParseStatus.PARTIALLY_SUCCEEDED in statuses
        or DependencyParseStatus.FAILED in statuses
        or coverage.unsupported_construct_count
        or coverage.unresolved_expression_count
    ):
        return DependencyParseStatus.PARTIALLY_SUCCEEDED
    if DependencyParseStatus.SUCCEEDED in statuses:
        return DependencyParseStatus.SUCCEEDED
    return DependencyParseStatus.NOT_APPLICABLE


def aggregate_dependency_bundles(
    *,
    repository_id: str,
    bundles: Sequence[DependencyEvidenceBundle],
) -> AggregatedDependencyEvidence:
    ordered_bundles = tuple(
        sorted(bundles, key=lambda item: (item.ecosystem.value, item.provider_id))
    )
    manifests = tuple(
        sorted(
            (manifest for bundle in ordered_bundles for manifest in bundle.manifests),
            key=lambda item: (item.path, item.evidence_id),
        )
    )
    declarations = tuple(
        sorted(
            (
                declaration
                for bundle in ordered_bundles
                for declaration in bundle.declarations
            ),
            key=lambda item: (
                item.source.path,
                item.source.line_start or 0,
                item.normalized_identity,
                item.declaration_kind.value,
                item.evidence_id,
            ),
        )
    )
    coverage = _merge_coverage(ordered_bundles)
    diagnostics = tuple(
        sorted(
            {
                diagnostic
                for bundle in ordered_bundles
                for diagnostic in bundle.diagnostics
            }
        )
    )
    return AggregatedDependencyEvidence(
        repository_id=repository_id,
        status=_aggregate_status(ordered_bundles, coverage),
        bundles=ordered_bundles,
        manifests=manifests,
        declarations=declarations,
        coverage=coverage,
        contributing_provider_ids=tuple(
            sorted({bundle.provider_id for bundle in ordered_bundles})
        ),
        diagnostics=diagnostics,
        evidence_fingerprint=_fingerprint(
            repository_id=repository_id, bundles=ordered_bundles
        ),
    )
