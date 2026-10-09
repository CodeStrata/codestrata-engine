"""Engine-local JSON, HTML and SARIF projections for quality envelopes."""

from __future__ import annotations

import json
from html import escape
from typing import Any

from codestrata.application.evidence.quality.envelope import QualityEnvelope
from codestrata.application.evidence.quality.models import FunctionStatus
from codestrata.application.rules.execution.family_bind import (
    launch_bind_fields,
    quality_launch_body,
)

JSON_PROJECTION_SCHEMA = "codestrata.quality.projection.json.v1"
HTML_PROJECTION_SCHEMA = "codestrata.quality.projection.html.v1"
SARIF_VERSION = "2.1.0"


def project_quality_json(envelope: QualityEnvelope) -> dict[str, object]:
    body = envelope.body
    launch = quality_launch_body(envelope)
    return {
        "schema_name": JSON_PROJECTION_SCHEMA,
        "schema_version": "1",
        "envelope_schema": envelope.schema_name,
        **launch_bind_fields(launch),
        "body_digest": envelope.body_digest,
        "repository_id": body.repository_id,
        "catalog_digest": body.catalog_digest,
        "yaml_runtime": body.yaml_runtime,
        "health_verdict": "none",
        "maintainability_index": None,
        "live_lookup": False,
        "executed_repository_code": False,
        "functions": [item.model_dump(mode="json") for item in body.functions],
        "files": [item.model_dump(mode="json") for item in body.files],
        "distribution": body.distribution.model_dump(mode="json"),
        "clone": body.clone.model_dump(mode="json"),
        "thresholds": body.thresholds.model_dump(mode="json"),
        "coverage": [item.model_dump(mode="json") for item in body.coverage],
        "capabilities": [item.model_dump(mode="json") for item in body.capabilities],
        "limitations": list(body.limitations),
    }


def dumps_quality_json(envelope: QualityEnvelope) -> str:
    return (
        json.dumps(
            project_quality_json(envelope),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def project_quality_html(envelope: QualityEnvelope) -> str:
    body = envelope.body
    launch = quality_launch_body(envelope)
    function_rows = []
    for item in body.functions:
        cyclomatic = str(item.cyclomatic) if item.cyclomatic is not None else "UNKNOWN"
        nloc = str(item.nloc) if item.nloc is not None else "UNKNOWN"
        nesting = str(item.max_nesting_depth) if item.max_nesting_depth is not None else "UNKNOWN"
        function_rows.append(
            "<tr>"
            f"<td>{escape(item.language)}</td>"
            f"<td>{escape(item.qualified_name)}</td>"
            f"<td>{escape(item.path)}</td>"
            f"<td>{escape(str(item.span.line_start))}-{escape(str(item.span.line_end))}</td>"
            f"<td>{escape(item.status.value)}</td>"
            f"<td>{escape(cyclomatic)}</td>"
            f"<td>{escape(nloc)}</td>"
            f"<td>{escape(nesting)}</td>"
            f"<td>{escape(item.cyclomatic_version)}</td>"
            "</tr>"
        )
    clone = body.clone
    clone_rows = [
        "<tr>"
        f"<td>{escape(run.left.path)}:{run.left.line_start}-{run.left.line_end}</td>"
        f"<td>{escape(run.right.path)}:{run.right.line_start}-{run.right.line_end}</td>"
        f"<td>{escape(str(run.token_count))}</td>"
        f"<td>{escape(run.normalization_version)}</td>"
        "</tr>"
        for run in clone.runs
    ]
    return "\n".join(
        (
            "<!DOCTYPE html>",
            f'<html data-schema="{HTML_PROJECTION_SCHEMA}">',
            '<head><meta charset="utf-8"><title>Structural quality</title></head>',
            "<body>",
            f"<p>launch_catalog_body_digest: {escape(launch.content_digest())}</p>",
            "<h1>Structural quality (M16/M17/M18)</h1>",
            f"<p>body_digest: {escape(envelope.body_digest)}</p>",
            "<p>health_verdict: none</p>",
            "<p>maintainability_index: none</p>",
            f"<p>clone: {escape(clone.status.value)} "
            f"{escape(str(clone.numerator))}/{escape(str(clone.denominator))} "
            f"{escape(clone.serialized or '')} scope={escape(clone.full_scope_status.value)}</p>",
            "<h2>Functions</h2>",
            "<table>",
            "<tr><th>language</th><th>function</th><th>path</th><th>span</th>"
            "<th>status</th><th>cyclomatic</th><th>nloc</th><th>nesting</th>"
            "<th>formula</th></tr>",
            *function_rows,
            "</table>",
            "<h2>Clone runs</h2>",
            "<table>",
            "<tr><th>left</th><th>right</th><th>tokens</th><th>normalization</th></tr>",
            *clone_rows,
            "</table>",
            "</body></html>",
            "",
        )
    )


def project_quality_sarif(envelope: QualityEnvelope) -> dict[str, Any]:
    body = envelope.body
    launch = quality_launch_body(envelope)
    results: list[dict[str, Any]] = []
    complexity_threshold = body.thresholds.complexity
    size_threshold = body.thresholds.function_lines
    nesting_threshold = body.thresholds.nesting
    for item in body.functions:
        if item.status is not FunctionStatus.MEASURED:
            continue
        if item.cyclomatic is not None and item.cyclomatic > complexity_threshold:
            results.append(
                _sarif_result(
                    rule_id="quality.complexity",
                    message=(
                        f"{item.qualified_name} cyclomatic={item.cyclomatic} "
                        f"> {complexity_threshold} ({item.cyclomatic_version})"
                    ),
                    path=item.path,
                    line=item.span.line_start,
                    level="warning",
                    properties={
                        "metric": "cyclomatic",
                        "formula_version": item.cyclomatic_version,
                        "value": item.cyclomatic,
                    },
                )
            )
        if item.nloc is not None and item.nloc > size_threshold:
            results.append(
                _sarif_result(
                    rule_id="quality.complexity",
                    message=(
                        f"{item.qualified_name} nloc={item.nloc} "
                        f"> {size_threshold} ({item.size_version})"
                    ),
                    path=item.path,
                    line=item.span.line_start,
                    level="note",
                    properties={
                        "metric": "function_nloc",
                        "formula_version": item.size_version,
                        "value": item.nloc,
                    },
                )
            )
        if item.max_nesting_depth is not None and item.max_nesting_depth > nesting_threshold:
            results.append(
                _sarif_result(
                    rule_id="quality.nesting",
                    message=(
                        f"{item.qualified_name} max_nesting_depth="
                        f"{item.max_nesting_depth} > {nesting_threshold} "
                        f"({item.nesting_version})"
                    ),
                    path=item.path,
                    line=item.span.line_start,
                    level="warning",
                    properties={
                        "metric": "max_nesting_depth",
                        "formula_version": item.nesting_version,
                        "value": item.max_nesting_depth,
                    },
                )
            )
    clone = body.clone
    if (
        clone.status.value == "value"
        and clone.serialized is not None
        and float(clone.serialized) > float(body.thresholds.clone_ratio)
    ):
        first = clone.merged_spans[0] if clone.merged_spans else None
        results.append(
            _sarif_result(
                rule_id="quality.clone_indicator",
                message=(
                    f"clone ratio {clone.serialized} > {body.thresholds.clone_ratio} "
                    f"({clone.numerator}/{clone.denominator}); indicative, not proof"
                ),
                path=first.path if first is not None else "",
                line=first.line_start if first is not None else 1,
                level="note",
                properties={
                    "numerator": clone.numerator,
                    "denominator": clone.denominator,
                    "normalization_version": clone.normalization_version,
                    "full_scope_status": clone.full_scope_status.value,
                },
            )
        )
    return {
        "version": SARIF_VERSION,
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "codestrata-quality",
                        "version": body.projection_version,
                        "rules": [
                            {
                                "id": item.capability_id,
                                "name": item.capability_id,
                                "shortDescription": {"text": item.coverage_requirement},
                                "properties": {
                                    "yaml_rule": item.yaml_rule,
                                    "health_verdict": "none",
                                    "maintainability_index": None,
                                    "live_lookup": False,
                                },
                            }
                            for item in body.capabilities
                        ],
                    }
                },
                "results": results,
                "properties": {
                    "body_digest": envelope.body_digest,
                    "launch_catalog_body_digest": launch.content_digest(),
                    "health_verdict": "none",
                    "maintainability_index": None,
                    "live_lookup": False,
                    "clone": body.clone.model_dump(mode="json"),
                    "distribution": body.distribution.model_dump(mode="json"),
                },
            }
        ],
    }


def _sarif_result(
    *,
    rule_id: str,
    message: str,
    path: str,
    line: int,
    level: str,
    properties: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ruleId": rule_id,
        "level": level,
        "message": {"text": message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": path},
                    "region": {"startLine": line},
                }
            }
        ],
        "properties": properties,
    }


__all__ = [
    "dumps_quality_json",
    "project_quality_html",
    "project_quality_json",
    "project_quality_sarif",
]
