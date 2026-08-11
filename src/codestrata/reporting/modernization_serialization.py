"""Serialization and file output helpers for modernization assessment reports."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from codestrata.reporters.report_paths import ReportPaths
from codestrata.reporting.assessment_json import (
    assessment_json_to_text,
    build_assessment_json_document,
)
from codestrata.reporting.customer_universe import write_customer_finding_artifacts
from codestrata.reporting.modernization_html import ModernizationHTMLReportRenderer
from codestrata.reporting.modernization_models import (
    AssessmentTiming,
    ModernizationReportInput,
)
from codestrata.reporting.modernization_view import validate_modernization_report_input


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise TypeError("Naive datetime is not supported")
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def modernization_report_input_to_dict(
    report_input: ModernizationReportInput,
) -> dict[str, Any]:
    """Return a deterministic JSON-ready dictionary of the internal report input."""

    return report_input.model_dump(mode="json")


def modernization_report_input_to_json(
    report_input: ModernizationReportInput,
    *,
    indent: int | None = 2,
) -> str:
    """Serialize ModernizationReportInput to stable JSON text."""

    payload = modernization_report_input_to_dict(report_input)
    return json.dumps(
        payload,
        indent=indent,
        sort_keys=True,
        ensure_ascii=False,
        default=_json_default,
        separators=(",", ": ") if indent is not None else (",", ":"),
    )


def modernization_report_input_from_json(
    payload: str | bytes | dict[str, Any],
) -> ModernizationReportInput:
    """Validate JSON (or a dict) against ModernizationReportInput."""

    if isinstance(payload, dict):
        data = payload
    else:
        data = json.loads(payload)
    return ModernizationReportInput.model_validate(data)


def write_modernization_html_report(
    report_input: ModernizationReportInput,
    output_path: Path | str,
) -> Path:
    """Render and write a UTF-8 HTML modernization assessment report."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    html = ModernizationHTMLReportRenderer().render(report_input)
    _atomic_write_text(path, html)
    return path


def write_modernization_json_report(
    report_input: ModernizationReportInput,
    output_path: Path | str,
) -> Path:
    """Validate, serialize, and write the sanitized assessment JSON report."""

    validated = validate_modernization_report_input(report_input)
    document = build_assessment_json_document(validated)
    text = assessment_json_to_text(document)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(path, text)
    return path


def write_modernization_assessment_reports(
    report_input: ModernizationReportInput,
    report_paths: ReportPaths,
) -> ReportPaths:
    """Validate once, render HTML, write assessment.html + lightweight assessment.json.

    Slice 17.12: ``assessment.json`` is a manifest (not a full head merge).
    Domain heads under ``heads/`` remain the source of truth. The full assessment
    JSON document is built in memory only to derive manifest summary fields and
    is not persisted as a duplicate artifact.
    """

    from time import perf_counter

    from codestrata.artifacts.layout import manifests_directory
    from codestrata.artifacts.manifest import (
        build_assessment_manifest,
        build_artifact_index_manifest,
        write_assessment_manifest,
        write_artifact_index_manifest,
    )

    validated = validate_modernization_report_input(report_input)
    started = perf_counter()
    artifact_input = validated
    document: dict[str, object]

    if validated.timing is None:
        html = ModernizationHTMLReportRenderer().render(validated)
        document = build_assessment_json_document(validated)
    else:
        base = validated.timing
        provisional = validated.model_copy(
            update={
                "timing": base.model_copy(
                    update={"report_ms": 0.0, "total_ms": base.total_ms}
                )
            }
        )
        html = ModernizationHTMLReportRenderer().render(provisional)
        report_ms = round((perf_counter() - started) * 1000, 2)
        total_ms = round(base.total_ms + report_ms, 2)
        finalized = validated.model_copy(
            update={
                "timing": AssessmentTiming(
                    total_ms=total_ms,
                    scan_ms=base.scan_ms,
                    analysis_ms=base.analysis_ms,
                    static_analysis_ms=base.static_analysis_ms,
                    ai_ms=base.ai_ms,
                    report_ms=report_ms,
                    graph_ms=base.graph_ms,
                    rules_ms=base.rules_ms,
                    evidence_ms=base.evidence_ms,
                    knowledge_ms=base.knowledge_ms,
                    files_loaded=base.files_loaded,
                    files_skipped=base.files_skipped,
                    cache_hits=base.cache_hits,
                    cache_misses=base.cache_misses,
                    peak_rss_mb=base.peak_rss_mb,
                )
            }
        )
        document = build_assessment_json_document(finalized)
        report_ms = round((perf_counter() - started) * 1000, 2)
        total_ms = round(base.total_ms + report_ms, 2)
        timing_payload = document.get("assessment", {}).get("timing")  # type: ignore[union-attr]
        if isinstance(timing_payload, dict):
            timing_payload["report_ms"] = report_ms
            timing_payload["total_ms"] = total_ms
        artifact_input = finalized

    run_directory = report_paths.run_directory
    run_directory.mkdir(parents=True, exist_ok=True)
    if report_paths.heads_directory is not None:
        report_paths.heads_directory.mkdir(parents=True, exist_ok=True)

    temp_paths: list[Path] = []
    renamed_paths: list[Path] = []
    try:
        temp_paths.append(_write_temp_sibling(report_paths.html_report_path, html))
        os.replace(temp_paths[0], report_paths.html_report_path)
        renamed_paths.append(report_paths.html_report_path)
        temp_paths.clear()
        write_customer_finding_artifacts(artifact_input, run_directory)

        assessment_block = document.get("assessment") if isinstance(document, dict) else None
        repo_block = document.get("repository") if isinstance(document, dict) else None
        summary = None
        scores: dict[str, object] = {}
        findings_summary: dict[str, object] = {}
        git_metadata: dict[str, object] = {}
        if isinstance(assessment_block, dict):
            summary = assessment_block.get("summary") or assessment_block.get("title")
            raw_scores = assessment_block.get("scores")
            if isinstance(raw_scores, dict):
                scores = raw_scores
            raw_findings = assessment_block.get("findings_summary")
            if isinstance(raw_findings, dict):
                findings_summary = raw_findings
        if isinstance(repo_block, dict):
            git_metadata = {
                key: repo_block.get(key)
                for key in ("commit", "branch", "remote", "name")
                if repo_block.get(key) is not None
            }

        run_id = report_paths.run_id or run_directory.name
        repository_name = report_paths.repository_name
        if isinstance(repo_block, dict) and repo_block.get("name"):
            repository_name = str(repo_block["name"])

        manifest = build_assessment_manifest(
            assessment_id=run_id,
            repository=repository_name,
            run_directory=run_directory,
            overall_summary=str(summary) if summary is not None else None,
            overall_scores=scores,
            findings_summary=findings_summary,
            git_metadata=git_metadata,
        )
        write_assessment_manifest(report_paths.json_report_path, manifest)
        renamed_paths.append(report_paths.json_report_path)

        # Refresh lightweight root index (best-effort).
        try:
            assessments_root = run_directory.parent
            runs = []
            if assessments_root.is_dir():
                for child in sorted(assessments_root.iterdir()):
                    if child.is_dir() and (child / "assessment.json").is_file():
                        runs.append(
                            {
                                "run_id": child.name,
                                "path": f"assessments/{child.name}",
                            }
                        )
            index = build_artifact_index_manifest(assessment_runs=runs)
            write_artifact_index_manifest(
                manifests_directory() / "artifact-manifest.json",
                index,
            )
        except OSError:
            pass
    except Exception:
        for renamed in renamed_paths:
            try:
                renamed.unlink(missing_ok=True)
            except OSError:
                pass
        for temp_path in temp_paths:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        _remove_empty_run_directory(run_directory)
        raise

    return report_paths


def _render_artifacts(report_input: ModernizationReportInput) -> tuple[str, str]:
    """Render HTML and full JSON document text (tests / callers needing both)."""

    html = ModernizationHTMLReportRenderer().render(report_input)
    document = build_assessment_json_document(report_input)
    json_text = assessment_json_to_text(document)
    return html, json_text


def _remove_empty_run_directory(run_directory: Path) -> None:
    try:
        if run_directory.exists() and not any(run_directory.iterdir()):
            run_directory.rmdir()
    except OSError:
        pass


def _atomic_write_text(path: Path, content: str) -> None:
    temp_path = _write_temp_sibling(path, content)
    try:
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _write_temp_sibling(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return temp_path
