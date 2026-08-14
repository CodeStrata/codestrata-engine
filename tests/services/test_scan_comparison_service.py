"""Tests for deterministic scan baseline comparison."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from codestrata.models import (
    AnalysisResult,
    Evidence,
    Finding,
    FindingCategory,
    FindingSource,
    Priority,
    Recommendation,
    Repository,
    RepositoryFacts,
    Severity,
    StructureFacts,
)
from codestrata.models.enums import Effort, RecommendationCategory, Risk
from codestrata.models.scan_comparison import ScanComparison
from codestrata.reporters import (
    ConsoleReporter,
    HtmlFileReporter,
    JsonFileReporter,
    TextFileReporter,
)
from codestrata.reporters.report_paths import create_report_paths, retain_recent_reports
from codestrata.services.scan_comparison_service import ScanComparisonService


def _finding(
    *,
    rule_id: str,
    title: str = "Finding",
    severity: Severity = Severity.MEDIUM,
    category: FindingCategory = FindingCategory.SECURITY,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        title=title,
        description=f"Description for {title}",
        category=category,
        severity=severity,
        source=FindingSource.DETERMINISTIC,
        evidence=[Evidence(file_path="a.py", description="evidence")],
    )


def _recommendation(
    *,
    rule_id: str,
    title: str = "Recommendation",
    priority: Priority = Priority.MEDIUM,
) -> Recommendation:
    return Recommendation(
        rule_id=rule_id,
        title=title,
        description=f"Action for {title}",
        rationale=f"Rationale for {title}",
        priority=priority,
        category=RecommendationCategory.TESTING,
        effort=Effort.MEDIUM,
        risk=Risk.MEDIUM,
        evidence=[Evidence(file_path="repository-facts", description="evidence")],
    )


def _result(
    tmp_path: Path,
    *,
    name: str = "sample",
    findings: list[Finding] | None = None,
    recommendations: list[Recommendation] | None = None,
    facts: RepositoryFacts | None = None,
) -> AnalysisResult:
    return AnalysisResult(
        repository=Repository(
            name=name,
            path=tmp_path / name,
            files=["a.py"],
        ),
        findings=findings or [],
        recommendations=recommendations or [],
        facts=facts or RepositoryFacts(),
    )


def _write_baseline(
    repository_directory: Path,
    timestamp: str,
    result: AnalysisResult,
) -> Path:
    run_directory = repository_directory / timestamp
    run_directory.mkdir(parents=True, exist_ok=True)
    JsonFileReporter().write(result=result, output_path=run_directory / "report.json")
    (run_directory / "report.txt").write_text("txt", encoding="utf-8")
    (run_directory / "report.html").write_text("<html></html>", encoding="utf-8")
    return run_directory


def test_no_baseline_available(tmp_path: Path) -> None:
    current = _result(tmp_path)
    current_run = tmp_path / "reports" / "sample" / "20260105-050505"
    current_run.mkdir(parents=True)

    comparison = ScanComparisonService().compare(
        current=current,
        repository_directory=tmp_path / "reports" / "sample",
        current_run_directory=current_run,
        current_timestamp="20260105-050505",
    )

    assert comparison.baseline_available is False
    assert comparison.current_timestamp == "20260105-050505"
    assert comparison.summary.new_findings == 0


def test_baseline_selected_from_latest_previous_valid_run(tmp_path: Path) -> None:
    repository_directory = tmp_path / "reports" / "sample"
    older = _result(tmp_path, findings=[_finding(rule_id="OLD")])
    newer = _result(tmp_path, findings=[_finding(rule_id="NEW")])
    _write_baseline(repository_directory, "20260101-010101", older)
    _write_baseline(repository_directory, "20260102-020202", newer)

    current_run = repository_directory / "20260103-030303"
    current_run.mkdir()
    current = _result(tmp_path, findings=[_finding(rule_id="NEW")])

    comparison = ScanComparisonService().compare(
        current=current,
        repository_directory=repository_directory,
        current_run_directory=current_run,
        current_timestamp="20260103-030303",
    )

    assert comparison.baseline_available is True
    assert comparison.baseline_timestamp == "20260102-020202"
    assert comparison.new_findings == []
    assert comparison.unchanged_findings[0].rule_id == "NEW"


def test_incomplete_prior_run_ignored(tmp_path: Path) -> None:
    repository_directory = tmp_path / "reports" / "sample"
    valid = _result(tmp_path, findings=[_finding(rule_id="SEC001")])
    _write_baseline(repository_directory, "20260101-010101", valid)

    incomplete = repository_directory / "20260102-020202"
    incomplete.mkdir(parents=True)
    (incomplete / "report.txt").write_text("txt", encoding="utf-8")

    current_run = repository_directory / "20260103-030303"
    current_run.mkdir()

    comparison = ScanComparisonService().compare(
        current=_result(tmp_path, findings=[_finding(rule_id="SEC001")]),
        repository_directory=repository_directory,
        current_run_directory=current_run,
    )

    assert comparison.baseline_timestamp == "20260101-010101"


def test_malformed_prior_json_ignored(tmp_path: Path) -> None:
    repository_directory = tmp_path / "reports" / "sample"
    valid = _result(tmp_path, findings=[_finding(rule_id="SEC001")])
    _write_baseline(repository_directory, "20260101-010101", valid)

    malformed = repository_directory / "20260102-020202"
    malformed.mkdir(parents=True)
    (malformed / "report.json").write_text("{not-json", encoding="utf-8")

    current_run = repository_directory / "20260103-030303"
    current_run.mkdir()

    comparison = ScanComparisonService().compare(
        current=_result(tmp_path, findings=[_finding(rule_id="SEC001")]),
        repository_directory=repository_directory,
        current_run_directory=current_run,
    )

    assert comparison.baseline_timestamp == "20260101-010101"


def test_repository_isolation(tmp_path: Path) -> None:
    first = tmp_path / "reports" / "first"
    second = tmp_path / "reports" / "second"
    _write_baseline(
        first,
        "20260101-010101",
        _result(tmp_path, name="first", findings=[_finding(rule_id="A")]),
    )
    _write_baseline(
        second,
        "20260102-020202",
        _result(tmp_path, name="second", findings=[_finding(rule_id="B")]),
    )

    current_run = first / "20260103-030303"
    current_run.mkdir()

    comparison = ScanComparisonService().compare(
        current=_result(tmp_path, name="first", findings=[_finding(rule_id="A")]),
        repository_directory=first,
        current_run_directory=current_run,
    )

    assert comparison.baseline_timestamp == "20260101-010101"
    assert comparison.unchanged_findings[0].rule_id == "A"


def test_new_and_resolved_findings(tmp_path: Path) -> None:
    baseline = _result(tmp_path, findings=[_finding(rule_id="OLD")])
    current = _result(tmp_path, findings=[_finding(rule_id="NEW")])

    comparison = ScanComparisonService().compare_results(
        current=current,
        baseline=baseline,
        current_timestamp="20260102-020202",
        baseline_timestamp="20260101-010101",
    )

    assert [item.rule_id for item in comparison.new_findings] == ["NEW"]
    assert [item.rule_id for item in comparison.resolved_findings] == ["OLD"]


def test_severity_increase_and_decrease(tmp_path: Path) -> None:
    baseline = _result(
        tmp_path,
        findings=[
            _finding(rule_id="UP", severity=Severity.LOW),
            _finding(rule_id="DOWN", severity=Severity.HIGH),
        ],
    )
    current = _result(
        tmp_path,
        findings=[
            _finding(rule_id="UP", severity=Severity.CRITICAL),
            _finding(rule_id="DOWN", severity=Severity.MEDIUM),
        ],
    )

    comparison = ScanComparisonService().compare_results(
        current=current,
        baseline=baseline,
        current_timestamp="current",
        baseline_timestamp="baseline",
    )

    directions = {change.rule_id: change.direction for change in comparison.severity_changes}
    assert directions["UP"] == "increased"
    assert directions["DOWN"] == "decreased"
    assert comparison.summary.worsened_findings == 1
    assert comparison.summary.improved_findings == 1


def test_new_and_resolved_recommendations(tmp_path: Path) -> None:
    baseline = _result(
        tmp_path,
        recommendations=[_recommendation(rule_id="REC.OLD")],
    )
    current = _result(
        tmp_path,
        recommendations=[_recommendation(rule_id="REC.NEW")],
    )

    comparison = ScanComparisonService().compare_results(
        current=current,
        baseline=baseline,
        current_timestamp="current",
        baseline_timestamp="baseline",
    )

    assert [item.rule_id for item in comparison.new_recommendations] == ["REC.NEW"]
    assert [item.rule_id for item in comparison.resolved_recommendations] == ["REC.OLD"]


def test_priority_increase_and_decrease(tmp_path: Path) -> None:
    baseline = _result(
        tmp_path,
        recommendations=[
            _recommendation(rule_id="REC.UP", priority=Priority.LOW),
            _recommendation(rule_id="REC.DOWN", priority=Priority.HIGH),
        ],
    )
    current = _result(
        tmp_path,
        recommendations=[
            _recommendation(rule_id="REC.UP", priority=Priority.CRITICAL),
            _recommendation(rule_id="REC.DOWN", priority=Priority.MEDIUM),
        ],
    )

    comparison = ScanComparisonService().compare_results(
        current=current,
        baseline=baseline,
        current_timestamp="current",
        baseline_timestamp="baseline",
    )

    directions = {change.rule_id: change.direction for change in comparison.priority_changes}
    assert directions["REC.UP"] == "increased"
    assert directions["REC.DOWN"] == "decreased"
    assert comparison.summary.worsened_priorities == 1
    assert comparison.summary.improved_priorities == 1


def test_boolean_and_numeric_fact_changes(tmp_path: Path) -> None:
    baseline = _result(
        tmp_path,
        facts=RepositoryFacts(
            structure=StructureFacts(has_tests=False, file_count=10),
        ),
    )
    current = _result(
        tmp_path,
        facts=RepositoryFacts(
            structure=StructureFacts(has_tests=True, file_count=12),
        ),
    )

    comparison = ScanComparisonService().compare_results(
        current=current,
        baseline=baseline,
        current_timestamp="current",
        baseline_timestamp="baseline",
    )

    paths = {change.path: change for change in comparison.fact_changes}
    assert "facts.structure.has_tests" in paths
    assert paths["facts.structure.has_tests"].previous_value is False
    assert paths["facts.structure.has_tests"].current_value is True
    assert paths["facts.structure.file_count"].previous_value == 10
    assert paths["facts.structure.file_count"].current_value == 12


def test_list_additions_removals_and_order_insensitive(tmp_path: Path) -> None:
    baseline = _result(
        tmp_path,
        facts=RepositoryFacts(
            structure=StructureFacts(architecture_layers=["api", "service"]),
        ),
    )
    reordered = _result(
        tmp_path,
        facts=RepositoryFacts(
            structure=StructureFacts(architecture_layers=["service", "api"]),
        ),
    )
    changed = _result(
        tmp_path,
        facts=RepositoryFacts(
            structure=StructureFacts(architecture_layers=["api", "domain"]),
        ),
    )

    no_change = ScanComparisonService().compare_results(
        current=reordered,
        baseline=baseline,
        current_timestamp="current",
        baseline_timestamp="baseline",
    )
    assert no_change.fact_changes == []

    with_change = ScanComparisonService().compare_results(
        current=changed,
        baseline=baseline,
        current_timestamp="current",
        baseline_timestamp="baseline",
    )
    layer_change = next(
        change
        for change in with_change.fact_changes
        if change.path == "facts.structure.architecture_layers"
    )
    assert layer_change.added_values == ["domain"]
    assert layer_change.removed_values == ["service"]


def test_comparison_ordering_is_deterministic(tmp_path: Path) -> None:
    baseline = _result(
        tmp_path,
        findings=[
            _finding(rule_id="B"),
            _finding(rule_id="A"),
        ],
    )
    current = _result(
        tmp_path,
        findings=[
            _finding(rule_id="C"),
            _finding(rule_id="A"),
        ],
    )

    first = ScanComparisonService().compare_results(
        current=current,
        baseline=baseline,
        current_timestamp="current",
        baseline_timestamp="baseline",
    )
    second = ScanComparisonService().compare_results(
        current=current,
        baseline=baseline,
        current_timestamp="current",
        baseline_timestamp="baseline",
    )

    assert [item.rule_id for item in first.new_findings] == ["C"]
    assert [item.rule_id for item in first.resolved_findings] == ["B"]
    assert first.model_dump() == second.model_dump()


def test_reports_include_comparison(tmp_path: Path) -> None:
    comparison = ScanComparisonService().compare_results(
        current=_result(tmp_path, findings=[_finding(rule_id="NEW")]),
        baseline=_result(tmp_path, findings=[_finding(rule_id="OLD")]),
        current_timestamp="20260102-020202",
        baseline_timestamp="20260101-010101",
    )
    result = _result(tmp_path, findings=[_finding(rule_id="NEW")])
    result = result.model_copy(update={"comparison": comparison})

    json_path = tmp_path / "report.json"
    txt_path = tmp_path / "report.txt"
    html_path = tmp_path / "report.html"

    JsonFileReporter().write(result=result, output_path=json_path)
    TextFileReporter().write(result=result, output_path=txt_path)
    HtmlFileReporter().write(result=result, output_path=html_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["comparison"]["baseline_available"] is True
    assert payload["comparison"]["summary"]["new_findings"] == 1

    text = txt_path.read_text(encoding="utf-8")
    assert "Changes Since Previous Scan" in text
    assert "New Findings" in text

    html = html_path.read_text(encoding="utf-8")
    assert "Changes Since Previous Scan" in html
    assert "New Findings" in html
    assert "20260101-010101" in html.replace("<wbr>", "")


def test_console_shows_comparison_summary(tmp_path: Path) -> None:
    console = Console(record=True, width=120, force_terminal=False)
    result = _result(tmp_path).model_copy(
        update={"comparison": ScanComparison.unavailable("20260102-020202")}
    )

    ConsoleReporter(console=console).render_summary(result)
    output = console.export_text()
    assert "Changes Since Previous Scan" in output
    assert "No previous completed scan is available for comparison." in output


def test_comparison_occurs_before_retention(
    tmp_path: Path,
) -> None:
    repository_directory = tmp_path / "reports" / "sample"
    for timestamp in [
        "20260101-010101",
        "20260102-020202",
        "20260103-030303",
    ]:
        _write_baseline(
            repository_directory,
            timestamp,
            _result(tmp_path, findings=[_finding(rule_id="BASE")]),
        )

    result = _result(tmp_path, findings=[_finding(rule_id="CURRENT")])
    report_paths = create_report_paths(
        result=result,
        base_directory=tmp_path / "reports",
    )

    comparison = ScanComparisonService().compare(
        current=result,
        repository_directory=repository_directory,
        current_run_directory=report_paths.directory,
        current_timestamp=report_paths.timestamp,
    )
    assert comparison.baseline_available is True
    assert comparison.baseline_timestamp == "20260103-030303"

    result = result.model_copy(update={"comparison": comparison})

    TextFileReporter().write(result=result, output_path=report_paths.text_report)
    JsonFileReporter().write(result=result, output_path=report_paths.json_report)
    HtmlFileReporter().write(result=result, output_path=report_paths.html_report)
    retain_recent_reports(repository_directory, keep=2)

    remaining = sorted(path.name for path in repository_directory.iterdir())
    assert "20260101-010101" not in remaining
    assert len([name for name in remaining if name.startswith("2026")]) == 2


def test_html_no_baseline_message(tmp_path: Path) -> None:
    result = _result(tmp_path).model_copy(update={"comparison": ScanComparison.unavailable()})
    html = HtmlFileReporter().render(result)
    assert "No previous completed scan is available for comparison." in html


def test_matched_pipeline_changes_render_as_concise_field_changes(
    tmp_path: Path,
) -> None:
    from codestrata.models.cicd import CicdFacts, CicdPipeline

    baseline = _result(
        tmp_path,
        facts=RepositoryFacts(
            cicd=CicdFacts(
                pipelines=[
                    CicdPipeline(
                        provider="github-actions",
                        path=".github/workflows/gradle-build.yml",
                        build_commands=["./gradlew build"],
                        test_commands=[],
                    )
                ]
            )
        ),
    )
    current = _result(
        tmp_path,
        facts=RepositoryFacts(
            cicd=CicdFacts(
                pipelines=[
                    CicdPipeline(
                        provider="github-actions",
                        path=".github/workflows/gradle-build.yml",
                        build_commands=["./gradlew build"],
                        test_commands=["./gradlew build"],
                    )
                ]
            )
        ),
    )

    comparison = ScanComparisonService().compare_results(
        current=current,
        baseline=baseline,
        current_timestamp="current",
        baseline_timestamp="baseline",
    )

    summaries = [change.display_text() for change in comparison.fact_changes]
    assert any(
        summary == ".github/workflows/gradle-build.yml: test capability No → Yes"
        for summary in summaries
    )
    assert all('{"provider"' not in summary for summary in summaries)
    assert all("build_commands" not in summary or "capability" in summary for summary in summaries)


def test_complete_pipeline_dictionaries_do_not_appear_in_html_or_text(
    tmp_path: Path,
) -> None:
    from codestrata.models.cicd import CicdFacts, CicdPipeline

    baseline = _result(
        tmp_path,
        facts=RepositoryFacts(
            cicd=CicdFacts(
                pipelines=[
                    CicdPipeline(
                        provider="github-actions",
                        path=".github/workflows/old.yml",
                        test_commands=[],
                    )
                ]
            )
        ),
    )
    current = _result(
        tmp_path,
        facts=RepositoryFacts(
            cicd=CicdFacts(
                pipelines=[
                    CicdPipeline(
                        provider="github-actions",
                        path=".github/workflows/old.yml",
                        test_commands=["./gradlew test"],
                    ),
                    CicdPipeline(
                        provider="github-actions",
                        path=".github/workflows/new.yml",
                        build_commands=["./gradlew build"],
                    ),
                ]
            )
        ),
    )
    comparison = ScanComparisonService().compare_results(
        current=current,
        baseline=baseline,
        current_timestamp="current",
        baseline_timestamp="baseline",
    )
    result = current.model_copy(update={"comparison": comparison})

    html = HtmlFileReporter().render(result)
    text_path = tmp_path / "report.txt"
    TextFileReporter().write(result=result, output_path=text_path)
    text = text_path.read_text(encoding="utf-8")

    assert '"build_commands"' not in html
    assert '"metadata"' not in html
    assert '"build_commands"' not in text
    assert "Added pipeline .github/workflows/new.yml (github-actions)" in html.replace("<wbr>", "")
    assert "Added pipeline .github/workflows/new.yml (github-actions)" in text
    assert ".github/workflows/old.yml: test capability No → Yes" in html.replace("<wbr>", "")
    assert ".github/workflows/old.yml: test capability No → Yes" in text


def test_added_and_removed_pipelines_are_reported_by_path(
    tmp_path: Path,
) -> None:
    from codestrata.models.cicd import CicdFacts, CicdPipeline

    baseline = _result(
        tmp_path,
        facts=RepositoryFacts(
            cicd=CicdFacts(
                pipelines=[
                    CicdPipeline(
                        provider="github-actions",
                        path=".github/workflows/removed.yml",
                    )
                ]
            )
        ),
    )
    current = _result(
        tmp_path,
        facts=RepositoryFacts(
            cicd=CicdFacts(
                pipelines=[
                    CicdPipeline(
                        provider="github-actions",
                        path=".github/workflows/added.yml",
                    )
                ]
            )
        ),
    )

    comparison = ScanComparisonService().compare_results(
        current=current,
        baseline=baseline,
        current_timestamp="current",
        baseline_timestamp="baseline",
    )
    summaries = {change.display_text() for change in comparison.fact_changes}

    assert "Added pipeline .github/workflows/added.yml (github-actions)" in summaries
    assert "Removed pipeline .github/workflows/removed.yml (github-actions)" in summaries


def test_analyzer_version_difference_produces_comparison_note(
    tmp_path: Path,
) -> None:
    baseline = _result(tmp_path).model_copy(
        update={"analyzer_version": "0.1.0", "ruleset_version": "1.0.0"}
    )
    current = _result(tmp_path).model_copy(
        update={"analyzer_version": "0.2.0", "ruleset_version": "1.1.0"}
    )

    comparison = ScanComparisonService().compare_results(
        current=current,
        baseline=baseline,
        current_timestamp="current",
        baseline_timestamp="baseline",
    )

    assert comparison.baseline_analyzer_version == "0.1.0"
    assert comparison.current_analyzer_version == "0.2.0"
    assert comparison.baseline_ruleset_version == "1.0.0"
    assert comparison.current_ruleset_version == "1.1.0"
    assert comparison.notes == [
        "Some differences may result from analyzer or ruleset version changes."
    ]
