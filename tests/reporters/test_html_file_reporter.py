"""Tests for the self-contained HTML report reporter."""

from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console

from codestrata.models import (
    AnalysisResult,
    ArchitectureFacts,
    BuildFacts,
    CicdFacts,
    CloudReadinessFacts,
    DependencyFacts,
    Evidence,
    Finding,
    FindingCategory,
    FindingSource,
    Priority,
    Recommendation,
    Repository,
    RepositoryFacts,
    SecurityFacts,
    Severity,
    StructureFacts,
    Technology,
    TechnologyCategory,
)
from codestrata.models.enums import Effort, RecommendationCategory, Risk
from codestrata.reporters import ConsoleReporter, HtmlFileReporter
from codestrata.reporters.json_file_reporter import JsonFileReporter
from codestrata.reporters.report_paths import create_report_paths, retain_recent_reports
from codestrata.reporters.text_file_reporter import TextFileReporter


def _recommendation(
    *,
    rule_id: str,
    title: str,
    priority: Priority,
    category: RecommendationCategory = RecommendationCategory.TESTING,
) -> Recommendation:
    return Recommendation(
        rule_id=rule_id,
        title=title,
        description=f"Action for {title}",
        rationale=f"Rationale for {title}",
        priority=priority,
        category=category,
        effort=Effort.MEDIUM,
        risk=Risk.MEDIUM,
        evidence=[
            Evidence(
                file_path="repository-facts",
                description=f"Evidence for {title}",
            )
        ],
        related_finding_ids=["finding-1"],
        actions=[f"Do {title}"],
    )


def _result_with_content(tmp_path: Path) -> AnalysisResult:
    return AnalysisResult(
        repository=Repository(
            name="sample-app",
            path=tmp_path,
            files=["src/App.java", "pom.xml"],
        ),
        technologies=[
            Technology(
                name="Java",
                category=TechnologyCategory.LANGUAGE,
                confidence=1.0,
                source="test",
            )
        ],
        facts=RepositoryFacts(
            structure=StructureFacts(
                file_count=2,
                source_file_count=1,
                test_file_count=0,
                has_tests=False,
            ),
            build=BuildFacts(build_systems=["maven"]),
            dependencies=DependencyFacts(dependency_count=3),
            cicd=CicdFacts(has_ci=False),
            security=SecurityFacts(secret_finding_count=1),
            architecture=ArchitectureFacts(has_api_layer=True),
            cloud=CloudReadinessFacts(
                has_docker=True,
                cloud_capabilities=["docker"],
            ),
        ),
        findings=[
            Finding(
                rule_id="SEC003",
                title="Secret detected",
                description="A secret was found in config.",
                category=FindingCategory.SECURITY,
                severity=Severity.CRITICAL,
                source=FindingSource.STATIC_ANALYSIS,
                evidence=[
                    Evidence(
                        file_path="config.env",
                        description="Secret pattern matched",
                        detected_value="REDACTED",
                    )
                ],
                affected_technologies=["Java"],
            ),
            Finding(
                rule_id="ARCH001",
                title="Layered architecture detected",
                description="Layers were detected.",
                category=FindingCategory.ARCHITECTURE,
                severity=Severity.INFO,
                source=FindingSource.STATIC_ANALYSIS,
            ),
        ],
        recommendations=[
            _recommendation(
                rule_id="REC.SECURITY.001",
                title="Rotate credentials",
                priority=Priority.CRITICAL,
                category=RecommendationCategory.SECURITY,
            ),
            _recommendation(
                rule_id="REC.TESTING.001",
                title="Add tests",
                priority=Priority.HIGH,
            ),
            _recommendation(
                rule_id="REC.CLOUD.001",
                title="Create deployment baseline",
                priority=Priority.MEDIUM,
                category=RecommendationCategory.CLOUD,
            ),
            _recommendation(
                rule_id="REC.ARCHITECTURE.002",
                title="Document boundaries",
                priority=Priority.LOW,
                category=RecommendationCategory.ARCHITECTURE,
            ),
        ],
        analyzer_version="0.3.0",
    )


def test_html_report_file_is_generated(tmp_path: Path) -> None:
    result = _result_with_content(tmp_path)
    output_path = tmp_path / "report.html"

    written = HtmlFileReporter().write(result=result, output_path=output_path)

    assert written == output_path
    assert output_path.is_file()
    assert output_path.stat().st_size > 0


def test_html_report_contains_required_sections(tmp_path: Path) -> None:
    result = _result_with_content(tmp_path)
    html = HtmlFileReporter().render(result)
    plain = html.replace("<wbr>", "")

    assert "sample-app" in html
    assert "Executive Summary" in html
    assert "Repository Facts" in html
    assert "Findings" in html
    assert "Modernization Recommendations" in html
    assert "Prioritized Roadmap" in html
    assert "Assessment Summary" in html
    assert "Immediate" in html
    assert "Near Term" in html
    assert "Later" in html
    assert "SEC003" in plain
    assert "REC.SECURITY.001" in plain
    assert "Rotate credentials" in html
    assert 'class="affected-technologies"' in html
    assert "<p><strong>Affected technologies:</strong>" not in html


def test_affected_technologies_are_not_nested_in_paragraph(tmp_path: Path) -> None:
    result = _result_with_content(tmp_path)
    html = HtmlFileReporter().render(result)

    assert 'class="affected-technologies"' in html
    assert "<p><strong>Affected technologies:</strong>" not in html
    # Block-level collection containers must not appear inside a <p>.
    assert "<p" not in html.split('class="affected-technologies"', 1)[1].split("</div>", 1)[0]
    assert "value-badges" in html or "None" in html


def test_affected_technologies_none_uses_valid_container(tmp_path: Path) -> None:
    result = AnalysisResult(
        repository=Repository(name="sample", path=tmp_path, files=[]),
        findings=[
            Finding(
                rule_id="ARCH001",
                title="No tech finding",
                description="desc",
                category=FindingCategory.ARCHITECTURE,
                severity=Severity.INFO,
                source=FindingSource.DETERMINISTIC,
                affected_technologies=[],
            )
        ],
    )
    html = HtmlFileReporter().render(result)
    section = html.split('class="affected-technologies"', 1)[1].split("</div>", 1)[0]
    assert "None" in section
    assert "<p>" not in section


def test_empty_findings_and_recommendations_render(tmp_path: Path) -> None:
    result = AnalysisResult(
        repository=Repository(
            name="empty-repo",
            path=tmp_path,
            files=[],
        ),
        findings=[],
        recommendations=[],
    )

    html = HtmlFileReporter().render(result)

    assert "No deterministic findings were detected." in html
    assert "No modernization recommendations were generated." in html


def test_html_escaping_prevents_script_injection(tmp_path: Path) -> None:
    result = AnalysisResult(
        repository=Repository(
            name='<script>alert("xss")</script>',
            path=tmp_path,
            files=["<img src=x onerror=alert(1)>.py"],
        ),
        findings=[
            Finding(
                rule_id="SEC001",
                title='<script>alert("title")</script>',
                description='Payload <b>bold</b> & "quotes"',
                category=FindingCategory.SECURITY,
                severity=Severity.HIGH,
                source=FindingSource.STATIC_ANALYSIS,
                evidence=[
                    Evidence(
                        file_path="<script>evil.js</script>",
                        description="<img src=x>",
                        detected_value="<svg/onload=alert(1)>",
                    )
                ],
            )
        ],
        recommendations=[
            _recommendation(
                rule_id="REC.SECURITY.001",
                title='<script>alert("rec")</script>',
                priority=Priority.HIGH,
                category=RecommendationCategory.SECURITY,
            )
        ],
    )

    html = HtmlFileReporter().render(result)
    plain = html.replace("<wbr>", "")

    assert "<script>alert(" not in html
    assert "&lt;script&gt;alert" in html
    assert "&lt;img src=x&gt;" in plain or "&lt;img src=x" in plain
    assert "&amp;" in html or "&quot;" in html


def test_unicode_text_renders_correctly(tmp_path: Path) -> None:
    result = AnalysisResult(
        repository=Repository(
            name="ユニコード-リポジトリ",
            path=tmp_path,
            files=["src/アプリケーション.py"],
        ),
        findings=[
            Finding(
                rule_id="SEC001",
                title="敏感な設定ファイル",
                description="検出: café résumé 日本語",
                category=FindingCategory.SECURITY,
                severity=Severity.MEDIUM,
                source=FindingSource.STATIC_ANALYSIS,
            )
        ],
    )

    html = HtmlFileReporter().render(result)

    assert "ユニコード-リポジトリ" in html
    assert "敏感な設定ファイル" in html
    assert "café résumé 日本語" in html
    assert 'charset="utf-8"' in html


def test_deterministic_finding_ordering(tmp_path: Path) -> None:
    result = AnalysisResult(
        repository=Repository(name="ordered", path=tmp_path, files=[]),
        findings=[
            Finding(
                rule_id="B002",
                title="Medium B",
                description="b",
                category=FindingCategory.ARCHITECTURE,
                severity=Severity.MEDIUM,
                source=FindingSource.DETERMINISTIC,
            ),
            Finding(
                rule_id="A001",
                title="Critical A",
                description="a",
                category=FindingCategory.SECURITY,
                severity=Severity.CRITICAL,
                source=FindingSource.DETERMINISTIC,
            ),
            Finding(
                rule_id="A002",
                title="Medium A",
                description="a2",
                category=FindingCategory.ARCHITECTURE,
                severity=Severity.MEDIUM,
                source=FindingSource.DETERMINISTIC,
            ),
        ],
    )

    html = HtmlFileReporter().render(result)
    critical_index = html.index("A001")
    medium_a_index = html.index("A002")
    medium_b_index = html.index("B002")

    assert critical_index < medium_a_index < medium_b_index


def test_cli_generated_reports_includes_html(tmp_path: Path) -> None:
    console = Console(record=True, width=140, force_terminal=False)
    result = AnalysisResult(
        repository=Repository(name="sample", path=tmp_path, files=[]),
    )

    ConsoleReporter(console=console).render_summary(
        result=result,
        text_report_path=tmp_path / "report.txt",
        json_report_path=tmp_path / "report.json",
        html_report_path=tmp_path / "report.html",
    )

    output = console.export_text()
    compact = "".join(output.split())
    assert "GeneratedReports" in compact
    assert "HTML" in compact
    assert "report.html" in compact


def test_create_report_paths_includes_html(tmp_path: Path) -> None:
    result = AnalysisResult(
        repository=Repository(name="sample", path=tmp_path, files=[]),
    )
    report_paths = create_report_paths(result=result, base_directory=tmp_path / "reports")

    assert report_paths.html_report == report_paths.directory / "assessment.html"


def test_retention_keeps_three_complete_runs_with_html(tmp_path: Path) -> None:
    repository_directory = tmp_path / "reports" / "sample"

    for timestamp in [
        "20260101-010101",
        "20260102-020202",
        "20260103-030303",
        "20260104-040404",
    ]:
        run_directory = repository_directory / timestamp
        run_directory.mkdir(parents=True, exist_ok=True)
        (run_directory / "report.txt").write_text("txt", encoding="utf-8")
        (run_directory / "report.json").write_text("{}", encoding="utf-8")
        (run_directory / "report.html").write_text("<html></html>", encoding="utf-8")

    retain_recent_reports(repository_directory, keep=3)

    remaining = sorted(path.name for path in repository_directory.iterdir())
    assert remaining == [
        "20260102-020202",
        "20260103-030303",
        "20260104-040404",
    ]


def test_html_failure_does_not_remove_previous_valid_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = AnalysisResult(
        repository=Repository(name="sample", path=tmp_path, files=[]),
    )
    repository_directory = tmp_path / "reports" / "sample"

    for timestamp in [
        "20260101-010101",
        "20260102-020202",
        "20260103-030303",
        "20260104-040404",
    ]:
        run_directory = repository_directory / timestamp
        run_directory.mkdir(parents=True, exist_ok=True)
        (run_directory / "report.txt").write_text("txt", encoding="utf-8")
        (run_directory / "report.json").write_text("{}", encoding="utf-8")
        (run_directory / "report.html").write_text("<html></html>", encoding="utf-8")

    report_paths = create_report_paths(
        result=result,
        base_directory=tmp_path / "reports",
    )

    def fail_html_write(
        self: HtmlFileReporter,
        result: AnalysisResult,
        output_path: Path,
    ) -> Path:
        del self
        del result
        del output_path
        raise RuntimeError("html write failed")

    monkeypatch.setattr(HtmlFileReporter, "write", fail_html_write)

    with pytest.raises(RuntimeError, match="html write failed"):
        TextFileReporter().write(result=result, output_path=report_paths.text_report)
        JsonFileReporter().write(result=result, output_path=report_paths.json_report)
        HtmlFileReporter().write(result=result, output_path=report_paths.html_report)
        retain_recent_reports(report_paths.directory.parent)

    remaining = sorted(path.name for path in repository_directory.iterdir())
    assert "20260101-010101" in remaining
    assert len([name for name in remaining if name.startswith("2026")]) == 4
