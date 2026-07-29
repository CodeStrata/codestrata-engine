"""Render analysis results for command-line users."""

import json
from collections.abc import Mapping
from typing import Any

import typer

from codestrata.models import AnalysisResult


def render_text(result: AnalysisResult) -> None:
    """Render a concise human-readable analysis summary."""

    typer.echo()
    typer.echo("Repository")
    typer.echo("-" * 60)
    typer.echo(f"Name:            {result.repository.name}")
    typer.echo(f"Files:           {result.repository.total_files}")
    typer.echo(f"Source:          {result.repository.source_url or 'Local repository'}")

    typer.echo()
    typer.echo("Detected Technologies")
    typer.echo("-" * 60)

    if result.technologies:
        for technology in result.technologies:
            version = f" {technology.version}" if technology.version else ""
            typer.echo(
                f"- {technology.name}{version} "
                f"({technology.category.value}, "
                f"{technology.confidence:.0%} confidence)"
            )
    else:
        typer.echo("No supported technologies detected.")

    typer.echo()
    typer.echo("Repository Metrics")
    typer.echo("-" * 60)

    metrics = _get_repository_metrics(result)

    if metrics:
        _render_metrics(metrics)
    else:
        typer.echo("No repository metrics available.")

    typer.echo()
    typer.echo("Analysis")
    typer.echo("-" * 60)
    typer.echo(f"Findings:        {len(result.findings)}")
    typer.echo(f"Recommendations: {len(result.recommendations)}")
    typer.echo(f"Analyzer:        {result.analyzer_version}")

    if result.started_at and result.completed_at:
        duration_ms = (result.completed_at - result.started_at).total_seconds() * 1000

        typer.echo(f"Duration:        {duration_ms:.2f} ms")

    typer.echo()


def render_json(result: AnalysisResult) -> None:
    """Render the complete analysis result as formatted JSON."""

    typer.echo(
        json.dumps(
            result.model_dump(mode="json"),
            indent=2,
        )
    )


def _get_repository_metrics(
    result: AnalysisResult,
) -> Mapping[str, Any] | None:
    """Return repository metrics from the consolidated metrics finding."""

    for finding in result.findings:
        if finding.rule_id == "repository.metrics.summary":
            return finding.metadata

    return None


def _render_metrics(metrics: Mapping[str, Any]) -> None:
    """Render repository metrics in a stable display order."""

    labels = {
        "total_files": "Total files",
        "source_files": "Source files",
        "test_files": "Test files",
        "configuration_files": "Configuration files",
        "build_files": "Build files",
        "docker_files": "Docker artifacts",
        "github_workflows": "GitHub workflows",
        "kubernetes_manifests": "Kubernetes manifests",
    }

    for key, label in labels.items():
        value = metrics.get(key)

        if value is not None:
            typer.echo(f"{label + ':':<22}{value}")
