"""M02 manifest observations: declared vs resolved, detection-only ecosystems."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.evidence.inventory.models import (
    ResolutionObservation,
    SupportKind,
)
from codestrata.application.evidence.inventory.service import ExtractorInventoryService

FIXTURES = Path(__file__).parent / "fixtures"


def _inspect(name: str):
    return ExtractorInventoryService().inspect_tree(FIXTURES / name)


def test_maven_declared_is_structural_not_a_resolved_lock() -> None:
    snapshot = _inspect("maven_declared")
    pom = next(item for item in snapshot.manifests if item.relative_path.endswith("pom.xml"))
    assert pom.support is SupportKind.STRUCTURAL
    assert pom.declared_count >= 1
    assert pom.resolution is ResolutionObservation.DECLARED_ONLY


def test_npm_missing_lock_is_unknown_not_zero_dependencies() -> None:
    snapshot = _inspect("npm_missing_lock")
    npm = next(item for item in snapshot.manifests if item.relative_path.endswith("package.json"))
    assert npm.support is SupportKind.STRUCTURAL
    assert npm.resolution is ResolutionObservation.UNKNOWN
    assert npm.declared_count >= 1


def test_npm_with_lock_records_resolved_occurrences_separately() -> None:
    snapshot = _inspect("npm_with_lock")
    manifest = next(
        item for item in snapshot.manifests if item.relative_path.endswith("package.json")
    )
    lock = next(
        item for item in snapshot.manifests if item.relative_path.endswith("package-lock.json")
    )
    assert manifest.support is SupportKind.STRUCTURAL
    assert manifest.declared_count >= 1
    assert manifest.resolution is ResolutionObservation.RESOLVED
    assert lock.support is SupportKind.STRUCTURAL
    assert lock.resolved_count >= 1


def test_composer_and_nuget_lower_tiers_unknown_resolution() -> None:
    composer = _inspect("composer_lower")
    nuget = _inspect("nuget_lower")
    composer_json = next(
        item for item in composer.manifests if item.relative_path.endswith("composer.json")
    )
    csproj = next(item for item in nuget.manifests if item.relative_path.endswith("App.csproj"))
    assert composer_json.support is SupportKind.STRUCTURAL
    assert composer_json.declared_count >= 1
    assert composer_json.resolution is ResolutionObservation.UNKNOWN
    assert csproj.support is SupportKind.STRUCTURAL
    assert csproj.declared_count >= 1
    assert csproj.resolution is ResolutionObservation.UNKNOWN


def test_workspace_packages_keep_workspace_diagnostic() -> None:
    snapshot = _inspect("workspace_packages")
    root = next(item for item in snapshot.manifests if item.relative_path == "package.json")
    assert root.support is SupportKind.STRUCTURAL
    assert "workspace_packages_detection_only" in root.diagnostics


def test_malformed_package_json_is_visible_parse_failure(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{not-json", encoding="utf-8")
    snapshot = ExtractorInventoryService().inspect_tree(tmp_path)
    npm = next(item for item in snapshot.manifests if item.relative_path == "package.json")
    assert npm.support is SupportKind.STRUCTURAL
    assert npm.resolution is ResolutionObservation.UNKNOWN
    assert any("package_json_parse_error" in note for note in npm.diagnostics)


def test_yarn_lock_is_unparsed_not_resolved(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"name":"app","dependencies":{"left-pad":"1.3.0"}}',
        encoding="utf-8",
    )
    (tmp_path / "yarn.lock").write_text("# yarn lockfile v1\n", encoding="utf-8")
    snapshot = ExtractorInventoryService().inspect_tree(tmp_path)
    lock = next(item for item in snapshot.manifests if item.relative_path == "yarn.lock")
    manifest = next(item for item in snapshot.manifests if item.relative_path == "package.json")
    assert lock.support is SupportKind.DETECTION_ONLY
    assert lock.resolution is ResolutionObservation.UNKNOWN
    assert "lock_format_unparsed" in lock.diagnostics
    assert manifest.resolution is ResolutionObservation.UNKNOWN


def test_duplicate_coordinates_are_retained() -> None:
    snapshot = _inspect("duplicate_coordinates")
    poms = [item for item in snapshot.manifests if item.relative_path.endswith("pom.xml")]
    assert len(poms) == 2
    assert any(item.duplicate_coordinates for item in poms)
    assert all(item.declared_count >= 1 for item in poms)
