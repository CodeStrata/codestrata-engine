"""Assessment knowledge persistence integration tests."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.knowledge import AssessmentRunStatus, KnowledgeArtifactKind
from codestrata.cli.assess import run_assessment
from codestrata.config import CodestrataSettings
from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore
from codestrata.reporting import AssessmentMode


def _settings(repo_path: Path, knowledge_dir: Path) -> CodestrataSettings:
    return CodestrataSettings.model_validate(
        {
            "repository": {"path": str(repo_path)},
            "workspace": {"directory": ".codestrata-workspace"},
            "knowledge": {"directory": str(knowledge_dir)},
            "static_analysis": {"enabled": False},
            "ai": {"bedrock": {}},
        }
    )


def test_assessment_persists_completed_run(tmp_path: Path) -> None:
    repo = tmp_path / "sample"
    repo.mkdir()
    (repo / "README.md").write_text("# sample\n", encoding="utf-8")
    (repo / "package.json").write_text('{"name":"sample"}\n', encoding="utf-8")
    knowledge_dir = tmp_path / "knowledge"
    output = tmp_path / "reports"

    with SqliteKnowledgeStore(knowledge_dir) as store:
        result = run_assessment(
            repo=str(repo),
            output_directory=output,
            mode=AssessmentMode.DETERMINISTIC,
            settings=_settings(repo, knowledge_dir),
            static_analysis_enabled=False,
            knowledge_store=store,
        )
        assert result.html_report_path.is_file()
        repos = store.registry.list_repositories()
        assert len(repos) == 1
        latest = store.runs.get_latest_completed_run(repos[0].repository_id)
        assert latest is not None
        assert latest.status is AssessmentRunStatus.COMPLETED
        kinds = {a.artifact_kind for a in store.runs.list_artifacts(latest.run_id)}
        assert KnowledgeArtifactKind.REPOSITORY_GRAPH in kinds
        assert KnowledgeArtifactKind.FINDINGS in kinds
        assert KnowledgeArtifactKind.RECOMMENDATIONS in kinds
        # Report prune independence: knowledge remains after report path exists
        assert store.snapshots.get_latest_snapshot(repos[0].repository_id) is not None
