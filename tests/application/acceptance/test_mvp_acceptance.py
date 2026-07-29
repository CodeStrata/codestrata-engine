"""Unit tests for MVP acceptance harness (Phase 5.13)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from codestrata.application.acceptance.qa import questions_passed
from codestrata.application.acceptance.service import MvpAcceptanceService, _reports_live_equal
from codestrata.application.acceptance.summary import load_acceptance_summary
from codestrata.application.onboarding import OnboardingApplicationService
from codestrata.cli import app
from codestrata.cli.acceptance import acceptance_app
from codestrata.domain.onboarding.enums import OnboardingStatus
from codestrata.domain.onboarding.models import (
    OnboardingResult,
    OnboardingSummary,
    RepositoryOnboardingManifest,
)
from codestrata.models import (
    AnalysisResult,
    Effort,
    Evidence,
    Finding,
    FindingCategory,
    FindingSource,
    Priority,
    Recommendation,
    RecommendationCategory,
    Repository,
    RepositoryFacts,
    Risk,
    Severity,
    StructureFacts,
    Technology,
    TechnologyCategory,
)
from codestrata.reporting.assessment_json import build_assessment_json_document
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput

runner = CliRunner()


def _write_report(path: Path, tmp_path: Path) -> None:
    analysis = AnalysisResult(
        repository=Repository(
            name="sample",
            path=tmp_path / "sample",
            default_branch="main",
            files=["README.md"],
            total_files=1,
        ),
        technologies=[
            Technology(
                name="Python",
                category=TechnologyCategory.LANGUAGE,
                confidence=1.0,
                source="test",
            )
        ],
        facts=RepositoryFacts(
            structure=StructureFacts(file_count=1, source_file_count=1, test_file_count=0)
        ),
        findings=[
            Finding(
                rule_id="TEST001",
                title="Sample finding",
                description="d",
                category=FindingCategory.TESTING,
                severity=Severity.LOW,
                source=FindingSource.DETERMINISTIC,
                evidence=[Evidence(file_path="README.md", description="root")],
            )
        ],
        recommendations=[
            Recommendation(
                rule_id="REC001",
                title="Sample rec",
                description="d",
                rationale="r",
                priority=Priority.LOW,
                category=RecommendationCategory.TESTING,
                effort=Effort.SMALL,
                risk=Risk.LOW,
                related_finding_ids=[],
                actions=["review"],
            )
        ],
    )
    document = build_assessment_json_document(
        ModernizationReportInput(
            analysis_result=analysis,
            assessment_mode=AssessmentMode.DETERMINISTIC,
            generated_at_utc=datetime(2026, 7, 25, 12, 0, tzinfo=UTC),
            knowledge_repository_id="repo:sample",
            knowledge_run_id="run:sample",
        )
    )
    path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")


def _onboarding_result(tmp_path: Path, label: str, *, scan_id: str) -> OnboardingResult:
    run_dir = tmp_path / "reports" / label / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / "report.json"
    html_path = run_dir / "report.html"
    _write_report(json_path, tmp_path)
    html_path.write_text("<html>ok</html>\n", encoding="utf-8")
    manifest = RepositoryOnboardingManifest(
        repository_id=f"repo:{label}",
        repository_name=label,
        scan_id=scan_id,
        report_version="1.2",
        languages_detected=("Python",),
        frameworks_detected=("Typer",),
        scan_timestamp=datetime(2026, 7, 25, 12, 0, tzinfo=UTC),
        codestrata_version="0.1.0",
        findings_count=1,
        recommendations_count=1,
        roadmap_initiative_count=0,
        chunks_indexed=3,
        html_report_path=str(html_path),
        json_report_path=str(json_path),
        run_directory=str(run_dir),
        status=OnboardingStatus.SUCCEEDED,
    )
    summary = OnboardingSummary(
        repository_analyzed=label,
        languages_detected=("Python",),
        frameworks_detected=("Typer",),
        findings_count=1,
        recommendations_count=1,
        roadmap_initiative_count=0,
        chunks_indexed=3,
        reports_generated=(str(html_path), str(json_path)),
        elapsed_ms=10.0,
        knowledge_repository_id=f"repo:{label}",
        knowledge_run_id=scan_id,
        status=OnboardingStatus.SUCCEEDED,
    )
    return OnboardingResult(
        status=OnboardingStatus.SUCCEEDED,
        summary=summary,
        manifest=manifest,
        manifest_path=str(run_dir / "repository-onboarding.json"),
    )


def test_questions_passed_hard_failure() -> None:
    ok, _ = questions_passed([{"status": "failed", "citations": 0}])
    assert not ok
    ok, detail = questions_passed([{"status": "insufficient_evidence", "citations": 0}])
    assert ok
    assert "pipeline ok" in detail


def test_reports_live_equal_ignores_scan_id(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    _write_report(path, tmp_path)
    left = json.loads(path.read_text(encoding="utf-8"))
    right = json.loads(path.read_text(encoding="utf-8"))
    left.setdefault("manifest", {})["scan_id"] = "run-a"
    right.setdefault("manifest", {})["scan_id"] = "run-b"
    left["assessment"]["generated_at"] = "2026-01-01T00:00:00Z"
    right["assessment"]["generated_at"] = "2026-01-02T00:00:00Z"
    assert _reports_live_equal(left, right)


def test_acceptance_status_cli_missing(tmp_path: Path) -> None:
    result = runner.invoke(
        acceptance_app,
        ["status", "--output", str(tmp_path / "missing")],
    )
    assert result.exit_code == 1


def test_acceptance_run_with_mocked_onboard(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    calls = {"n": 0}

    def _fake_onboard(self, repository: str, **kwargs):  # noqa: ANN001
        del self, repository, kwargs
        calls["n"] += 1
        return _onboarding_result(tmp_path, "synthetic-multilang", scan_id=f"scan-{calls['n']}")

    monkeypatch.setattr(OnboardingApplicationService, "onboard", _fake_onboard)

    from types import SimpleNamespace

    from codestrata.application.acceptance import service as acceptance_service

    monkeypatch.setattr(
        acceptance_service,
        "ACCEPTANCE_TARGETS",
        (("synthetic-multilang", repo),),
    )
    rag = SimpleNamespace(
        load_corpus_from_run=lambda _p: object(),
        build_answer_stack=lambda *a, **k: (object(), object(), object(), object()),
        ask_predefined_questions=lambda *_a, **_k: [
            {"status": "success", "citations": 1}
        ],
        mcp_health_check=lambda *_a, **_k: {"status": "success"},
    )
    monkeypatch.setattr(acceptance_service, "load_acceptance_rag_helpers", lambda: rag)
    monkeypatch.setattr(
        acceptance_service,
        "questions_passed",
        lambda _rows: (True, "1/1 grounded"),
    )
    monkeypatch.setattr(
        acceptance_service,
        "mcp_health_passed",
        lambda _payload: (True, "success"),
    )

    out = tmp_path / "mvp"
    result = MvpAcceptanceService().run(
        output_directory=out,
        repositories=("synthetic-multilang",),
    )
    assert result.ok
    assert (out / "summary.json").is_file()
    assert (out / "summary.md").is_file()
    loaded = load_acceptance_summary(out)
    assert loaded is not None
    assert loaded["ok"] is True

    cli = runner.invoke(acceptance_app, ["status", "--output", str(out)])
    assert cli.exit_code == 0
    assert "PASS" in cli.stdout


def test_acceptance_config_profile_commands(tmp_path: Path) -> None:
    """MVP acceptance surface includes config profile/validate commands."""

    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        """,
        encoding="utf-8",
    )
    profile = runner.invoke(
        app,
        ["config", "profile", "--config", str(config), "--profile", "local"],
        env={"CODESTRATA_PROFILE": None, "AWS_REGION": None, "AWS_PROFILE": None},
    )
    assert profile.exit_code == 0, profile.output
    assert json.loads(profile.output)["profile"] == "local"

    validate = runner.invoke(
        app,
        ["config", "validate", "--config", str(config), "--profile", "community"],
        env={"CODESTRATA_PROFILE": None, "AWS_REGION": None, "AWS_PROFILE": None},
    )
    assert validate.exit_code == 0, validate.output
    assert json.loads(validate.output)["ok"] is True
