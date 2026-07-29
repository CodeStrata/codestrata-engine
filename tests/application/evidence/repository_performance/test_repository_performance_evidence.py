"""Repository performance evidence tests (Phase 4.9.2)."""

from __future__ import annotations

import ast
import random
from pathlib import Path

from codestrata.application.evidence.repository_performance.artifacts import (
    repository_performance_evidence_payload,
    write_repository_performance_evidence_artifact,
)
from codestrata.application.evidence.repository_performance.discovery import (
    classify_performance_candidate,
    discover_performance_candidates,
    is_ignored_path,
)
from codestrata.application.evidence.repository_performance.service import (
    RepositoryPerformanceEvidenceService,
)
from codestrata.config import load_settings
from codestrata.config.settings import RepositoryPerformanceEvidenceSettings
from codestrata.domain.evidence.repository_performance.enums import (
    PerformanceBlockingKind,
    PerformanceCachingKind,
    PerformanceConcurrencyKind,
    PerformanceConfigurationKind,
    PerformanceDataAccessKind,
    PerformanceEvidenceFamily,
    PerformanceFrontendKind,
    PerformanceObservabilityKind,
    PerformanceResourceKind,
    RepositoryPerformanceParseStatus,
)
from codestrata.domain.evidence.repository_performance.identifiers import (
    REPOSITORY_PERFORMANCE_EVIDENCE_ARTIFACT_FILENAME,
    REPOSITORY_PERFORMANCE_EVIDENCE_SCHEMA_VERSION,
)
from codestrata.services.artifact_serialization import dumps_stable_json

_APP_PACKAGE = Path("src/codestrata/application/evidence/repository_performance")
_FORBIDDEN_IMPORT_PREFIXES = (
    "codestrata.domain.performance",
    "codestrata.application.performance",
    "codestrata.domain.findings",
    "codestrata.application.reporting",
    "codestrata.reporting",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]  # engine root


def test_package_boundary_no_forbidden_imports() -> None:
    package_dir = _repo_root() / _APP_PACKAGE
    assert package_dir.is_dir()
    for path in sorted(package_dir.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name
                    assert not any(
                        mod == prefix or mod.startswith(prefix + ".")
                        for prefix in _FORBIDDEN_IMPORT_PREFIXES
                    ), f"{path.name} imports {mod}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                mod = node.module
                assert not any(
                    mod == prefix or mod.startswith(prefix + ".")
                    for prefix in _FORBIDDEN_IMPORT_PREFIXES
                ), f"{path.name} imports from {mod}"
        assert "FindingCategory" not in source
        assert "emit_finding" not in source.lower()


def test_defaults_disabled(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    assert settings.evidence.repository_performance.enabled is False
    assert settings.analysis.performance.enabled is False
    assert settings.evidence.repository_ai_readiness.enabled is False


def test_configuration_enablement(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."

        [evidence.repository_performance]
        enabled = true
        max_files = 100
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.evidence.repository_performance.enabled is True
    assert settings.evidence.repository_performance.max_files == 100
    assert settings.analysis.performance.enabled is False
    assert settings.evidence.repository_ai_readiness.enabled is False


def test_disabled_returns_not_applicable() -> None:
    service = RepositoryPerformanceEvidenceService(
        RepositoryPerformanceEvidenceSettings(enabled=False)
    )
    evidence = service.collect(
        repository_id="repo:x",
        relative_paths=("PetEntity.java",),
        file_texts={"PetEntity.java": "@Entity\nclass Pet {}\n"},
    )
    assert evidence.status is RepositoryPerformanceParseStatus.NOT_APPLICABLE
    assert evidence.file_candidates == ()


def test_empty_non_performance_repo_succeeds() -> None:
    service = RepositoryPerformanceEvidenceService(
        RepositoryPerformanceEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="repo:plain",
        relative_paths=("src/main.py", "src/utils.py"),
        file_texts={"src/main.py": "print('hi')\n", "src/utils.py": "x = 1\n"},
    )
    assert evidence.status is RepositoryPerformanceParseStatus.SUCCEEDED
    assert evidence.file_candidates == ()
    assert evidence.coverage.candidate_files_discovered == 0
    assert evidence.limitations


def test_readme_only_non_performance_repo() -> None:
    service = RepositoryPerformanceEvidenceService(
        RepositoryPerformanceEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="repo:readme",
        relative_paths=("README.md",),
        file_texts={"README.md": "# Demo\n"},
    )
    assert evidence.status is RepositoryPerformanceParseStatus.SUCCEEDED
    assert evidence.file_candidates == () or evidence.coverage.candidate_files_discovered == 0


def test_family_data_access() -> None:
    service = RepositoryPerformanceEvidenceService(
        RepositoryPerformanceEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="repo:data",
        relative_paths=("src/PetEntity.java",),
        file_texts={"src/PetEntity.java": "@Entity\npublic class Pet {}\n"},
    )
    assert evidence.data_access_facts
    assert any(item.kind is PerformanceDataAccessKind.JPA for item in evidence.data_access_facts)
    assert PerformanceEvidenceFamily.DATA_ACCESS.value in evidence.coverage.families_represented


def test_family_blocking_operations() -> None:
    service = RepositoryPerformanceEvidenceService(
        RepositoryPerformanceEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="repo:blocking",
        relative_paths=("src/RestTemplateClient.java",),
        file_texts={
            "src/RestTemplateClient.java": (
                "class Client {\n  void pause() { Thread.sleep(10); }\n}\n"
            )
        },
    )
    assert evidence.blocking_operations_facts
    assert any(
        item.kind is PerformanceBlockingKind.THREAD_SLEEP
        for item in evidence.blocking_operations_facts
    )


def test_family_caching() -> None:
    service = RepositoryPerformanceEvidenceService(
        RepositoryPerformanceEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="repo:cache",
        relative_paths=("src/UserCache.java",),
        file_texts={"src/UserCache.java": "@Cacheable\npublic class UserCache {}\n"},
    )
    assert evidence.caching_facts
    assert any(item.kind is PerformanceCachingKind.SPRING_CACHE for item in evidence.caching_facts)


def test_family_concurrency_async() -> None:
    service = RepositoryPerformanceEvidenceService(
        RepositoryPerformanceEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="repo:concurrency",
        relative_paths=("src/AsyncWorker.java",),
        file_texts={
            "src/AsyncWorker.java": (
                "import java.util.concurrent.CompletableFuture;\n"
                "class AsyncWorker {\n  CompletableFuture<Void> run() { return null; }\n}\n"
            )
        },
    )
    assert evidence.concurrency_async_facts
    assert any(
        item.kind is PerformanceConcurrencyKind.COMPLETABLE_FUTURE
        for item in evidence.concurrency_async_facts
    )


def test_family_resource_management() -> None:
    service = RepositoryPerformanceEvidenceService(
        RepositoryPerformanceEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="repo:resource",
        relative_paths=("src/HikariPoolConfig.java",),
        file_texts={"src/HikariPoolConfig.java": "HikariDataSource ds = new HikariDataSource();\n"},
    )
    assert evidence.resource_management_facts
    assert any(
        item.kind is PerformanceResourceKind.HIKARICP for item in evidence.resource_management_facts
    )


def test_family_frontend_performance() -> None:
    service = RepositoryPerformanceEvidenceService(
        RepositoryPerformanceEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="repo:frontend",
        relative_paths=("webpack.config.js",),
        file_texts={
            "webpack.config.js": ("module.exports = { optimization: { splitChunks: {} } };\n")
        },
    )
    assert evidence.frontend_performance_facts
    assert any(
        item.kind is PerformanceFrontendKind.WEBPACK for item in evidence.frontend_performance_facts
    )


def test_family_observability_profiling() -> None:
    service = RepositoryPerformanceEvidenceService(
        RepositoryPerformanceEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="repo:obs",
        relative_paths=("src/MicrometerConfig.java",),
        file_texts={
            "src/MicrometerConfig.java": "MeterRegistry registry;\n@Timed\nvoid timed() {}\n"
        },
    )
    assert evidence.observability_profiling_facts
    assert any(
        item.kind is PerformanceObservabilityKind.MICROMETER
        for item in evidence.observability_profiling_facts
    )


def test_family_configuration_controls() -> None:
    service = RepositoryPerformanceEvidenceService(
        RepositoryPerformanceEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="repo:config",
        relative_paths=("application.yml",),
        file_texts={
            "application.yml": (
                "server.tomcat.threads.max: 200\n"
                "spring.datasource.hikari.maximumPoolSize: 10\n"
                "timeout: 5s\n"
            )
        },
    )
    assert evidence.configuration_controls_facts
    assert any(
        item.kind
        in {
            PerformanceConfigurationKind.THREAD_POOL,
            PerformanceConfigurationKind.DATASOURCE_CONFIG,
            PerformanceConfigurationKind.TIMEOUT_CONFIG,
        }
        for item in evidence.configuration_controls_facts
    )


def test_discover_sorted_and_ignored() -> None:
    paths = [
        "node_modules/pkg/webpack.config.js",
        "webpack.config.js",
        "PetEntity.java",
    ]
    found = discover_performance_candidates(paths)
    assert [item.path for item in found] == ["PetEntity.java", "webpack.config.js"]
    assert is_ignored_path("node_modules/pkg/webpack.config.js", ignore_markers=("/node_modules/",))
    hit = classify_performance_candidate("PetEntity.java")
    assert hit is not None
    assert hit.data_kind is PerformanceDataAccessKind.JPA


def test_deterministic_byte_identical(tmp_path: Path) -> None:
    service = RepositoryPerformanceEvidenceService(
        RepositoryPerformanceEvidenceSettings(enabled=True)
    )
    paths = [
        "PetEntity.java",
        "UserCache.java",
        "webpack.config.js",
        "application.yml",
    ]
    texts = {
        "PetEntity.java": "@Entity\nclass Pet {}\n",
        "UserCache.java": "@Cacheable\nclass UserCache {}\n",
        "webpack.config.js": "module.exports = { optimization: { splitChunks: {} } };\n",
        "application.yml": "spring.datasource.hikari.maximumPoolSize: 10\ntimeout: 5s\n",
    }
    shuffled = paths[:]
    random.Random(7).shuffle(shuffled)
    left = service.collect(
        repository_id="repo:det",
        relative_paths=tuple(shuffled),
        file_texts=texts,
    )
    right = service.collect(
        repository_id="repo:det",
        relative_paths=tuple(reversed(paths)),
        file_texts=texts,
    )
    left_text = dumps_stable_json(repository_performance_evidence_payload(left))
    right_text = dumps_stable_json(repository_performance_evidence_payload(right))
    assert left_text == right_text
    assert left.evidence_fingerprint == right.evidence_fingerprint
    assert left.schema_version == REPOSITORY_PERFORMANCE_EVIDENCE_SCHEMA_VERSION

    written = write_repository_performance_evidence_artifact(left, tmp_path)
    assert written.path.name == REPOSITORY_PERFORMANCE_EVIDENCE_ARTIFACT_FILENAME
    assert written.path.read_text(encoding="utf-8") == left_text
    again = write_repository_performance_evidence_artifact(right, tmp_path / "b")
    assert again.path.read_text(encoding="utf-8") == left_text

    assert "Finding" not in left_text
    assert "severity" not in left_text.lower()
    assert "performance_score" not in left_text
    assert "/Users/" not in left_text


def test_dedupe_technologies() -> None:
    service = RepositoryPerformanceEvidenceService(
        RepositoryPerformanceEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="repo:dedupe",
        relative_paths=("a/UserCache.java", "b/OrderCache.java"),
        file_texts={
            "a/UserCache.java": "@Cacheable\nclass UserCache {}\n",
            "b/OrderCache.java": "@Cacheable\nclass OrderCache {}\n",
        },
    )
    assert len(evidence.caching_facts) == 2
    assert evidence.coverage.technologies_represented.count("spring_cache") == 1
