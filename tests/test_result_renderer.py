"""Tests for CLI result rendering."""

import json
from pathlib import Path

import pytest

from codestrata.models import (
    AnalysisResult,
    Finding,
    FindingCategory,
    FindingSource,
    Repository,
    Severity,
    Technology,
    TechnologyCategory,
)
from codestrata.result_renderer import render_json, render_text


def _create_result() -> AnalysisResult:
    repository = Repository(
        name="sample",
        path=Path("/tmp/sample"),
        source_url="https://github.com/example/sample",
        files=[
            "pom.xml",
            "src/main/java/Sample.java",
            "src/test/java/SampleTests.java",
        ],
        total_files=3,
    )

    technologies = [
        Technology(
            name="Java",
            category=TechnologyCategory.LANGUAGE,
            confidence=1.0,
            source="file_extension",
        )
    ]

    finding = Finding(
        rule_id="repository.metrics.summary",
        title="Repository Metrics",
        description="Collected repository metrics.",
        category=FindingCategory.MAINTAINABILITY,
        severity=Severity.INFO,
        source=FindingSource.DETERMINISTIC,
        metadata={
            "total_files": 3,
            "source_files": 2,
            "test_files": 1,
            "configuration_files": 1,
            "build_files": 1,
            "docker_files": 0,
            "github_workflows": 0,
            "kubernetes_manifests": 0,
        },
    )

    return AnalysisResult(
        repository=repository,
        technologies=technologies,
        findings=[finding],
        recommendations=[],
        analyzer_version="0.2.0",
    )


def test_render_text_outputs_human_readable_summary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = _create_result()

    render_text(result)

    output = capsys.readouterr().out

    assert "Repository" in output
    assert "sample" in output
    assert "Detected Technologies" in output
    assert "Java" in output
    assert "Source files:" in output
    assert "Test files:" in output

    assert "/tmp/sample" not in output
    assert '"repository"' not in output


def test_render_json_outputs_complete_analysis_result(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = _create_result()

    render_json(result)

    output = capsys.readouterr().out
    payload = json.loads(output)

    assert payload["repository"]["name"] == "sample"
    assert payload["repository"]["path"] == "/tmp/sample"
    assert payload["technologies"][0]["name"] == "Java"
    assert payload["findings"][0]["rule_id"] == "repository.metrics.summary"
