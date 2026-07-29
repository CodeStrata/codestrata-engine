"""CLI for Architecture Conclusions (Phase 4.2.3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from codestrata.application.architecture.conclusions.factory import (
    create_architecture_conclusion_service,
)
from codestrata.config import load_settings

architecture_app = typer.Typer(
    name="architecture",
    help=(
        "Architecture assessment helpers.\n\n"
        "Conclusions, assessment sections, and report presentation are optional "
        "(`[analysis.architecture_conclusions]` / "
        "`[assessment.sections.architecture]` / "
        "`[report.sections.architecture]`; all disabled by default)."
    ),
    no_args_is_help=True,
)

conclusions_app = typer.Typer(
    name="conclusions",
    help="Inspect architecture conclusion policies and results.",
    no_args_is_help=True,
)
architecture_app.add_typer(conclusions_app, name="conclusions")

assessment_app = typer.Typer(
    name="assessment",
    help="Inspect architecture assessment section artifacts (Phase 4.2.4).",
    no_args_is_help=True,
)
architecture_app.add_typer(assessment_app, name="assessment")

report_app = typer.Typer(
    name="report",
    help=(
        "Inspect architecture presentation content from report.json "
        "(Phase 4.2.5; does not re-run analysis)."
    ),
    no_args_is_help=True,
)
architecture_app.add_typer(report_app, name="report")


def _load_assessment_artifact(artifact: Path) -> dict[str, Any]:
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise typer.BadParameter("architecture assessment artifact must be a JSON object")
    return payload


def _load_report_architecture_section(report: Path) -> dict[str, Any]:
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
    architecture = assessment.get("architecture")
    if architecture is None:
        raise typer.BadParameter(
            "Architecture report section absent. Enable "
            "[report.sections.architecture] and re-run assess, or pass a report "
            "that includes assessment.architecture."
        )
    if not isinstance(architecture, dict):
        raise typer.BadParameter("assessment.architecture must be a JSON object")
    return architecture


def _as_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


@assessment_app.command("inspect")
def inspect_architecture_assessment(
    artifact: Annotated[
        Path,
        typer.Option(
            "--artifact",
            help="architecture-assessment.json from an assess run.",
        ),
    ],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Inspect the architecture assessment section summary."""

    payload = _load_assessment_artifact(artifact)
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "section_id": payload.get("section_id"),
                    "section_version": payload.get("section_version"),
                    "status": payload.get("status"),
                    "architecture_pack_id": payload.get("architecture_pack_id"),
                    "architecture_pack_version": payload.get("architecture_pack_version"),
                    "finding_ids": payload.get("finding_ids", []),
                    "conclusion_ids": payload.get("conclusion_ids", []),
                    "recommendation_group_ids": payload.get(
                        "recommendation_group_ids", []
                    ),
                    "business_impact": payload.get("business_impact"),
                    "execution_summary": payload.get("execution_summary"),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return
    typer.echo(f"section: {payload.get('section_id')}@{payload.get('section_version')}")
    typer.echo(f"status: {payload.get('status')}")
    typer.echo(
        f"pack: {payload.get('architecture_pack_id')}@"
        f"{payload.get('architecture_pack_version')}"
    )
    typer.echo(f"findings: {len(_as_list(payload.get('finding_ids')))}")
    typer.echo(f"conclusions: {len(_as_list(payload.get('conclusion_ids')))}")
    typer.echo(
        "recommendation groups: "
        f"{len(_as_list(payload.get('recommendation_group_ids')))}"
    )


@assessment_app.command("findings")
def list_architecture_assessment_findings(
    artifact: Annotated[Path, typer.Option("--artifact")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    payload = _load_assessment_artifact(artifact)
    findings = _as_list(payload.get("finding_summaries"))
    if json_output:
        typer.echo(json.dumps({"findings": findings}, indent=2, ensure_ascii=False))
        return
    for item in findings:
        if isinstance(item, dict):
            typer.echo(
                f"{item.get('finding_id')} [{item.get('severity')}] {item.get('title')}"
            )


@assessment_app.command("conclusions")
def list_architecture_assessment_conclusions(
    artifact: Annotated[Path, typer.Option("--artifact")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    payload = _load_assessment_artifact(artifact)
    conclusions = _as_list(payload.get("conclusions"))
    if json_output:
        typer.echo(
            json.dumps({"conclusions": conclusions}, indent=2, ensure_ascii=False)
        )
        return
    for item in conclusions:
        if isinstance(item, dict):
            typer.echo(
                f"{item.get('conclusion_id')} [{item.get('category')}] {item.get('title')}"
            )


@assessment_app.command("recommendations")
def list_architecture_assessment_recommendations(
    artifact: Annotated[Path, typer.Option("--artifact")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    payload = _load_assessment_artifact(artifact)
    groups = _as_list(payload.get("recommendation_groups"))
    if json_output:
        typer.echo(
            json.dumps({"recommendation_groups": groups}, indent=2, ensure_ascii=False)
        )
        return
    for item in groups:
        if isinstance(item, dict):
            typer.echo(
                f"{item.get('recommendation_group_id')}: {item.get('title')}"
            )


@assessment_app.command("coverage")
def show_architecture_assessment_coverage(
    artifact: Annotated[Path, typer.Option("--artifact")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    payload = _load_assessment_artifact(artifact)
    coverage = payload.get("coverage")
    if json_output:
        typer.echo(json.dumps({"coverage": coverage}, indent=2, ensure_ascii=False))
        return
    areas: list[object] = []
    if isinstance(coverage, dict):
        areas = _as_list(coverage.get("areas"))
    for item in areas:
        if isinstance(item, dict):
            typer.echo(
                f"{item.get('area_id')}: {item.get('status')} ratio={item.get('ratio')}"
            )


@assessment_app.command("limitations")
def show_architecture_assessment_limitations(
    artifact: Annotated[Path, typer.Option("--artifact")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    payload = _load_assessment_artifact(artifact)
    limitations = _as_list(payload.get("limitations"))
    if json_output:
        typer.echo(
            json.dumps({"limitations": limitations}, indent=2, ensure_ascii=False)
        )
        return
    for item in limitations:
        if isinstance(item, dict):
            typer.echo(f"{item.get('limitation_id')}: {item.get('summary')}")


@assessment_app.command("traceability")
def show_architecture_assessment_traceability(
    artifact: Annotated[Path, typer.Option("--artifact")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    payload = _load_assessment_artifact(artifact)
    trace = payload.get("traceability")
    edges = _as_list(trace.get("edges") if isinstance(trace, dict) else [])
    if json_output:
        typer.echo(
            json.dumps(
                {"edge_count": len(edges), "edges": edges},
                indent=2,
                ensure_ascii=False,
            )
        )
        return
    typer.echo(f"edges: {len(edges)}")
    for item in edges[:20]:
        if isinstance(item, dict):
            typer.echo(
                f"{item.get('relation')}: {item.get('source_id')} -> {item.get('target_id')}"
            )


@report_app.command("inspect")
def inspect_architecture_report(
    report: Annotated[
        Path,
        typer.Option("--report", help="report.json from an assess run."),
    ],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Inspect the architecture report presentation section."""

    section = _load_report_architecture_section(report)
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "section_id": section.get("section_id"),
                    "section_version": section.get("section_version"),
                    "status": section.get("status"),
                    "status_label": section.get("status_label"),
                    "executive_summary": section.get("executive_summary"),
                    "architecture_pack_id": section.get("architecture_pack_id"),
                    "architecture_pack_version": section.get(
                        "architecture_pack_version"
                    ),
                    "finding_count": len(_as_list(section.get("findings"))),
                    "conclusion_count": len(_as_list(section.get("conclusions"))),
                    "recommendation_group_count": len(
                        _as_list(section.get("recommendation_groups"))
                    ),
                    "key_metrics": section.get("key_metrics", []),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return
    typer.echo(f"section: {section.get('section_id')}@{section.get('section_version')}")
    typer.echo(f"status: {section.get('status_label')} ({section.get('status')})")
    typer.echo(
        f"pack: {section.get('architecture_pack_id')}@"
        f"{section.get('architecture_pack_version')}"
    )
    typer.echo(f"findings: {len(_as_list(section.get('findings')))}")
    typer.echo(f"conclusions: {len(_as_list(section.get('conclusions')))}")
    typer.echo(
        "recommendation groups: "
        f"{len(_as_list(section.get('recommendation_groups')))}"
    )
    summary = section.get("executive_summary")
    if summary:
        typer.echo("")
        typer.echo(str(summary))


@report_app.command("conclusions")
def list_architecture_report_conclusions(
    report: Annotated[Path, typer.Option("--report")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    section = _load_report_architecture_section(report)
    conclusions = _as_list(section.get("conclusions"))
    if json_output:
        typer.echo(
            json.dumps({"conclusions": conclusions}, indent=2, ensure_ascii=False)
        )
        return
    for item in conclusions:
        if isinstance(item, dict):
            typer.echo(
                f"{item.get('conclusion_id')} [{item.get('materiality')}] "
                f"{item.get('title')}"
            )


@report_app.command("recommendations")
def list_architecture_report_recommendations(
    report: Annotated[Path, typer.Option("--report")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    section = _load_report_architecture_section(report)
    groups = _as_list(section.get("recommendation_groups"))
    if json_output:
        typer.echo(
            json.dumps({"recommendation_groups": groups}, indent=2, ensure_ascii=False)
        )
        return
    for item in groups:
        if isinstance(item, dict):
            typer.echo(f"{item.get('recommendation_group_id')}: {item.get('title')}")


@report_app.command("findings")
def list_architecture_report_findings(
    report: Annotated[Path, typer.Option("--report")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    section = _load_report_architecture_section(report)
    findings = _as_list(section.get("findings"))
    if json_output:
        typer.echo(json.dumps({"findings": findings}, indent=2, ensure_ascii=False))
        return
    for item in findings:
        if isinstance(item, dict):
            linked = "linked" if item.get("linked_to_conclusion") else "unlinked"
            typer.echo(
                f"{item.get('finding_id')} [{item.get('severity')}] "
                f"{item.get('title')} ({linked})"
            )


@report_app.command("coverage")
def show_architecture_report_coverage(
    report: Annotated[Path, typer.Option("--report")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    section = _load_report_architecture_section(report)
    coverage = _as_list(section.get("coverage_summary"))
    if json_output:
        typer.echo(
            json.dumps({"coverage_summary": coverage}, indent=2, ensure_ascii=False)
        )
        return
    for item in coverage:
        if isinstance(item, dict):
            typer.echo(
                f"{item.get('label')}: {item.get('status')} — {item.get('display')}"
            )


@report_app.command("limitations")
def show_architecture_report_limitations(
    report: Annotated[Path, typer.Option("--report")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    section = _load_report_architecture_section(report)
    limitations = _as_list(section.get("limitations"))
    if json_output:
        typer.echo(
            json.dumps({"limitations": limitations}, indent=2, ensure_ascii=False)
        )
        return
    for item in limitations:
        if isinstance(item, dict):
            typer.echo(f"{item.get('category')}: {item.get('summary')}")


@report_app.command("traceability")
def show_architecture_report_traceability(
    report: Annotated[Path, typer.Option("--report")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    section = _load_report_architecture_section(report)
    trace = section.get("traceability_summary") or {}
    if json_output:
        typer.echo(
            json.dumps({"traceability_summary": trace}, indent=2, ensure_ascii=False)
        )
        return
    if isinstance(trace, dict):
        typer.echo(trace.get("summary") or f"edges: {trace.get('edge_count', 0)}")
        for item in _as_list(trace.get("sample_edges"))[:20]:
            if isinstance(item, dict):
                typer.echo(
                    f"{item.get('relation')}: {item.get('source_id')} -> "
                    f"{item.get('target_id')}"
                )


@conclusions_app.command("policies")
def list_policies(
    category: Annotated[str | None, typer.Option("--category")] = None,
    config: Annotated[Path, typer.Option("--config", "-c")] = Path("codestrata.toml"),
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """List architecture conclusion policies."""

    settings = load_settings(config) if config.exists() else None
    service = create_architecture_conclusion_service(settings)
    rows = service.list_policies(category=category)
    if json_output:
        typer.echo(json.dumps({"policies": rows}, indent=2, ensure_ascii=False))
        return
    for row in rows:
        typer.echo(f"{row['policy_id']}@{row['policy_version']} — {row['title']}")


@conclusions_app.command("list")
def list_conclusions(
    artifact: Annotated[
        Path,
        typer.Option("--artifact", help="architecture_conclusions.json from an assess run."),
    ],
    category: Annotated[str | None, typer.Option("--category")] = None,
    status: Annotated[str | None, typer.Option("--status")] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """List conclusions from a persisted assessment artifact."""

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    conclusions = payload.get("conclusions", [])
    if category:
        conclusions = [item for item in conclusions if item.get("category") == category]
    if status:
        conclusions = [item for item in conclusions if item.get("status") == status]
    if json_output:
        typer.echo(json.dumps({"conclusions": conclusions}, indent=2, ensure_ascii=False))
        return
    for item in conclusions:
        typer.echo(
            f"{item.get('conclusion_id')} [{item.get('category')}] {item.get('title')}"
        )


@conclusions_app.command("inspect")
def inspect_conclusion(
    conclusion_id: Annotated[str, typer.Argument()],
    artifact: Annotated[Path, typer.Option("--artifact")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Inspect one conclusion from an artifact."""

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    match = next(
        (
            item
            for item in payload.get("conclusions", [])
            if item.get("conclusion_id") == conclusion_id
        ),
        None,
    )
    if match is None:
        typer.echo("Conclusion not found", err=True)
        raise typer.Exit(code=1)
    if json_output:
        typer.echo(json.dumps(match, indent=2, ensure_ascii=False))
        return
    for key in (
        "conclusion_id",
        "category",
        "title",
        "summary",
        "executive_interpretation",
        "primary_finding_id",
        "confidence",
        "materiality",
        "business_impact",
    ):
        typer.echo(f"{key}: {match.get(key)}")


@conclusions_app.command("explain")
def explain_conclusion(
    conclusion_id: Annotated[str, typer.Argument()],
    artifact: Annotated[Path, typer.Option("--artifact")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Explain relationships and source findings for a conclusion."""

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    match = next(
        (
            item
            for item in payload.get("conclusions", [])
            if item.get("conclusion_id") == conclusion_id
        ),
        None,
    )
    if match is None:
        typer.echo("Conclusion not found", err=True)
        raise typer.Exit(code=1)
    source_ids = set(match.get("source_finding_ids", []))
    relationships = [
        item
        for item in payload.get("relationships", [])
        if item.get("source_finding_id") in source_ids
        or item.get("target_finding_id") in source_ids
    ]
    explanation = {
        "conclusion_id": conclusion_id,
        "source_finding_ids": match.get("source_finding_ids", []),
        "relationships": relationships,
        "limitations": match.get("limitations", []),
        "technical_interpretation": match.get("technical_interpretation"),
        "executive_interpretation": match.get("executive_interpretation"),
    }
    if json_output:
        typer.echo(json.dumps(explanation, indent=2, ensure_ascii=False))
        return
    typer.echo(explanation["executive_interpretation"])
    typer.echo(f"Sources: {', '.join(explanation['source_finding_ids'])}")


@conclusions_app.command("plan")
def plan_conclusions(
    config: Annotated[Path, typer.Option("--config", "-c")] = Path("codestrata.toml"),
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Show which conclusion policies would run under current configuration."""

    settings = load_settings(config) if config.exists() else None
    service = create_architecture_conclusion_service(settings)
    rows_list = list(service.list_policies())
    enabled = True
    if settings is not None:
        enabled = settings.analysis.architecture_conclusions.enabled
        from codestrata.application.architecture.conclusions.factory import enabled_policy_ids

        active = enabled_policy_ids(settings)
        rows_list = [row for row in rows_list if row["policy_id"] in active]
    payload = {"feature_enabled": enabled, "policies": rows_list}
    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    typer.echo(f"Feature enabled: {enabled}")
    for row in rows_list:
        typer.echo(f"  - {row['policy_id']}")
