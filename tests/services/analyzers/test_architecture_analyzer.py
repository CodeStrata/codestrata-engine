"""Tests for deterministic architecture analysis."""

from __future__ import annotations

from pathlib import Path

from codestrata.models import Repository
from codestrata.services.analyzers.architecture_analyzer import (
    ArchitectureAnalyzer,
)


def _repository(
    root: Path,
    files: list[str],
) -> Repository:
    """Create a repository fixture with empty files."""

    for relative_path in files:
        file_path = root / relative_path
        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        file_path.write_text(
            "",
            encoding="utf-8",
        )

    return Repository(
        name=root.name,
        path=root,
        files=files,
    )


def _rule_ids(
    repository: Repository,
) -> set[str]:
    """Run the analyzer and return rule identifiers."""

    result = ArchitectureAnalyzer().analyze(
        repository=repository,
        technologies=[],
    )

    return {finding.rule_id for finding in result.findings if finding.rule_id is not None}


def test_detects_layered_architecture(
    tmp_path: Path,
) -> None:
    """Controller, service, and repository folders imply complete layering."""

    repository = _repository(
        tmp_path,
        [
            "src/main/java/com/example/controller/UserController.java",
            "src/main/java/com/example/service/UserService.java",
            "src/main/java/com/example/repository/UserRepository.java",
        ],
    )

    result = ArchitectureAnalyzer().analyze(repository=repository, technologies=[])
    finding = next(item for item in result.findings if item.rule_id == "ARCH001")

    assert finding.title == "Layered application architecture detected"
    assert result.facts.architecture is not None
    assert result.facts.architecture.has_service_layer is True
    assert "ARCH002" in {item.rule_id for item in result.findings}
    assert "ARCH003" in {item.rule_id for item in result.findings}
    assert "ARCH007" in {item.rule_id for item in result.findings}


def test_controllers_and_repositories_without_service_are_partial(
    tmp_path: Path,
) -> None:
    """Controllers plus repositories alone must not claim complete layering."""

    repository = _repository(
        tmp_path,
        [
            "src/main/java/org/example/owner/OwnerController.java",
            "src/main/java/org/example/owner/OwnerRepository.java",
        ],
    )

    result = ArchitectureAnalyzer().analyze(repository=repository, technologies=[])
    finding = next(item for item in result.findings if item.rule_id == "ARCH001")

    assert finding.title == "Application architecture components detected"
    assert finding.metadata["complete_layered_architecture"] is False
    assert result.facts.architecture is not None
    assert result.facts.architecture.has_service_layer is False
    assert result.facts.architecture.has_api_layer is True
    assert result.facts.architecture.has_persistence_layer is True


def test_production_service_class_enables_service_layer(
    tmp_path: Path,
) -> None:
    """A production *Service class should establish the service layer."""

    repository = _repository(
        tmp_path,
        [
            "src/main/java/org/example/owner/OwnerController.java",
            "src/main/java/org/example/owner/ClinicService.java",
            "src/main/java/org/example/owner/OwnerRepository.java",
        ],
    )

    result = ArchitectureAnalyzer().analyze(repository=repository, technologies=[])
    finding = next(item for item in result.findings if item.rule_id == "ARCH001")

    assert finding.title == "Layered application architecture detected"
    assert result.facts.architecture is not None
    assert result.facts.architecture.has_service_layer is True


def test_test_only_service_directories_do_not_enable_service_layer(
    tmp_path: Path,
) -> None:
    """Service classes under test directories must not set has_service_layer."""

    repository = _repository(
        tmp_path,
        [
            "src/main/java/org/example/owner/OwnerController.java",
            "src/main/java/org/example/owner/OwnerRepository.java",
            "src/test/java/org/example/service/FakeClinicService.java",
        ],
    )

    result = ArchitectureAnalyzer().analyze(repository=repository, technologies=[])

    assert result.facts.architecture is not None
    assert result.facts.architecture.has_service_layer is False
    finding = next(item for item in result.findings if item.rule_id == "ARCH001")
    assert finding.title == "Application architecture components detected"


def test_detects_api_layer(
    tmp_path: Path,
) -> None:
    """API directories should be detected."""

    repository = _repository(
        tmp_path,
        [
            "src/api/users.ts",
        ],
    )

    assert "ARCH002" in _rule_ids(repository)


def test_detects_persistence_layer(
    tmp_path: Path,
) -> None:
    """Repository and DAO directories should be detected."""

    repository = _repository(
        tmp_path,
        [
            "src/dao/UserDao.java",
        ],
    )

    assert "ARCH003" in _rule_ids(repository)


def test_reports_missing_test_structure(
    tmp_path: Path,
) -> None:
    """Repositories without conventional test folders should be reported."""

    repository = _repository(
        tmp_path,
        [
            "src/main/java/com/example/Application.java",
        ],
    )

    rule_ids = _rule_ids(repository)

    assert "ARCH004" in rule_ids
    assert "ARCH005" not in rule_ids


def test_detects_test_structure(
    tmp_path: Path,
) -> None:
    """Conventional test directories should be detected."""

    repository = _repository(
        tmp_path,
        [
            "src/test/java/com/example/ApplicationTest.java",
        ],
    )

    rule_ids = _rule_ids(repository)

    assert "ARCH005" in rule_ids
    assert "ARCH004" not in rule_ids


def test_detects_multi_application_repository(
    tmp_path: Path,
) -> None:
    """Apps or packages directories imply a multi-application repository."""

    repository = _repository(
        tmp_path,
        [
            "apps/customer-api/src/index.ts",
            "apps/admin-api/src/index.ts",
        ],
    )

    assert "ARCH006" in _rule_ids(repository)


def test_detects_single_application_structure(
    tmp_path: Path,
) -> None:
    """Multiple architectural components imply one application structure."""

    repository = _repository(
        tmp_path,
        [
            "src/controller/UserController.java",
            "src/service/UserService.java",
        ],
    )

    assert "ARCH007" in _rule_ids(repository)


def test_does_not_infer_architecture_from_unrelated_files(
    tmp_path: Path,
) -> None:
    """Unrelated paths should not produce architecture-shape findings."""

    repository = _repository(
        tmp_path,
        [
            "README.md",
            "LICENSE",
        ],
    )

    rule_ids = _rule_ids(repository)

    assert "ARCH001" not in rule_ids
    assert "ARCH002" not in rule_ids
    assert "ARCH003" not in rule_ids
    assert "ARCH006" not in rule_ids
    assert "ARCH007" not in rule_ids
