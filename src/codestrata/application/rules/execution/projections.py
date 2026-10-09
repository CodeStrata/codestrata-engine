"""Minimal generic JSON, HTML and SARIF projections of launch-catalog results.

E11 owns the complete CLI/report experience. These adapters copy canonical
status and coverage; they do not recompute operators or invent a health score.
"""

from __future__ import annotations

import json
from html import escape
from typing import Any

from codestrata.domain.contracts.enums import ResultStatus
from codestrata.domain.rules.execution_models import LaunchExecutionBody, LaunchRuleRecord

JSON_SCHEMA = "codestrata.launch-catalog.projection.json.v1"
HTML_SCHEMA = "codestrata.launch-catalog.projection.html.v1"
SARIF_VERSION = "2.1.0"


def _status_value(record: LaunchRuleRecord) -> str:
    if record.status is None:
        return record.coverage_state.value
    return record.status.value


def _sarif_level(status: ResultStatus | None) -> str:
    if status is ResultStatus.FAIL:
        return "error"
    if status is ResultStatus.ERROR:
        return "error"
    if status is ResultStatus.UNKNOWN:
        return "warning"
    return "note"


def project_launch_json(body: LaunchExecutionBody) -> dict[str, Any]:
    return {
        "schema_name": JSON_SCHEMA,
        "schema_version": body.schema_version,
        "canonical_schema": body.schema_name,
        "body_digest": body.content_digest(),
        "plan_digest": body.plan_digest,
        "facts_digest": body.facts_digest,
        "purpose": body.purpose.value,
        "preview_cannot_authorize_production": body.preview_cannot_authorize_production,
        "health_verdict": "none",
        "catalog_kind": body.catalog_kind,
        "records": [
            {
                "rule_id": record.rule_id,
                "status": _status_value(record),
                "coverage_state": record.coverage_state.value,
                "enabled": record.enabled,
                "suppressed": record.suppressed,
                "reason": record.reason,
                "evidence": [item.model_dump(mode="json") for item in record.evidence],
                "diagnostics": [item.model_dump(mode="json") for item in record.diagnostics],
            }
            for record in body.records
        ],
        "limitations": list(body.limitations),
    }


def dumps_launch_json(body: LaunchExecutionBody) -> str:
    return (
        json.dumps(
            project_launch_json(body),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def project_launch_html(body: LaunchExecutionBody) -> str:
    rows: list[str] = []
    for record in body.records:
        rows.append(
            "\n".join(
                (
                    f'<section data-rule="{escape(record.rule_id)}">',
                    f"<h2>{escape(record.rule_id)}</h2>",
                    f"<p>status: {escape(_status_value(record))}</p>",
                    f"<p>coverage_state: {escape(record.coverage_state.value)}</p>",
                    f"<p>enabled: {str(record.enabled).lower()}</p>",
                    f"<p>suppressed: {str(record.suppressed).lower()}</p>",
                    f"<p>reason: {escape(record.reason or '')}</p>",
                    "</section>",
                )
            )
        )
    limitation_rows = "".join(f"<li>{escape(item)}</li>" for item in body.limitations)
    return "\n".join(
        (
            "<!DOCTYPE html>",
            f'<html data-schema="{HTML_SCHEMA}">',
            '<head><meta charset="utf-8"><title>Launch catalog</title></head>',
            "<body>",
            "<h1>Launch catalog results</h1>",
            f"<p>body_digest: {escape(body.content_digest())}</p>",
            f"<p>purpose: {escape(body.purpose.value)}</p>",
            "<p>health_verdict: none</p>",
            "<p>FAIL is a violation; ERROR is processing failure.</p>",
            *rows,
            "<h2>Limitations</h2>",
            f"<ul>{limitation_rows}</ul>",
            "</body></html>",
            "",
        )
    )


def project_launch_sarif(body: LaunchExecutionBody) -> dict[str, Any]:
    rules = []
    results = []
    for record in body.records:
        rules.append(
            {
                "id": record.rule_id,
                "name": record.rule_id,
                "shortDescription": {"text": record.rule_id},
                "properties": {
                    "coverage_state": record.coverage_state.value,
                    "enabled": record.enabled,
                    "suppressed": record.suppressed,
                    "health_verdict": "none",
                },
            }
        )
        if record.status is None and not record.enabled:
            kind = "informational"
            level = "note"
            text = f"{record.rule_id} disabled"
        elif record.suppressed:
            kind = "informational"
            level = "note"
            text = f"{record.rule_id} suppressed status={_status_value(record)}"
        else:
            kind = "fail" if record.status is ResultStatus.FAIL else "informational"
            level = _sarif_level(record.status)
            text = f"{record.rule_id} {_status_value(record)}"
        results.append(
            {
                "ruleId": record.rule_id,
                "level": level,
                "kind": kind,
                "message": {"text": text},
                "properties": {
                    "status": _status_value(record),
                    "coverage_state": record.coverage_state.value,
                    "enabled": record.enabled,
                    "suppressed": record.suppressed,
                    "health_verdict": "none",
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
                        "name": "codestrata-launch-catalog",
                        "informationUri": "https://docs.codestrata.ai",
                        "rules": rules,
                    }
                },
                "results": results,
                "properties": {
                    "body_digest": body.content_digest(),
                    "purpose": body.purpose.value,
                    "health_verdict": "none",
                },
            }
        ],
    }
