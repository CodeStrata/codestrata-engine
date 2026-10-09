"""Engine-local JSON, HTML and SARIF projections for supply-chain envelopes."""

from __future__ import annotations

import json
from html import escape
from typing import Any

from codestrata.application.evidence.supply_chain.envelope import SupplyChainEnvelope
from codestrata.application.rules.execution.family_bind import (
    launch_bind_fields,
    supply_chain_launch_body,
)

JSON_PROJECTION_SCHEMA = "codestrata.supply_chain.projection.json.v1"
HTML_PROJECTION_SCHEMA = "codestrata.supply_chain.projection.html.v1"
SARIF_VERSION = "2.1.0"


def project_supply_chain_json(envelope: SupplyChainEnvelope) -> dict[str, object]:
    body = envelope.body
    launch = supply_chain_launch_body(envelope)
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
        "live_lookup": False,
        "executed_repository_code": False,
        "feed": body.feed.model_dump(mode="json"),
        "matching": body.matching.model_dump(mode="json"),
        "hygiene": body.hygiene.model_dump(mode="json"),
        "scopes": [item.model_dump(mode="json") for item in body.scopes],
        "matches": [item.model_dump(mode="json") for item in body.matches],
        "licenses": [item.model_dump(mode="json") for item in body.licenses],
        "license_policy": (
            None if body.license_policy is None else body.license_policy.model_dump(mode="json")
        ),
        "license_summary": body.license_summary.model_dump(mode="json"),
        "coverage": [item.model_dump(mode="json") for item in body.coverage],
        "capabilities": [item.model_dump(mode="json") for item in body.capabilities],
        "limitations": list(body.limitations),
    }


def dumps_supply_chain_json(envelope: SupplyChainEnvelope) -> str:
    return (
        json.dumps(
            project_supply_chain_json(envelope),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def project_supply_chain_html(envelope: SupplyChainEnvelope) -> str:
    body = envelope.body
    launch = supply_chain_launch_body(envelope)
    rows = []
    for item in body.matches:
        paths = " | ".join(" > ".join(path) for path in item.dependency_paths)
        rows.append(
            "<tr>"
            f"<td>{escape(item.alias_group)}</td>"
            f"<td>{escape(item.advisory_id)}</td>"
            f"<td>{escape(','.join(item.aliases))}</td>"
            f"<td>{escape(item.package_name)}@{escape(item.resolved_version)}</td>"
            f"<td>{escape(item.affected_range)}</td>"
            f"<td>{escape(item.feed_severity)}</td>"
            f"<td>{escape(item.lock_path)}</td>"
            f"<td>{escape(paths)}</td>"
            "</tr>"
        )
    scope_rows = []
    for scope in body.scopes:
        scope_rows.append(
            "<tr>"
            f"<td>{escape(scope.manifest_path)}</td>"
            f"<td>{escape(scope.status.value)}</td>"
            f"<td>{escape(str(scope.numerator))}</td>"
            f"<td>{escape(str(scope.denominator))}</td>"
            f"<td>{escape(scope.serialized or '')}</td>"
            f"<td>{escape(scope.reason or '')}</td>"
            "</tr>"
        )
    return "\n".join(
        (
            "<!DOCTYPE html>",
            f'<html data-schema="{HTML_PROJECTION_SCHEMA}">',
            '<head><meta charset="utf-8"><title>Supply chain</title></head>',
            "<body>",
            f"<p>launch_catalog_body_digest: {escape(launch.content_digest())}</p>",
            "<h1>Resolved dependency and vulnerability matching</h1>",
            f"<p>body_digest: {escape(envelope.body_digest)}</p>",
            "<p>health_verdict: none</p>",
            "<p>live_lookup: false</p>",
            f"<p>feed: {escape(body.feed.provider_id)} {escape(body.feed.status.value)} "
            f"{escape(body.feed.reason)}</p>",
            f"<p>matching: {escape(body.matching.status.value)} "
            f"count={escape(str(body.matching.match_count))} "
            f"(zero matches is not secure)</p>",
            "<h2>M12 scopes</h2>",
            "<table>",
            "<tr><th>manifest</th><th>status</th><th>resolved</th>"
            "<th>eligible</th><th>ratio</th><th>reason</th></tr>",
            *scope_rows,
            "</table>",
            "<h2>M13 matches</h2>",
            "<table>",
            "<tr><th>alias-group</th><th>advisory</th><th>aliases</th>"
            "<th>package</th><th>range</th><th>feed-severity</th>"
            "<th>lock</th><th>paths</th></tr>",
            *rows,
            "</table>",
            "<h2>M14 licenses</h2>",
            "<p>Configured allow/deny only; not a legal compliance verdict.</p>",
            f"<p>policy_present: {escape(str(body.license_summary.policy_present).lower())} "
            f"known_spdx={escape(str(body.license_summary.known_spdx))} "
            f"unknown={escape(str(body.license_summary.unknown))} "
            f"disallowed={escape(str(body.license_summary.disallowed))}</p>",
            "<table>",
            "<tr><th>package</th><th>version</th><th>expression</th>"
            "<th>status</th><th>decision</th><th>source</th></tr>",
            *[
                "<tr>"
                f"<td>{escape(item.package_name)}</td>"
                f"<td>{escape(item.resolved_version)}</td>"
                f"<td>{escape(item.normalized_expression or item.raw_expression)}</td>"
                f"<td>{escape(item.expression_status.value)}</td>"
                f"<td>{escape(item.decision.value)}</td>"
                f"<td>{escape(item.license_source)}</td>"
                "</tr>"
                for item in body.licenses
            ],
            "</table>",
            "</body></html>",
            "",
        )
    )


def project_supply_chain_sarif(envelope: SupplyChainEnvelope) -> dict[str, Any]:
    body = envelope.body
    launch = supply_chain_launch_body(envelope)
    results = []
    for match in body.matches:
        results.append(
            {
                "ruleId": "security.known_vulnerability",
                "level": "warning",
                "message": {
                    "text": (
                        f"{match.advisory_id} aliases={','.join(match.aliases)} "
                        f"{match.package_name}@{match.resolved_version} "
                        f"severity={match.feed_severity}"
                    )
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": match.lock_path},
                            "region": {"startLine": 1},
                        }
                    }
                ],
                "properties": {
                    "alias_group": match.alias_group,
                    "aliases": list(match.aliases),
                    "snapshot_digest": match.snapshot_digest,
                    "feed_severity": match.feed_severity,
                    "severity_basis": match.severity_basis,
                    "dependency_paths": [list(path) for path in match.dependency_paths],
                },
            }
        )
    for item in body.licenses:
        if item.decision.value != "disallowed":
            continue
        results.append(
            {
                "ruleId": "license.disallowed",
                "level": "warning",
                "message": {
                    "text": (
                        f"{item.package_name}@{item.resolved_version} "
                        f"license={item.normalized_expression or item.raw_expression} "
                        f"decision={item.decision.value} (not legal compliance)"
                    )
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": item.lock_path},
                            "region": {"startLine": 1},
                        }
                    }
                ],
                "properties": {
                    "expression": item.normalized_expression,
                    "license_source": item.license_source,
                    "configured_decision_rule": item.decision_rule,
                    "legal_compliance_verdict": False,
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
                        "name": "codestrata-supply-chain",
                        "version": body.projection_version,
                        "rules": [
                            {
                                "id": item.capability_id,
                                "name": item.capability_id,
                                "shortDescription": {"text": item.coverage_requirement},
                                "properties": {
                                    "yaml_rule": item.yaml_rule,
                                    "health_verdict": "none",
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
                    "live_lookup": False,
                    "matching": body.matching.model_dump(mode="json"),
                    "feed": body.feed.model_dump(mode="json"),
                    "license_summary": body.license_summary.model_dump(mode="json"),
                    "legal_compliance_verdict": False,
                },
            }
        ],
    }
