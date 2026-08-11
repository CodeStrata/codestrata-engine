"""Load assessment run artifacts for SV.5 (privacy-safe references)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class AssessmentRunArtifacts:
    """Loaded artifacts for one assessment run directory."""

    run_id: str
    source: str
    repository_id: str | None
    project_name: str | None
    github_repository: str | None
    qualified_revision_type: str | None
    qualified_revision_value: str | None
    assessment_run_reference: str
    run_directory: Path
    report: dict[str, Any]
    findings: dict[str, Any] | list[Any]
    recommendations: dict[str, Any] | list[Any]
    html: str
    present_files: tuple[str, ...]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def assessment_of(report: dict[str, Any]) -> dict[str, Any]:
    assessment = report.get("assessment")
    return assessment if isinstance(assessment, dict) else report


def load_run_directory(
    run_directory: Path,
    *,
    run_id: str,
    source: str,
    assessment_run_reference: str,
    repository_id: str | None = None,
    project_name: str | None = None,
    github_repository: str | None = None,
    qualified_revision_type: str | None = None,
    qualified_revision_value: str | None = None,
) -> AssessmentRunArtifacts:
    report_path = run_directory / "report.json"
    findings_path = run_directory / "findings.json"
    recommendations_path = run_directory / "recommendations.json"
    html_path = run_directory / "report.html"
    missing = [
        name
        for name, path in (
            ("report.json", report_path),
            ("findings.json", findings_path),
            ("recommendations.json", recommendations_path),
            ("report.html", html_path),
        )
        if not path.is_file()
    ]
    if missing:
        raise FileNotFoundError(f"missing artifacts: {', '.join(missing)}")

    present = tuple(sorted(p.name for p in run_directory.iterdir() if p.is_file()))
    return AssessmentRunArtifacts(
        run_id=run_id,
        source=source,
        repository_id=repository_id,
        project_name=project_name,
        github_repository=github_repository,
        qualified_revision_type=qualified_revision_type,
        qualified_revision_value=qualified_revision_value,
        assessment_run_reference=assessment_run_reference,
        run_directory=run_directory,
        report=_load_json(report_path),
        findings=_load_json(findings_path),
        recommendations=_load_json(recommendations_path),
        html=html_path.read_text(encoding="utf-8"),
        present_files=present,
    )


def finding_list(findings_doc: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(findings_doc, list):
        return [item for item in findings_doc if isinstance(item, dict)]
    items = findings_doc.get("findings") or []
    return [item for item in items if isinstance(item, dict)]


def recommendation_list(
    recommendations_doc: dict[str, Any] | list[Any],
) -> list[dict[str, Any]]:
    if isinstance(recommendations_doc, list):
        return [item for item in recommendations_doc if isinstance(item, dict)]
    items = recommendations_doc.get("recommendations") or []
    return [item for item in items if isinstance(item, dict)]


def report_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    assessment = assessment_of(report)
    return [item for item in (assessment.get("findings") or []) if isinstance(item, dict)]


def report_recommendations(report: dict[str, Any]) -> list[dict[str, Any]]:
    assessment = assessment_of(report)
    items = assessment.get("deterministic_recommendations") or assessment.get("recommendations") or []
    return [item for item in items if isinstance(item, dict)]


def report_priority_actions(report: dict[str, Any]) -> list[dict[str, Any]]:
    assessment = assessment_of(report)
    return [
        item for item in (assessment.get("priority_actions") or []) if isinstance(item, dict)
    ]


def report_evidence(report: dict[str, Any]) -> list[dict[str, Any]]:
    assessment = assessment_of(report)
    return [item for item in (assessment.get("evidence") or []) if isinstance(item, dict)]
