"""Integration tests for static-analysis reporters and baseline comparison."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from codestrata.models import (
    AnalysisResult,
    Evidence,
    Finding,
    FindingCategory,
    FindingSource,
    Repository,
    Severity,
)
from codestrata.models.scan_comparison import ScanComparison
from codestrata.reporters import ConsoleReporter, HtmlFileReporter, TextFileReporter
from codestrata.services.scan_comparison_service import ScanComparisonService
from codestrata.static_analysis.models import StaticAnalysisResult, StaticAnalysisStatus


def _pmd_finding(path: str = "src/main/java/A.java", line: int = 10) -> Finding:
    return Finding(
        rule_id="PMD.JAVA.BESTPRACTICES.UNUSEDPRIVATEFIELD",
        title="Unused private field",
        description="Avoid unused private fields",
        category=FindingCategory.MAINTAINABILITY,
        severity=Severity.INFO,
        source=FindingSource.EXTERNAL_STATIC_ANALYSIS,
        evidence=[
            Evidence(
                file_path=path,
                line_number=line,
                column_number=4,
                description="Avoid unused private fields",
            )
        ],
        metadata={
            "provider_id": "pmd",
            "provider_name": "PMD",
            "provider_version": "7.1.0",
            "external_rule_id": "UnusedPrivateField",
            "ruleset": "Best Practices",
            "original_priority": 5,
        },
    )


def test_console_and_html_include_provider_summary(tmp_path: Path) -> None:
    result = AnalysisResult(
        repository=Repository(name="sample", path=tmp_path, files=["A.java"]),
        findings=[_pmd_finding()],
        static_analysis_results=[
            StaticAnalysisResult(
                provider_id="pmd",
                provider_name="PMD",
                provider_version="7.1.0",
                status=StaticAnalysisStatus.COMPLETED,
                findings=[_pmd_finding()],
                files_analyzed=1,
                duration_ms=12.5,
            )
        ],
    )

    console = Console(record=True, width=120, force_terminal=False)
    ConsoleReporter(console=console).render_summary(result)
    output = console.export_text()
    assert "Static Analysis Providers" in output
    assert "PMD" in output
    assert "completed" in output

    html = HtmlFileReporter().render(result)
    assert "Static Analysis Providers" in html
    assert "PMD" in html
    assert "src/main/java/A.java:10:4" in html.replace("<wbr>", "")
    assert "Best Practices" in html
    assert "/var/" not in html
    assert "codestrata-pmd-" not in html


def test_baseline_comparison_for_pmd_findings(tmp_path: Path) -> None:
    baseline = AnalysisResult(
        repository=Repository(name="sample", path=tmp_path, files=["A.java"]),
        findings=[_pmd_finding(line=10)],
        static_analysis_results=[
            StaticAnalysisResult(
                provider_id="pmd",
                provider_name="PMD",
                provider_version="7.0.0",
                status=StaticAnalysisStatus.COMPLETED,
            )
        ],
    )
    current = AnalysisResult(
        repository=Repository(name="sample", path=tmp_path, files=["A.java"]),
        findings=[_pmd_finding(line=20)],
        static_analysis_results=[
            StaticAnalysisResult(
                provider_id="pmd",
                provider_name="PMD",
                provider_version="7.1.0",
                status=StaticAnalysisStatus.COMPLETED,
            )
        ],
    )

    comparison = ScanComparisonService().compare_results(
        current=current,
        baseline=baseline,
        current_timestamp="current",
        baseline_timestamp="baseline",
    )
    assert len(comparison.new_findings) == 1
    assert len(comparison.resolved_findings) == 1
    assert any("provider versions changed" in note.lower() for note in comparison.notes)


def test_text_report_includes_provider_section(tmp_path: Path) -> None:
    result = AnalysisResult(
        repository=Repository(name="sample", path=tmp_path, files=[]),
        static_analysis_results=[
            StaticAnalysisResult(
                provider_id="pmd",
                provider_name="PMD",
                status=StaticAnalysisStatus.UNAVAILABLE,
                error_message="PMD executable was not found.",
            )
        ],
        comparison=ScanComparison.unavailable(),
    )
    path = tmp_path / "report.txt"
    TextFileReporter().write(result=result, output_path=path)
    text = path.read_text(encoding="utf-8")
    assert "Static Analysis Providers" in text
    assert "unavailable" in text
