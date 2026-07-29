"""Build performance benchmark records from assessment outputs + recorder."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from codestrata.benchmark.environment import capture_environment
from codestrata.benchmark.models import (
    BENCHMARK_SCHEMA_VERSION,
    COMPARISON_KEYS,
    PerformanceBenchmarkDocument,
    PerformanceBenchmarkRun,
)
from codestrata.benchmark.recorder import BenchmarkRecorder
from codestrata.benchmark.redaction import redact_ai_metrics
from codestrata.scan_boundary import ScanSourceRole

DEFAULT_MEASUREMENT_LIMITATIONS = [
    "Average RSS is sampled at stage boundaries only (not continuous).",
    "Peak RSS uses resource.getrusage heuristics (macOS bytes vs Linux KiB).",
    "Graph memory is estimated from serialized artifact sizes, not live heap.",
    "Largest assessment/evidence objects are estimated from on-disk artifact sizes.",
    "Stage timings with recorder disabled are reconstructed from assessment.timing "
    "and known adapter durations only.",
    "CPU time is process cumulative (RUSAGE_SELF), not per-stage.",
]


def build_suite_document(
    runs: list[PerformanceBenchmarkRun],
    *,
    environment: dict[str, Any] | None = None,
    limitations: list[str] | None = None,
) -> PerformanceBenchmarkDocument:
    """Aggregate one or more runs into the suite document."""

    completed = [run for run in runs if run.status == "completed"]
    failed = [run for run in runs if run.status == "failed"]
    expected_failures = [run for run in runs if run.status in {"failed_expected", "skipped"}]
    summary = {
        "run_count": len(runs),
        "completed_count": len(completed),
        "failed_count": len(failed),
        "expected_failure_or_skip_count": len(expected_failures),
        "total_ms_by_label": {run.label: (run.timings or {}).get("total_ms") for run in completed},
        "peak_rss_mb_by_label": {
            run.label: (run.memory or {}).get("peak_rss_mb") for run in completed
        },
    }
    return PerformanceBenchmarkDocument(
        schema_version=BENCHMARK_SCHEMA_VERSION,
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        environment=environment or capture_environment(),
        comparison_keys=list(COMPARISON_KEYS),
        measurement_limitations=limitations or list(DEFAULT_MEASUREMENT_LIMITATIONS),
        runs=runs,
        summary=summary,
    )


def build_run_record(
    *,
    label: str,
    repository_path: Path,
    run_directory: Path | None,
    report_json_path: Path | None = None,
    recorder: BenchmarkRecorder | None = None,
    command_result: Any | None = None,
    status: str = "completed",
    failure: dict[str, Any] | None = None,
    ai_requested: bool = False,
    notes: list[str] | None = None,
) -> PerformanceBenchmarkRun:
    """Build one run record from outputs (post-hoc safe; does not re-assess)."""

    recorder = recorder or BenchmarkRecorder(enabled=False)
    report_payload = _load_json(report_json_path) if report_json_path else None
    assessment = (report_payload or {}).get("assessment") or {}
    timing = assessment.get("timing") or {}
    repository_block = assessment.get("repository") or {}
    scan_boundary = _load_scan_boundary(run_directory, repository_path)

    repo_metrics = _repository_metrics(
        label=label,
        repository_path=repository_path,
        scan_boundary=scan_boundary,
        repository_block=repository_block,
        assessment=assessment,
    )
    timings = _timings_block(
        recorder=recorder,
        timing=timing,
        command_result=command_result,
    )
    memory = _memory_block(recorder=recorder, timing=timing)
    graphs = _graphs_block(run_directory=run_directory, command_result=command_result)
    report_metrics = _report_block(
        run_directory=run_directory,
        assessment=assessment,
        command_result=command_result,
        timing=timing,
    )
    ai_metrics = _ai_block(
        assessment=assessment,
        command_result=command_result,
        ai_requested=ai_requested,
        recorder=recorder,
    )
    artifacts = _artifacts_block(run_directory=run_directory)

    return PerformanceBenchmarkRun(
        run_id=str(uuid4()),
        label=label,
        status=status,
        repository=repo_metrics,
        timings=timings,
        memory=memory,
        graphs=graphs,
        report=report_metrics,
        ai=ai_metrics,
        artifacts=artifacts,
        failure=failure,
        notes=list(notes or []),
    )


def _load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _load_scan_boundary(
    run_directory: Path | None,
    repository_path: Path,
) -> dict[str, Any]:
    if run_directory is not None:
        diag = _load_json(run_directory / "scan-boundary-diagnostics.json")
        if isinstance(diag, dict):
            return diag
    return {}


def _repository_metrics(
    *,
    label: str,
    repository_path: Path,
    scan_boundary: dict[str, Any],
    repository_block: dict[str, Any],
    assessment: dict[str, Any],
) -> dict[str, Any]:
    resolved = repository_path.expanduser().resolve()
    disk_bytes = _directory_size_bytes(resolved) if resolved.is_dir() else None
    role_counts = scan_boundary.get("role_counts") or {}
    if not isinstance(role_counts, dict):
        role_counts = {}

    production = int(role_counts.get(ScanSourceRole.PRODUCTION.value, 0) or 0)
    test = int(role_counts.get(ScanSourceRole.TEST.value, 0) or 0)
    fixture = int(role_counts.get(ScanSourceRole.FIXTURE.value, 0) or 0)
    example = int(role_counts.get(ScanSourceRole.EXAMPLE.value, 0) or 0)
    generated = int(role_counts.get(ScanSourceRole.GENERATED.value, 0) or 0)
    documentation = int(role_counts.get(ScanSourceRole.DOCUMENTATION.value, 0) or 0)
    vendor = int(role_counts.get(ScanSourceRole.VENDOR.value, 0) or 0)
    included = int(scan_boundary.get("included_files") or repository_block.get("file_count") or 0)
    excluded = int(scan_boundary.get("excluded_files") or 0)

    languages = []
    technologies = assessment.get("technologies") or []
    if isinstance(technologies, list):
        for item in technologies:
            if isinstance(item, dict) and item.get("name"):
                languages.append(str(item["name"]))
            elif isinstance(item, str):
                languages.append(item)

    supported = production + test + fixture + example + generated
    unsupported = max(0, included - supported) if included else None

    return {
        "name": repository_block.get("name") or label,
        "path": str(resolved),
        "size_bytes": disk_bytes,
        "total_files_discovered": included + excluded if included or excluded else None,
        "files_assessed": included or repository_block.get("file_count"),
        "production_files": production,
        "test_files": test + fixture,
        "fixture_files": fixture,
        "example_files": example,
        "generated_files": generated,
        "documentation_files": documentation,
        "vendor_files": vendor,
        "excluded_files": excluded,
        "supported_source_files": supported if supported else None,
        "unsupported_files": unsupported,
        "detected_languages": languages,
        "total_source_lines": None,
        "source_role_counts": dict(sorted((str(k), int(v)) for k, v in role_counts.items())),
        "boundary_policy_version": scan_boundary.get("policy_version"),
    }


def _timings_block(
    *,
    recorder: BenchmarkRecorder,
    timing: dict[str, Any],
    command_result: Any | None,
) -> dict[str, Any]:
    stages: dict[str, float] = {}
    # Prefer live recorder stages when present.
    for name in recorder.stage_order:
        stages[name] = float(recorder.stages_ms[name])
    # Fill gaps from assessment.timing / command result (do not overwrite).
    mapping = {
        "repository_discovery": timing.get("scan_ms"),
        "analysis": timing.get("analysis_ms"),
        "graph_generation": timing.get("graph_ms"),
        "finding_synthesis": timing.get("rules_ms"),
        "ai_enrichment": timing.get("ai_ms"),
        "report_generation": timing.get("report_ms"),
        "static_analysis": timing.get("static_analysis_ms"),
        "evidence_collection": timing.get("evidence_ms"),
        "knowledge": timing.get("knowledge_ms"),
    }
    if command_result is not None:
        mapping.update(
            {
                "architecture_report_adapter": getattr(
                    command_result, "architecture_report_adapter_ms", None
                ),
                "technical_debt_report_adapter": getattr(
                    command_result, "technical_debt_report_adapter_ms", None
                ),
                "dependency_report_adapter": getattr(
                    command_result, "dependency_report_adapter_ms", None
                ),
                "security_report_adapter": getattr(
                    command_result, "security_report_adapter_ms", None
                ),
                "testing_report_adapter": getattr(
                    command_result, "testing_report_adapter_ms", None
                ),
                "cloud_report_adapter": getattr(command_result, "cloud_report_adapter_ms", None),
            }
        )
    for name, value in mapping.items():
        if name in stages or value is None:
            continue
        stages[name] = round(max(0.0, float(value)), 2)

    total = timing.get("total_ms")
    if total is None and command_result is not None:
        total = getattr(command_result, "duration_ms", None)
    total_ms = float(total) if total is not None else sum(stages.values())
    total_ms = max(0.0, total_ms)

    stage_rows: list[dict[str, float | str]] = []
    for name, duration in stages.items():
        duration = max(0.0, float(duration))
        pct = round((duration / total_ms) * 100.0, 2) if total_ms > 0 else 0.0
        stage_rows.append(
            {
                "id": name,
                "duration_ms": duration,
                "pct_of_total": pct,
            }
        )
    stage_rows.sort(key=lambda row: (-float(row["duration_ms"]), str(row["id"])))

    return {
        "total_ms": round(float(total_ms), 2),
        "cpu_time_ms": recorder.cpu_time_ms(),
        "stages": stage_rows,
        "raw": {key: stages[key] for key in sorted(stages)},
    }


def _memory_block(
    *,
    recorder: BenchmarkRecorder,
    timing: dict[str, Any],
) -> dict[str, Any]:
    peak = recorder.peak_rss()
    if peak is None:
        peak = timing.get("peak_rss_mb")
    return {
        "peak_rss_mb": peak,
        "average_rss_mb": recorder.average_rss(),
        "sample_count": len(recorder.memory_samples_mb),
        "graph_memory_estimate_bytes": recorder.meta.get("graph_memory_estimate_bytes"),
        "largest_assessment_object_bytes": recorder.meta.get("largest_assessment_object_bytes"),
        "largest_evidence_collection_bytes": recorder.meta.get("largest_evidence_collection_bytes"),
        "availability": "available" if peak is not None else "unavailable",
    }


def _graphs_block(
    *,
    run_directory: Path | None,
    command_result: Any | None,
) -> dict[str, Any]:
    summary = {}
    if run_directory is not None:
        payload = _load_json(run_directory / "graphs" / "graph-summary.json")
        if isinstance(payload, dict):
            summary = payload
    repo_nodes = summary.get("repository_node_count")
    repo_edges = summary.get("repository_relationship_count")
    know_nodes = summary.get("knowledge_node_count")
    know_edges = summary.get("knowledge_relationship_count")
    assess_nodes = summary.get("assessment_node_count")
    assess_edges = summary.get("assessment_relationship_count")
    if command_result is not None:
        repo_nodes = repo_nodes or getattr(command_result, "repository_graph_node_count", None)
        repo_edges = repo_edges or getattr(
            command_result, "repository_graph_relationship_count", None
        )
        assess_nodes = assess_nodes or getattr(command_result, "assessment_graph_node_count", None)
        assess_edges = assess_edges or getattr(
            command_result, "assessment_graph_relationship_count", None
        )
    serialization_ms = None
    return {
        "repository": {"nodes": repo_nodes, "edges": repo_edges},
        "engineering_knowledge": {
            "nodes": know_nodes,
            "edges": know_edges,
            "entity_counts": summary.get("matched_concepts_by_knowledge_type") or {},
            "relationship_counts": {
                "total": know_edges,
            },
        },
        "assessment": {"nodes": assess_nodes, "edges": assess_edges},
        "serialization_ms": serialization_ms,
        "binding_count": summary.get("binding_count"),
    }


def _report_block(
    *,
    run_directory: Path | None,
    assessment: dict[str, Any],
    command_result: Any | None,
    timing: dict[str, Any],
) -> dict[str, Any]:
    html_bytes = None
    json_bytes = None
    sections = []
    if run_directory is not None:
        html = run_directory / "report.html"
        js = run_directory / "report.json"
        if html.is_file():
            html_bytes = html.stat().st_size
        if js.is_file():
            json_bytes = js.stat().st_size
    findings = assessment.get("findings")
    findings_count = 0
    if isinstance(findings, list):
        findings_count = len(findings)
    elif isinstance(findings, dict):
        items = findings.get("items") or findings.get("findings") or []
        findings_count = len(items) if isinstance(items, list) else 0
    if command_result is not None:
        findings_count = getattr(command_result, "findings_count", findings_count)
    recommendations_count = 0
    summary = assessment.get("summary") or {}
    if isinstance(summary, dict):
        recommendations_count = int(summary.get("recommendation_count") or 0)
    if command_result is not None:
        recommendations_count = getattr(
            command_result, "recommendations_count", recommendations_count
        )
    for key in (
        "architecture",
        "technical_debt",
        "dependency",
        "security",
        "testing",
        "cloud",
        "ai_readiness",
        "performance",
        "roadmap",
    ):
        if isinstance(assessment.get(key), dict):
            sections.append(key)
    return {
        "html_bytes": html_bytes,
        "json_bytes": json_bytes,
        "findings_count": findings_count,
        "recommendations_count": recommendations_count,
        "sections_rendered": sections,
        "generation_ms": timing.get("report_ms"),
        "print_stylesheet_ms": None,
    }


def _ai_block(
    *,
    assessment: dict[str, Any],
    command_result: Any | None,
    ai_requested: bool,
    recorder: BenchmarkRecorder,
) -> dict[str, Any]:
    ai = assessment.get("ai") or {}
    status = None
    if isinstance(ai, dict):
        status = ai.get("status") or ai.get("execution_status")
    raw: dict[str, Any] = {
        "enabled": ai_requested,
        "status": status,
        "provider": None,
        "model": None,
        "request_duration_ms": None,
        "response_duration_ms": None,
        "overall_enrichment_ms": (assessment.get("timing") or {}).get("ai_ms"),
        "retry_count": 0,
        "fallback_triggered": False,
        "section_generation_success": None,
        "unavailable": False,
        "reason": None,
    }
    if command_result is not None:
        raw["model"] = getattr(command_result, "model_id", None)
        raw["overall_enrichment_ms"] = raw["overall_enrichment_ms"] or getattr(
            command_result, "latency_ms", None
        )
        raw["section_generation_success"] = bool(getattr(command_result, "ai_executed", False))
    if not ai_requested:
        raw["unavailable"] = True
        raw["reason"] = "not_requested"
        raw["fallback_triggered"] = True
    elif not raw.get("section_generation_success"):
        raw["unavailable"] = True
        raw["reason"] = status or "provider_unavailable_or_failed"
        raw["fallback_triggered"] = True
    # Merge recorder meta AI fields if present (already redacted upstream).
    meta_ai = recorder.meta.get("ai")
    if isinstance(meta_ai, dict):
        raw.update(meta_ai)
    return redact_ai_metrics(raw)


def _artifacts_block(run_directory: Path | None) -> dict[str, Any]:
    if run_directory is None or not run_directory.is_dir():
        return {"total_output_bytes": 0, "files": {}}
    files: dict[str, int] = {}
    total = 0
    for path in sorted(run_directory.rglob("*")):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        rel = path.relative_to(run_directory).as_posix()
        files[rel] = size
        total += size
    # Highlight primary artifacts.
    highlighted = {
        key: files[key]
        for key in (
            "report.html",
            "report.json",
            "scan-boundary-diagnostics.json",
            "performance-benchmark.json",
        )
        if key in files
    }
    graphs = {key: value for key, value in files.items() if key.startswith("graphs/")}
    assessments = {
        key: value
        for key, value in files.items()
        if key.endswith("-assessment.json") or key.endswith("-evidence.json")
    }
    return {
        "total_output_bytes": total,
        "primary": highlighted,
        "graphs_bytes": sum(graphs.values()),
        "assessment_artifacts_bytes": sum(assessments.values()),
        "file_count": len(files),
    }


def _directory_size_bytes(root: Path) -> int | None:
    total = 0
    try:
        for path in root.rglob("*"):
            if path.is_symlink():
                continue
            if path.is_file():
                try:
                    total += path.stat().st_size
                except OSError:
                    continue
    except OSError:
        return None
    return total


def estimate_artifact_object_sizes(run_directory: Path) -> dict[str, int]:
    """Estimate largest assessment/evidence artifacts from disk sizes."""

    largest_assessment = 0
    largest_evidence = 0
    graphs_total = 0
    if not run_directory.is_dir():
        return {
            "largest_assessment_object_bytes": 0,
            "largest_evidence_collection_bytes": 0,
            "graph_memory_estimate_bytes": 0,
        }
    for path in run_directory.rglob("*"):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        name = path.name
        rel = path.relative_to(run_directory).as_posix()
        if rel.startswith("graphs/"):
            graphs_total += size
        if name.endswith("-assessment.json"):
            largest_assessment = max(largest_assessment, size)
        if name.endswith("-evidence.json"):
            largest_evidence = max(largest_evidence, size)
    return {
        "largest_assessment_object_bytes": largest_assessment,
        "largest_evidence_collection_bytes": largest_evidence,
        "graph_memory_estimate_bytes": graphs_total,
    }
