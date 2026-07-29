"""Tests for Maven and package.json dependency parsers/extractors."""

from __future__ import annotations

import json

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
    RepositoryIdentity,
    RepositoryManifest,
    RepositoryRevision,
    RepositoryRevisionType,
    RepositorySourceType,
)
from codestrata.domain.repository_graph import (
    DependencyScope,
    DependencyVersion,
    RepositoryNodeType,
    RepositoryRelationshipType,
)
from codestrata.domain.repository_graph.factories import REPOSITORY_GRAPH_SCHEMA_VERSION
from codestrata.services.repository_graph import (
    MavenDependencyExtractor,
    PackageJsonDependencyExtractor,
    RepositoryDependencyExtractor,
    RepositoryExtractionContext,
    RepositoryGraphAssembler,
    RepositoryStructureExtractor,
)
from codestrata.services.repository_graph.extractors.maven_parser import (
    is_malformed_maven_pom,
    parse_maven_dependencies,
)
from codestrata.services.repository_graph.extractors.package_json_parser import (
    is_malformed_package_json,
    parse_package_json_dependencies,
)
from tests.services.inventory.memory_reader import InMemoryContentReader


def _fp(digest: str = "a" * 64) -> FileFingerprint:
    return FileFingerprint(algorithm=HashAlgorithm.SHA256, digest=digest)


def _entry(path: str, *, language: str | None = None) -> RepositoryFileEntry:
    return RepositoryFileEntry(
        path=path,
        file_kind=RepositoryFileKind.DEPENDENCY_MANIFEST,
        size_bytes=10,
        fingerprint=_fp(),
        language=language,
        generated=False,
        executable=False,
        media_type="application/octet-stream",
    )


def _manifest(*paths: str) -> RepositoryManifest:
    return RepositoryManifest(
        identity=RepositoryIdentity(
            repository_key="demo",
            source_type=RepositorySourceType.LOCAL,
            display_name="Demo",
            source_location=None,
        ),
        revision=RepositoryRevision(
            revision_id="rev-1",
            revision_type=RepositoryRevisionType.WORKING_TREE,
            branch="main",
        ),
        files=tuple(_entry(path) for path in paths),
    )


def _metadata() -> GraphMetadata:
    return GraphMetadata(
        graph_id=GraphId("graph:repo:demo:test"),
        graph_type=GraphType.REPOSITORY,
        schema_version=REPOSITORY_GRAPH_SCHEMA_VERSION,
        generator_version="1.0.0",
        source_fingerprint="sha256:" + ("b" * 64),
        generation_mode=GraphGenerationMode.FULL,
        status=GraphStatus.VALID,
    )


def test_maven_property_substitution_and_parent_version() -> None:
    pom = b"""<?xml version="1.0" encoding="UTF-8"?>
<project>
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>${boot.version}</version>
  </parent>
  <properties>
    <boot.version>3.4.5</boot.version>
    <java.version>21</java.version>
    <lib.version>${nested.version}</lib.version>
    <nested.version>1.2.3</nested.version>
  </properties>
  <dependencies>
    <dependency>
      <groupId>com.example</groupId>
      <artifactId>lib</artifactId>
      <version>${lib.version}</version>
    </dependency>
  </dependencies>
</project>
"""
    facts = parse_maven_dependencies(pom, source_file="pom.xml")
    by_name = {(item.namespace, item.name): item for item in facts}
    assert by_name[("com.example", "lib")].version_raw == "1.2.3"
    assert (
        by_name[("org.springframework.boot", "spring-boot-starter-parent")].version_raw == "3.4.5"
    )
    assert by_name[("org.springframework.boot", "spring-boot")].version_raw == "3.4.5"
    assert by_name[(None, "java")].version_raw == "21"
    assert by_name[(None, "java")].ecosystem == "jvm"


def test_maven_dependency_management() -> None:
    pom = b"""
<project>
  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>org.example</groupId>
        <artifactId>bom-lib</artifactId>
        <version>9.9.9</version>
      </dependency>
    </dependencies>
  </dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>org.example</groupId>
      <artifactId>bom-lib</artifactId>
    </dependency>
  </dependencies>
</project>
"""
    facts = parse_maven_dependencies(pom, source_file="pom.xml")
    managed_or_direct = [item for item in facts if item.name == "bom-lib"]
    assert len(managed_or_direct) == 1
    assert managed_or_direct[0].direct is True
    assert managed_or_direct[0].version_raw == "9.9.9"


def test_maven_empty_and_malformed() -> None:
    assert parse_maven_dependencies(b"", source_file="pom.xml") == ()
    assert parse_maven_dependencies(b"<project></project>", source_file="pom.xml") == ()
    assert is_malformed_maven_pom(b"<project>")
    assert parse_maven_dependencies(b"<project>", source_file="pom.xml") == ()


def test_package_json_sections_and_engines() -> None:
    payload = {
        "dependencies": {"express": "^4.21.0"},
        "devDependencies": {"jest": "^29.0.0"},
        "peerDependencies": {"react": "^18.0.0"},
        "engines": {"node": ">=18"},
    }
    facts = parse_package_json_dependencies(
        json.dumps(payload).encode("utf-8"),
        source_file="package.json",
    )
    by_name = {item.name: item for item in facts}
    assert by_name["express"].scope is DependencyScope.RUNTIME
    assert by_name["jest"].scope is DependencyScope.DEVELOPMENT
    assert by_name["react"].scope is DependencyScope.OPTIONAL
    assert by_name["nodejs"].version_raw == ">=18"
    assert by_name["nodejs"].ecosystem == "nodejs"


def test_package_json_empty_and_malformed() -> None:
    assert parse_package_json_dependencies(b"", source_file="package.json") == ()
    assert parse_package_json_dependencies(b"{}", source_file="package.json") == ()
    assert is_malformed_package_json(b"{")
    assert parse_package_json_dependencies(b"{", source_file="package.json") == ()


def test_dependency_version_helpers() -> None:
    assert DependencyVersion(raw="1.8").is_java_8()
    assert DependencyVersion(raw="8").is_java_8()
    assert DependencyVersion(raw="2.7.18").is_spring_boot_2()
    assert DependencyVersion(raw="3.4.5").major == 3
    assert DependencyVersion(raw=">=18").major == 18


def test_extractors_emit_depends_on_and_deterministic_graph() -> None:
    pom = b"""
<project>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>2.7.18</version>
  </parent>
  <properties>
    <java.version>17</java.version>
  </properties>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter</artifactId>
    </dependency>
  </dependencies>
</project>
"""
    package = json.dumps(
        {
            "dependencies": {"express": "4.0.0"},
            "engines": {"node": "18"},
        }
    ).encode("utf-8")
    manifest = _manifest("pom.xml", "package.json", "src/App.java")
    reader = InMemoryContentReader(
        {
            "pom.xml": pom,
            "package.json": package,
            "src/App.java": b"class App {}",
        }
    )
    context = RepositoryExtractionContext(manifest=manifest, content_reader=reader)
    structure = RepositoryStructureExtractor().extract(context)
    dependencies = RepositoryDependencyExtractor().extract(context)
    graph = RepositoryGraphAssembler().assemble((structure, dependencies), metadata=_metadata())

    dep_nodes = [
        node for node in graph.nodes if node.node_type == RepositoryNodeType.DEPENDENCY.value
    ]
    assert dep_nodes
    names = {node.properties["name"] for node in dep_nodes}
    assert "spring-boot" in names
    assert "express" in names
    assert "java" in names
    assert "nodejs" in names

    depends = [
        rel
        for rel in graph.relationships
        if rel.relationship_type == RepositoryRelationshipType.DEPENDS_ON.value
    ]
    assert depends
    assert all(rel.source_node_id.root == "repo:demo" for rel in depends)

    first = graph.snapshot.model_dump(mode="json")
    second = (
        RepositoryGraphAssembler()
        .assemble(
            (
                RepositoryStructureExtractor().extract(context),
                RepositoryDependencyExtractor().extract(context),
            ),
            metadata=_metadata(),
        )
        .snapshot.model_dump(mode="json")
    )
    assert first == second


def test_malformed_manifest_emits_diagnostic() -> None:
    manifest = _manifest("pom.xml", "package.json")
    reader = InMemoryContentReader(
        {
            "pom.xml": b"<project>",
            "package.json": b"{",
        }
    )
    context = RepositoryExtractionContext(manifest=manifest, content_reader=reader)
    maven = MavenDependencyExtractor().extract(context)
    npm = PackageJsonDependencyExtractor().extract(context)
    assert maven.diagnostics
    assert npm.diagnostics
    assert maven.nodes == ()
    assert npm.nodes == ()
