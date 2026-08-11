"""Reusable Evidence presentation for HTML (Slice 2.7).

Renders domain EvidenceRef envelopes already sanitized by the domain contract.
Does not perform new HTML-layer redaction or invent evidence.
"""

from __future__ import annotations

from collections.abc import Sequence
from contextvars import ContextVar
from typing import Any

from codestrata.reporters.html_rendering import escape_and_wrap, escape_html
from codestrata.reporting.html_v2.anchors import evidence_anchor
from codestrata.reporting.html_v2.labels import completeness_label, limitation_label
from codestrata.reporting.html_v2.models import EvidenceRefView

# Document-scoped set of evidence anchors already emitted with an HTML id.
# Prevents duplicate id="" when the same Evidence supports multiple Findings.
_claimed_evidence_anchors: ContextVar[set[str] | None] = ContextVar(
    "codestrata_html_claimed_evidence_anchors",
    default=None,
)


def begin_evidence_anchor_scope() -> object:
    """Start a document-scoped evidence-anchor claim set; returns a reset token."""

    return _claimed_evidence_anchors.set(set())


def end_evidence_anchor_scope(token: object) -> None:
    _claimed_evidence_anchors.reset(token)  # type: ignore[arg-type]


def render_evidence_ref_panel(
    refs: Sequence[EvidenceRefView],
    *,
    primary_evidence_id: str | None = None,
    heading: str = "Evidence",
) -> str:
    """Render EvidenceRef cards. Omit the panel entirely when empty."""

    items = tuple(refs)
    if not items:
        return ""
    claimed = _claimed_evidence_anchors.get()
    cards = []
    for ref in items:
        is_primary = primary_evidence_id is not None and ref.evidence_id == primary_evidence_id
        anchor = evidence_anchor(ref.evidence_id)
        emit_anchor = True
        if claimed is not None:
            if anchor in claimed:
                emit_anchor = False
            else:
                claimed.add(anchor)
        cards.append(_render_one(ref, primary=is_primary, emit_anchor=emit_anchor))
    return (
        f'<div class="evidence-panel">\n'
        f"<h4>{escape_html(heading)}</h4>\n"
        f'<div class="evidence-stack">{"".join(cards)}</div>\n'
        "</div>"
    )


def _render_one(ref: EvidenceRefView, *, primary: bool, emit_anchor: bool = True) -> str:
    anchor = evidence_anchor(ref.evidence_id)
    rows: list[str] = []
    if primary:
        rows.append('<p class="evidence-primary-label">Primary evidence</p>')
    location = _location_line(ref)
    if location:
        rows.append(f"<p><em>Location</em> {location}</p>")
    if ref.symbolic_reference:
        rows.append(
            f"<p><em>Subject</em> "
            f"<code>{escape_and_wrap(ref.symbolic_reference)}</code></p>"
        )
    measurement = _measurement_block(ref)
    if measurement:
        rows.append(measurement)
    if ref.snippet_text:
        rows.append(
            '<blockquote class="evidence-snippet">'
            f"{escape_html(ref.snippet_text)}"
            "</blockquote>"
        )
    if ref.graph_kind or ref.graph_ref_id:
        bits = []
        if ref.graph_kind:
            bits.append(escape_html(ref.graph_kind.replace("_", " ")))
        if ref.graph_ref_id:
            bits.append(f"<code>{escape_and_wrap(ref.graph_ref_id)}</code>")
        rows.append(f"<p><em>Graph reference</em> {' — '.join(bits)}</p>")
    if ref.kind:
        rows.append(f"<p><em>Kind</em> {escape_html(ref.kind.replace('_', ' '))}</p>")
    if ref.production_mode:
        rows.append(
            f"<p><em>Mode</em> {escape_html(ref.production_mode.replace('_', ' '))}</p>"
        )
    if ref.evidence_confidence_level:
        rows.append(
            "<p><em>Evidence confidence</em> "
            f"{escape_html(ref.evidence_confidence_level.replace('_', ' ').title())}</p>"
        )
        if ref.evidence_confidence_limitations:
            lim = "".join(
                f"<li>{escape_html(limitation_label(item))}</li>"
                for item in ref.evidence_confidence_limitations
            )
            rows.append(
                f'<div class="limitations"><em>Evidence confidence limitations</em>'
                f"<ul>{lim}</ul></div>"
            )
    if ref.limitations:
        lim = "".join(
            f"<li>{escape_html(limitation_label(item))}</li>" for item in ref.limitations
        )
        rows.append(f'<div class="limitations"><em>Evidence limitations</em><ul>{lim}</ul></div>')
    body = "\n".join(rows) or '<p class="muted">No additional evidence details.</p>'
    id_attr = f' id="{escape_html(anchor)}"' if emit_anchor else ""
    data_attr = f' data-evidence-id="{escape_html(anchor)}"'
    return (
        f'<article class="evidence-card"{id_attr}{data_attr}>\n'
        f"{body}\n"
        "</article>"
    )


def _location_line(ref: EvidenceRefView) -> str:
    path = (ref.path or "").strip()
    if not path:
        return ""
    # Never render absolute or file:// paths — builder should already sanitize.
    if path.startswith("/") or path.startswith("file:"):
        return ""
    line = f"<code>{escape_and_wrap(path)}</code>"
    if ref.line_start is not None and ref.line_end is not None:
        if ref.line_start == ref.line_end:
            line += f", line {int(ref.line_start)}"
        else:
            line += f", lines {int(ref.line_start)}–{int(ref.line_end)}"
    elif ref.line_start is not None:
        line += f", line {int(ref.line_start)}"
    return line


def _measurement_block(ref: EvidenceRefView) -> str:
    if not ref.measurement_name and ref.measurement_value is None:
        return ""
    parts: list[str] = []
    name = ref.measurement_name or "Measurement"
    if ref.measurement_value is not None:
        parts.append(f"{escape_html(name)}: {escape_html(str(ref.measurement_value))}")
    else:
        parts.append(escape_html(name))
    if ref.threshold_operator and ref.threshold_value is not None:
        op = ref.threshold_operator.replace("_", " ")
        parts.append(
            f"Threshold: {escape_html(op)} {escape_html(str(ref.threshold_value))}"
        )
    elif ref.threshold_value is not None:
        parts.append(f"Threshold: {escape_html(str(ref.threshold_value))}")
    if ref.comparison_result:
        parts.append(f"Comparison: {escape_html(ref.comparison_result.replace('_', ' '))}")
    return "<p><em>Measurement</em> " + " · ".join(parts) + "</p>"


def evidence_ref_view_from_domain(ref: Any) -> EvidenceRefView:
    """Project a domain EvidenceRef (or stable dict) into EvidenceRefView."""

    if isinstance(ref, EvidenceRefView):
        return ref
    evidence_id = str(getattr(ref, "evidence_id", "") or "")
    location = getattr(ref, "location", None)
    snippet = getattr(ref, "snippet", None)
    measurement = getattr(ref, "measurement", None)
    graph = getattr(ref, "graph_ref", None)
    path = getattr(location, "path", None) if location is not None else None
    return EvidenceRefView(
        evidence_id=evidence_id,
        kind=str(getattr(getattr(ref, "kind", None), "value", getattr(ref, "kind", "") or "")),
        production_mode=str(
            getattr(
                getattr(ref, "production_mode", None),
                "value",
                getattr(ref, "production_mode", "") or "",
            )
        ),
        path=str(path) if path else None,
        line_start=getattr(location, "line_start", None) if location is not None else None,
        line_end=getattr(location, "line_end", None) if location is not None else None,
        symbolic_reference=(
            getattr(location, "symbolic_reference", None) if location is not None else None
        ),
        snippet_text=getattr(snippet, "text", None) if snippet is not None else None,
        measurement_name=getattr(measurement, "metric_name", None) if measurement is not None else None,
        measurement_value=(
            getattr(measurement, "measured_value", None) if measurement is not None else None
        ),
        threshold_operator=(
            str(
                getattr(
                    getattr(measurement, "threshold_operator", None),
                    "value",
                    getattr(measurement, "threshold_operator", None) or "",
                )
            )
            or None
            if measurement is not None
            else None
        ),
        threshold_value=getattr(measurement, "threshold", None) if measurement is not None else None,
        comparison_result=(
            str(
                getattr(
                    getattr(measurement, "comparison_result", None),
                    "value",
                    getattr(measurement, "comparison_result", None) or "",
                )
            )
            or None
            if measurement is not None
            else None
        ),
        graph_kind=(
            str(
                getattr(
                    getattr(graph, "graph_kind", None),
                    "value",
                    getattr(graph, "graph_kind", None) or "",
                )
            )
            or None
            if graph is not None
            else None
        ),
        graph_ref_id=getattr(graph, "graph_id", None) if graph is not None else None,
        graph_reference_kind=(
            str(
                getattr(
                    getattr(graph, "reference_kind", None),
                    "value",
                    getattr(graph, "reference_kind", None) or "",
                )
            )
            or None
            if graph is not None
            else None
        ),
        graph_node_ids=tuple(getattr(graph, "node_ids", ()) or ()) if graph is not None else (),
        graph_edge_ids=tuple(getattr(graph, "edge_ids", ()) or ()) if graph is not None else (),
        graph_relationship_type=(
            getattr(graph, "relationship_type", None) if graph is not None else None
        ),
        graph_cycle_id=getattr(graph, "cycle_id", None) if graph is not None else None,
        measurement_scope=(
            str(
                getattr(
                    getattr(measurement, "scope", None),
                    "value",
                    getattr(measurement, "scope", None) or "",
                )
            )
            or None
            if measurement is not None
            else None
        ),
        limitations=tuple(getattr(ref, "limitations", ()) or ()),
        evidence_confidence_level=_evidence_confidence_level(ref),
        evidence_confidence_limitations=_evidence_confidence_limitations(ref),
    )


def _evidence_confidence_level(ref: Any) -> str | None:
    confidence = getattr(ref, "evidence_confidence", None)
    if confidence is None and isinstance(ref, dict):
        confidence = ref.get("evidence_confidence")
    if confidence is None:
        return None
    level = getattr(confidence, "level", None)
    if level is None and isinstance(confidence, dict):
        level = confidence.get("level")
    if level is None:
        return None
    return str(getattr(level, "value", level))


def _evidence_confidence_limitations(ref: Any) -> tuple[str, ...]:
    confidence = getattr(ref, "evidence_confidence", None)
    if confidence is None and isinstance(ref, dict):
        confidence = ref.get("evidence_confidence")
    if confidence is None:
        return ()
    limitations = getattr(confidence, "limitations", None)
    if limitations is None and isinstance(confidence, dict):
        limitations = confidence.get("limitations") or ()
    return tuple(limitations or ())
