"""Engine-local JSON, HTML and SARIF projections for security envelopes."""

from __future__ import annotations

import json
from html import escape
from typing import Any

from codestrata.application.evidence.security.envelope import SecurityEnvelope
from codestrata.application.rules.execution.family_bind import (
    launch_bind_fields,
    security_launch_body,
)

JSON_PROJECTION_SCHEMA = "codestrata.security.projection.json.v1"
HTML_PROJECTION_SCHEMA = "codestrata.security.projection.html.v1"
SARIF_VERSION = "2.1.0"


def project_security_json(envelope: SecurityEnvelope) -> dict[str, object]:
    body = envelope.body
    launch = security_launch_body(envelope)
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
        "git_history_scanned": False,
        "counts": body.counts.model_dump(mode="json"),
        "findings": [item.model_dump(mode="json") for item in body.findings],
        "coverage": [item.model_dump(mode="json") for item in body.coverage],
        "capabilities": [item.model_dump(mode="json") for item in body.capabilities],
        "limitations": list(body.limitations),
        "executed_repository_code": body.executed_repository_code,
    }


def dumps_security_json(envelope: SecurityEnvelope) -> str:
    return (
        json.dumps(
            project_security_json(envelope),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def project_security_html(envelope: SecurityEnvelope) -> str:
    body = envelope.body
    launch = security_launch_body(envelope)
    rows = []
    for item in body.findings:
        rows.append(
            "<tr>"
            f"<td>{escape(item.rule_id)}</td>"
            f"<td>{escape(item.path)}</td>"
            f"<td>{escape(item.detector_id)}</td>"
            f"<td>{escape(item.safe_secret_type)}</td>"
            f"<td>{escape(item.redacted_span)}</td>"
            f"<td>{escape(item.production_context_status)}</td>"
            f"<td>{escape(item.effective_severity)}</td>"
            "</tr>"
        )
    counts = body.counts.model_dump(mode="json")
    count_items = "".join(
        f"<li>{escape(str(key))}: {escape(str(value))}</li>"
        for key, value in sorted(counts.items())
    )
    return "\n".join(
        (
            "<!DOCTYPE html>",
            f'<html data-schema="{HTML_PROJECTION_SCHEMA}">',
            '<head><meta charset="utf-8"><title>Security</title></head>',
            "<body>",
            "<h1>Secret and configuration findings</h1>",
            f"<p>body_digest: {escape(envelope.body_digest)}</p>",
            f"<p>launch_catalog_body_digest: {escape(launch.content_digest())}</p>",
            "<p>health_verdict: none</p>",
            "<p>git_history_scanned: false</p>",
            "<p>Static configuration observations only; no runtime exploit claim.</p>",
            "<h2>Counts</h2>",
            f"<ul>{count_items}</ul>",
            "<h2>Findings</h2>",
            "<table>",
            "<tr><th>rule</th><th>path</th><th>detector</th>"
            "<th>type</th><th>redacted</th><th>context</th><th>severity</th></tr>",
            *rows,
            "</table>",
            "</body></html>",
            "",
        )
    )


def project_security_sarif(envelope: SecurityEnvelope) -> dict[str, Any]:
    body = envelope.body
    launch = security_launch_body(envelope)
    rules = [
        {
            "id": item.capability_id,
            "name": item.capability_id,
            "shortDescription": {"text": item.coverage_requirement},
            "properties": {
                "yaml_rule": True,
                "health_verdict": "none",
                "git_history_scanned": False,
            },
        }
        for item in body.capabilities
    ]
    results = []
    for finding in body.findings:
        results.append(
            {
                "ruleId": finding.rule_id,
                "level": "warning",
                "message": {
                    "text": (
                        f"{finding.rule_id} at {finding.path} "
                        f"detector={finding.detector_id} "
                        f"type={finding.safe_secret_type} "
                        f"span={finding.redacted_span}"
                    )
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": finding.path},
                            "region": {"startLine": finding.line_start or 1},
                        }
                    }
                ],
                "properties": {
                    "detector_id": finding.detector_id,
                    "safe_secret_type": finding.safe_secret_type,
                    "redacted_span": finding.redacted_span,
                    "production_context_status": finding.production_context_status,
                    "default_severity": finding.default_severity,
                    "effective_severity": finding.effective_severity,
                    "severity_basis": finding.severity_basis,
                },
            }
        )
    return {
        "version": SARIF_VERSION,
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "codestrata-security",
                        "version": body.projection_version,
                        "rules": rules,
                    }
                },
                "results": results,
                "properties": {
                    "body_digest": envelope.body_digest,
                    "launch_catalog_body_digest": launch.content_digest(),
                    "health_verdict": "none",
                    "git_history_scanned": False,
                    "counts": body.counts.model_dump(mode="json"),
                },
            }
        ],
    }
