"""Integration tests for security analysis in the main pipeline."""

from __future__ import annotations

from pathlib import Path

from codestrata.models import Repository
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
