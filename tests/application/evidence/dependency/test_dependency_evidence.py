"""Dependency Evidence platform tests (Phase 4.4.2)."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.evidence.dependency.artifacts import (
    dependency_evidence_payload,
    write_dependency_evidence_artifact,
)
from codestrata.application.evidence.dependency.gradle_collector import parse_gradle_text
from codestrata.application.evidence.dependency.maven_collector import parse_pom_text
from codestrata.application.evidence.dependency.normalize import (
    normalize_python_distribution_name,
    resolve_local_properties,
)
from codestrata.application.evidence.dependency.paths import (
    is_ignored_path,
    select_manifest_paths,
)
from codestrata.application.evidence.dependency.python_collector import (
    parse_pyproject_text,
    parse_requirements_text,
)
from codestrata.application.evidence.dependency.service import DependencyEvidenceService
from codestrata.config import load_settings
from codestrata.config.settings import DependencyEvidenceSettings
from codestrata.domain.evidence.dependency.enums import (
    DependencyDeclarationKind,
    DependencyManifestType,
    DependencyParseStatus,
    DependencyVersionResolutionStatus,
)
from codestrata.domain.evidence.dependency.identifiers import (
    DEPENDENCY_EVIDENCE_ARTIFACT_FILENAME,
    DEPENDENCY_EVIDENCE_SCHEMA_VERSION,
)
from codestrata.domain.evidence.dependency.models import AggregatedDependencyEvidence
from codestrata.services.artifact_serialization import dumps_stable_json, loads_stable_json

FIXTURES = Path(__file__).parent / "fixtures"


def _load_tree(root: Path) -> tuple[tuple[str, ...], dict[str, str]]:
    paths: list[str] = []
    texts: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        try:
            texts[rel] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        paths.append(rel)
    return tuple(paths), texts


def test_settings_disabled_by_default(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    assert settings.evidence.dependency.enabled is False
    assert settings.evidence.dependency.maven.enabled is True
    assert settings.evidence.complexity.enabled is True


def test_settings_can_enable_dependency_evidence(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        [evidence.dependency]
        enabled = true
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.evidence.dependency.enabled is True


def test_manifest_discovery_and_exclusions() -> None:
    paths = (
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "pyproject.toml",
        "requirements.txt",
        "package.json",
        ".codestrata/workspace/pom.xml",
        "target/classes/pom.xml",
        "src/main/resources/readme.txt",
    )
    selected, excluded = select_manifest_paths(paths)
    assert "pom.xml" in selected
    assert "build.gradle" in selected
    assert "pyproject.toml" in selected
    assert "requirements.txt" in selected
    assert "package.json" not in selected
    assert ".codestrata/workspace/pom.xml" not in selected
    assert excluded >= 1
    assert is_ignored_path(".codestrata/workspace/x")


def test_maven_dependencies_management_plugins_profiles_properties() -> None:
    text = (FIXTURES / "maven" / "pom.xml").read_text(encoding="utf-8")
    manifest, decls = parse_pom_text(path="pom.xml", text=text)
    assert manifest.parse_status in {
        DependencyParseStatus.SUCCEEDED,
        DependencyParseStatus.PARTIALLY_SUCCEEDED,
    }
    identities = {item.normalized_identity for item in decls}
    assert "org.springframework.boot:spring-boot-starter-web" in identities
    assert "com.h2database:h2" in identities
    managed = [
        item
        for item in decls
        if item.declaration_kind is DependencyDeclarationKind.DEPENDENCY_MANAGEMENT
    ]
    assert managed
    plugins = [
        item
        for item in decls
        if item.declaration_kind is DependencyDeclarationKind.PLUGIN
    ]
    assert plugins
    profiled = [item for item in decls if item.profile == "mysql"]
    assert profiled
    resolved = [
        item
        for item in decls
        if item.resolved_version_local == "1.2.3"
    ]
    assert resolved
    unresolved_prop = [
        item for item in decls if item.raw_version == "${missing.version}"
    ]
    assert unresolved_prop
    assert unresolved_prop[0].resolved_version_local is None
    assert (
        unresolved_prop[0].version_resolution_status
        is DependencyVersionResolutionStatus.PROVEN_UNRESOLVED
    )
    assert any("parent_not_fetched" in item for item in manifest.unsupported_constructs)
    assert any("${missing.version}" in item for item in manifest.unresolved_expressions)


def test_local_property_resolution() -> None:
    resolved, ok = resolve_local_properties("${lib.version}", {"lib.version": "9.9.9"})
    assert ok and resolved == "9.9.9"
    unresolved, ok2 = resolve_local_properties("${missing}", {"lib.version": "1"})
    assert not ok2 and unresolved == "${missing}"


def test_gradle_static_and_dynamic() -> None:
    groovy = (FIXTURES / "gradle" / "build.gradle").read_text(encoding="utf-8")
    manifest, decls = parse_gradle_text(
        path="build.gradle",
        text=groovy,
        manifest_type=DependencyManifestType.BUILD_GRADLE,
    )
    identities = {item.normalized_identity for item in decls}
    assert "org.springframework.boot:spring-boot-starter" in identities
    assert any(item.declaration_kind.value == "plugin" for item in decls)
    assert manifest.unsupported_constructs
    # Gradle interpolations/dynamics are coverage diagnostics, not proven unresolved.
    assert not any("${" in item for item in manifest.unresolved_expressions)
    assert any(
        "unsupported_version_resolution" in item or ":dynamic:" in item
        for item in manifest.unsupported_constructs
    ) or any(
        "version_resolution_unsupported" in item for item in manifest.diagnostics
    )

    kts = (FIXTURES / "gradle" / "build.gradle.kts").read_text(encoding="utf-8")
    kts_manifest, kts_decls = parse_gradle_text(
        path="build.gradle.kts",
        text=kts,
        manifest_type=DependencyManifestType.BUILD_GRADLE_KTS,
    )
    assert any("junit" in item.normalized_identity for item in kts_decls)
    assert kts_manifest.parse_status in {
        DependencyParseStatus.SUCCEEDED,
        DependencyParseStatus.PARTIALLY_SUCCEEDED,
    }


def test_pyproject_pep621_and_poetry() -> None:
    text = (FIXTURES / "python" / "pyproject.toml").read_text(encoding="utf-8")
    manifest, decls = parse_pyproject_text(path="pyproject.toml", text=text)
    names = {item.normalized_identity for item in decls}
    assert "requests" in names
    assert "pytest" in names
    optional = [
        item
        for item in decls
        if item.declaration_kind is DependencyDeclarationKind.OPTIONAL
    ]
    assert optional
    poetry = [item for item in decls if item.group_name == "poetry"]
    assert poetry
    assert normalize_python_distribution_name("PyYAML") == "pyyaml"
    assert manifest.parse_status in {
        DependencyParseStatus.SUCCEEDED,
        DependencyParseStatus.PARTIALLY_SUCCEEDED,
    }


def test_requirements_includes_markers_cycles() -> None:
    root = FIXTURES / "python"
    paths, texts = _load_tree(root)
    _ = paths
    text = texts["requirements.txt"]
    manifest, decls = parse_requirements_text(
        path="requirements.txt",
        text=text,
        file_texts=texts,
    )
    names = {item.normalized_identity for item in decls}
    assert "flask" in names
    assert "httpx" in names  # from included file
    assert any(item.environment_marker for item in decls)
    assert any(item.extras for item in decls)
    assert any(item.is_editable or item.is_local_path for item in decls)
    # Cycle file
    cycle_text = texts["requirements-cycle-a.txt"]
    cycle_manifest, _ = parse_requirements_text(
        path="requirements-cycle-a.txt",
        text=cycle_text,
        file_texts=texts,
    )
    assert any(
        "cycle" in item for item in cycle_manifest.diagnostics
    ) or cycle_manifest.parse_status is DependencyParseStatus.PARTIALLY_SUCCEEDED


def test_malformed_manifests() -> None:
    bad_pom, _ = parse_pom_text(path="pom.xml", text="<project>")
    assert bad_pom.parse_status is DependencyParseStatus.FAILED
    bad_py, _ = parse_pyproject_text(path="pyproject.toml", text="[[[")
    assert bad_py.parse_status is DependencyParseStatus.FAILED


def test_service_collect_deterministic_and_artifact(tmp_path: Path) -> None:
    paths, texts = _load_tree(FIXTURES)
    # Include ignored path to prove exclusion.
    paths = paths + (".codestrata/workspace/pom.xml",)
    texts = dict(texts)
    texts[".codestrata/workspace/pom.xml"] = "<project></project>"
    service = DependencyEvidenceService(
        DependencyEvidenceSettings(enabled=True)
    )
    first = service.collect(
        repository_id="repo:demo",
        relative_paths=paths,
        file_texts=texts,
        configuration_fingerprint="stable",
    )
    second = service.collect(
        repository_id="repo:demo",
        relative_paths=paths,
        file_texts=texts,
        configuration_fingerprint="stable",
    )
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.schema_version == DEPENDENCY_EVIDENCE_SCHEMA_VERSION
    assert first.declarations
    assert first.evidence_fingerprint
    assert "/Users/" not in dumps_stable_json(first.model_dump(mode="json"))
    # No findings / interpretation fields.
    payload = dependency_evidence_payload(first)
    assert "findings" not in payload
    assert "conclusions" not in payload
    written = write_dependency_evidence_artifact(first, tmp_path)
    assert written.path.name == DEPENDENCY_EVIDENCE_ARTIFACT_FILENAME
    restored = AggregatedDependencyEvidence.model_validate(
        {
            key: value
            for key, value in loads_stable_json(
                written.path.read_text(encoding="utf-8")
            ).items()
            if key != "artifact_schema_id"
        }
    )
    assert restored.evidence_fingerprint == first.evidence_fingerprint


def test_disabled_service_returns_empty() -> None:
    service = DependencyEvidenceService(
        DependencyEvidenceSettings(enabled=False)
    )
    result = service.collect(
        repository_id="repo:x",
        relative_paths=("pom.xml",),
        file_texts={"pom.xml": "<project></project>"},
    )
    assert result.declarations == ()
    assert "dependency_evidence_disabled" in result.diagnostics
