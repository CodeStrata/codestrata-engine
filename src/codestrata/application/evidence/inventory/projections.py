"""JSON, HTML and SARIF projections for inventory envelopes.

These adapters copy canonical envelope values and bind the E03.3 launch-catalog
projection. They do not recompute coverage, invent a health score, or import
parser modules.
"""

from __future__ import annotations

import json
from html import escape
from typing import Any

from codestrata.application.evidence.inventory.envelope import InventoryEnvelope
from codestrata.application.evidence.inventory.facts import CapabilityCoverageRecord

JSON_PROJECTION_SCHEMA = "codestrata.inventory.projection.json.v1"
JSON_PROJECTION_VERSION = "1"
HTML_PROJECTION_SCHEMA = "codestrata.inventory.projection.html.v1"
SARIF_VERSION = "2.1.0"


def _coverage_view(record: CapabilityCoverageRecord) -> dict[str, object]:
    return {
        "capability_id": record.capability_id,
        "version": record.version,
        "scope": record.scope,
        "applicability": record.applicability.value,
        "evaluated": record.evaluated,
        "eligible": record.eligible,
        "unknown": record.unknown,
        "error": record.error,
        "excluded": record.excluded,
        "coverage_ratio": record.coverage_ratio,
        "coverage_reason": record.coverage_reason,
        "limitations": list(record.limitations),
    }


def _family_bind() -> tuple[Any, Any]:
    from codestrata.application.rules.execution.family_bind import (
        inventory_launch_body,
        launch_bind_fields,
    )

    return inventory_launch_body, launch_bind_fields


def project_inventory_json(envelope: InventoryEnvelope) -> dict[str, object]:
    inventory_launch_body, launch_bind_fields = _family_bind()
    body = envelope.body
    launch = inventory_launch_body(envelope)
    return {
        "schema_name": JSON_PROJECTION_SCHEMA,
        "schema_version": JSON_PROJECTION_VERSION,
        "envelope_schema": envelope.schema_name,
        "envelope_version": envelope.schema_version,
        **launch_bind_fields(launch),
        "body_digest": envelope.body_digest,
        "repository_id": body.repository_id,
        "source_revision": body.source_revision,
        "working_state_digest": body.working_state_digest,
        "descriptive_only": True,
        "health_verdict": "none",
        "capabilities": [item.model_dump(mode="json") for item in body.capabilities],
        "coverage": [_coverage_view(item) for item in body.coverage],
        "freshness": [item.model_dump(mode="json") for item in body.freshness],
        "registered_facts": body.registered_facts.model_dump(mode="json"),
        "classification": body.facts.get("classification"),
        "limitations": list(body.limitations),
        "executed_repository_code": body.executed_repository_code,
        "ci_execution_observed": body.ci_execution_observed,
    }


def dumps_inventory_json(envelope: InventoryEnvelope) -> str:
    return (
        json.dumps(
            project_inventory_json(envelope),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def project_inventory_html(envelope: InventoryEnvelope) -> str:
    inventory_launch_body, _ = _family_bind()
    body = envelope.body
    launch = inventory_launch_body(envelope)
    sections: list[str] = []
    for record in body.coverage:
        ratio = record.coverage_ratio if record.coverage_ratio is not None else "null"
        reason = record.coverage_reason or ""
        sections.append(
            "\n".join(
                (
                    f'<section data-capability="{escape(record.capability_id)}">',
                    f"<h2>{escape(record.capability_id)}</h2>",
                    f"<p>applicability: {escape(record.applicability.value)}</p>",
                    f"<p>evaluated: {record.evaluated}</p>",
                    f"<p>eligible: {record.eligible}</p>",
                    f"<p>unknown: {record.unknown}</p>",
                    f"<p>error: {record.error}</p>",
                    f"<p>excluded: {record.excluded}</p>",
                    f"<p>coverage_ratio: {escape(ratio)}</p>",
                    f"<p>coverage_reason: {escape(reason)}</p>",
                    "<p>health_verdict: none</p>",
                    "</section>",
                )
            )
        )
    freshness_rows = []
    for item in body.freshness:
        freshness_rows.append(
            f"<li>{escape(item.capability_id)}: {escape(item.status)} ({escape(item.reason)})</li>"
        )
    limitation_rows = "".join(f"<li>{escape(item)}</li>" for item in body.limitations)
    return "\n".join(
        (
            "<!DOCTYPE html>",
            f'<html data-schema="{HTML_PROJECTION_SCHEMA}">',
            '<head><meta charset="utf-8"><title>Inventory</title></head>',
            "<body>",
            "<h1>Inventory coverage</h1>",
            f"<p>body_digest: {escape(envelope.body_digest)}</p>",
            f"<p>launch_catalog_body_digest: {escape(launch.content_digest())}</p>",
            f"<p>repository_id: {escape(body.repository_id)}</p>",
            "<p>descriptive_only: true</p>",
            "<p>health_verdict: none</p>",
            "<p>This projection copies canonical coverage; it does not calculate scores.</p>",
            *sections,
            "<h2>Freshness</h2>",
            "<ul>",
            *freshness_rows,
            "</ul>",
            "<h2>Limitations</h2>",
            f"<ul>{limitation_rows}</ul>",
            "</body></html>",
            "",
        )
    )


def project_inventory_sarif(envelope: InventoryEnvelope) -> dict[str, Any]:
    inventory_launch_body, _ = _family_bind()
    body = envelope.body
    launch = inventory_launch_body(envelope)
    rules = []
    results = []
    for manifest in body.capabilities:
        rules.append(
            {
                "id": manifest.capability_id,
                "name": manifest.capability_id,
                "shortDescription": {"text": f"{manifest.family.value} {manifest.outcome.value}"},
                "properties": {
                    "descriptive_only": True,
                    "health_verdict": "none",
                    "yaml_rule": False,
                },
            }
        )
    coverage_by_id = {item.capability_id: item for item in body.coverage}
    for manifest in body.capabilities:
        record = coverage_by_id.get(manifest.capability_id)
        if record is None:
            continue
        ratio = record.coverage_ratio if record.coverage_ratio is not None else "null"
        message = (
            f"{record.capability_id} coverage_ratio={ratio} "
            f"evaluated={record.evaluated} eligible={record.eligible} "
            f"reason={record.coverage_reason or ''}"
        )
        results.append(
            {
                "ruleId": record.capability_id,
                "level": "note",
                "kind": "informational",
                "message": {"text": message},
                "properties": {
                    **_coverage_view(record),
                    "health_verdict": "none",
                    "descriptive_only": True,
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
                        "name": "codestrata-inventory",
                        "version": body.projection_version,
                        "informationUri": "https://codestrata.dev/inventory",
                        "rules": rules,
                    }
                },
                "results": results,
                "properties": {
                    "body_digest": envelope.body_digest,
                    "launch_catalog_body_digest": launch.content_digest(),
                    "health_verdict": "none",
                    "descriptive_only": True,
                    "ci_execution_observed": body.ci_execution_observed,
                },
            }
        ],
    }


def dumps_inventory_sarif(envelope: InventoryEnvelope) -> str:
    return (
        json.dumps(
            project_inventory_sarif(envelope),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )
