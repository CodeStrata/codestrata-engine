"""Repository-testing evidence tests (Phase 4.6.2)."""

from __future__ import annotations

import ast
import json
import random
from pathlib import Path

from codestrata.application.evidence.repository_testing.artifacts import (
    repository_testing_evidence_payload,
    write_repository_testing_evidence_artifact,
)
from codestrata.application.evidence.repository_testing.discovery import (
    classify_test_candidate,
    discover_candidates,
    is_ignored_path,
)
from codestrata.application.evidence.repository_testing.limitations import (
    standard_limitations,
)
from codestrata.application.evidence.repository_testing.service import (
    RepositoryTestingEvidenceService,
)
from codestrata.config import load_settings
from codestrata.config.settings import RepositoryTestingEvidenceSettings
from codestrata.domain.evidence.repository_testing.enums import (
    CoverageFactType,
    EvidenceConfirmationLevel,
    FrameworkEvidenceBasis,
    RepositoryTestingParseStatus,
)
from codestrata.domain.evidence.repository_testing.enums import (
    TestDiscoveryBasis as DiscoveryBasis,
)
from codestrata.domain.evidence.repository_testing.enums import (
    TestFileRole as FileRole,
)
from codestrata.domain.evidence.repository_testing.enums import (
    TestFrameworkFamily as FrameworkFamily,
)
from codestrata.domain.evidence.repository_testing.enums import (
    TestMarkerType as MarkerType,
)
from codestrata.domain.evidence.repository_testing.identifiers import (
    REPOSITORY_TESTING_EVIDENCE_ARTIFACT_FILENAME,
    REPOSITORY_TESTING_EVIDENCE_SCHEMA_VERSION,
    make_bundle_id,
)
from codestrata.domain.evidence.repository_testing.models import (
    AggregatedRepositoryTestingEvidence,
)
from codestrata.domain.testing.assessment.identifiers import (
    SECTION_SCHEMA_VERSION as TESTING_ASSESSMENT_SCHEMA_VERSION,
)
from codestrata.services.artifact_serialization import dumps_stable_json

_APP_PACKAGE = Path(
    "src/codestrata/application/evidence/repository_testing"
)
_FORBIDDEN_IMPORT_PREFIXES = (
    "codestrata.domain.testing",
    "codestrata.application.testing",
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
        assert "emit_finding" not in source.lower()
        assert "from codestrata.domain.findings" not in source
        assert "FindingCategory" not in source


def test_collecting_evidence_does_not_create_findings() -> None:
    service = RepositoryTestingEvidenceService(
        RepositoryTestingEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="fixture",
        relative_paths=("tests/test_sample.py",),
        file_texts={
            "tests/test_sample.py": (
                "import pytest\n"
                "@pytest.mark.skip\n"
                "def test_ok():\n"
                "    assert True\n"
            ),
        },
    )
    payload = repository_testing_evidence_payload(evidence)
    text = dumps_stable_json(payload)
    assert "Finding" not in text
    assert "finding_id" not in text
    assert "severity" not in text.lower()
    assert evidence.marker_facts
    assert all("Finding" not in item.summary for item in evidence.limitations)


def test_discovery_dirs_filenames_and_exclusions() -> None:
    paths = (
        "tests/test_foo.py",
        "src/test/java/com/example/FooTest.java",
        "src/test/java/com/example/FooIT.java",
        "__tests__/widget.test.ts",
        "cypress/e2e/login.cy.js",
        "fixtures/sample.json",
        "src/main/java/com/example/Controllers.java",
        "src/main/python/service.py",
        "node_modules/pkg/test_foo.py",
        "target/test-classes/FooTest.java",
        "vendor/lib/foo_test.go",
        "pkg/foo_test.go",
    )
    found = discover_candidates(paths)
    by_path = {path: (role, bases, lang) for path, role, bases, lang in found}

    assert "tests/test_foo.py" in by_path
    assert DiscoveryBasis.DIRECTORY_CONVENTION in by_path["tests/test_foo.py"][1]
    assert DiscoveryBasis.FILENAME_CONVENTION in by_path["tests/test_foo.py"][1]

    assert "src/test/java/com/example/FooTest.java" in by_path
    assert by_path["src/test/java/com/example/FooTest.java"][0] is FileRole.UNIT_TEST

    assert "src/test/java/com/example/FooIT.java" in by_path
    assert (
        by_path["src/test/java/com/example/FooIT.java"][0]
        is FileRole.INTEGRATION_TEST
    )

    assert "__tests__/widget.test.ts" in by_path
    assert by_path["cypress/e2e/login.cy.js"][0] is FileRole.END_TO_END_TEST
    assert by_path["fixtures/sample.json"][0] is FileRole.TEST_FIXTURE
    assert "pkg/foo_test.go" in by_path

    assert "src/main/java/com/example/Controllers.java" not in by_path
    assert "src/main/python/service.py" not in by_path
    assert "node_modules/pkg/test_foo.py" not in by_path
    assert "target/test-classes/FooTest.java" not in by_path
    assert "vendor/lib/foo_test.go" not in by_path

    # Visit.java must not match *IT.java via lowercase endswith("it.java").
    assert classify_test_candidate(
        "src/main/java/org/example/owner/Visit.java"
    ) == (None, (), None)
    assert classify_test_candidate("tests/.DS_Store") == (None, (), None)
    integration_role, _, _ = classify_test_candidate(
        "src/test/java/org/example/MySqlIntegrationTests.java"
    )
    assert integration_role is FileRole.INTEGRATION_TEST

    assert is_ignored_path(
        "node_modules/pkg/test_foo.py",
        ignore_markers=("/node_modules/",),
    )
    assert is_ignored_path("target/x", ignore_markers=("/target/",))
    assert is_ignored_path("vendor/x", ignore_markers=("/vendor/",))

    role, bases, _ = classify_test_candidate("tests/test_foo.py")
    assert role is FileRole.UNIT_TEST
    assert DiscoveryBasis.DIRECTORY_CONVENTION in bases
    assert DiscoveryBasis.FILENAME_CONVENTION in bases


def test_candidate_confirmation_is_discovered_until_inspected() -> None:
    service = RepositoryTestingEvidenceService(
        RepositoryTestingEvidenceSettings(enabled=True)
    )
    # Discovered path without text stays discovered_candidate (or skipped).
    evidence = service.collect(
        repository_id="fixture",
        relative_paths=("tests/test_pending.py",),
        file_texts={},
        load_errors={"tests/test_pending.py": "file_too_large"},
    )
    assert len(evidence.file_candidates) == 1
    candidate = evidence.file_candidates[0]
    assert (
        candidate.confirmation_level
        is EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    )
    assert candidate.confirmation_level is not EvidenceConfirmationLevel.DECLARED
    assert DiscoveryBasis.DIRECTORY_CONVENTION in candidate.discovery_bases


def test_structural_indicators_across_languages() -> None:
    service = RepositoryTestingEvidenceService(
        RepositoryTestingEvidenceSettings(enabled=True)
    )
    paths = (
        "tests/test_pytest.py",
        "src/test/java/ExampleTest.java",
        "__tests__/widget.test.ts",
        "e2e/login.spec.ts",
        "pkg/foo_test.go",
        "tests/broken.xyz",
    )
    texts = {
        "tests/test_pytest.py": (
            "import pytest\n"
            "class TestThing:\n"
            "    pass\n"
            "@pytest.fixture\n"
            "def client():\n"
            "    return 1\n"
            "@pytest.mark.skip\n"
            "def test_one():\n"
            "    assert True\n"
        ),
        "src/test/java/ExampleTest.java": (
            "import org.junit.jupiter.api.Test;\n"
            "import org.junit.jupiter.api.Disabled;\n"
            "class ExampleTest {\n"
            "  @Disabled\n"
            "  @Test void runs() {}\n"
            "}\n"
        ),
        "__tests__/widget.test.ts": (
            "describe('widget', () => {\n"
            "  test('renders', () => {});\n"
            "  test.skip('later', () => {});\n"
            "});\n"
        ),
        "e2e/login.spec.ts": (
            "import { test } from '@playwright/test';\n"
            "test('login', async () => {});\n"
        ),
        "pkg/foo_test.go": "func TestFoo(t *testing.T) {}\n",
        "tests/broken.xyz": "not a supported structural body\n",
    }
    evidence = service.collect(
        repository_id="fixture",
        relative_paths=paths,
        file_texts=texts,
        load_errors={"tests/broken.xyz": "unsupported_encoding"},
    )
    by_path = {item.path: item for item in evidence.structural_test_facts}

    assert "python_def_test" in by_path["tests/test_pytest.py"].structural_counts
    assert "python_class_test" in by_path["tests/test_pytest.py"].structural_counts
    assert "pytest_fixture" in by_path["tests/test_pytest.py"].structural_counts
    assert FrameworkFamily.PYTEST in by_path["tests/test_pytest.py"].framework_hints

    assert "java_test" in by_path["src/test/java/ExampleTest.java"].structural_counts
    assert "java_disabled" in by_path["src/test/java/ExampleTest.java"].structural_counts

    assert "js_describe" in by_path["__tests__/widget.test.ts"].structural_counts
    assert "js_test" in by_path["__tests__/widget.test.ts"].structural_counts
    assert "js_test_skip" in by_path["__tests__/widget.test.ts"].structural_counts

    assert (
        "playwright_import" in by_path["e2e/login.spec.ts"].structural_counts
        or "js_test" in by_path["e2e/login.spec.ts"].structural_counts
    )
    assert "go_func_test" in by_path["pkg/foo_test.go"].structural_counts

    assert any(d.diagnostic_code == "unsupported_encoding" for d in evidence.diagnostics)
    assert evidence.coverage.unsupported_candidate_files >= 1


def test_frameworks_declared_vs_structurally_observed() -> None:
    service = RepositoryTestingEvidenceService(
        RepositoryTestingEvidenceSettings(enabled=True)
    )
    pom = """
    <project>
      <dependencies>
        <dependency>
          <groupId>junit</groupId>
          <artifactId>junit</artifactId>
          <version>4.13.2</version>
        </dependency>
      </dependencies>
      <build>
        <plugins>
          <plugin>
            <artifactId>maven-surefire-plugin</artifactId>
            <version>3.0.0</version>
          </plugin>
        </plugins>
      </build>
    </project>
    """
    package_json = json.dumps(
        {
            "devDependencies": {"jest": "^29.0.0"},
            "scripts": {"test": "jest"},
        }
    )
    pyproject = "[project]\ndependencies = [\"pytest>=8\"]\n"
    requirements = "pytest==8.0.0\n"
    evidence = service.collect(
        repository_id="fixture",
        relative_paths=(
            "pom.xml",
            "package.json",
            "pyproject.toml",
            "requirements.txt",
            "tests/test_sample.py",
        ),
        file_texts={
            "pom.xml": pom,
            "package.json": package_json,
            "pyproject.toml": pyproject,
            "requirements.txt": requirements,
            "tests/test_sample.py": "def test_ok():\n    assert True\n",
        },
    )
    declared = {
        item.framework
        for item in evidence.framework_facts
        if item.basis is FrameworkEvidenceBasis.DECLARED
    }
    observed = {
        item.framework
        for item in evidence.framework_facts
        if item.basis is FrameworkEvidenceBasis.STRUCTURALLY_OBSERVED
    }
    assert FrameworkFamily.JUNIT in declared
    assert FrameworkFamily.SUREFIRE in declared
    assert FrameworkFamily.JEST in declared
    assert FrameworkFamily.PYTEST in declared
    assert FrameworkFamily.PYTEST in observed
    # Same family may appear under both bases when both exist.
    pytest_bases = {
        item.basis
        for item in evidence.framework_facts
        if item.framework is FrameworkFamily.PYTEST
    }
    assert FrameworkEvidenceBasis.DECLARED in pytest_bases
    assert FrameworkEvidenceBasis.STRUCTURALLY_OBSERVED in pytest_bases
    assert evidence.coverage.frameworks_declared >= 1
    assert evidence.coverage.frameworks_structurally_observed >= 1


def test_test_type_classifications() -> None:
    service = RepositoryTestingEvidenceService(
        RepositoryTestingEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="fixture",
        relative_paths=(
            "src/test/java/FooIT.java",
            "cypress/e2e/flow.cy.js",
            "tests/integration/test_api.py",
        ),
        file_texts={
            "src/test/java/FooIT.java": "@Test void it() {}\n",
            "cypress/e2e/flow.cy.js": "cy.visit('/');\n",
            "tests/integration/test_api.py": "def test_api():\n    assert True\n",
        },
    )
    roles = {item.path: item.role for item in evidence.file_candidates}
    assert roles["src/test/java/FooIT.java"] is FileRole.INTEGRATION_TEST
    assert roles["cypress/e2e/flow.cy.js"] is FileRole.END_TO_END_TEST
    assert roles["tests/integration/test_api.py"] is FileRole.INTEGRATION_TEST

    # Overlapping discovery bases preserved when applicable.
    it_candidate = next(
        item
        for item in evidence.file_candidates
        if item.path == "src/test/java/FooIT.java"
    )
    assert DiscoveryBasis.FILENAME_CONVENTION in it_candidate.discovery_bases
    assert DiscoveryBasis.DIRECTORY_CONVENTION in it_candidate.discovery_bases


def test_markers_collected_without_findings() -> None:
    service = RepositoryTestingEvidenceService(
        RepositoryTestingEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="fixture",
        relative_paths=(
            "src/test/java/SkipTest.java",
            "tests/test_skip.py",
            "__tests__/focus.test.ts",
        ),
        file_texts={
            "src/test/java/SkipTest.java": "@Disabled\n@Test void x() {}\n",
            "tests/test_skip.py": (
                "@pytest.mark.skip\n"
                "@pytest.mark.skipif(True)\n"
                "@pytest.mark.xfail\n"
                "def test_a():\n"
                "    pass\n"
            ),
            "__tests__/focus.test.ts": (
                "test.skip('a', () => {});\n"
                "test.only('b', () => {});\n"
            ),
        },
    )
    types = {item.marker_type for item in evidence.marker_facts}
    assert MarkerType.DISABLED in types
    assert MarkerType.SKIPPED in types
    assert MarkerType.CONDITIONAL_SKIP in types
    assert MarkerType.EXPECTED_FAILURE in types
    assert MarkerType.FOCUSED in types
    payload = dumps_stable_json(repository_testing_evidence_payload(evidence))
    assert "Finding" not in payload
    assert "severity" not in payload.lower()


def test_fixtures_metadata_only_no_content() -> None:
    service = RepositoryTestingEvidenceService(
        RepositoryTestingEvidenceSettings(enabled=True)
    )
    secret_fixture = '{"password":"should-not-appear","rows":[1,2,3]}'
    evidence = service.collect(
        repository_id="fixture",
        relative_paths=("fixtures/users.json", "tests/test_ok.py"),
        file_texts={
            "fixtures/users.json": secret_fixture,
            "tests/test_ok.py": "def test_ok():\n    assert True\n",
        },
    )
    assert evidence.fixture_facts
    assert any(item.path == "fixtures/users.json" for item in evidence.fixture_facts)
    payload = dumps_stable_json(repository_testing_evidence_payload(evidence))
    assert "should-not-appear" not in payload
    assert "[1,2,3]" not in payload


def test_coverage_configuration_no_percentages() -> None:
    service = RepositoryTestingEvidenceService(
        RepositoryTestingEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="fixture",
        relative_paths=(".coveragerc", "pom.xml", "tests/test_ok.py"),
        file_texts={
            ".coveragerc": "[run]\nsource = src\nomit = */tests/*\n",
            "pom.xml": (
                "<plugin><artifactId>jacoco-maven-plugin</artifactId></plugin>\n"
            ),
            "tests/test_ok.py": "def test_ok():\n    assert True\n",
        },
    )
    assert evidence.coverage_facts
    assert any(
        item.fact_type is CoverageFactType.COVERAGE_CONFIGURATION
        for item in evidence.coverage_facts
    )
    assert evidence.coverage.coverage_configurations >= 1
    # Jacoco plugin mention is recorded as declared framework evidence.
    assert any(
        item.framework is FrameworkFamily.JACOCO
        for item in evidence.framework_facts
    )
    payload = dumps_stable_json(repository_testing_evidence_payload(evidence))
    for forbidden in (
        "percentage",
        "line_rate",
        "branch_rate",
        "coverage_percent",
        "percent_covered",
    ):
        assert forbidden not in payload.lower()


def test_ci_invocation_redaction_and_relative_paths() -> None:
    service = RepositoryTestingEvidenceService(
        RepositoryTestingEvidenceSettings(enabled=True)
    )
    workflow = """
name: CI
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Run tests
        continue-on-error: true
        run: TOKEN=secret npm test
"""
    evidence = service.collect(
        repository_id="fixture",
        relative_paths=(".github/workflows/ci.yml", "tests/test_ok.py"),
        file_texts={
            ".github/workflows/ci.yml": workflow,
            "tests/test_ok.py": "def test_ok():\n    assert True\n",
        },
    )
    assert evidence.ci_test_invocation_facts
    ci = evidence.ci_test_invocation_facts[0]
    assert ci.continue_on_error is True
    assert "TOKEN=***" in ci.command_projection
    assert "secret" not in ci.command_projection
    payload = dumps_stable_json(repository_testing_evidence_payload(evidence))
    assert "secret" not in payload
    assert "/Users/" not in payload
    assert "/Users/satish" not in payload


def test_lifecycle_disabled_succeeded_partial_insufficient() -> None:
    disabled = RepositoryTestingEvidenceService(
        RepositoryTestingEvidenceSettings(enabled=False)
    )
    na = disabled.collect(
        repository_id="fixture",
        relative_paths=("tests/test_ok.py",),
        file_texts={"tests/test_ok.py": "def test_ok():\n    assert True\n"},
    )
    assert na.status is RepositoryTestingParseStatus.NOT_APPLICABLE
    assert na.file_candidates == ()

    enabled = RepositoryTestingEvidenceService(
        RepositoryTestingEvidenceSettings(enabled=True)
    )
    ok = enabled.collect(
        repository_id="fixture",
        relative_paths=("tests/test_ok.py", "fixtures/data.json"),
        file_texts={
            "tests/test_ok.py": "def test_ok():\n    assert True\n",
            "fixtures/data.json": "{}",
        },
    )
    assert ok.status is RepositoryTestingParseStatus.SUCCEEDED
    assert ok.fixture_facts

    partial = enabled.collect(
        repository_id="fixture",
        relative_paths=("tests/test_ok.py", "tests/test_big.py"),
        file_texts={"tests/test_ok.py": "def test_ok():\n    assert True\n"},
        load_errors={"tests/test_big.py": "file_too_large"},
    )
    assert partial.status is RepositoryTestingParseStatus.PARTIALLY_SUCCEEDED
    assert partial.file_candidates
    assert partial.diagnostics

    # Orchestration-level empty inventory construction (collector has paths).
    insufficient = AggregatedRepositoryTestingEvidence(
        bundle_id=make_bundle_id(
            repository_id="empty", fingerprint="insufficient"
        ),
        repository_id="empty",
        status=RepositoryTestingParseStatus.INSUFFICIENT_EVIDENCE,
        limitations=standard_limitations(),
        evidence_fingerprint="insufficient",
    )
    assert (
        insufficient.status
        is RepositoryTestingParseStatus.INSUFFICIENT_EVIDENCE
    )


def test_coverage_summary_reconciles_with_record_lengths() -> None:
    service = RepositoryTestingEvidenceService(
        RepositoryTestingEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="fixture",
        relative_paths=(
            "tests/test_ok.py",
            "fixtures/data.json",
            ".coveragerc",
            "package.json",
            ".github/workflows/ci.yml",
        ),
        file_texts={
            "tests/test_ok.py": (
                "@pytest.mark.skip\ndef test_ok():\n    assert True\n"
            ),
            "fixtures/data.json": "{}",
            ".coveragerc": "[run]\nsource=src\n",
            "package.json": json.dumps(
                {"devDependencies": {"jest": "29"}, "scripts": {"test": "jest"}}
            ),
            ".github/workflows/ci.yml": "jobs:\n  t:\n    steps:\n"
            "      - run: npm test\n",
        },
    )
    cov = evidence.coverage
    assert cov.candidate_test_files_discovered == len(evidence.file_candidates)
    assert cov.marker_facts == len(evidence.marker_facts)
    assert cov.fixture_support_candidates == len(evidence.fixture_facts)
    assert cov.coverage_configurations == sum(
        1
        for item in evidence.coverage_facts
        if "configuration" in item.fact_type.value
    )
    assert cov.frameworks_declared == sum(
        1
        for item in evidence.framework_facts
        if item.basis is FrameworkEvidenceBasis.DECLARED
    )
    assert cov.frameworks_structurally_observed == sum(
        1
        for item in evidence.framework_facts
        if item.basis is FrameworkEvidenceBasis.STRUCTURALLY_OBSERVED
    )


def test_determinism_shuffle_paths() -> None:
    service = RepositoryTestingEvidenceService(
        RepositoryTestingEvidenceSettings(enabled=True)
    )
    paths = [
        "tests/test_b.py",
        "tests/test_a.py",
        "package.json",
        "fixtures/x.json",
        ".github/workflows/ci.yml",
    ]
    texts = {
        "tests/test_b.py": "def test_b():\n    assert True\n",
        "tests/test_a.py": "def test_a():\n    assert True\n",
        "package.json": json.dumps(
            {"devDependencies": {"jest": "29"}, "scripts": {"test": "jest"}}
        ),
        "fixtures/x.json": "{}",
        ".github/workflows/ci.yml": "- run: npm test\n",
    }
    first_paths = list(paths)
    second_paths = list(paths)
    random.Random(7).shuffle(second_paths)
    first = service.collect(
        repository_id="fixture",
        relative_paths=tuple(first_paths),
        file_texts=texts,
    )
    second = service.collect(
        repository_id="fixture",
        relative_paths=tuple(second_paths),
        file_texts={k: texts[k] for k in reversed(list(texts))},
    )
    assert first.bundle_id == second.bundle_id
    assert first.evidence_fingerprint == second.evidence_fingerprint
    a = dumps_stable_json(repository_testing_evidence_payload(first))
    b = dumps_stable_json(repository_testing_evidence_payload(second))
    assert a == b
    assert first.schema_version == REPOSITORY_TESTING_EVIDENCE_SCHEMA_VERSION


def test_artifact_write_stable(tmp_path: Path) -> None:
    service = RepositoryTestingEvidenceService(
        RepositoryTestingEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="fixture",
        relative_paths=("tests/test_ok.py",),
        file_texts={"tests/test_ok.py": "def test_ok():\n    assert True\n"},
    )
    write = write_repository_testing_evidence_artifact(evidence, tmp_path)
    again = write_repository_testing_evidence_artifact(evidence, tmp_path)
    assert write.path.name == REPOSITORY_TESTING_EVIDENCE_ARTIFACT_FILENAME
    assert write.path.read_bytes() == again.path.read_bytes()


def test_settings_default_false_and_enable(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    assert settings.evidence.repository_testing.enabled is False

    config.write_text(
        """
        [repository]
        path = "."
        [evidence.repository_testing]
        enabled = true
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.evidence.repository_testing.enabled is True


def test_independent_of_testing_gates(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        [evidence.repository_testing]
        enabled = true
        [rules.testing]
        enabled = false
        [assessment.sections.testing]
        enabled = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.evidence.repository_testing.enabled is True
    assert settings.rules.testing.enabled is False
    assert settings.assessment.sections.testing.enabled is False


def test_regression_testing_assessment_and_security_imports() -> None:
    from codestrata.application.evidence.repository_sensitive.service import (
        RepositorySensitiveEvidenceService,
    )
    from codestrata.application.testing.assessment.assembler import (
        TestAssessmentAssembler,
    )
    from codestrata.config.settings import RepositorySensitiveEvidenceSettings
    from codestrata.domain.testing.assessment.identifiers import SCHEMA_NAME

    assert TESTING_ASSESSMENT_SCHEMA_VERSION == "1.2.0"
    assert SCHEMA_NAME == "testing-assessment"
    section = TestAssessmentAssembler().assemble_empty(
        repository_id="fixture", pack_enabled=True
    )
    assert section.section_version == "1.2.0"
    assert section.findings == ()
    assert section.execution_summary.total_finding_count == 0

    # Security evidence import path remains usable.
    sensitive = RepositorySensitiveEvidenceService(
        RepositorySensitiveEvidenceSettings(enabled=False)
    )
    evidence = sensitive.collect(
        repository_id="fixture",
        relative_paths=(),
        file_texts={},
    )
    assert evidence is not None
