"""Tests for RepositoryStructureExtractor and path-based module resolution."""

from __future__ import annotations

from codestrata.domain.graph import (
    GraphGenerationMode,
    GraphId,
    GraphMetadata,
    GraphStatus,
    GraphType,
)
from codestrata.domain.repository import (
    FileFingerprint,
    HashAlgorithm,
    RepositoryFileEntry,
    RepositoryFileKind,
    RepositoryFingerprint,
    RepositoryGraphChangeSet,
    RepositoryIdentity,
    RepositoryManifest,
    RepositoryPath,
    RepositoryRevision,
    RepositoryRevisionType,
    RepositorySourceType,
)
from codestrata.domain.repository_graph import RepositoryNodeType, RepositoryRelationshipType
from codestrata.services.repository_graph import (
    PathBasedModuleResolver,
    RepositoryExtractionContext,
    RepositoryExtractionScope,
    RepositoryGraphAssembler,
    RepositoryStructureExtractor,
)
from tests.services.inventory.memory_reader import InMemoryContentReader


def _fp(digest: str = "a" * 64) -> FileFingerprint:
    return FileFingerprint(algorithm=HashAlgorithm.SHA256, digest=digest)


def _entry(
    path: str,
    *,
    kind: RepositoryFileKind = RepositoryFileKind.SOURCE,
    language: str | None = "Java",
    digest: str = "a" * 64,
    size_bytes: int = 10,
    generated: bool = False,
    executable: bool = False,
    media_type: str | None = "text/x-java-source",
) -> RepositoryFileEntry:
    return RepositoryFileEntry(
        path=path,
        file_kind=kind,
        size_bytes=size_bytes,
        fingerprint=_fp(digest),
        language=language,
        generated=generated,
        executable=executable,
        media_type=media_type,
    )


def _manifest(*files: RepositoryFileEntry) -> RepositoryManifest:
    return RepositoryManifest(
        identity=RepositoryIdentity(
            repository_key="demo",
            source_type=RepositorySourceType.LOCAL,
            display_name="Demo",
            source_location="/repos/demo",
        ),
        revision=RepositoryRevision(
            revision_id="rev-1",
            revision_type=RepositoryRevisionType.WORKING_TREE,
            branch="main",
        ),
        files=files,
    )


def _context(
    manifest: RepositoryManifest,
    *,
    scope: RepositoryExtractionScope = RepositoryExtractionScope.FULL,
    change_set: RepositoryGraphChangeSet | None = None,
) -> RepositoryExtractionContext:
    files = {entry.path.root: b"x" for entry in manifest.files}
    return RepositoryExtractionContext(
        manifest=manifest,
        content_reader=InMemoryContentReader(files),
        scope=scope,
        change_set=change_set,
    )


def _metadata() -> GraphMetadata:
    return GraphMetadata(
        graph_id=GraphId("graph:demo"),
        graph_type=GraphType.REPOSITORY,
        schema_version="1.0.0",
        generator_version="0.1.0",
        source_fingerprint="fp:1",
        generation_mode=GraphGenerationMode.FULL,
        status=GraphStatus.VALID,
    )


def _nodes_by_type(result):
    grouped: dict[str, list] = {}
    for node in result.nodes:
        grouped.setdefault(node.node_type, []).append(node)
    return grouped


def _contains_pairs(result) -> set[tuple[str, str]]:
    return {
        (rel.source_node_id.root, rel.target_node_id.root)
        for rel in result.relationships
        if rel.relationship_type == RepositoryRelationshipType.CONTAINS
    }


def test_full_extraction_basic_and_assembler() -> None:
    manifest = _manifest(
        _entry("README.md", kind=RepositoryFileKind.DOCUMENTATION, language="Markdown"),
        _entry("src/App.java"),
    )
    result = RepositoryStructureExtractor().extract(_context(manifest))
    by_type = _nodes_by_type(result)
    assert result.extractor_id == "repository-structure"
    assert len(by_type[RepositoryNodeType.REPOSITORY]) == 1
    assert len(by_type[RepositoryNodeType.FILE]) == 2
    assert RepositoryNodeType.MODULE not in by_type
    assert result.statistics.node_count == 3
    assert result.statistics.duration_ms is None

    repo = by_type[RepositoryNodeType.REPOSITORY][0]
    assert repo.properties["name"] == "Demo"
    assert repo.properties["source_type"] == "local"
    assert repo.properties["branch"] == "main"
    assert repo.properties["revision"] == "rev-1"

    file_ids = {node.id.root for node in by_type[RepositoryNodeType.FILE]}
    assert "repo:demo:file:README.md" in file_ids
    assert "repo:demo:file:src/App.java" in file_ids
    pairs = _contains_pairs(result)
    assert ("repo:demo", "repo:demo:file:README.md") in pairs
    assert ("repo:demo", "repo:demo:file:src/App.java") in pairs

    graph = RepositoryGraphAssembler().assemble((result,), metadata=_metadata())
    assert len(graph.nodes) == 3


def test_root_manifest_does_not_create_module() -> None:
    manifest = _manifest(
        _entry("pom.xml", kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language="XML"),
        _entry("src/Main.java"),
    )
    result = RepositoryStructureExtractor().extract(_context(manifest))
    assert all(node.node_type != RepositoryNodeType.MODULE for node in result.nodes)
    pairs = _contains_pairs(result)
    assert ("repo:demo", "repo:demo:file:pom.xml") in pairs
    assert ("repo:demo", "repo:demo:file:src/Main.java") in pairs


def test_single_nested_module() -> None:
    manifest = _manifest(
        _entry("pom.xml", kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language="XML"),
        _entry("src/Main.java"),
        _entry(
            "services/orders/pom.xml",
            kind=RepositoryFileKind.DEPENDENCY_MANIFEST,
            language="XML",
        ),
        _entry("services/orders/src/Order.java"),
    )
    result = RepositoryStructureExtractor().extract(_context(manifest))
    modules = [node for node in result.nodes if node.node_type == RepositoryNodeType.MODULE]
    assert len(modules) == 1
    assert modules[0].id.root == "repo:demo:module:services/orders"
    assert modules[0].properties["build_system"] == "maven"
    assert modules[0].properties["name"] == "orders"
    pairs = _contains_pairs(result)
    assert ("repo:demo", "repo:demo:module:services/orders") in pairs
    assert (
        "repo:demo:module:services/orders",
        "repo:demo:file:services/orders/src/Order.java",
    ) in pairs
    assert ("repo:demo", "repo:demo:file:src/Main.java") in pairs
    assert (
        "repo:demo",
        "repo:demo:file:services/orders/src/Order.java",
    ) not in pairs


def test_nested_modules_deepest_ownership() -> None:
    manifest = _manifest(
        _entry("services/pom.xml", kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language="XML"),
        _entry(
            "services/orders/pom.xml",
            kind=RepositoryFileKind.DEPENDENCY_MANIFEST,
            language="XML",
        ),
        _entry("services/orders/src/Order.java"),
        _entry("services/Shared.java"),
    )
    result = RepositoryStructureExtractor().extract(_context(manifest))
    module_ids = {
        node.id.root for node in result.nodes if node.node_type == RepositoryNodeType.MODULE
    }
    assert module_ids == {"repo:demo:module:services", "repo:demo:module:services/orders"}
    pairs = _contains_pairs(result)
    assert ("repo:demo", "repo:demo:module:services") in pairs
    assert ("repo:demo:module:services", "repo:demo:module:services/orders") in pairs
    assert (
        "repo:demo:module:services/orders",
        "repo:demo:file:services/orders/src/Order.java",
    ) in pairs
    assert ("repo:demo:module:services", "repo:demo:file:services/Shared.java") in pairs
    assert (
        "repo:demo:module:services",
        "repo:demo:file:services/orders/src/Order.java",
    ) not in pairs


def test_multiple_ecosystems_create_distinct_modules() -> None:
    files = [
        _entry("java/svc/pom.xml", kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language="XML"),
        _entry("gradle/svc/build.gradle", kind=RepositoryFileKind.BUILD, language="Gradle"),
        _entry("js/app/package.json", kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language="JSON"),
        _entry(
            "py/lib/pyproject.toml",
            kind=RepositoryFileKind.DEPENDENCY_MANIFEST,
            language="TOML",
        ),
        _entry(
            "php/app/composer.json",
            kind=RepositoryFileKind.DEPENDENCY_MANIFEST,
            language="JSON",
        ),
        _entry("go/svc/go.mod", kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language=None),
        _entry(
            "rust/crate/Cargo.toml",
            kind=RepositoryFileKind.DEPENDENCY_MANIFEST,
            language="TOML",
        ),
        _entry("dotnet/app/App.csproj", kind=RepositoryFileKind.BUILD, language="C#"),
    ]
    result = RepositoryStructureExtractor().extract(_context(_manifest(*files)))
    modules = {
        node.properties["path"]: node.properties["build_system"]
        for node in result.nodes
        if node.node_type == RepositoryNodeType.MODULE
    }
    assert modules == {
        "java/svc": "maven",
        "gradle/svc": "gradle",
        "js/app": "npm",
        "py/lib": "python",
        "php/app": "composer",
        "go/svc": "go",
        "rust/crate": "cargo",
        "dotnet/app": "dotnet",
    }


def test_module_identity_uses_full_path() -> None:
    manifest = _manifest(
        _entry("a/svc/pom.xml", kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language="XML"),
        _entry("b/svc/pom.xml", kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language="XML"),
    )
    first = RepositoryStructureExtractor().extract(_context(manifest))
    second = RepositoryStructureExtractor().extract(_context(manifest))
    ids = sorted(
        node.id.root for node in first.nodes if node.node_type == RepositoryNodeType.MODULE
    )
    assert ids == ["repo:demo:module:a/svc", "repo:demo:module:b/svc"]
    assert first == second


def test_multiple_markers_warn_and_keep_one_module() -> None:
    manifest = _manifest(
        _entry("svc/pom.xml", kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language="XML"),
        _entry("svc/build.gradle", kind=RepositoryFileKind.BUILD, language="Gradle"),
        _entry("svc/src/App.java"),
    )
    result = RepositoryStructureExtractor().extract(_context(manifest))
    modules = [node for node in result.nodes if node.node_type == RepositoryNodeType.MODULE]
    assert len(modules) == 1
    assert modules[0].properties["build_system"] == "maven"
    assert any(item.code == "multiple-module-markers" for item in result.diagnostics)


def test_file_properties_and_relationship_determinism() -> None:
    manifest = _manifest(
        _entry(
            "src/App.java",
            digest="ab" * 32,
            size_bytes=42,
            generated=True,
            executable=True,
            media_type="text/x-java-source",
        )
    )
    result = RepositoryStructureExtractor().extract(_context(manifest))
    file_node = next(node for node in result.nodes if node.node_type == RepositoryNodeType.FILE)
    assert file_node.properties["file_kind"] == "source"
    assert file_node.properties["language"] == "Java"
    assert file_node.properties["content_hash"] == "ab" * 32
    assert file_node.properties["hash_algorithm"] == "sha256"
    assert file_node.properties["size_bytes"] == 42
    assert file_node.properties["generated"] is True
    assert file_node.properties["executable"] is True
    assert file_node.properties["media_type"] == "text/x-java-source"
    assert len({rel.id for rel in result.relationships}) == len(result.relationships)


def test_manifest_order_does_not_affect_result() -> None:
    files = (
        _entry("z/pom.xml", kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language="XML"),
        _entry("a/pom.xml", kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language="XML"),
        _entry("z/A.java"),
        _entry("a/B.java"),
    )
    first = RepositoryStructureExtractor().extract(_context(_manifest(*files)))
    second = RepositoryStructureExtractor().extract(_context(_manifest(*reversed(files))))
    assert first.nodes == second.nodes
    assert first.relationships == second.relationships


def test_incremental_emits_changed_files_and_deleted_paths() -> None:
    manifest = _manifest(
        _entry("keep.java"),
        _entry("changed.java", digest="b" * 64),
        _entry("svc/pom.xml", kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language="XML"),
        _entry("svc/New.java"),
    )
    change_set = RepositoryGraphChangeSet(
        added_paths=(RepositoryPath("svc/New.java"),),
        modified_paths=(RepositoryPath("changed.java"),),
        deleted_paths=(RepositoryPath("gone.java"),),
        metadata_changed_paths=(),
        repository_fingerprint=RepositoryFingerprint(
            algorithm=HashAlgorithm.SHA256,
            digest="c" * 64,
            manifest_version="1.0",
            file_count=4,
        ),
    )
    result = RepositoryStructureExtractor().extract(
        _context(
            manifest,
            scope=RepositoryExtractionScope.INCREMENTAL,
            change_set=change_set,
        )
    )
    file_paths = {
        node.properties["path"]
        for node in result.nodes
        if node.node_type == RepositoryNodeType.FILE
    }
    assert file_paths == {"changed.java", "svc/New.java"}
    assert "keep.java" not in file_paths
    assert any(node.node_type == RepositoryNodeType.REPOSITORY for node in result.nodes)
    assert any(
        node.id.root == "repo:demo:module:svc"
        for node in result.nodes
        if node.node_type == RepositoryNodeType.MODULE
    )
    assert [path.root for path in result.deleted_repository_paths] == ["gone.java"]
    # Incremental is not silently treated as full extraction.
    assert len(file_paths) < len(manifest.files)


def test_path_based_resolver_unit() -> None:
    resolution = PathBasedModuleResolver().resolve(
        _manifest(
            _entry("pom.xml", kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language="XML"),
            _entry("apps/api/pom.xml", kind=RepositoryFileKind.DEPENDENCY_MANIFEST, language="XML"),
            _entry("apps/api/src/Api.java"),
        )
    )
    assert [module.path.root for module in resolution.modules] == ["apps/api"]
    assert resolution.file_module_paths["apps/api/src/Api.java"] == "apps/api"
    assert resolution.file_module_paths["pom.xml"] is None
