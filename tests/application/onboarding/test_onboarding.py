"""Repository onboarding tests (Phase 5.11)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codestrata.application.assessment.service import AssessmentCommandResult
from codestrata.application.onboarding import (
    OnboardingApplicationService,
    format_onboarding_result,
)
from codestrata.application.onboarding.manifest import (
    load_onboarding_manifest,
    write_onboarding_manifest,
)
from codestrata.application.onboarding.settings_overrides import apply_onboarding_settings
from codestrata.application.onboarding.validation import (
    validate_embedding_provider,
    validate_output_directory,
    validate_repository_source,
)
from codestrata.cli import app
from codestrata.config.settings import CodestrataSettings
from codestrata.domain.onboarding.enums import OnboardingStatus
from codestrata.domain.onboarding.errors import OnboardingError
from codestrata.domain.onboarding.models import RepositoryOnboardingManifest
from codestrata.reporting.modernization_models import AssessmentMode

runner = CliRunner()


def _settings(tmp_path: Path, repo: Path) -> CodestrataSettings:
    return CodestrataSettings.model_validate(
        {
            "repository": {"path": str(repo)},
            "workspace": {"directory": str(tmp_path / "ws")},
            "static_analysis": {"enabled": False},
            "knowledge": {"directory": str(tmp_path / "knowledge")},
            "ai": {"bedrock": {}, "embedding_provider": "deterministic"},
        }
    )


def _fake_assessment(
    tmp_path: Path,
    *,
    write_reports: bool = True,
    force_reindex: bool = False,
    repo_name: str = "demo-app",
) -> AssessmentCommandResult:
    run_dir = tmp_path / "reports" / repo_name / "20260725-120000"
    run_dir.mkdir(parents=True, exist_ok=True)
    html = run_dir / "report.html"
    json_report = run_dir / "report.json"
    if write_reports:
        html.write_text("<html>ok</html>", encoding="utf-8")
        json_report.write_text(
            json.dumps(
                {
                    "schema_version": "1.2",
                    "assessment": {
                        "technologies": [
                            {"name": "Python", "category": "language"},
                            {"name": "FastAPI", "category": "framework"},
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )
    return AssessmentCommandResult(
        repository_name=repo_name,
        run_directory=run_dir,
        html_report_path=html,
        json_report_path=json_report,
        mode=AssessmentMode.DETERMINISTIC,
        findings_count=2,
        technologies_count=2,
        recommendations_count=3,
        phases_count=0,
        ai_executed=False,
        duration_ms=12.0,
        rule_finding_count=2,
        phase3_recommendation_count=3,
        roadmap_report_initiative_count=1,
        knowledge_repository_id="repo-1",
        knowledge_run_id="run-1",
        knowledge_snapshot_id="snap-1",
        knowledge_corpus_id="corpus-1",
        knowledge_chunk_count=4,
        knowledge_index_status="succeeded" if not force_reindex else "succeeded",
        knowledge_vector_count=4,
        knowledge_index_fingerprint="fp-abc",
    )


def test_validate_repository_and_provider(tmp_path: Path) -> None:
    repo = tmp_path / "app"
    repo.mkdir()
    assert Path(validate_repository_source(str(repo))).exists()
    with pytest.raises(OnboardingError, match="does not exist"):
        validate_repository_source(str(tmp_path / "missing"))
    assert validate_embedding_provider("deterministic") == "deterministic"
    with pytest.raises(OnboardingError, match="Unknown embedding provider"):
        validate_embedding_provider("anthropic")
    with pytest.raises(OnboardingError, match="not implemented"):
        validate_embedding_provider("local_sentence_transformer")


def test_output_directory_write_permissions(tmp_path: Path) -> None:
    out = validate_output_directory(tmp_path / "out")
    assert out.is_dir()


def test_settings_overrides_enable_knowledge(tmp_path: Path) -> None:
    repo = tmp_path / "app"
    repo.mkdir()
    settings = _settings(tmp_path, repo)
    assert settings.knowledge.projection.enabled is False
    enabled = apply_onboarding_settings(settings, skip_index=False, provider="openai")
    assert enabled.knowledge.projection.enabled is True
    assert enabled.knowledge.chunking.enabled is True
    assert enabled.knowledge.embedding.enabled is True
    assert enabled.knowledge.indexing.enabled is True
    assert enabled.knowledge.embedding.provider == "openai"
    assert enabled.ai.embedding_provider == "openai"
    assert enabled.report.sections.roadmap.enabled is True
    skipped = apply_onboarding_settings(settings, skip_index=True, provider=None)
    assert skipped.knowledge.indexing.enabled is False


def test_successful_onboarding_and_manifest(tmp_path: Path) -> None:
    repo = tmp_path / "app"
    repo.mkdir()
    settings = _settings(tmp_path, repo)
    calls: list[dict[str, object]] = []

    def fake_runner(**kwargs: object) -> AssessmentCommandResult:
        calls.append(kwargs)
        return _fake_assessment(
            tmp_path,
            write_reports=bool(kwargs.get("write_reports", True)),
            force_reindex=bool(kwargs.get("force_reindex", False)),
        )

    service = OnboardingApplicationService(assess_runner=fake_runner)
    result = service.onboard(
        str(repo),
        settings=settings,
        output_directory=tmp_path / "reports",
        provider="deterministic",
    )
    assert result.status == OnboardingStatus.SUCCEEDED
    assert result.summary.findings_count == 2
    assert result.summary.recommendations_count == 3
    assert result.summary.roadmap_initiative_count == 1
    assert result.summary.chunks_indexed == 4
    assert "Python" in result.summary.languages_detected
    assert "FastAPI" in result.summary.frameworks_detected
    assert result.manifest_path is not None
    loaded = load_onboarding_manifest(Path(result.manifest_path))
    assert loaded.repository_id == "repo-1"
    assert loaded.scan_id == "run-1"
    assert loaded.index_fingerprint == "fp-abc"
    assert loaded.embedding_provider == "deterministic"
    assert loaded.codestrata_version
    assert calls[0]["write_reports"] is True
    assert calls[0]["force_reindex"] is False


def test_force_reindex_and_skip_flags(tmp_path: Path) -> None:
    repo = tmp_path / "app"
    repo.mkdir()
    settings = _settings(tmp_path, repo)
    seen: dict[str, object] = {}

    def fake_runner(**kwargs: object) -> AssessmentCommandResult:
        seen.update(kwargs)
        return _fake_assessment(
            tmp_path,
            write_reports=bool(kwargs.get("write_reports", True)),
            force_reindex=bool(kwargs.get("force_reindex", False)),
        )

    service = OnboardingApplicationService(assess_runner=fake_runner)
    result = service.onboard(
        str(repo),
        settings=settings,
        output_directory=tmp_path / "reports",
        force_reindex=True,
        skip_report=True,
        skip_index=True,
    )
    assert seen["force_reindex"] is True
    assert seen["write_reports"] is False
    assert result.summary.chunks_indexed == 0
    assert result.summary.reports_generated == ()
    assert any("skip-report" in w.lower() for w in result.warnings)
    assert any("skip-index" in w.lower() for w in result.warnings)


def test_repeatable_onboarding(tmp_path: Path) -> None:
    repo = tmp_path / "app"
    repo.mkdir()
    settings = _settings(tmp_path, repo)
    service = OnboardingApplicationService(
        assess_runner=lambda **kwargs: _fake_assessment(tmp_path)
    )
    first = service.onboard(str(repo), settings=settings, output_directory=tmp_path / "r1")
    second = service.onboard(str(repo), settings=settings, output_directory=tmp_path / "r2")
    assert first.manifest.repository_id == second.manifest.repository_id
    assert first.summary.languages_detected == second.summary.languages_detected


def test_manifest_roundtrip(tmp_path: Path) -> None:
    manifest = RepositoryOnboardingManifest(
        repository_id="r1",
        repository_name="demo",
        scan_id="s1",
        report_version="1.2",
        scan_timestamp=datetime.now(UTC),
        codestrata_version="0.1.0",
        languages_detected=("Python",),
    )
    path = write_onboarding_manifest(manifest, tmp_path)
    loaded = load_onboarding_manifest(path)
    assert loaded.repository_id == "r1"
    assert loaded.languages_detected == ("Python",)


def test_cli_onboard_injected_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "app"
    repo.mkdir()
    config = tmp_path / "codestrata.toml"
    config.write_text(
        f"""
        [repository]
        path = "{repo}"

        [static_analysis]
        enabled = false
        """,
        encoding="utf-8",
    )

    def fake_run(repository: str, **kwargs: object):
        return OnboardingApplicationService(
            assess_runner=lambda **kw: _fake_assessment(tmp_path)
        ).onboard(
            repository,
            settings=_settings(tmp_path, repo),
            output_directory=tmp_path / "reports",
            skip_index=True,
        )

    monkeypatch.setattr("codestrata.cli.onboard.run_onboarding", fake_run)
    result = runner.invoke(
        app,
        [
            "onboard",
            str(repo),
            "--config",
            str(config),
            "--output",
            str(tmp_path / "reports"),
            "--skip-index",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Repository onboarding complete" in result.stdout


def test_provider_validation_in_cli(tmp_path: Path) -> None:
    repo = tmp_path / "app"
    repo.mkdir()
    config = tmp_path / "codestrata.toml"
    config.write_text(
        f"""
        [repository]
        path = "{repo}"
        """,
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "onboard",
            str(repo),
            "--config",
            str(config),
            "--provider",
            "not-a-provider",
        ],
    )
    assert result.exit_code == 1
    combined = result.stderr + result.stdout
    assert "Unknown embedding provider" in combined


def test_format_summary_includes_counts(tmp_path: Path) -> None:
    repo = tmp_path / "app"
    repo.mkdir()
    service = OnboardingApplicationService(
        assess_runner=lambda **kwargs: _fake_assessment(tmp_path)
    )
    result = service.onboard(
        str(repo),
        settings=_settings(tmp_path, repo),
        output_directory=tmp_path / "reports",
    )
    text = format_onboarding_result(result)
    assert "Findings:" in text
    assert "Roadmap initiatives:" in text
    assert "Chunks indexed:" in text
