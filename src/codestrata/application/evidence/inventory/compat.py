"""Project inventory facts into RepositoryFacts for enabled analyzers (E05.3).

Downstream analyzers read the existing RepositoryFacts contract. This mapping
preserves declared-vs-resolved honesty: missing lock is not zero dependencies,
and CI observations do not claim jobs ran. No health score is assigned.
"""

from __future__ import annotations

from codestrata.application.evidence.inventory.facts import (
    CiInvocationFact,
    DependencyDeclarationFact,
    ExtractionStatus,
    InventoryFactBundle,
)
from codestrata.application.evidence.inventory.models import ResolutionObservation
from codestrata.models import (
    BuildFacts,
    CicdFacts,
    CicdPipeline,
    Dependency,
    DependencyFacts,
    DependencyManifest,
    RepositoryFacts,
)
from codestrata.models.normalized_facts import (
    ArchitectureFacts,
    StructureFacts,
    TechnologyFacts,
    canonical_technology_name,
)


def project_repository_facts(bundle: InventoryFactBundle) -> RepositoryFacts:
    """Compatible facts every enabled analyzer can merge without parsers."""

    class_counts = bundle.classification.class_counts
    file_count = (
        class_counts.source
        + class_counts.test
        + class_counts.config
        + class_counts.infra
        + class_counts.docs
        + class_counts.generated
        + class_counts.vendor
        + class_counts.binary
        + class_counts.unknown
    )
    languages = tuple(
        dict.fromkeys(
            canonical_technology_name(item.language) for item in bundle.files if item.language
        )
    )
    ecosystems = tuple(dict.fromkeys(item.ecosystem for item in bundle.declarations))
    manifests = [
        DependencyManifest(
            path=item.manifest_path,
            ecosystem=item.ecosystem,
            manifest_type="manifest",
            lockfile=False,
        )
        for item in _unique_manifests(bundle)
    ]
    dependencies = [
        Dependency(
            name=item.coordinate,
            version=item.declared_version,
            ecosystem=item.ecosystem,
            manifest_path=item.manifest_path,
            unmanaged_version=item.resolution is ResolutionObservation.UNKNOWN,
        )
        for item in bundle.declarations
    ]
    lock_files = tuple(
        dict.fromkeys(item.lock_path for item in bundle.resolutions if item.lock_path)
    )
    pipelines = _ci_pipelines(bundle)
    complete_routes = [
        item
        for item in bundle.surfaces
        if item.declaration_kind == "http_route"
        and item.extraction_status is ExtractionStatus.COMPLETE
    ]
    return RepositoryFacts(
        structure=StructureFacts(
            file_count=file_count,
            source_file_count=class_counts.source,
            test_file_count=class_counts.test,
            has_tests=class_counts.test > 0,
        ),
        technology=TechnologyFacts(
            programming_languages=list(languages),
            detected_technologies=list(dict.fromkeys([*languages, *ecosystems])),
            build_tools=list(ecosystems),
        ),
        build=BuildFacts(
            build_systems=list(ecosystems),
            build_files=list(dict.fromkeys(item.manifest_path for item in bundle.declarations)),
            lock_files=list(lock_files),
            modules=[item.component_key for item in bundle.components],
        ),
        dependencies=DependencyFacts(
            manifests=manifests,
            dependencies=dependencies,
            dependency_count=len(dependencies),
            direct_dependency_count=sum(1 for item in bundle.declarations if item.direct),
        ),
        cicd=CicdFacts(
            pipelines=pipelines,
            providers=list(dict.fromkeys(item.provider for item in pipelines)),
            ci_platforms=list(dict.fromkeys(item.provider for item in pipelines)),
            pipeline_files=list(dict.fromkeys(item.path for item in pipelines)),
            pipeline_count=len(pipelines),
            job_count=sum(len(item.jobs) for item in pipelines),
            has_ci=bool(pipelines),
            has_tests=any(item.test_commands for item in pipelines),
            has_security_scanning=any(item.security_commands for item in pipelines),
        ),
        architecture=ArchitectureFacts(
            has_api_layer=True if complete_routes else None,
        ),
    )


def _unique_manifests(
    bundle: InventoryFactBundle,
) -> tuple[DependencyDeclarationFact, ...]:
    seen: set[tuple[str, str]] = set()
    ordered = []
    for item in bundle.declarations:
        key = (item.manifest_path, item.ecosystem)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return tuple(ordered)


def _ci_pipelines(bundle: InventoryFactBundle) -> list[CicdPipeline]:
    by_path: dict[str, list[CiInvocationFact]] = {}
    for item in bundle.ci:
        by_path.setdefault(item.path, []).append(item)
    pipelines: list[CicdPipeline] = []
    for path, invocations in sorted(by_path.items()):
        jobs = list(dict.fromkeys(row.job for row in invocations if row.job))
        test_commands = [
            row.literal_command
            for row in invocations
            if row.literal_command and row.tool_category == "test" and not row.unresolved
        ]
        security_commands = [
            row.literal_command
            for row in invocations
            if row.literal_command and row.tool_category == "security" and not row.unresolved
        ]
        metadata: dict[str, object] = {
            "configuration_not_execution": True,
            "unresolved_invocations": sum(1 for row in invocations if row.unresolved),
        }
        pipelines.append(
            CicdPipeline(
                provider="github-actions" if path.startswith(".github/workflows/") else "unknown",
                path=path,
                jobs=jobs,
                test_commands=test_commands,
                security_commands=security_commands,
                metadata=metadata,
            )
        )
    return pipelines
