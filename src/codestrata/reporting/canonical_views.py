"""Project one canonical result to JSON, HTML and SARIF.

Copies envelope, comparison and co-change fields in the order supplied.
Does not rank hotspots, compute deltas, or assign outcome movement.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from html import escape
from typing import Any

from codestrata.design_system.embedded_fonts import (
    embedded_font_faces_css,
    font_license_html_comment,
)
from codestrata.domain.contracts.comparison import ComparisonEnvelope
from codestrata.domain.contracts.driver_manifest import build_outcome_driver_manifest
from codestrata.domain.contracts.enums import ResultStatus
from codestrata.domain.contracts.envelope import CanonicalEnvelope
from codestrata.security.redaction import redact_secrets

JSON_SCHEMA = "codestrata.canonical-report.json.v1"
HTML_SCHEMA = "codestrata.canonical-report.html.v1"
SARIF_VERSION = "2.1.0"

_SEVERITY_LEVEL = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "info": "note",
    "informational": "note",
}

_UNHEALTHY = {
    ResultStatus.UNKNOWN.value,
    ResultStatus.NOT_APPLICABLE.value,
    ResultStatus.ERROR.value,
    "insufficient",
    "not_applicable",
    "no_baseline",
}


@dataclass(frozen=True, slots=True)
class CochangeView:
    """Already-computed M26 pair. Jaccard is displayed, never divided here."""

    scope: str
    left: str
    right: str
    support: int | None
    union: int | None
    jaccard: str | None
    supported_relation: bool | None
    qualified_incomplete_window: bool
    unavailable_reason: str | None = None


@dataclass(frozen=True, slots=True)
class CanonicalReportInput:
    envelope: CanonicalEnvelope
    comparison: ComparisonEnvelope | None = None
    cochange: tuple[CochangeView, ...] = ()
    purpose: str | None = None
    context_only_concern: str | None = None


def _redact_tree(value: Any) -> Any:
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        return {str(key): _redact_tree(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_tree(item) for item in value]
    return value


def project_canonical_json(report: CanonicalReportInput) -> dict[str, Any]:
    body = report.envelope.body
    payload: dict[str, Any] = {
        "schema_name": JSON_SCHEMA,
        "body_digest": report.envelope.body_digest,
        "purpose": report.purpose,
        "preview_cannot_authorize_production": _preview(report.purpose),
        "health_score": None,
        "snapshot": {
            # Schema key stays working_state_digest. The value is the file-inventory digest.
            "source_revision": body.source_revision,
            "working_state_digest": body.working_state_digest,
        },
        "findings": [item.model_dump(mode="json") for item in body.findings],
        "evidence": [item.model_dump(mode="json") for item in body.evidence],
        "inventory": [item.model_dump(mode="json") for item in body.facts],
        "graph_limitations": list(body.graph.limitations),
        "hotspots": [item.model_dump(mode="json") for item in body.hotspots],
        "ownership": [item.model_dump(mode="json") for item in body.ownership],
        "cochange": [_cochange_dump(item) for item in report.cochange],
        "change_summary": (
            None if body.change_summary is None else body.change_summary.model_dump(mode="json")
        ),
        "coverage": [item.model_dump(mode="json") for item in body.coverage],
        "freshness": [item.model_dump(mode="json") for item in body.freshness],
        "envelope_comparison": body.comparison.model_dump(mode="json"),
        "comparison": (
            None if report.comparison is None else report.comparison.model_dump(mode="json")
        ),
        "driver_catalog": _driver_catalog(),
        "context_only_concern": report.context_only_concern,
        "signature_trust": report.envelope.operational.signature,
        "limitations": list(body.limitations),
    }
    redacted = _redact_tree(payload)
    if not isinstance(redacted, dict):
        return payload
    return redacted


def dumps_canonical_json(report: CanonicalReportInput) -> str:
    return (
        json.dumps(
            project_canonical_json(report),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


CANONICAL_SCREEN_CSS = """
:root{color-scheme:light;--canvas:#f6f7f4;--paper:#ffffff;--ink:#0b3f3f;
--muted:#4d635c;--line:#d7e0db;--accent:#89f537}
body{font-family:"Google Sans Flex",sans-serif;margin:0 auto;max-width:1120px;
padding:1.5rem;background:#f6f7f4;color:#0b3f3f;line-height:1.5}
h1{font-size:1.6rem;font-weight:600}
h2{font-size:1.15rem;font-weight:600;margin-top:1.6rem;color:#0b3f3f}
p,li,td,th{overflow-wrap:break-word}p{max-width:68ch}a{color:#0b5f5f}
code{font-family:"IBM Plex Mono",ui-monospace,monospace;background:#eef2ef;
color:#0b3f3f;overflow-wrap:anywhere}
table{border-collapse:collapse;width:100%;background:#ffffff;display:block;
overflow-x:auto;max-width:100%}
td,th{border:1px solid #d7e0db;padding:.45rem .55rem;text-align:left;
vertical-align:top;color:#0b3f3f}
th{color:#3e574f}
.outcome-unknown,.outcome-not-applicable,.outcome-error{background:#fff4e8;color:#8a4b12}
@media print{body{background:#ffffff;color:#0b3f3f}table{background:#ffffff}
td,th{border-color:#d7e0db;color:#0b3f3f}a{color:#0b5f5f}}
""".strip()


def project_canonical_html(report: CanonicalReportInput) -> str:
    body = report.envelope.body
    sections = (
        _heading(),
        _states(report),
        _findings(body),
        _hotspots(body),
        _ownership(body),
        _cochange(report),
        _change(body),
        _coverage(body),
        _delta(report),
        _inventory(body),
    )
    document = (
        "<!DOCTYPE html>\n"
        f'<html data-schema="{HTML_SCHEMA}">\n'
        "<head><meta charset=\"utf-8\"><title>CodeStrata report</title>"
        f"{font_license_html_comment()}"
        f"<style>{CANONICAL_SCREEN_CSS}</style>"
        f"<style>{embedded_font_faces_css()}</style></head>\n<body>\n"
        + "\n".join(sections)
        + "\n</body></html>\n"
    )
    return redact_secrets(document)


def project_canonical_sarif(report: CanonicalReportInput) -> dict[str, Any]:
    body = report.envelope.body
    results = [_sarif_finding(item) for item in body.findings]
    statuses = [item.result for item in body.findings]
    unknown_present = ResultStatus.UNKNOWN.value in statuses
    scan_clean = bool(statuses) and all(item == ResultStatus.PASS.value for item in statuses)
    document = {
        "version": SARIF_VERSION,
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "codestrata",
                        "informationUri": "https://docs.codestrata.ai",
                        "rules": [
                            {
                                "id": item.rule_id,
                                "properties": {
                                    "default_severity": item.default_severity,
                                    "effective_severity": item.effective_severity,
                                },
                            }
                            for item in body.findings
                        ],
                    }
                },
                "results": results,
                "properties": {
                    "body_digest": report.envelope.body_digest,
                    "purpose": report.purpose,
                    "scan_clean": scan_clean,
                    "unknown_disclosed": unknown_present,
                    "health_score": None,
                    "hotspots": [item.model_dump(mode="json") for item in body.hotspots],
                    "ownership": [item.model_dump(mode="json") for item in body.ownership],
                    "cochange": [_cochange_dump(item) for item in report.cochange],
                    "change_summary": (
                        None
                        if body.change_summary is None
                        else body.change_summary.model_dump(mode="json")
                    ),
                    "coverage": [item.model_dump(mode="json") for item in body.coverage],
                    "freshness": [item.model_dump(mode="json") for item in body.freshness],
                    "comparison": (
                        None
                        if report.comparison is None
                        else report.comparison.model_dump(mode="json")
                    ),
                },
            }
        ],
    }
    redacted = _redact_tree(document)
    if not isinstance(redacted, dict):
        return document
    return redacted


def _driver_catalog() -> list[dict[str, str]]:
    manifest = build_outcome_driver_manifest()
    return [
        {
            "id": item.id,
            "comparison_unit": item.comparison_unit,
            "outcome_or_context_role": item.outcome_or_context_role,
            "applicability": item.applicability,
            "direction": item.direction,
            "epsilon": item.epsilon,
            "empty_scope": item.empty_scope,
        }
        for item in manifest.drivers
    ]


def _cochange_dump(item: CochangeView) -> dict[str, Any]:
    return {
        "scope": item.scope,
        "left": item.left,
        "right": item.right,
        "support": item.support,
        "union": item.union,
        "jaccard": item.jaccard,
        "supported_relation": item.supported_relation,
        "qualified_incomplete_window": item.qualified_incomplete_window,
        "unavailable_reason": item.unavailable_reason,
    }


def _cause(comparison: ComparisonEnvelope | None) -> str | None:
    if comparison is None:
        return None
    return comparison.cause_attribution.value


def _preview(purpose: str | None) -> bool:
    return purpose in {"preview", "candidate"}


def _e(value: object) -> str:
    return escape("" if value is None else str(value), quote=True)


def _code(value: object) -> str:
    text = _e(value)
    if not text:
        return ""
    return f"<code>{text}</code>"


def _code_list(values: object) -> str:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        return ""
    return ", ".join(_code(item) for item in values)


def _outcome_class(value: object) -> str:
    text = "" if value is None else str(value)
    if text in _UNHEALTHY:
        return f"outcome outcome-{text.replace('_', '-')}"
    return "outcome"


def _heading() -> str:
    return "<h1>CodeStrata canonical report</h1><p>health_score: none</p>"


def _states(report: CanonicalReportInput) -> str:
    body = report.envelope.body
    preview = (
        "<p>preview purpose: cannot authorize production</p>"
        if _preview(report.purpose)
        else f"<p>purpose: {_e(report.purpose)}</p>"
    )
    concern = report.context_only_concern
    if body.change_summary is not None and body.change_summary.narrative_only_context:
        concern = concern or "narrative_only_context"
    return "\n".join(
        (
            "<section id=\"run-states\">",
            "<h2>Snapshot, execution, coverage and verification</h2>",
            preview,
            f"<p>source revision: <code>{_e(body.source_revision)}</code></p>",
            f"<p>file-inventory digest: {_e(body.working_state_digest)}</p>",
            (
                "<p>File-inventory digest is SHA-256 of the sorted assessed file-path list. "
                "It is not the Git working-state digest and does not prove file-content "
                "equality.</p>"
            ),
            f"<p>signature_trust: {_e(report.envelope.operational.signature)}</p>",
            f"<p data-concern=\"context-only\">{_e(concern)}</p>",
            "</section>",
        )
    )


def _findings(body: Any) -> str:
    rows = []
    for item in body.findings:
        rows.append(
            "<tr>"
            f'<td id="finding-{_e(item.finding_id)}"><code>{_e(item.finding_id)}</code></td>'
            f"<td class=\"{_outcome_class(item.result)}\">{_e(item.result)}</td>"
            f"<td>{_e(item.default_severity)}</td>"
            f"<td>{_e(item.effective_severity)}</td>"
            f"<td>{_e(item.override_provenance)}</td>"
            f"<td>{_code_list(item.evidence_ids)}</td>"
            "</tr>"
        )
    if not rows:
        rows.append("<tr><td colspan=\"6\">no findings</td></tr>")
    return (
        "<section id=\"findings\"><h2>Findings</h2>"
        "<table><thead><tr><th>id</th><th>result</th><th>default severity</th>"
        "<th>effective severity</th><th>exception attribution</th><th>evidence</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></section>"
    )


def _hotspots(body: Any) -> str:
    blocks = []
    for item in body.hotspots:
        contributors = "".join(
            "<li>"
            f"{_e(part.name)} role={_e(part.role.value)} value={_e(part.value)} "
            f"reason={_e(part.coverage_reason)}"
            "</li>"
            for part in item.contributors
        )
        finding_links = " ".join(
            f'<a href="#finding-{_e(fid)}">{_e(fid)}</a>' for fid in item.active_finding_ids
        )
        evidence_links = " ".join(
            f'<a href="#evidence-{_e(eid)}">{_e(eid)}</a>' for eid in item.evidence_ids
        )
        blocks.append(
            f'<article id="hotspot-{_e(item.record_id)}">'
            f"<p>list_kind: {_e(item.list_kind.value)}</p>"
            f"<p>ranking_value: {_e(item.ranking_value)}</p>"
            f"<p>priority_explanation: {_e(item.priority_explanation)}</p>"
            f"<ul>{contributors}</ul>"
            f"<p>findings: {finding_links}</p>"
            f"<p>evidence: {evidence_links}</p>"
            "</article>"
        )
    if not blocks:
        blocks.append(
            "<p>Engineering Hotspots unavailable: m22_records_not_attached. "
            "Ranking is not calculated here.</p>"
        )
    return (
        "<section id=\"engineering-hotspots\"><h2>Engineering Hotspots</h2>"
        + "".join(blocks)
        + "</section>"
    )


def _ownership(body: Any) -> str:
    rows = []
    for item in body.ownership:
        rows.append(
            "<tr>"
            f"<td>{_e(item.scope.value)}</td>"
            f"<td>{_e(item.subject_id)}</td>"
            f"<td>{_e(item.numerator)}</td>"
            f"<td>{_e(item.denominator)}</td>"
            f"<td>{_e(item.serialized_ratio)}</td>"
            f"<td>{_e(item.history_profile_id)}</td>"
            f"<td class=\"{_outcome_class(item.status.value)}\">{_e(item.status.value)}</td>"
            f"<td>{_e(item.notes)}</td>"
            "</tr>"
        )
    return (
        "<section id=\"ownership-concentration\">"
        "<h2>Ownership concentration</h2>"
        "<table><thead><tr><th>scope</th><th>subject</th><th>numerator</th>"
        "<th>denominator</th><th>ratio</th><th>pinned history</th>"
        "<th>status</th><th>limitations</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></section>"
    )


def _cochange(report: CanonicalReportInput) -> str:
    if not report.cochange:
        body = (
            "<p>temporal co-change unavailable. "
            "No pair, support, or union denominator was supplied.</p>"
        )
    else:
        rows = []
        for item in report.cochange:
            rows.append(
                "<tr>"
                f"<td>{_e(item.left)} / {_e(item.right)}</td>"
                f"<td>{_e(item.scope)}</td>"
                f"<td>{_e(item.support)}</td>"
                f"<td>{_e(item.union)}</td>"
                f"<td>{_e(item.jaccard)}</td>"
                f"<td>{_e(item.supported_relation)}</td>"
                f"<td>{_e(item.unavailable_reason)}</td>"
                f"<td>{_e(item.qualified_incomplete_window)}</td>"
                "</tr>"
            )
        body = (
            "<table><thead><tr><th>pair</th><th>scope</th><th>support</th>"
            "<th>union denominator</th><th>jaccard</th><th>supported</th>"
            "<th>unavailable reason</th><th>incomplete window</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )
    return f"<section id=\"temporal-co-change\"><h2>Temporal co-change</h2>{body}</section>"


def _change(body: Any) -> str:
    summary = body.change_summary
    if summary is None:
        inner = "<p>change summary unavailable</p>"
    else:
        inner = "\n".join(
            (
                f"<p>changed_file_count: {_e(summary.changed_file_count)}</p>",
                f"<p>changed_component_count: {_e(summary.changed_component_count)}</p>",
                f"<p>boundary_spread_count: {_e(summary.boundary_spread_count)}</p>",
                f"<p>boundary_spread_status: "
                f"<span class=\"{_outcome_class(summary.boundary_spread_status.value)}\">"
                f"{_e(summary.boundary_spread_status.value)}</span></p>",
                f"<p>crossed_boundary_count: {_e(summary.crossed_boundary_count)}</p>",
                f"<p>crossed_boundary_pairs: {_e(', '.join(summary.crossed_boundary_pairs))}</p>",
                f"<p>crossed_boundary_status: {_e(summary.crossed_boundary_status.value)}</p>",
                f"<p>affected_component_ids: {_e(', '.join(summary.affected_component_ids))}</p>",
                f"<p>affected_test_ids: {_e(', '.join(summary.affected_test_ids))}</p>",
                f"<p>affected_test_count: {_e(_test_count_text(summary))}</p>",
                f"<p>test_association_status: {_e(_test_association_status(summary))}</p>",
                f"<p>visited_nodes: {_e(summary.visited_nodes)}</p>",
                f"<p>visited_edges: {_e(summary.visited_edges)}</p>",
                f"<p>cutoff_reason: {_e(summary.cutoff_reason or 'none')}</p>",
                f"<p>lower_bound: {_e(summary.lower_bound)}</p>",
                f"<p>narrative_only_context: {_e(summary.narrative_only_context)}</p>",
            )
        )
    return (
        "<section id=\"change-summary\">"
        f"<h2>Change summary and blast radius</h2>{inner}</section>"
    )


def _coverage(body: Any) -> str:
    rows = []
    freshness = {item.capability_id: item for item in body.freshness}
    for item in body.coverage:
        fresh = freshness.get(item.capability_id)
        rows.append(
            "<tr>"
            f"<td>{_e(item.capability_id)}</td>"
            f"<td>{_e(item.scope)}</td>"
            f"<td class=\"{_outcome_class(item.execution_state.value)}\">"
            f"{_e(item.execution_state.value)}</td>"
            f"<td>{_e(item.coverage_ratio)}</td>"
            f"<td>{_e(item.coverage_reason)}</td>"
            f"<td>{_e(None if fresh is None else fresh.state.value)}</td>"
            f"<td>{_e(None if fresh is None else fresh.reason_code)}</td>"
            f"<td>{_e(None if fresh is None else fresh.explanation)}</td>"
            f"<td>{_e(None if fresh is None else fresh.feed_provider)}</td>"
            f"<td>{_code(None if fresh is None else fresh.git_head)}</td>"
            f"<td>{_e(None if fresh is None else fresh.git_window)}</td>"
            "</tr>"
        )
    extra = []
    covered = {item.capability_id for item in body.coverage}
    for fresh in body.freshness:
        if fresh.capability_id in covered:
            continue
        extra.append(
            "<tr>"
            f"<td>{_e(fresh.capability_id)}</td><td></td><td></td><td></td><td></td>"
            f"<td class=\"{_outcome_class(fresh.state.value)}\">{_e(fresh.state.value)}</td>"
            f"<td>{_e(fresh.reason_code)}</td>"
            f"<td>{_e(fresh.explanation)}</td>"
            f"<td>{_e(fresh.feed_provider)}</td>"
            f"<td>{_code(fresh.git_head)}</td>"
            f"<td>{_e(fresh.git_window)}</td>"
            "</tr>"
        )
    return (
        "<section id=\"capability-coverage\"><h2>Capability coverage and freshness</h2>"
        "<table><thead><tr><th>capability</th><th>scope</th><th>execution</th>"
        "<th>coverage</th><th>coverage reason</th><th>freshness</th><th>freshness reason</th>"
        "<th>explanation</th><th>vulnerability feed</th><th>git head</th><th>git window</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "".join(extra)
        + "</tbody></table>"
        f"<p>limitations: {_e(', '.join(body.limitations))}</p></section>"
    )


def _test_count_text(summary: Any) -> str:
    if summary.affected_test_count is None:
        return "UNKNOWN"
    return str(summary.affected_test_count)


def _test_association_status(summary: Any) -> str:
    if summary.affected_test_count is None:
        return "UNKNOWN"
    return "complete"


def _coverage_lines(body: Any, comparison: ComparisonEnvelope | None) -> str:
    candidate_parts = []
    for item in body.coverage:
        shown = item.coverage_ratio
        if shown is None:
            shown = item.execution_state.value
        candidate_parts.append(f"{item.capability_id}:{shown}")
    candidate_text = ", ".join(candidate_parts) if candidate_parts else "UNKNOWN"
    if comparison is None:
        baseline_text = "UNKNOWN"
    else:
        baseline_text = comparison.coverage_status.value
    return (
        f"<p>baseline coverage: {_e(baseline_text)}</p>"
        f"<p>candidate coverage: {_e(candidate_text)}</p>"
    )


def _delta_lead(report: CanonicalReportInput) -> str:
    recorded = report.envelope.body.comparison
    comparison = report.comparison
    if comparison is None:
        return recorded.explanation
    movement = comparison.movement.value
    incompatible = comparison.compatibility.value == "incompatible"
    if incompatible or movement in {"insufficient", "not_applicable"}:
        reasons = ", ".join(comparison.compatibility_reasons) or recorded.reason_code
        return f"{comparison.compatibility.value} comparison; {reasons}"
    return recorded.explanation


def _delta(report: CanonicalReportInput) -> str:
    recorded = report.envelope.body.comparison
    if not recorded.has_baseline or (
        report.comparison is not None and not report.comparison.has_baseline
    ):
        table = (
            "<p>no baseline</p>"
            "<p>delta unavailable</p>"
            "<p>outcome movement unavailable</p>"
        )
    else:
        comparison = report.comparison
        movement = recorded.movement
        if comparison is not None:
            movement = comparison.movement.value
        rows = []
        if comparison is not None:
            catalog = {item["id"]: item for item in _driver_catalog()}
            for item in comparison.driver_deltas:
                driver = catalog.get(item.driver_id, {})
                rows.append(
                    "<tr>"
                    f"<td>{_e(item.driver_id)}</td>"
                    f"<td>{_e(item.comparison_unit)}</td>"
                    f"<td>{_e(driver.get('applicability'))}</td>"
                    f"<td>{_e(item.base_value)}</td>"
                    f"<td>{_e(item.candidate_value)}</td>"
                    f"<td>{_e(item.delta)}</td>"
                    f"<td>{_e(movement)}</td>"
                    f"<td>{_e(item.compatible)}</td>"
                    f"<td>{_e(item.compatibility_reason)}</td>"
                    f"<td>{_e(item.cause.value)}</td>"
                    f"<td>{_e(', '.join(comparison.excluded_driver_ids))}</td>"
                    "</tr>"
                )
        note = ""
        if movement in {"insufficient", "not_applicable"}:
            note = "<p>outcome movement unavailable for a full verdict</p>"
        table = (
            f"<p>movement: <span class=\"{_outcome_class(movement)}\">{_e(movement)}</span></p>"
            f"{_coverage_lines(report.envelope.body, comparison)}"
            f"<p>cause: {_e(_cause(comparison))}</p>"
            "<table><thead><tr><th>metric</th><th>unit</th><th>scope</th>"
            "<th>before</th><th>after</th><th>delta</th><th>outcome movement</th>"
            "<th>compatible</th><th>compatibility reason</th><th>cause</th>"
            "<th>excluded drivers</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
            + note
        )
    return (
        "<section id=\"before-after-delta\"><h2>Before / After / Delta</h2>"
        f"<p>{_e(_delta_lead(report))}</p>{table}</section>"
    )


def _inventory(body: Any) -> str:
    rows = "".join(
        f"<tr><td>{_e(item.fact_id)}</td><td>{_e(item.measurement_id)}</td></tr>"
        for item in body.facts
    )
    evidence = "".join(
        f'<li id="evidence-{_e(item.evidence_id)}">{_e(item.relative_path)} '
        f"{_e(item.limitation)}</li>"
        for item in body.evidence
    )
    return (
        "<section id=\"inventory-git\"><h2>Inventory and Git</h2>"
        f"<table><tbody>{rows}</tbody></table><ul>{evidence}</ul>"
        f"<p>graph limitations: {_e(', '.join(body.graph.limitations))}</p></section>"
    )


def _sarif_finding(item: Any) -> dict[str, Any]:
    result = item.result
    level = _SEVERITY_LEVEL.get(item.effective_severity, "warning")
    kind = "fail" if result == ResultStatus.FAIL.value else "informational"
    if result == ResultStatus.UNKNOWN.value:
        level = "warning"
        kind = "review"
    if result == ResultStatus.NOT_APPLICABLE.value:
        level = "note"
        kind = "informational"
    fingerprint = hashlib.sha256(
        f"{item.finding_id}|{item.rule_id}|{item.subject_id}|{item.occurrence_key or ''}".encode()
    ).hexdigest()
    return {
        "ruleId": item.rule_id,
        "level": level,
        "kind": kind,
        "message": {"text": f"{item.rule_id} {result}"},
        "partialFingerprints": {"codestrata/v1": fingerprint},
        "properties": {
            "status": result,
            "default_severity": item.default_severity,
            "effective_severity": item.effective_severity,
            "exception_attribution": item.override_provenance,
            "healthy_badge": result not in _UNHEALTHY and result != ResultStatus.FAIL.value,
        },
    }
