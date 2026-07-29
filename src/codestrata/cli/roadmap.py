"""CLI for Modernization Roadmap Engine inspection (Phase 5.10)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

roadmap_app = typer.Typer(
    name="roadmap",
    help=(
        "Engine assess modernization roadmap section helpers.\n\n"
        "Inspect phased plans from report.json produced by Community Engine "
        "assess when `[report.sections.roadmap] enabled = true` "
        "(disabled by default). Does not re-run assessments.\n\n"
        "Distinct from CodeStrata Platform Strategic Roadmap."
    ),
    no_args_is_help=True,
)


def _load_report_roadmap_section(report: Path) -> dict[str, Any]:
    if not report.is_file():
        raise typer.BadParameter(f"report.json not found: {report}")
    try:
        payload = json.loads(report.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise typer.BadParameter(f"report.json is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise typer.BadParameter("report.json must be a JSON object")
    assessment = payload.get("assessment")
    if not isinstance(assessment, dict):
        raise typer.BadParameter("report.json missing assessment object")
    roadmap = assessment.get("roadmap")
    if roadmap is None:
        raise typer.BadParameter(
            "Roadmap report section absent. Enable [report.sections.roadmap] and "
            "re-run assess, or pass a report that includes assessment.roadmap."
        )
    if not isinstance(roadmap, dict):
        raise typer.BadParameter("assessment.roadmap must be a JSON object")
    return roadmap


def _as_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


@roadmap_app.command("inspect")
def inspect_roadmap_report(
    report: Annotated[
        Path,
        typer.Option("--report", help="Path to report.json from an assess run."),
    ],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Inspect the phased modernization roadmap section from report.json."""

    section = _load_report_roadmap_section(report)
    if json_output:
        typer.echo(json.dumps(section, indent=2, sort_keys=True))
        return
    typer.echo(f"status: {section.get('status_label') or section.get('status')}")
    typer.echo(f"summary: {section.get('summary')}")
    typer.echo(f"confidence: {section.get('confidence')}")
    typer.echo(f"phases: {len(_as_list(section.get('phases')))}")
    initiative_total = section.get(
        "initiatives_total",
        len(_as_list(section.get("initiatives"))),
    )
    typer.echo(f"initiatives: {initiative_total}")
    typer.echo(f"engine: {section.get('engine_version')}")


@roadmap_app.command("phases")
def list_roadmap_phases(
    report: Annotated[
        Path,
        typer.Option("--report", help="Path to report.json from an assess run."),
    ],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """List roadmap phases from report.json."""

    section = _load_report_roadmap_section(report)
    phases = _as_list(section.get("phases"))
    if json_output:
        typer.echo(json.dumps(phases, indent=2, sort_keys=True))
        return
    if not phases:
        typer.echo("No roadmap phases.")
        return
    for phase in phases:
        if not isinstance(phase, dict):
            continue
        ids = _as_list(phase.get("initiative_ids"))
        typer.echo(
            f"{phase.get('sequence')}: {phase.get('title')} "
            f"({len(ids)} initiative(s)) — {phase.get('objective')}"
        )


@roadmap_app.command("initiatives")
def list_roadmap_initiatives(
    report: Annotated[
        Path,
        typer.Option("--report", help="Path to report.json from an assess run."),
    ],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """List roadmap initiatives from report.json."""

    section = _load_report_roadmap_section(report)
    initiatives = _as_list(section.get("initiatives"))
    if json_output:
        typer.echo(json.dumps(initiatives, indent=2, sort_keys=True))
        return
    if not initiatives:
        typer.echo("No roadmap initiatives.")
        return
    for item in initiatives:
        if not isinstance(item, dict):
            continue
        typer.echo(
            f"{item.get('sequence')}: [{item.get('phase')}] {item.get('title')} "
            f"priority={item.get('priority')} effort={item.get('effort')} "
            f"risk={item.get('risk')}"
        )


@roadmap_app.command("generate")
def generate_roadmap_preview(
    recommendations: Annotated[
        Path,
        typer.Option(
            "--recommendations",
            help="recommendations.json (Phase 3 RecommendationResult) artifact.",
        ),
    ],
    findings: Annotated[
        Path | None,
        typer.Option(
            "--findings",
            help="Optional findings.json (Phase 3 RuleEvaluationResult) artifact.",
        ),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json")] = True,
) -> None:
    """Generate a roadmap preview from existing recommendation/finding artifacts.

    Does not re-run assessment. Writes to stdout only.
    """

    from codestrata.application.roadmap import ModernizationRoadmapEngine
    from codestrata.domain.findings import RuleEvaluationResult
    from codestrata.domain.recommendations import RecommendationResult
    from codestrata.reporting.roadmap.adapter import RoadmapReportAdapter

    if not recommendations.is_file():
        raise typer.BadParameter(f"recommendations artifact not found: {recommendations}")
    rec_payload = json.loads(recommendations.read_text(encoding="utf-8"))
    if not isinstance(rec_payload, dict):
        raise typer.BadParameter("recommendations artifact must be a JSON object")
    try:
        recommendation_result = RecommendationResult.model_validate(rec_payload)
    except Exception:
        # Accept assess-run recommendations.json shape (recommendations_payload).
        recommendation_result = RecommendationResult.model_validate(
            {
                "version": rec_payload.get("version", "1.0.0"),
                "recommendations": rec_payload.get("recommendations", []),
                "providers_evaluated": rec_payload.get("providers_evaluated", []),
                "providers_skipped": rec_payload.get("providers_skipped", []),
                "recommendation_count": rec_payload.get(
                    "recommendation_count",
                    len(rec_payload.get("recommendations", []) or []),
                ),
                "unmatched_finding_ids": rec_payload.get("unmatched_finding_ids", []),
            }
        )
    rule_evaluation = None
    if findings is not None:
        if not findings.is_file():
            raise typer.BadParameter(f"findings artifact not found: {findings}")
        finding_payload = json.loads(findings.read_text(encoding="utf-8"))
        if not isinstance(finding_payload, dict):
            raise typer.BadParameter("findings artifact must be a JSON object")
        try:
            rule_evaluation = RuleEvaluationResult.model_validate(finding_payload)
        except Exception:
            findings_list = finding_payload.get("findings", [])
            rule_evaluation = RuleEvaluationResult.model_validate(
                {
                    "findings": findings_list,
                    "rules_evaluated": finding_payload.get("rules_evaluated", []),
                    "rules_skipped": finding_payload.get("rules_skipped", []),
                    "finding_count": finding_payload.get(
                        "finding_count",
                        len(findings_list or []),
                    ),
                }
            )
    domain = ModernizationRoadmapEngine().generate_from_artifacts(
        recommendation_result=recommendation_result,
        rule_evaluation=rule_evaluation,
    )
    report = RoadmapReportAdapter().adapt(domain)
    payload = report.model_dump(mode="json")
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(payload.get("summary"))
    typer.echo(f"initiatives: {payload.get('initiatives_total')}")
