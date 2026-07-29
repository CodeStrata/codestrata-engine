"""Tests for shared evidence location formatting."""

from __future__ import annotations

from io import StringIO
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
from codestrata.reporters import (
    ConsoleReporter,
    HtmlFileReporter,
    JsonFileReporter,
    TextFileReporter,
)
from codestrata.reporters.evidence_location import (
    REPOSITORY_LEVEL_EVIDENCE_LABEL,
    format_evidence_item_location,
    format_evidence_location,
)


def test_format_evidence_location_path_only() -> None:
    assert format_evidence_location("src/App.java") == "src/App.java"


def test_format_evidence_location_path_and_line() -> None:
    assert format_evidence_location("src/App.java", 42) == "src/App.java:42"


def test_format_evidence_location_path_line_and_column() -> None:
    assert format_evidence_location("src/App.java", 42, 9) == "src/App.java:42:9"


def test_format_evidence_location_ignores_column_without_line() -> None:
    assert format_evidence_location("src/App.java", None, 9) == "src/App.java"


def test_format_evidence_item_location() -> None:
    evidence = Evidence(
        file_path="path/to/File.java",
        line_number=10,
        column_number=3,
    )
    assert format_evidence_item_location(evidence) == "path/to/File.java:10:3"


def test_repository_root_paths_use_human_readable_label() -> None:
    assert format_evidence_location(".") == REPOSITORY_LEVEL_EVIDENCE_LABEL
    assert format_evidence_location("./") == REPOSITORY_LEVEL_EVIDENCE_LABEL
    assert format_evidence_location(".", 12) == f"{REPOSITORY_LEVEL_EVIDENCE_LABEL}:12"
    assert format_evidence_location(".", 12, 4) == f"{REPOSITORY_LEVEL_EVIDENCE_LABEL}:12:4"


def test_html_report_shows_repository_level_label(tmp_path: Path) -> None:
    result = AnalysisResult(
        repository=Repository(name="sample", path=tmp_path, files=[]),
        findings=[
            Finding(
                rule_id="ARCH001",
                title="Architecture note",
                description="Repository-wide finding",
                category=FindingCategory.ARCHITECTURE,
                severity=Severity.INFO,
                source=FindingSource.DETERMINISTIC,
                evidence=[Evidence(file_path=".", description="Whole repository")],
            )
        ],
    )
    html = HtmlFileReporter().render(result)
    plain = html.replace("<wbr>", "")
    assert REPOSITORY_LEVEL_EVIDENCE_LABEL in plain
    assert 'class="technical-value evidence-location">.</' not in plain


def test_json_report_preserves_root_path(tmp_path: Path) -> None:
    result = AnalysisResult(
        repository=Repository(name="sample", path=tmp_path, files=[]),
        findings=[
            Finding(
                rule_id="ARCH001",
                title="Architecture note",
                description="Repository-wide finding",
                category=FindingCategory.ARCHITECTURE,
                severity=Severity.INFO,
                source=FindingSource.DETERMINISTIC,
                evidence=[Evidence(file_path=".", description="Whole repository")],
            )
        ],
    )
    output = tmp_path / "report.json"
    JsonFileReporter().write(result=result, output_path=output)
    payload = output.read_text(encoding="utf-8")
    assert '"file_path": "."' in payload or '"file_path":"."' in payload
    assert REPOSITORY_LEVEL_EVIDENCE_LABEL not in payload


def test_console_and_text_show_repository_level_label(tmp_path: Path) -> None:
    result = AnalysisResult(
        repository=Repository(name="sample", path=tmp_path, files=[]),
        findings=[
            Finding(
                rule_id="ARCH001",
                title="Architecture note",
                description="Repository-wide finding",
                category=FindingCategory.ARCHITECTURE,
                severity=Severity.INFO,
                source=FindingSource.DETERMINISTIC,
                evidence=[Evidence(file_path="./", description="Whole repository")],
            )
        ],
    )

    buffer = StringIO()
    console = Console(file=buffer, width=120, force_terminal=False)
    ConsoleReporter(console=console).render_detailed(result)
    assert REPOSITORY_LEVEL_EVIDENCE_LABEL in buffer.getvalue()

    text_path = tmp_path / "report.txt"
    TextFileReporter().write(result=result, output_path=text_path)
    assert REPOSITORY_LEVEL_EVIDENCE_LABEL in text_path.read_text(encoding="utf-8")
