"""Engine-local JSON, HTML and SARIF projections for maintainability envelopes.

HTML displays the canonical order and explanations. It never computes another
priority, rank or score.
"""

from __future__ import annotations

import json
from html import escape
from typing import Any

from codestrata.application.evidence.maintainability.envelope import MaintainabilityEnvelope
from codestrata.domain.contracts.enums import ContributorRole

JSON_PROJECTION_SCHEMA = "codestrata.maintainability.projection.json.v1"
HTML_PROJECTION_SCHEMA = "codestrata.maintainability.projection.html.v1"
SARIF_VERSION = "2.1.0"


def project_maintainability_json(envelope: MaintainabilityEnvelope) -> dict[str, object]:
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
        "opaque_score": None,
        "runtime_failure_probability": None,
        "cost_to_fix": None,
        "developer_blame": None,
        "live_lookup": False,
        "executed_repository_code": False,
        "input_state_digest": body.input_state_digest,
        "history": None if body.history is None else body.history.model_dump(mode="json"),
        "complete_hotspots": [item.model_dump(mode="json") for item in body.complete_hotspots],
        "partial_hotspots": [item.model_dump(mode="json") for item in body.partial_hotspots],
        "static_function_ids": list(body.static_function_ids),
        "staleness": [item.model_dump(mode="json") for item in body.staleness],
        "concerns": [item.model_dump(mode="json") for item in body.concerns],
        "finding_rejections": [item.model_dump(mode="json") for item in body.finding_rejections],
        "thresholds": body.thresholds.model_dump(mode="json"),
        "coverage": [item.model_dump(mode="json") for item in body.coverage],
        "capabilities": [item.model_dump(mode="json") for item in body.capabilities],
        "metadata_snapshot_digest": body.metadata_snapshot_digest,
        "limitations": list(body.limitations),
    }


def dumps_maintainability_json(envelope: MaintainabilityEnvelope) -> str:
    return (
        json.dumps(
            project_maintainability_json(envelope),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def _contributor_rows(item: Any) -> list[str]:
    rows = []
    for contributor in item.contributors:
        role = contributor.role.value if contributor.role is not None else ""
        value = contributor.value if contributor.value is not None else "UNKNOWN"
        reason = contributor.coverage_reason or ""
        rows.append(
            "<tr>"
            f"<td>{escape(contributor.name)}</td>"
            f"<td>{escape(role)}</td>"
            f"<td>{escape(value)}</td>"
            f"<td>{escape(contributor.measurement_id)}/"
            f"{escape(contributor.measurement_version)}</td>"
            f"<td>{escape(reason)}</td>"
            "</tr>"
        )
    return rows


def _hotspot_section(title: str, items: tuple[Any, ...]) -> list[str]:
    blocks: list[str] = [f"<h2>{escape(title)}</h2>"]
    if not items:
        blocks.append("<p>none</p>")
        return blocks
    for item in items:
        rank = item.ranking_value if item.ranking_value is not None else "UNRANKED"
        findings = ", ".join(item.active_finding_ids) or "none"
        blocks.extend(
            (
                f"<h3>{escape(item.subject_id)}</h3>",
                f"<p>record_id: {escape(item.record_id)}</p>",
                f"<p>list_kind: {escape(item.list_kind.value)}</p>",
                f"<p>ranking_value: {escape(str(rank))} "
                "(complexity × changed lines only; not a health score)</p>",
                f"<p>history: {escape(item.history_profile_id)} "
                f"window={escape(item.history_window)}</p>",
                f"<p>priority_explanation: {escape(item.priority_explanation)}</p>",
                f"<p>active_finding_ids: {escape(findings)}</p>",
                "<p>High rank is not runtime failure probability.</p>",
                "<table>",
                "<tr><th>contributor</th><th>role</th><th>value</th>"
                "<th>measurement</th><th>coverage</th></tr>",
                *_contributor_rows(item),
                "</table>",
            )
        )
    return blocks


def project_maintainability_html(envelope: MaintainabilityEnvelope) -> str:
    body = envelope.body
    window = "missing" if body.history is None else body.history.window
    profile = "missing" if body.history is None else body.history.profile_id
    concern_rows = [
        "<tr>"
        f"<td>{escape(item.finding_id)}</td>"
        f"<td>{escape(item.effective_severity)}</td>"
        f"<td>{escape(item.evidence_class)}</td>"
        f"<td>{escape('comparable' if item.hotspot_comparable else 'incomparable')}</td>"
        f"<td>{escape(item.hotspot_value or '')}</td>"
        f"<td>{escape(item.explanation)}</td>"
        "</tr>"
        for item in body.concerns
    ]
    stale_rows = [
        "<tr>"
        f"<td>{escape(item.package_id)}</td>"
        f"<td>{escape(item.installed_version)}</td>"
        f"<td>{escape(item.status.value)}</td>"
        f"<td>{escape('UNKNOWN' if item.days is None else str(item.days))}</td>"
        f"<td>{escape(item.reason)}</td>"
        "</tr>"
        for item in body.staleness
    ]
    return "\n".join(
        (
            "<!DOCTYPE html>",
            f'<html data-schema="{HTML_PROJECTION_SCHEMA}">',
            '<head><meta charset="utf-8"><title>Engineering hotspots</title></head>',
            "<body>",
            "<h1>Engineering Hotspots (M22) and dependency age (M23)</h1>",
            f"<p>body_digest: {escape(envelope.body_digest)}</p>",
            "<p>health_verdict: none</p>",
            "<p>opaque_score: none</p>",
            "<p>runtime_failure_probability: none</p>",
            "<p>cost_to_fix: none</p>",
            "<p>developer_blame: none</p>",
            f"<p>pinned history: {escape(profile)} window={escape(window)}</p>",
            "<p>HTML displays the canonical Engine order; it does not compute "
            "another priority or score.</p>",
            *_hotspot_section(
                "Complete comparable ranking (descending value, then component ID)",
                body.complete_hotspots,
            ),
            *_hotspot_section(
                "Partial/UNKNOWN ranking inputs (ordered by subject ID; static evidence retained)",
                body.partial_hotspots,
            ),
            "<h2>Static complexity subjects retained</h2>",
            f"<p>{escape(', '.join(body.static_function_ids) or 'none')}</p>",
            "<h2>Dependency staleness (M23)</h2>",
            "<p>Age does not prove insecure or unsupported.</p>",
            "<table>",
            "<tr><th>package</th><th>version</th><th>status</th><th>days</th>"
            "<th>reason</th></tr>",
            *stale_rows,
            "</table>",
            "<h2>Finding-concern order (canonical; not a weighted score)</h2>",
            "<table>",
            "<tr><th>finding</th><th>severity</th><th>evidence_class</th>"
            "<th>hotspot</th><th>value</th><th>explanation</th></tr>",
            *concern_rows,
            "</table>",
            "</body></html>",
            "",
        )
    )


def project_maintainability_sarif(envelope: MaintainabilityEnvelope) -> dict[str, Any]:
    body = envelope.body
    results: list[dict[str, Any]] = []
    for item in body.complete_hotspots:
        ranking = [
            contributor
            for contributor in item.contributors
            if contributor.role is ContributorRole.RANKING
        ]
        results.append(
            {
                "ruleId": "maintainability.hotspot",
                "level": "note",
                "message": {"text": item.priority_explanation},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": item.subject_id},
                            "region": {"startLine": 1},
                        }
                    }
                ],
                "properties": {
                    "record_id": item.record_id,
                    "ranking_value": item.ranking_value,
                    "list_kind": item.list_kind.value,
                    "history_window": item.history_window,
                    "ranking_contributors": [c.model_dump(mode="json") for c in ranking],
                    "opaque_score": False,
                },
            }
        )
    for stale in body.staleness:
        if stale.days is None:
            continue
        results.append(
            {
                "ruleId": "maintainability.dependency_age",
                "level": "note",
                "message": {
                    "text": (
                        f"{stale.package_id}@{stale.installed_version} age_days="
                        f"{stale.days} ({stale.formula_version}); age does not "
                        "prove insecure or unsupported"
                    )
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": stale.package_id},
                            "region": {"startLine": 1},
                        }
                    }
                ],
                "properties": {
                    "days": stale.days,
                    "status": stale.status.value,
                    "source_snapshot_id": stale.source_snapshot_id,
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
                        "name": "codestrata-maintainability",
                        "informationUri": "https://codestrata.io",
                    }
                },
                "results": results,
                "properties": {
                    "body_digest": envelope.body_digest,
                    "health_verdict": "none",
                    "opaque_score": None,
                    "runtime_failure_probability": None,
                    "canonical_order": True,
                },
            }
        ],
    }


__all__ = [
    "dumps_maintainability_json",
    "project_maintainability_html",
    "project_maintainability_json",
    "project_maintainability_sarif",
]
