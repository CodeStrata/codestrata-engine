"""Integration tests for security analysis in the main pipeline."""

from __future__ import annotations

from pathlib import Path

from codestrata.models import Repository
from codestrata.models.enums import Severity
from codestrata.services.analyzers import (
    CompositeAnalyzer,
    SecurityAnalyzer,
)


def test_composite_analyzer_runs_security_analysis(
    tmp_path: Path,
) -> None:
    """The main analyzer pipeline should include security findings."""

    source_file = tmp_path / "src" / "config.js"
    source_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    source_file.write_text(
        'const password = "production-password";',
        encoding="utf-8",
    )

    repository = Repository(
        name=tmp_path.name,
        path=tmp_path,
        files=["src/config.js"],
    )

    result = CompositeAnalyzer(
        analyzers=[SecurityAnalyzer()],
    ).analyze(
        repository=repository,
        technologies=[],
    )

    rule_ids = {finding.rule_id for finding in result.findings if finding.rule_id is not None}

    assert "SEC004" in rule_ids
    secret = next(f for f in result.findings if f.rule_id == "SEC004")
    assert secret.severity is Severity.HIGH
    assert secret.metadata.get("security_context") == "production"
    assert "Context: Production source" in secret.description


def test_composite_analyzer_demotes_fixture_known_secrets(
    tmp_path: Path,
) -> None:
    """Known-token patterns in fixtures stay detected but are demoted."""

    fixture = tmp_path / "test" / "fixtures" / "secrets.ts"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(
        'export const token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef1234";\n',
        encoding="utf-8",
    )

    repository = Repository(
        name=tmp_path.name,
        path=tmp_path,
        files=["test/fixtures/secrets.ts"],
    )

    result = CompositeAnalyzer(
        analyzers=[SecurityAnalyzer()],
    ).analyze(
        repository=repository,
        technologies=[],
    )

    secrets = [f for f in result.findings if f.rule_id == "SEC003"]
    assert secrets, "expected fixture GitHub token still detected (recall)"
    for finding in secrets:
        assert finding.severity is Severity.INFO
        assert finding.metadata.get("security_context") in {
            "test_fixture",
            "mock_credential",
            "test",
        }
        assert "Context:" in finding.description
