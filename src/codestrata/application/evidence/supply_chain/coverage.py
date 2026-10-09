"""M12 resolution coverage using the ratified same-scope formula."""

from __future__ import annotations

from collections import defaultdict

from codestrata.application.evidence.supply_chain.models import (
    DeclarationRecord,
    HygieneCounts,
    MetricStatusName,
    ResolutionOccurrence,
    ScopeCoverage,
)
from codestrata.domain.contracts.enums import MetricStatus
from codestrata.domain.contracts.formulas import m12_resolution_coverage


def compute_scope_coverage(
    declarations: tuple[DeclarationRecord, ...],
    occurrences: tuple[ResolutionOccurrence, ...],
    *,
    unknown_ecosystem: bool = False,
) -> tuple[ScopeCoverage, ...]:
    """Coverage is per manifest/workspace/environment scope.

    Multiple resolved versions or transitive packages cannot raise a
    declaration's contribution above one. A declaration is fully resolved only
    when every required context for that declaration has exactly one exact
    lock version.
    """

    if unknown_ecosystem and not declarations:
        return (
            ScopeCoverage(
                scope_id="unknown",
                manifest_path="",
                status=MetricStatusName.UNKNOWN,
                reason="unknown_denominator",
            ),
        )

    grouped: dict[str, list[DeclarationRecord]] = defaultdict(list)
    for item in declarations:
        grouped[item.scope_id].append(item)
    if not grouped:
        return (
            ScopeCoverage(
                scope_id="empty",
                manifest_path="",
                status=MetricStatusName.NOT_APPLICABLE,
                numerator=0,
                denominator=0,
                reason="zero_eligible",
            ),
        )

    occ_by_decl: dict[str, list[ResolutionOccurrence]] = defaultdict(list)
    for occurrence in occurrences:
        if occurrence.declaration_id:
            occ_by_decl[occurrence.declaration_id].append(occurrence)

    scopes: list[ScopeCoverage] = []
    for scope_id, items in sorted(grouped.items(), key=lambda pair: pair[0]):
        eligible = [item for item in items if item.eligible]
        eligible_ids = list(dict.fromkeys(item.declaration_id for item in eligible))
        resolved_ids: list[str] = []
        for declaration_id in eligible_ids:
            related = occ_by_decl.get(declaration_id, [])
            exact_versions = {
                item.resolved_version
                for item in related
                if item.exact and item.resolved_version and not item.unsupported_scheme
            }
            # One declaration / many versions is not complete.
            if len(exact_versions) == 1:
                resolved_ids.append(declaration_id)
        computation = m12_resolution_coverage(eligible_ids, resolved_ids)
        missing = computation.status is MetricStatus.VALUE and computation.numerator == 0
        if computation.status is MetricStatus.NOT_APPLICABLE:
            missing = False
        occurrence_count = sum(len(occ_by_decl.get(item_id, ())) for item_id in eligible_ids)
        transitive = sum(
            1
            for item_id in eligible_ids
            for item in occ_by_decl.get(item_id, ())
            if not item.direct
        )
        extra_transitive = sum(
            1
            for item in occurrences
            if item.ecosystem == (eligible[0].ecosystem if eligible else "")
            and parent_lock_matches(item.lock_path, eligible[0].manifest_path if eligible else "")
            and not item.direct
            and item.declaration_id is None
        )
        scopes.append(
            ScopeCoverage(
                scope_id=scope_id,
                manifest_path=items[0].manifest_path,
                environment=items[0].environment,
                status=MetricStatusName(computation.status.value),
                numerator=computation.numerator,
                denominator=computation.denominator,
                serialized=computation.serialized,
                reason=computation.reason,
                missing_resolution=bool(missing),
                fully_resolved_ids=tuple(resolved_ids),
                eligible_ids=tuple(eligible_ids),
                occurrence_count=occurrence_count + extra_transitive,
                transitive_count=transitive + extra_transitive,
            )
        )
    return tuple(scopes)


def parent_lock_matches(lock_path: str, manifest_path: str) -> bool:
    from codestrata.application.evidence.supply_chain.locks import parent_dir

    return parent_dir(lock_path) == parent_dir(manifest_path)


def coverage_not_above_one(scope: ScopeCoverage) -> bool:
    if scope.numerator is None or scope.denominator is None:
        return True
    if scope.denominator == 0:
        return True
    return scope.numerator <= scope.denominator


def count_hygiene(declarations: tuple[DeclarationRecord, ...]) -> HygieneCounts:
    conflict_keys = {
        (item.scope_id, item.package_name.lower()) for item in declarations if item.is_conflict
    }
    duplicate_keys = {
        (item.scope_id, item.package_name.lower()) for item in declarations if item.is_duplicate
    }
    return HygieneCounts(
        mutable=sum(1 for item in declarations if item.is_mutable),
        unbounded=sum(1 for item in declarations if item.is_unbounded),
        unresolved=sum(1 for item in declarations if item.is_unresolved_expression),
        duplicate=len(duplicate_keys),
        conflicting=len(conflict_keys),
    )
