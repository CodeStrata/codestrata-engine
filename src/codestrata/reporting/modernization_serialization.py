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


def _canonical_html(report_input: ModernizationReportInput) -> str:
    from codestrata.reporting.assessment_canonical import canonical_html_for_report

    return canonical_html_for_report(report_input)


def _write_canonical_sidecars(
    report_input: ModernizationReportInput,
    html_path: Path,
    canonical_html: str,
) -> None:
    """Write JSON, SARIF, and the analysis result beside the canonical HTML."""

    from codestrata.reporting.assessment_canonical import canonical_report_for_input
    from codestrata.reporting.canonical_views import dumps_canonical_json, project_canonical_sarif
    from codestrata.reporting.journey_observations import observe_repository
    from codestrata.security.redaction import redact_report_payload

    report = canonical_report_for_input(report_input)
    _atomic_write_text(html_path, canonical_html)
    _atomic_write_text(html_path.with_name("canonical-report.json"), dumps_canonical_json(report))
    _atomic_write_text(
        html_path.with_name("canonical-report.sarif.json"),
        json.dumps(project_canonical_sarif(report), indent=2, sort_keys=True) + "\n",
    )
    analysis = report_input.analysis_result
    metadata = dict(analysis.metadata)
    root = Path(analysis.repository.path)
    if root.is_dir() and "canonical_hotspots" not in metadata:
        # Unsealed fixture/debug path only. Production assess seals first.
        observed = observe_repository(root.resolve())
        metadata["coverage_status"] = observed.coverage_status
        if observed.metrics:
            metadata["metrics"] = observed.metrics
        if observed.feed_digest:
            metadata["feed_digest"] = observed.feed_digest
        analysis = analysis.model_copy(update={"metadata": metadata})
    redacted = redact_report_payload(analysis.model_dump(mode="json"))
    _atomic_write_text(
        html_path.with_name("analysis-result.json"),
        json.dumps(redacted, indent=2, sort_keys=True) + "\n",
    )


def _attach_canonical_views(
    report_input: ModernizationReportInput,
    html: str,
) -> tuple[str, str]:
    """Generate canonical HTML view sidecar without contaminating customer report."""

    canonical_html = _canonical_html(report_input)
    return html, canonical_html


def write_modernization_html_report(
    report_input: ModernizationReportInput,
    output_path: Path | str,
) -> Path:
    """Render and write a UTF-8 HTML modernization assessment report."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    canonical_html = _canonical_html(report_input)
    html = ModernizationHTMLReportRenderer().render(report_input)
    _atomic_write_text(path, html)
    canonical_path = path.with_name("canonical-report.html")
    _write_canonical_sidecars(report_input, canonical_path, canonical_html)
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
        build_artifact_index_manifest,
        build_assessment_manifest,
        write_artifact_index_manifest,
        write_assessment_manifest,
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
            update={"timing": base.model_copy(update={"report_ms": 0.0, "total_ms": base.total_ms})}
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
        assessment_payload = document.get("assessment")
        timing_payload = (
            assessment_payload.get("timing") if isinstance(assessment_payload, dict) else None
        )
        if isinstance(timing_payload, dict):
            timing_payload["report_ms"] = report_ms
            timing_payload["total_ms"] = total_ms
        artifact_input = finalized

    html, canonical_html = _attach_canonical_views(artifact_input, html)

    run_directory = report_paths.run_directory
    run_directory.mkdir(parents=True, exist_ok=True)
    if report_paths.heads_directory is not None:
        report_paths.heads_directory.mkdir(parents=True, exist_ok=True)

    temp_paths: list[Path] = []
    renamed_paths: list[Path] = []
    try:
        html_temp = _write_temp_sibling(report_paths.html_report_path, html)
        temp_paths.append(html_temp)
        os.replace(html_temp, report_paths.html_report_path)
        renamed_paths.append(report_paths.html_report_path)

        canonical_path = report_paths.html_report_path.with_name("canonical-report.html")
        canonical_temp = _write_temp_sibling(canonical_path, canonical_html)
        temp_paths.append(canonical_temp)
        os.replace(canonical_temp, canonical_path)
        renamed_paths.append(canonical_path)
        _write_canonical_sidecars(artifact_input, canonical_path, canonical_html)

        renamed_paths.append(run_directory / "findings.json")
        renamed_paths.append(run_directory / "recommendations.json")
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
        _rollback_report_write(run_directory, renamed_paths, temp_paths)
        raise

    return report_paths


def _render_artifacts(report_input: ModernizationReportInput) -> tuple[str, str]:
    """Render HTML and full JSON document text (tests / callers needing both)."""

    html = ModernizationHTMLReportRenderer().render(report_input)
    document = build_assessment_json_document(report_input)
    json_text = assessment_json_to_text(document)
    return html, json_text


def _rollback_report_write(
    run_directory: Path,
    renamed_paths: list[Path],
    temp_paths: list[Path],
) -> None:
    """Drop promoted artifacts and every staging file from a failed report write."""

    for path in (*renamed_paths, *temp_paths):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    if run_directory.is_dir():
        for temp_path in run_directory.glob("*.tmp"):
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
    _remove_empty_run_directory(run_directory)


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
