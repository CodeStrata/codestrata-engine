"""CLI tests for roadmap inspect/generate (Phase 5.10)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from codestrata.application.roadmap import (
    ModernizationRoadmapEngine,
    RoadmapSourceRecommendation,
)
from codestrata.cli import app
from codestrata.domain.recommendations import (
    Recommendation,
    RecommendationAction,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationResult,
)
from codestrata.reporting.roadmap.adapter import RoadmapReportAdapter

runner = CliRunner()


def test_roadmap_inspect_from_report(tmp_path: Path) -> None:
    domain = ModernizationRoadmapEngine().generate(
        recommendations=(
            RoadmapSourceRecommendation(
                id="r1",
                title="Add tests",
                summary="Add tests",
                priority="high",
                category="testing",
                related_finding_ids=("f1",),
                action_count=1,
            ),
        )
    )
    section = RoadmapReportAdapter().adapt(domain)
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "schema_version": "1.2",
                "assessment": {"roadmap": section.model_dump(mode="json")},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["roadmap", "inspect", "--report", str(report)])
    assert result.exit_code == 0
    assert "Succeeded" in result.stdout or "succeeded" in result.stdout.lower()
    assert "initiative" in result.stdout.lower()


def test_roadmap_generate_from_recommendations(tmp_path: Path) -> None:
    rec = Recommendation.create(
        provider_id="test",
        title="Add README",
        summary="Document the repository",
        rationale="Missing documentation finding",
        priority=RecommendationPriority.MEDIUM,
        category=RecommendationCategory.DOCUMENTATION,
        related_finding_ids=("finding-docs",),
        actions=(
            RecommendationAction(
                order=1,
                title="Create README",
                description="Add a top-level README.md",
            ),
        ),
    )
    result = RecommendationResult.from_recommendations(
        recommendations=(rec,),
        providers_evaluated=("test",),
    )
    artifact = tmp_path / "recommendations.json"
    artifact.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    cli = runner.invoke(
        app,
        ["roadmap", "generate", "--recommendations", str(artifact), "--json"],
    )
    assert cli.exit_code == 0
    payload = json.loads(cli.stdout)
    assert payload["status"] == "succeeded"
    assert payload["initiatives_total"] >= 1
