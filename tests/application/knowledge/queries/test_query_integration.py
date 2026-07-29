"""End-to-end assessment → knowledge query integration."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.cli.assess import run_assessment
from codestrata.config import CodestrataSettings
from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore
from codestrata.reporting import AssessmentMode


def test_query_service_reads_assessment_without_reports(tmp_path: Path) -> None:
    repo = tmp_path / "sample"
    repo.mkdir()
    (repo / "README.md").write_text("# sample\n", encoding="utf-8")
    (repo / "package.json").write_text('{"name":"sample"}\n', encoding="utf-8")
    knowledge_dir = tmp_path / "knowledge"
    output = tmp_path / "reports"
    settings = CodestrataSettings.model_validate(
        {
            "repository": {"path": str(repo)},
            "workspace": {"directory": ".codestrata-workspace"},
            "knowledge": {"directory": str(knowledge_dir)},
            "static_analysis": {"enabled": False},
            "ai": {"bedrock": {}},
        }
    )

    with SqliteKnowledgeStore(knowledge_dir) as store:
        result = run_assessment(
            repo=str(repo),
            output_directory=output,
            mode=AssessmentMode.DETERMINISTIC,
            settings=settings,
            static_analysis_enabled=False,
            knowledge_store=store,
        )
        assert result.html_report_path.is_file()

        service = KnowledgeQueryService(store)
        repos = service.list_repositories()
        assert len(repos) == 1
        latest = service.get_latest_completed_run(repos[0].repository_id)
        assert latest is not None
        snapshot = service.get_latest_repository_snapshot(repos[0].repository_id)
        assert snapshot is not None
        manifest = service.get_repository_manifest(snapshot.snapshot_id)
        assert manifest.files
        graph = service.get_repository_graph(run_id=latest.run_id)
        assert graph.nodes
        findings = service.get_findings(latest.run_id)
        recommendations = service.get_recommendations(latest.run_id)
        assert isinstance(findings, tuple)
        assert isinstance(recommendations, tuple)
        # Query path must not depend on opening report artifacts.
        assert "report.json" not in str(service.get_assessment_run(latest.run_id).model_dump())
        comparison = service.compare_repository_snapshots(
            snapshot.snapshot_id,
            snapshot.snapshot_id,
        )
        assert comparison.counts.added == 0
