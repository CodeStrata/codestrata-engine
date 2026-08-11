"""Project Technology Inventory from existing AnalysisResult facts (Epic 3 Slice 3.2)."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.models import AnalysisResult, Technology
from codestrata.models.build_facts import BuildFacts
from codestrata.models.dependency_facts import DependencyFacts
from codestrata.models.enums import TechnologyCategory
from codestrata.models.normalized_facts import StructureFacts, TechnologyFacts
from codestrata.reporting.contract.ordering import sorted_technologies
from codestrata.reporting.modernization_models import HighlightedVersionInput
from codestrata.reporting.technology.models import (
    RepositoryCompositionView,
    TechnologyInventoryFact,
    TechnologyInventoryGroup,
    TechnologyInventorySection,
)

# Display groups — only rendered when non-empty.
_GROUP_SPECS: tuple[tuple[str, str, frozenset[str]], ...] = (
    ("languages", "Languages", frozenset({"language"})),
    (
        "frameworks_libraries",
        "Frameworks and major libraries",
        frozenset({"framework", "library", "testing"}),
    ),
    ("build_package", "Build and package systems", frozenset({"build_tool"})),
    (
        "runtime_platform",
        "Runtime and platform versions",
        frozenset({"runtime", "container"}),
    ),
    (
        "service_indicators",
        "Application or service indicators",
        frozenset({"database", "cloud", "infrastructure", "other"}),
    ),
)

_RANGE_MARKERS = ("^", "~", "*", "x", "X", "[", "(", ",", "||", " - ")


def build_technology_inventory(
    analysis: AnalysisResult,
    *,
    highlighted_versions: Sequence[HighlightedVersionInput] = (),
) -> TechnologyInventorySection:
    """Build a factual Technology Inventory section from existing detections."""

    del highlighted_versions  # surfaced separately via document.version_highlights
    technologies = list(sorted_technologies(analysis.technologies))
    facts = _dedupe_technologies(technologies)
    facts = _apply_conflicting_versions(facts)

    # Enrich with repository-relative paths from dependency manifests / build files
    # when the technology name appears in those paths (structured only — no guessing).
    deps = analysis.facts.dependencies if analysis.facts else None
    build = analysis.facts.build if analysis.facts else None
    structure = analysis.facts.structure if analysis.facts else None
    tech_facts = analysis.facts.technology if analysis.facts else None

    facts = _attach_manifest_evidence(facts, deps=deps, build=build)
    facts = _merge_build_system_facts(facts, build=build)

    groups = _build_groups(facts)
    ecosystem_group = _ecosystem_group(deps)
    if ecosystem_group is not None:
        groups = (*groups, ecosystem_group)

    composition = _composition(
        structure=structure,
        build=build,
        deps=deps,
        tech_facts=tech_facts,
    )

    limitations = _collect_limitations(
        facts=facts,
        groups=groups,
        composition=composition,
        technologies=technologies,
        tech_facts=tech_facts,
        deps=deps,
    )
    status, status_label = _status(fact_count=len(facts), composition=composition)
    confidence, confidence_label = _section_confidence(facts)

    return TechnologyInventorySection(
        status=status,
        status_label=status_label,
        confidence=confidence,
        confidence_label=confidence_label,
        limitations=limitations,
        groups=groups,
        composition=composition,
        fact_count=len(facts),
    )


def _category_value(tech: Technology) -> str:
    raw = tech.category
    return str(getattr(raw, "value", raw) or "other").strip().lower()


def _normalize_name(name: str) -> str:
    return name.strip().lower()


def _version_state(version: str | None, *, dynamic: bool = False) -> str:
    if dynamic:
        return "range"
    text = (version or "").strip()
    if not text:
        return "unavailable"
    if any(marker in text for marker in _RANGE_MARKERS):
        return "range"
    return "exact"


def _confidence_label(confidence: float | None) -> str:
    if confidence is None:
        return "unavailable"
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.6:
        return "moderate"
    return "limited"


def _safe_path(path: str | None) -> str | None:
    if path is None:
        return None
    text = path.strip().replace("\\", "/")
    if not text or text.startswith("/") or text.startswith("file:"):
        return None
    if ".." in text.split("/"):
        return None
    return text


def _dedupe_technologies(technologies: Sequence[Technology]) -> list[TechnologyInventoryFact]:
    """Merge compatible detections; keep conflicting versions as separate facts."""

    # Group by (name, category, version_state_key)
    buckets: dict[tuple[str, str, str], list[Technology]] = {}
    for tech in technologies:
        name = tech.name.strip()
        if not name:
            continue
        category = _category_value(tech)
        version = (tech.version or "").strip() or ""
        key = (_normalize_name(name), category, version.lower())
        buckets.setdefault(key, []).append(tech)

    facts: list[TechnologyInventoryFact] = []
    for (_nkey, category, _vkey), items in buckets.items():
        # Strongest confidence wins for shared fields; merge sources.
        ranked = sorted(
            items,
            key=lambda item: (
                -(item.confidence if item.confidence is not None else -1.0),
                0 if item.version else 1,
                item.name.lower(),
            ),
        )
        primary = ranked[0]
        sources = tuple(
            sorted(
                {
                    str(item.source).strip()
                    for item in ranked
                    if item.source and str(item.source).strip()
                }
            )
        )
        confidence = primary.confidence
        for item in ranked[1:]:
            if item.confidence is None:
                continue
            if confidence is None or item.confidence > confidence:
                confidence = item.confidence
        version = (primary.version or "").strip() or None
        limitations: list[str] = []
        if version is None:
            limitations.append("version unavailable")
        if confidence is None:
            limitations.append("detection confidence unavailable")
        safe_sources = tuple(
            path for raw in sources if (path := _safe_path(raw)) is not None
        )
        # Keep non-path source labels (e.g. analyzer names) when they are not absolute.
        label_sources = tuple(
            raw
            for raw in sources
            if _safe_path(raw) is None and not raw.startswith("/") and not raw.startswith("file:")
        )
        display_source = (
            safe_sources[0]
            if safe_sources
            else (label_sources[0] if label_sources else None)
        )
        facts.append(
            TechnologyInventoryFact(
                name=primary.name.strip(),
                category=category,
                version=version,
                version_state=_version_state(version),
                source=display_source,
                evidence_paths=(),
                confidence=confidence,
                confidence_label=_confidence_label(confidence),
                limitations=tuple(limitations),
            )
        )
        # If multiple distinct sources, record as limitation on the fact.
        if len(safe_sources) + len(label_sources) > 1:
            merged_labels = tuple(sorted({*safe_sources, *label_sources}))
            facts[-1] = facts[-1].model_copy(
                update={
                    "limitations": tuple(
                        sorted(
                            set(facts[-1].limitations)
                            | {f"sources: {', '.join(merged_labels)}"}
                        )
                    ),
                    "source": display_source,
                }
            )
    facts.sort(key=lambda item: (item.category, item.name.lower(), item.version or ""))
    return facts


def _apply_conflicting_versions(
    facts: Sequence[TechnologyInventoryFact],
) -> list[TechnologyInventoryFact]:
    by_identity: dict[tuple[str, str], list[TechnologyInventoryFact]] = {}
    for fact in facts:
        key = (_normalize_name(fact.name), fact.category)
        by_identity.setdefault(key, []).append(fact)

    out: list[TechnologyInventoryFact] = []
    for group in by_identity.values():
        versions = {(item.version or "").strip() for item in group if (item.version or "").strip()}
        conflicting = len(versions) > 1
        for item in group:
            if conflicting:
                out.append(
                    item.model_copy(
                        update={
                            "version_state": "conflicting"
                            if item.version
                            else item.version_state,
                            "limitations": tuple(
                                sorted(
                                    set(item.limitations)
                                    | {"conflicting versions detected for this technology"}
                                )
                            ),
                        }
                    )
                )
            else:
                out.append(item)
    out.sort(key=lambda item: (item.category, item.name.lower(), item.version or ""))
    return out


def _attach_manifest_evidence(
    facts: Sequence[TechnologyInventoryFact],
    *,
    deps: DependencyFacts | None,
    build: BuildFacts | None,
) -> list[TechnologyInventoryFact]:
    path_index: list[str] = []
    if deps is not None:
        for manifest in deps.manifests:
            safe = _safe_path(manifest.path)
            if safe:
                path_index.append(safe)
    if build is not None:
        for path in (*build.build_files, *build.lock_files, *build.wrapper_files):
            safe = _safe_path(path)
            if safe:
                path_index.append(safe)
    path_index = sorted(set(path_index))

    out: list[TechnologyInventoryFact] = []
    for fact in facts:
        needle = _normalize_name(fact.name)
        matches = tuple(
            path
            for path in path_index
            if needle and needle in path.lower()
        )
        # Prefer explicit source as evidence label when no path match.
        evidence = matches
        if not evidence and fact.source:
            source_path = _safe_path(fact.source)
            if source_path:
                evidence = (source_path,)
        out.append(fact.model_copy(update={"evidence_paths": evidence}))
    return out


def _build_groups(facts: Sequence[TechnologyInventoryFact]) -> tuple[TechnologyInventoryGroup, ...]:
    by_category: dict[str, list[TechnologyInventoryFact]] = {}
    for fact in facts:
        by_category.setdefault(fact.category, []).append(fact)

    groups: list[TechnologyInventoryGroup] = []
    assigned: set[str] = set()
    for group_id, title, categories in _GROUP_SPECS:
        collected: list[TechnologyInventoryFact] = []
        for category in sorted(categories):
            collected.extend(by_category.get(category, ()))
            assigned.add(category)
        if not collected:
            continue
        collected.sort(key=lambda item: (item.name.lower(), item.version or ""))
        groups.append(
            TechnologyInventoryGroup(group_id=group_id, title=title, facts=tuple(collected))
        )

    # Any leftover categories → service indicators overflow (already covered) or skip.
    leftovers = [
        fact
        for category, items in by_category.items()
        if category not in assigned
        for fact in items
    ]
    if leftovers:
        leftovers.sort(key=lambda item: (item.category, item.name.lower()))
        # Append into service indicators if present, else new group.
        for index, group in enumerate(groups):
            if group.group_id == "service_indicators":
                merged = tuple(
                    sorted(
                        (*group.facts, *leftovers),
                        key=lambda item: (item.name.lower(), item.version or ""),
                    )
                )
                groups[index] = group.model_copy(update={"facts": merged})
                leftovers = []
                break
        if leftovers:
            groups.append(
                TechnologyInventoryGroup(
                    group_id="service_indicators",
                    title="Application or service indicators",
                    facts=tuple(leftovers),
                )
            )
    return tuple(groups)


def _merge_build_system_facts(
    facts: Sequence[TechnologyInventoryFact],
    *,
    build: BuildFacts | None,
) -> list[TechnologyInventoryFact]:
    """Add BuildFacts.build_systems when not already represented as build_tool facts."""

    if build is None or not build.build_systems:
        return list(facts)
    existing = {
        _normalize_name(fact.name)
        for fact in facts
        if fact.category == "build_tool"
    }
    evidence = tuple(
        sorted(
            {
                path
                for raw in (*build.build_files, *build.lock_files, *build.wrapper_files)
                if (path := _safe_path(raw))
            }
        )
    )
    out = list(facts)
    for system in sorted({item.strip() for item in build.build_systems if item.strip()}, key=str.lower):
        if _normalize_name(system) in existing:
            continue
        out.append(
            TechnologyInventoryFact(
                name=system,
                category="build_tool",
                version=None,
                version_state="unavailable",
                source="build_facts",
                evidence_paths=evidence,
                confidence=None,
                confidence_label="unavailable",
                limitations=("version unavailable", "observed from build system detection"),
            )
        )
    out.sort(key=lambda item: (item.category, item.name.lower(), item.version or ""))
    return out


def _ecosystem_group(deps: DependencyFacts | None) -> TechnologyInventoryGroup | None:
    if deps is None or not deps.manifests:
        return None
    # One fact per ecosystem (structured), with representative manifest paths.
    by_eco: dict[str, list[str]] = {}
    for manifest in deps.manifests:
        eco = (manifest.ecosystem or "").strip()
        if not eco:
            continue
        path = _safe_path(manifest.path)
        by_eco.setdefault(eco, [])
        if path and path not in by_eco[eco]:
            by_eco[eco].append(path)
    if not by_eco:
        return None
    facts = tuple(
        TechnologyInventoryFact(
            name=eco,
            category="ecosystem",
            version=None,
            version_state="unavailable",
            source="dependency_manifest",
            evidence_paths=tuple(sorted(paths)),
            confidence=None,
            confidence_label="unavailable",
            limitations=("ecosystem observed from dependency manifests",),
        )
        for eco, paths in sorted(by_eco.items(), key=lambda pair: pair[0].lower())
    )
    return TechnologyInventoryGroup(
        group_id="dependency_ecosystems",
        title="Dependency ecosystems",
        facts=facts,
    )


def _composition(
    *,
    structure: StructureFacts | None,
    build: BuildFacts | None,
    deps: DependencyFacts | None,
    tech_facts: TechnologyFacts | None,
) -> RepositoryCompositionView | None:
    del tech_facts
    if structure is None and build is None and deps is None:
        return None
    modules = tuple(sorted({*(build.modules if build else ())}, key=str.lower))
    manifests = tuple(
        sorted(
            {
                path
                for manifest in (deps.manifests if deps else ())
                if (path := _safe_path(manifest.path))
            }
        )
    )
    build_files = tuple(
        sorted(
            {
                path
                for raw in (*(build.build_files if build else ()), *(build.lock_files if build else ()))
                if (path := _safe_path(raw))
            }
        )
    )
    ecosystems = tuple(
        sorted(
            {
                manifest.ecosystem.strip()
                for manifest in (deps.manifests if deps else ())
                if manifest.ecosystem and manifest.ecosystem.strip()
            },
            key=str.lower,
        )
    )
    if (
        structure is None
        or (
            structure.file_count is None
            and structure.source_file_count is None
            and structure.test_file_count is None
        )
    ) and not modules and not manifests and not build_files:
        # Still useful if we only have ecosystems
        if not ecosystems:
            return None

    return RepositoryCompositionView(
        total_files=structure.file_count if structure else None,
        source_files=structure.source_file_count if structure else None,
        test_files=structure.test_file_count if structure else None,
        application_count=structure.application_count if structure else None,
        modules=modules,
        manifest_paths=manifests,
        build_file_paths=build_files,
        ecosystems=ecosystems,
    )


def _collect_limitations(
    *,
    facts: Sequence[TechnologyInventoryFact],
    groups: Sequence[TechnologyInventoryGroup],
    composition: RepositoryCompositionView | None,
    technologies: Sequence[Technology],
    tech_facts: TechnologyFacts | None,
    deps: DependencyFacts | None,
) -> tuple[str, ...]:
    notes: list[str] = [
        "Technology Inventory lists detections from this assessment only. "
        "It is not an assessment of modernity, readiness, or architecture quality."
    ]
    if not technologies and not (tech_facts and tech_facts.detected_technologies):
        notes.append("No technology detections were produced for this repository scan.")
    if any(fact.version_state == "unavailable" for fact in facts):
        notes.append("Some detected technologies do not include an exact version.")
    if any(fact.version_state == "conflicting" for fact in facts):
        notes.append("Conflicting versions were observed for one or more technologies.")
    if any(fact.confidence_label in {"limited", "unavailable"} for fact in facts):
        notes.append("Some detections have limited or unavailable confidence.")
    if composition is None:
        notes.append("Repository composition metrics were not available for this scan.")
    if deps is not None and deps.dynamic_version_dependencies:
        notes.append("Dynamic dependency versions were observed in manifests.")
    # Preserve fact-level unique limitations that are inventory-relevant.
    for fact in facts:
        for item in fact.limitations:
            if item.startswith("sources:"):
                continue
            if item not in notes:
                notes.append(item)
    # Deduplicate while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for note in notes:
        key = note.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    del groups
    return tuple(out)


def _status(
    *,
    fact_count: int,
    composition: RepositoryCompositionView | None,
) -> tuple[str, str]:
    if fact_count == 0 and composition is None:
        return "inventory_unavailable", "Inventory unavailable"
    if fact_count == 0 and composition is not None:
        return "partial_inventory", "Partial inventory"
    if fact_count > 0 and composition is not None:
        return "inventory_generated", "Inventory generated"
    return "partial_inventory", "Partial inventory"


def _section_confidence(facts: Sequence[TechnologyInventoryFact]) -> tuple[str, str]:
    if not facts:
        return "unavailable", "Confidence unavailable"
    labels = {fact.confidence_label for fact in facts}
    if labels == {"high"}:
        return "high", "High confidence"
    if "limited" in labels or "unavailable" in labels:
        if "high" in labels or "moderate" in labels:
            return "limited", "Limited confidence"
        return "unavailable", "Confidence unavailable"
    if "moderate" in labels:
        return "moderate", "Moderate confidence"
    return "unavailable", "Confidence unavailable"


def category_group_id(category: str | TechnologyCategory) -> str | None:
    """Map a technology category to an inventory group id (for tests)."""

    value = str(getattr(category, "value", category)).strip().lower()
    for group_id, _title, categories in _GROUP_SPECS:
        if value in categories:
            return group_id
    if value == "ecosystem":
        return "dependency_ecosystems"
    return "service_indicators"
