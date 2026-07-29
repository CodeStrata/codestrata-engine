"""Regression tests for scan-boundary and source-role precision (Phase 13.6.3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.application.evidence.language.adapters import classify_source_path
from codestrata.config.settings import CodestrataSettings, ScanBoundarySettings
from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.scan_boundary import (
    BOUNDARY_POLICY_VERSION,
    BoundaryPolicy,
    BoundaryService,
    ScanSourceRole,
    classify_path_role,
    default_ignore_path_markers,
)
from codestrata.security.filesystem import iter_repository_files
from codestrata.services.scanners.local_repository_scanner import LocalRepositoryScanner


def _touch(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_export_staging_excluded_from_platform_root_scan(tmp_path: Path) -> None:
    _touch(tmp_path / "engine" / "src" / "app.py")
    _touch(tmp_path / ".export-staging" / "engine" / "src" / "app.py", "copy\n")
    _touch(tmp_path / "export-staging" / "docs" / "README.md")

    files = LocalRepositoryScanner().scan(tmp_path).files
    assert "engine/src/app.py" in files
    assert all(".export-staging" not in f and "export-staging/" not in f for f in files)


def test_codestrata_examples_excluded_from_platform_root_scan(tmp_path: Path) -> None:
    _touch(tmp_path / "platform" / "main.py")
    _touch(
        tmp_path / ".codestrata-examples" / "spring-petclinic" / "pom.xml",
        "<project/>\n",
    )

    files = LocalRepositoryScanner().scan(tmp_path).files
    assert files == ["platform/main.py"]


def test_directly_selected_example_root_is_scanned(tmp_path: Path) -> None:
    root = tmp_path / ".codestrata-examples" / "spring-petclinic"
    _touch(root / "pom.xml", "<project/>\n")
    _touch(root / "src" / "main" / "java" / "App.java", "class App {}\n")

    files = LocalRepositoryScanner().scan(root).files
    assert "pom.xml" in files
    assert "src/main/java/App.java" in files
    assert any(f.endswith(".java") for f in files)


def test_codestrata_test_knowledge_excluded(tmp_path: Path) -> None:
    _touch(tmp_path / "src" / "app.py")
    _touch(
        tmp_path / ".codestrata-test-knowledge" / "secrets" / "aws.txt",
        "AKIAIOSFODNN7EXAMPLE\n",
    )

    files = LocalRepositoryScanner().scan(tmp_path).files
    assert files == ["src/app.py"]
    assert all(".codestrata-test-knowledge" not in f for f in files)


def test_previous_report_outputs_excluded(tmp_path: Path) -> None:
    _touch(tmp_path / "src" / "app.py")
    _touch(tmp_path / "reports" / "run-1" / "report.json", "{}\n")
    _touch(tmp_path / "reports" / "validation" / "out.json", "{}\n")

    files = LocalRepositoryScanner().scan(tmp_path).files
    assert files == ["src/app.py"]


def test_nested_validation_outputs_excluded(tmp_path: Path) -> None:
    _touch(tmp_path / "lib" / "x.py")
    _touch(tmp_path / "reports" / "validation" / "nested" / "graph.json", "{}\n")
    files = set(LocalRepositoryScanner().scan(tmp_path).files)
    assert files == {"lib/x.py"}


def test_test_fixtures_classified_as_fixture_or_test() -> None:
    assert classify_path_role("src/test/fixtures/data.json") is ScanSourceRole.FIXTURE
    assert classify_source_path("tests/unit/test_app.py") is SourceClassification.TEST
    assert classify_source_path("src/fixtures/sample.yaml") is SourceClassification.FIXTURE


def test_production_roots_override_heuristics() -> None:
    policy = BoundaryPolicy(production_roots=("tests/legacy_prod",))
    service = BoundaryService(policy)
    decision = service.decide("tests/legacy_prod/util.py")
    assert decision.included is True
    assert decision.role is ScanSourceRole.PRODUCTION


def test_explicit_include_overrides_default_exclusion(tmp_path: Path) -> None:
    _touch(tmp_path / "vendor" / "first_party" / "lib.py", "print(1)\n")
    _touch(tmp_path / "app.py")
    policy = BoundaryPolicy(include_paths=("vendor/first_party",))
    files = LocalRepositoryScanner(boundary_policy=policy).scan(tmp_path).files
    assert "app.py" in files
    assert "vendor/first_party/lib.py" in files


def test_explicit_exclude_overrides_heuristic_inclusion(tmp_path: Path) -> None:
    _touch(tmp_path / "src" / "app.py")
    _touch(tmp_path / "src" / "generated_helpers" / "x.py")
    policy = BoundaryPolicy(exclude_paths=("src/generated_helpers",))
    files = LocalRepositoryScanner(boundary_policy=policy).scan(tmp_path).files
    assert files == ["src/app.py"]


def test_repeated_scans_have_stable_file_counts(tmp_path: Path) -> None:
    _touch(tmp_path / "a.py")
    _touch(tmp_path / "b" / "c.py")
    scanner = LocalRepositoryScanner()
    first = scanner.scan(tmp_path).files
    second = scanner.scan(tmp_path).files
    assert first == second
    assert len(first) == 2


def test_security_findings_do_not_arise_from_excluded_synthetic_secrets(
    tmp_path: Path,
) -> None:
    _touch(tmp_path / "ok.py", "print('ok')\n")
    secrets = tmp_path / ".codestrata-test-knowledge" / "aws_key.txt"
    _touch(secrets, "AKIAIOSFODNN7EXAMPLE\n-----BEGIN PRIVATE KEY-----\n")
    repository = LocalRepositoryScanner().scan(tmp_path)
    assert secrets.name not in " ".join(repository.files)
    texts = {path: (tmp_path / path).read_text(encoding="utf-8") for path in repository.files}
    assert all("AKIA" not in body for body in texts.values())
    assert all("PRIVATE KEY" not in body for body in texts.values())


def test_windows_and_posix_path_normalization() -> None:
    service = BoundaryService()
    posix = service.decide("src/main.py")
    windows = service.decide("src\\main.py")
    assert posix.included is windows.included
    assert posix.role is windows.role
    excluded = service.decide(".export-staging\\engine\\app.py")
    assert excluded.included is False


def test_symlink_handling_does_not_escape_repository_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    _touch(outside / "secret.txt", "secret\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    _touch(repo / "app.py")
    (repo / "escape").symlink_to(outside, target_is_directory=True)
    files = LocalRepositoryScanner().scan(repo).files
    assert files == ["app.py"]


def test_no_infinite_traversal_loops(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _touch(repo / "a.py")
    nested = repo / "loop"
    nested.mkdir()
    (nested / "back").symlink_to(repo, target_is_directory=True)
    files = LocalRepositoryScanner().scan(repo).files
    assert files == ["a.py"]


def test_boundary_policy_from_settings() -> None:
    settings = CodestrataSettings.model_validate(
        {
            "repository": {"path": "."},
            "scan": {
                "exclude_paths": ["legacy/"],
                "include_paths": ["vendor/ours"],
                "production_roots": ["tests/prodish"],
                "source_role_overrides": {"docs/api": "production"},
            },
        }
    )
    policy = BoundaryPolicy.from_settings(settings)
    assert "legacy" in policy.exclude_paths[0] or policy.exclude_paths == ("legacy",)
    assert policy.include_paths == ("vendor/ours",)
    assert policy.production_roots == ("tests/prodish",)
    service = BoundaryService(policy)
    assert service.decide("docs/api/spec.md").role is ScanSourceRole.PRODUCTION
    assert service.decide("legacy/old.py").included is False


def test_diagnostics_payload_shape(tmp_path: Path) -> None:
    _touch(tmp_path / "src" / "a.py")
    _touch(tmp_path / ".export-staging" / "x.py")
    scanner = LocalRepositoryScanner()
    scanner.scan(tmp_path)
    payload = scanner.last_diagnostics.to_dict()
    assert payload["policy_version"] == BOUNDARY_POLICY_VERSION
    assert payload["included_files"] == 1
    assert payload["excluded_files"] >= 1
    assert "production" in payload["role_counts"]
    assert isinstance(payload["default_excluded_directories"], list)
    assert ".export-staging" in payload["default_excluded_directories"]
    json.dumps(payload)  # must be serializable


def test_default_ignore_markers_include_codestrata_paths() -> None:
    markers = default_ignore_path_markers()
    assert "/.export-staging/" in markers
    assert "/.codestrata-examples/" in markers
    assert "/.codestrata-test-knowledge/" in markers
    assert "/reports/" in markers


def test_iter_repository_files_uses_shared_service(tmp_path: Path) -> None:
    _touch(tmp_path / "app.py")
    _touch(tmp_path / "node_modules" / "x.js")
    files = iter_repository_files(tmp_path)
    assert files == ["app.py"]


def test_scan_boundary_settings_model() -> None:
    settings = ScanBoundarySettings(
        include_default_directories=["vendor"],
        example_roots=["demos"],
    )
    policy = BoundaryPolicy.from_settings(
        CodestrataSettings.model_validate(
            {"repository": {"path": "."}, "scan": settings.model_dump()}
        )
    )
    assert "vendor" not in policy.excluded_directory_names
    assert policy.example_roots == ("demos",)


@pytest.mark.parametrize(
    ("path", "role"),
    [
        ("examples/demo/App.java", ScanSourceRole.EXAMPLE),
        ("docs/guide.md", ScanSourceRole.DOCUMENTATION),
        ("third_party/lib/x.c", ScanSourceRole.VENDOR),
        ("src/main/App.java", ScanSourceRole.PRODUCTION),
        (
            "src/main/java/org/springframework/samples/petclinic/owner/OwnerController.java",
            ScanSourceRole.PRODUCTION,
        ),
        (
            "src/test/java/org/springframework/samples/petclinic/system/I18nPropertiesSyncTest.java",
            ScanSourceRole.TEST,
        ),
    ],
)
def test_heuristic_roles(path: str, role: ScanSourceRole) -> None:
    assert classify_path_role(path) is role
