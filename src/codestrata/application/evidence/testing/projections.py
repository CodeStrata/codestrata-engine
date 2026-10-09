"""Engine-local JSON, HTML and SARIF projections for testing envelopes."""

from __future__ import annotations

import json
from html import escape
from typing import Any

from codestrata.application.evidence.testing.envelope import TestingEnvelope
from codestrata.application.evidence.testing.models import GapStatus, SkipKind

JSON_PROJECTION_SCHEMA = "codestrata.testing.projection.json.v1"
HTML_PROJECTION_SCHEMA = "codestrata.testing.projection.html.v1"
SARIF_VERSION = "2.1.0"


def project_testing_json(envelope: TestingEnvelope) -> dict[str, object]:
    body = envelope.body
    return {
        "schema_name": JSON_PROJECTION_SCHEMA,
        "schema_version": "1",
        "envelope_schema": envelope.schema_name,
        "body_digest": envelope.body_digest,
        "repository_id": body.repository_id,
        "catalog_digest": body.catalog_digest,
        "yaml_runtime": body.yaml_runtime,
        "health_verdict": "none",
        "runtime_coverage": None,
        "coverage_percent": None,
        "label": "static_test_association_not_runtime_coverage",
        "live_lookup": False,
        "executed_repository_code": False,
        "association": body.association.model_dump(mode="json"),
        "skipped": body.skipped.model_dump(mode="json"),
        "ci_gap": body.ci_gap.model_dump(mode="json"),
        "thresholds": body.thresholds.model_dump(mode="json"),
        "coverage": [item.model_dump(mode="json") for item in body.coverage],
        "capabilities": [item.model_dump(mode="json") for item in body.capabilities],
        "limitations": list(body.limitations),
    }


def dumps_testing_json(envelope: TestingEnvelope) -> str:
    return (
        json.dumps(
            project_testing_json(envelope),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def project_testing_html(envelope: TestingEnvelope) -> str:
    body = envelope.body
    assoc = body.association
    skipped = body.skipped
    gap = body.ci_gap
    association_rows = [
        "<tr>"
        f"<td>{escape(item.production_path)}</td>"
        f"<td>{escape(item.test_path)}</td>"
        f"<td>{escape(item.method.value)}</td>"
        f"<td>{escape(item.confidence.value)}</td>"
        f"<td>{escape(item.witness)}</td>"
        "</tr>"
        for item in assoc.associations
    ]
    skip_rows = [
        "<tr>"
        f"<td>{escape(item.path)}</td>"
        f"<td>{escape(item.name)}</td>"
        f"<td>{escape(item.kind.value)}</td>"
        f"<td>{escape(item.annotation)}</td>"
        f"<td>{escape(item.reason or '')}</td>"
        f"<td>{escape(item.static_condition or '')}</td>"
        "</tr>"
        for item in skipped.records
        if item.kind is not SkipKind.ENABLED
    ]
    gap_rows = [
        "<tr>"
        f"<td>{escape(item.tool)}</td>"
        f"<td>{escape(item.kind)}</td>"
        f"<td>{escape(item.status.value)}</td>"
        f"<td>{escape(item.reason)}</td>"
        f"<td>{escape(item.checked_scope)}</td>"
        "</tr>"
        for item in gap.gaps
    ]
    return "\n".join(
        (
            "<!DOCTYPE html>",
            f'<html data-schema="{HTML_PROJECTION_SCHEMA}">',
            "<head><meta charset=\"utf-8\"><title>Testing evidence</title></head>",
            "<body>",
            "<h1>Static test association and CI gaps (M19/M20/M21)</h1>",
            f"<p>body_digest: {escape(envelope.body_digest)}</p>",
            "<p>health_verdict: none</p>",
            "<p>runtime_coverage: none (static association, not measured runtime coverage)</p>",
            "<p>coverage_percent: none (a missing coverage report is not 0% code coverage)</p>",
            f"<p>association: {escape(assoc.status.value)} "
            f"{escape(str(assoc.associated))}/{escape(str(assoc.eligible))} "
            f"{escape(assoc.serialized or '')} scope={escape(assoc.full_scope_status.value)}</p>",
            f"<p>explicit_disabled: {escape(str(skipped.explicit_disabled))} "
            f"conditional={escape(str(skipped.conditional))} "
            f"unknown_eligibility={escape(str(skipped.unknown_eligibility))}</p>",
            f"<p>ci_gap: {escape(gap.status.value)} proven_absent="
            f"{escape(str(gap.proven_absent))} unknown={escape(str(gap.unknown))}</p>",
            "<h2>Associations</h2>",
            "<table>",
            "<tr><th>production</th><th>test</th><th>method</th>"
            "<th>confidence</th><th>witness</th></tr>",
            *association_rows,
            "</table>",
            "<h2>Skipped / disabled</h2>",
            "<table>",
            "<tr><th>path</th><th>name</th><th>kind</th><th>annotation</th>"
            "<th>reason</th><th>condition</th></tr>",
            *skip_rows,
            "</table>",
            "<h2>CI gaps</h2>",
            "<table>",
            "<tr><th>tool</th><th>kind</th><th>status</th><th>reason</th><th>scope</th></tr>",
            *gap_rows,
            "</table>",
            "</body></html>",
            "",
        )
    )


def project_testing_sarif(envelope: TestingEnvelope) -> dict[str, Any]:
    body = envelope.body
    results: list[dict[str, Any]] = []
    assoc = body.association
    if (
        assoc.status.value == "value"
        and assoc.eligible
        and assoc.associated is not None
        and assoc.associated < assoc.eligible
    ):
        first = assoc.unassociated[0] if assoc.unassociated else ""
        results.append(
            _sarif_result(
                rule_id="quality.test_association",
                message=(
                    f"static association {assoc.serialized} "
                    f"({assoc.associated}/{assoc.eligible}); advisory, not runtime coverage"
                ),
                path=first,
                line=1,
                level="note",
                properties={
                    "associated": assoc.associated,
                    "eligible": assoc.eligible,
                    "formula_version": assoc.formula_version,
                    "runtime_coverage": None,
                },
            )
        )
    skipped = body.skipped
    if skipped.explicit_disabled:
        for item in skipped.records:
            if item.kind is not SkipKind.EXPLICIT_DISABLED:
                continue
            results.append(
                _sarif_result(
                    rule_id="testing.disabled",
                    message=(
                        f"{item.name} explicitly disabled"
                        + (f" reason={item.reason}" if item.reason else "")
                    ),
                    path=item.path,
                    line=item.span.line_start,
                    level=(
                        "warning"
                        if skipped.explicit_disabled
                        and skipped.explicit_disabled >= body.thresholds.disabled_medium_min
                        else "note"
                    ),
                    properties={
                        "kind": item.kind.value,
                        "annotation": item.annotation,
                        "static_condition": item.static_condition,
                    },
                )
            )
    for gap in body.ci_gap.gaps:
        if gap.status is not GapStatus.PROVEN_ABSENT:
            continue
        witness = gap.invocations[0] if gap.invocations else None
        results.append(
            _sarif_result(
                rule_id="testing.ci_gap",
                message=(
                    f"declared {gap.kind} tool {gap.tool} has no statically observed "
                    "invocation in complete supported CI"
                ),
                path=witness.path if witness is not None else "",
                line=(witness.line or 1) if witness is not None else 1,
                level="warning",
                properties={
                    "status": gap.status.value,
                    "reason": gap.reason,
                    "checked_scope": gap.checked_scope,
                    "coverage_percent": None,
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
                        "name": "codestrata-testing",
                        "version": body.projection_version,
                        "rules": [
                            {
                                "id": item.capability_id,
                                "name": item.capability_id,
                                "shortDescription": {"text": item.coverage_requirement},
                                "properties": {
                                    "yaml_rule": item.yaml_rule,
                                    "health_verdict": "none",
                                    "runtime_coverage": False,
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
                    "health_verdict": "none",
                    "runtime_coverage": None,
                    "coverage_percent": None,
                    "association": body.association.model_dump(mode="json"),
                    "ci_gap": body.ci_gap.model_dump(mode="json"),
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
    "dumps_testing_json",
    "project_testing_html",
    "project_testing_json",
    "project_testing_sarif",
]
