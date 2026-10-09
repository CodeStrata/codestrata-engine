"""E05.2 inventory fact emission: IDs, coverage, declared vs resolved."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.evidence.inventory.emission import InventoryFactEmitter
from codestrata.application.evidence.inventory.facts import (
    CAP_M01,
    CAP_M02,
    CAP_M03,
)
from codestrata.application.evidence.inventory.models import ResolutionObservation
from codestrata.domain.repository_graph.mapping import ROOT_COMPONENT_KEY

FIXTURES = Path(__file__).parent / "fixtures"


def _emit(name: str, *, key: str = "demo"):
    return InventoryFactEmitter().emit_tree(FIXTURES / name, repository_key=key)


def test_file_and_component_ids_are_stable_and_relative() -> None:
    first = _emit("mixed_language")
    second = _emit("mixed_language")
    assert first.to_canonical_dict() == second.to_canonical_dict()
    java = next(item for item in first.files if item.relative_path.endswith("App.java"))
    assert java.subject_id == "repo:demo:file:src/main/java/com/example/App.java"
    assert java.content_digest
    assert first.working_state_digest
    assert first.source_revision == first.working_state_digest
    dumped = str(first.to_canonical_dict())
    assert "C:\\" not in dumped
    assert "/Users/" not in dumped
    mapped = next(
        item for item in first.file_component_map if item.relative_path.endswith("App.java")
    )
    assert mapped.component_id.startswith("repo:demo:module:")
    assert mapped.file_id == java.subject_id


def test_maven_declared_keeps_missing_lock_out_of_resolved_absence() -> None:
    bundle = _emit("maven_declared")
    decls = [item for item in bundle.declarations if item.ecosystem == "maven"]
    assert decls
    assert all(item.resolution is not ResolutionObservation.RESOLVED for item in decls)
    m02 = next(item for item in bundle.coverage if item.capability_id == CAP_M02)
    assert m02.eligible == len({item.declaration_id for item in decls})
    assert "coverage_unit_is_declaration_id" in m02.limitations
    assert any("resolution_occurrences=" in note for note in m02.limitations)


def test_npm_missing_lock_is_unknown_not_zero_dependencies() -> None:
    bundle = _emit("npm_missing_lock")
    decls = [item for item in bundle.declarations if item.ecosystem == "npm"]
    assert decls
    assert all(item.resolution is ResolutionObservation.UNKNOWN for item in decls)
    assert all(item.coordinate != "" for item in decls)
    assert not [item for item in bundle.resolutions if item.declaration_id]
    m02 = next(item for item in bundle.coverage if item.capability_id == CAP_M02)
    assert m02.unknown >= 1
    assert m02.eligible == len({item.declaration_id for item in decls})


def test_npm_lock_occurrences_are_separate_from_declaration_coverage() -> None:
    bundle = _emit("npm_with_lock")
    decls = [item for item in bundle.declarations if item.ecosystem == "npm"]
    assert decls
    occurrences = [item for item in bundle.resolutions if item.ecosystem == "npm"]
    assert occurrences
    assert any(item.resolved_identity == "left-pad" for item in occurrences)
    m02 = next(item for item in bundle.coverage if item.capability_id == CAP_M02)
    assert m02.eligible == len({item.declaration_id for item in decls})
    assert m02.evaluated <= m02.eligible


def test_ci_facts_prove_configuration_not_execution() -> None:
    bundle = _emit("ci_direct_command")
    assert bundle.ci
    assert bundle.ci_execution_observed is False
    assert all(item.proves_execution is False for item in bundle.ci)
    pytest_row = next(item for item in bundle.ci if item.literal_command == "pytest")
    assert pytest_row.parser_rule == "gha.step.run.literal"
    m03 = next(item for item in bundle.coverage if item.capability_id == CAP_M03)
    assert m03.eligible >= 1


def test_malformed_ci_is_unresolved_not_absent() -> None:
    bundle = _emit("ci_malformed_yaml")
    assert bundle.ci
    assert bundle.ci[0].unresolved is True
    assert bundle.ci[0].proves_execution is False


def test_empty_repo_coverage_is_not_applicable(tmp_path: Path) -> None:
    bundle = InventoryFactEmitter().emit_tree(tmp_path, repository_key="empty")
    m01 = next(item for item in bundle.coverage if item.capability_id == CAP_M01)
    assert m01.coverage_ratio is None
    assert m01.coverage_reason == "zero_eligible_files"


def test_oversize_file_is_bounded_and_visible(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    huge = tmp_path / "src" / "blob.py"
    huge.write_text("x = 1\n" + ("a" * 200), encoding="utf-8")
    bundle = InventoryFactEmitter().emit_tree(tmp_path, repository_key="budget", max_file_bytes=32)
    oversize = next(item for item in bundle.files if item.relative_path.endswith("blob.py"))
    assert oversize.ignore_reason == "oversize"
    assert oversize.unread_reason == "oversize"
    assert oversize.structurally_supported is False
    assert oversize.subject_id.startswith("repo:budget:file:")


def test_no_package_scripts_run_during_emission() -> None:
    root = FIXTURES / "npm_missing_lock"
    marker = root / "EXECUTED"
    if marker.exists():
        marker.unlink()
    bundle = _emit("npm_missing_lock")
    assert bundle.executed_repository_code is False
    assert not marker.exists()


def test_root_manifest_maps_to_repository_component() -> None:
    bundle = _emit("npm_missing_lock")
    mapped = next(
        item for item in bundle.file_component_map if item.relative_path == "package.json"
    )
    assert mapped.component_key == ROOT_COMPONENT_KEY
    assert mapped.component_id == "repo:demo:module:_repository"


def test_evidence_binds_revision_and_digest() -> None:
    bundle = _emit("maven_declared", key="revdemo")
    assert bundle.evidence
    for item in bundle.evidence:
        assert item.working_state_digest == bundle.working_state_digest
        assert item.source_revision == bundle.source_revision
        posix = item.relative_path.replace("\\", "/")
        assert "\\" not in item.relative_path or posix == item.relative_path
        assert not item.relative_path.startswith("/")
