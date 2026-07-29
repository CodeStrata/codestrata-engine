"""Ensure credentials never leak into reports or baselines."""

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
from codestrata.models.scan_comparison import ScanComparison
from codestrata.reporters import (
    ConsoleReporter,
    HtmlFileReporter,
    JsonFileReporter,
    TextFileReporter,
)
from codestrata.security.redaction import Redactor

TOKEN = "ghp_report_leak_token_value_1234567890"
HELPER = "/tmp/codestrata-git-auth-leak/codestrata-askpass.sh"


def _result(tmp_path: Path) -> AnalysisResult:
    return AnalysisResult(
        repository=Repository(
            name="sample",
            path=tmp_path / "sample",
            source_url="https://github.com/example/sample.git",
            files=["README.md"],
        ),
        findings=[
            Finding(
                rule_id="SEC001",
                title="Example",
                description="Safe description",
                category=FindingCategory.SECURITY,
                severity=Severity.LOW,
                source=FindingSource.DETERMINISTIC,
                evidence=[Evidence(file_path="README.md", description="ok")],
            )
        ],
        comparison=ScanComparison.unavailable(),
        analyzer_version="0.1.0",
    )


def test_reports_do_not_contain_auth_secrets(tmp_path: Path) -> None:
    result = _result(tmp_path)
    # Simulate a buggy description that somehow included secrets; redaction utility
    # remains available for operational layers. Reports themselves should not be
    # given secrets by the scanner.
    html = HtmlFileReporter().render(result)
    json_path = tmp_path / "report.json"
    text_path = tmp_path / "report.txt"
    JsonFileReporter().write(result=result, output_path=json_path)
    TextFileReporter().write(result=result, output_path=text_path)

    buffer = StringIO()
    console = Console(file=buffer, width=120, force_terminal=False)
    ConsoleReporter(console=console).render_summary(result)
    console_text = buffer.getvalue()

    payloads = [
        html,
        json_path.read_text(encoding="utf-8"),
        text_path.read_text(encoding="utf-8"),
        console_text,
    ]
    for payload in payloads:
        assert TOKEN not in payload
        assert HELPER not in payload
        assert "CODESTRATA_GIT_ASKPASS_PASSWORD" not in payload
        assert "GIT_ASKPASS" not in payload
        assert f"{TOKEN}@" not in payload


def test_redactor_protects_exception_and_warning_text() -> None:
    redactor = Redactor(secrets=[TOKEN], helper_paths=[HELPER])
    message = redactor.redact(
        f"clone failed helper={HELPER} token={TOKEN} url=https://x:{TOKEN}@github.com/o/r"
    )
    assert TOKEN not in message
    assert HELPER not in message
