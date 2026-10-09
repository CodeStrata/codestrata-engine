"""Collect declarations and overlay lock resolution without installing packages."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from codestrata.application.evidence.dependency.service import DependencyEvidenceService
from codestrata.application.evidence.inventory.npm import collect_npm_facts
from codestrata.application.evidence.supply_chain.locks import parent_dir, parse_lockfiles
from codestrata.application.evidence.supply_chain.models import (
    DeclarationRecord,
    ResolutionOccurrence,
)
from codestrata.application.rules.dependency.helpers import (
    has_proven_unresolved_version,
    is_exact_version,
    is_local_or_direct_reference,
    is_mutable_version,
)
from codestrata.config.settings import DependencyEvidenceSettings
from codestrata.domain.evidence.dependency.enums import DependencyDeclarationKind
from codestrata.domain.evidence.dependency.models import DependencyDeclarationEvidence
from codestrata.domain.evidence.language.identifiers import stable_evidence_id

UNSUPPORTED_MANIFESTS = {
    "cargo.toml": "cargo",
    "go.mod": "go",
    "go.sum": "go",
    "gemfile": "ruby",
    "gemfile.lock": "ruby",
}

_UNBOUNDED_HINTS = ("*", "latest", "x", "X")


def collect_supply_chain_inputs(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
) -> tuple[
    tuple[DeclarationRecord, ...],
    tuple[ResolutionOccurrence, ...],
    tuple[str, ...],
]:
    """Return declarations, lock occurrences and collection diagnostics."""

    diagnostics: list[str] = []
    declarations = list(_from_existing_collectors(relative_paths, file_texts))
    declarations.extend(_from_npm(relative_paths, file_texts))
    occurrences, lock_diags = parse_lockfiles(relative_paths, file_texts)
    diagnostics.extend(lock_diags)
    diagnostics.extend(_unsupported_manifests(relative_paths))
    linked = _link_occurrences(tuple(declarations), occurrences)
    annotated = _annotate_hygiene(tuple(declarations))
    return annotated, linked, tuple(sorted(set(diagnostics)))


def _unsupported_manifests(relative_paths: Sequence[str]) -> list[str]:
    notes: list[str] = []
    for path in relative_paths:
        name = PurePosixPath(path).name.lower()
        ecosystem = UNSUPPORTED_MANIFESTS.get(name)
        if ecosystem:
            notes.append(f"unknown_ecosystem:{ecosystem}:{path.replace(chr(92), '/')}")
    return notes


def _from_existing_collectors(
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
) -> list[DeclarationRecord]:
    evidence = DependencyEvidenceService(DependencyEvidenceSettings(enabled=True)).collect(
        repository_id="supply-chain",
        relative_paths=relative_paths,
        file_texts=file_texts,
    )
    records: list[DeclarationRecord] = []
    for item in evidence.declarations:
        if is_local_or_direct_reference(item):
            continue
        records.append(_from_dependency_declaration(item))
    return records


def _from_dependency_declaration(item: DependencyDeclarationEvidence) -> DeclarationRecord:
    range_text = item.raw_version
    environment = (
        item.profile or item.configuration_name or item.group_name or item.environment_marker or ""
    )
    scope_id = _scope_id(item.ecosystem.value, item.source.path, environment)
    management = (
        item.is_dependency_management
        or item.declaration_kind is DependencyDeclarationKind.DEPENDENCY_MANAGEMENT
    )
    return DeclarationRecord(
        declaration_id=item.evidence_id,
        ecosystem=item.ecosystem.value,
        package_name=item.normalized_identity,
        declared_range=range_text,
        manifest_path=item.source.path,
        scope_id=scope_id,
        environment=environment,
        line=item.source.line_start,
        eligible=not management,
        eligibility_reason="dependency_management" if management else "supported_declaration",
        is_mutable=is_mutable_version(range_text),
        is_unbounded=_is_unbounded(range_text),
        is_unresolved_expression=has_proven_unresolved_version(item),
    )


def _from_npm(
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
) -> list[DeclarationRecord]:
    records: list[DeclarationRecord] = []
    for facts in collect_npm_facts(relative_paths, file_texts):
        for item in facts.declarations:
            environment = item.scope
            records.append(
                DeclarationRecord(
                    declaration_id=item.declaration_id,
                    ecosystem="npm",
                    package_name=item.name,
                    declared_range=item.declared_range,
                    manifest_path=item.manifest_path,
                    scope_id=_scope_id("npm", item.manifest_path, ""),
                    environment=environment,
                    line=item.line,
                    is_mutable=is_mutable_version(item.declared_range),
                    is_unbounded=_is_unbounded(item.declared_range),
                )
            )
    return records


def _is_unbounded(version: str | None) -> bool:
    text = (version or "").strip()
    if not text:
        return True
    if text in _UNBOUNDED_HINTS:
        return True
    if text.startswith("*") or text.endswith(".*"):
        return True
    if text in {">=0.0.0", ">=0", ">0"}:
        return True
    if not is_exact_version(text) and any(token in text for token in ("*", "x", "X", "latest")):
        return True
    return False


def _scope_id(ecosystem: str, manifest_path: str, environment: str) -> str:
    return stable_evidence_id("supply_chain.scope", ecosystem, manifest_path, environment)


def _link_occurrences(
    declarations: tuple[DeclarationRecord, ...],
    occurrences: tuple[ResolutionOccurrence, ...],
) -> tuple[ResolutionOccurrence, ...]:
    by_dir: dict[tuple[str, str], list[DeclarationRecord]] = defaultdict(list)
    for item in declarations:
        by_dir[(item.ecosystem, parent_dir(item.manifest_path))].append(item)
    linked: list[ResolutionOccurrence] = []
    for occurrence in occurrences:
        lock_dir = parent_dir(occurrence.lock_path)
        candidates = by_dir.get((occurrence.ecosystem, lock_dir), [])
        match = next(
            (
                item
                for item in candidates
                if _names_equal(item.package_name, occurrence.package_name)
            ),
            None,
        )
        linked.append(
            occurrence.model_copy(
                update={
                    "declaration_id": match.declaration_id if match else None,
                    "direct": match is not None and occurrence.direct,
                }
            )
        )
    return tuple(linked)


def _names_equal(left: str, right: str) -> bool:
    return left.strip().lower() == right.strip().lower()


def _annotate_hygiene(
    declarations: tuple[DeclarationRecord, ...],
) -> tuple[DeclarationRecord, ...]:
    """Flag duplicates/conflicts using declaration identity within a scope."""

    from collections import Counter

    id_counts = Counter(item.declaration_id for item in declarations)
    name_scope: dict[tuple[str, str], list[DeclarationRecord]] = defaultdict(list)
    for item in declarations:
        name_scope[(item.scope_id, item.package_name.lower())].append(item)
    updated: list[DeclarationRecord] = []
    for item in declarations:
        siblings = name_scope[(item.scope_id, item.package_name.lower())]
        ranges = {sibling.declared_range or "" for sibling in siblings}
        duplicate = len(siblings) > 1 and len(ranges) == 1
        conflict = len(ranges) > 1
        updated.append(
            item.model_copy(
                update={
                    "is_duplicate": duplicate or id_counts[item.declaration_id] > 1,
                    "is_conflict": conflict,
                }
            )
        )
    return tuple(updated)


def attach_lock_paths(
    declarations: tuple[DeclarationRecord, ...],
    occurrences: tuple[ResolutionOccurrence, ...],
) -> tuple[DeclarationRecord, ...]:
    lock_by_decl = {
        item.declaration_id: item.lock_path for item in occurrences if item.declaration_id
    }
    return tuple(
        item.model_copy(update={"lock_path": lock_by_decl.get(item.declaration_id)})
        for item in declarations
    )
