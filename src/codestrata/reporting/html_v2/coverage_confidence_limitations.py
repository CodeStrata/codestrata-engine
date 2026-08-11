"""Canonical Coverage / Confidence / Limitations presentation (Epic 3 Slice 3.11).

Presentation-only helper shared by every assessment head. Reuses existing
deterministic coverage rows, confidence labels, and limitations — does not
invent percentages, estimates, or new completeness calculations.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from codestrata.reporters.html_rendering import escape_html
from codestrata.reporting.html_v2.labels import limitation_label

# Customer-facing confidence vocabulary (Slice 3.11).
_CONFIDENCE_DISPLAY: dict[str, str] = {
    "high": "High",
    "moderate": "Moderate",
    "medium": "Moderate",
    "limited": "Limited",
    "low": "Limited",
    "unavailable": "Unavailable",
    "unknown": "Unavailable",
    "legacy": "Unavailable",
}

COVERAGE_UNAVAILABLE = "Coverage unavailable."
CONFIDENCE_UNAVAILABLE = "Unavailable"
LIMITATIONS_UNAVAILABLE = "Limitations unavailable."

# Stable CSS class for the canonical trailing block.
CCL_BLOCK_CLASS = "assessment-ccl"
CCL_COVERAGE_GROUP = "coverage"
CCL_CONFIDENCE_GROUP = "confidence"
CCL_LIMITATIONS_GROUP = "limitations"


def normalize_confidence_display(
    confidence: str | None = None,
    confidence_label: str | None = None,
) -> str:
    """Map any existing confidence token/label to the canonical vocabulary."""

    for raw in (confidence, confidence_label):
        text = str(raw or "").strip()
        if not text:
            continue
        lowered = text.lower().replace("confidence", "").strip()
        # "High confidence" → "high"; "Confidence unavailable" → "unavailable"
        if lowered.startswith("confidence "):
            lowered = lowered[len("confidence ") :].strip()
        mapped = _CONFIDENCE_DISPLAY.get(lowered)
        if mapped is not None:
            return mapped
        # Exact key without stripping
        mapped = _CONFIDENCE_DISPLAY.get(text.lower())
        if mapped is not None:
            return mapped
    return CONFIDENCE_UNAVAILABLE


def dedupe_limitations(limitations: Sequence[str]) -> tuple[str, ...]:
    """Merge deterministic limitations and deduplicate case-insensitively."""

    seen: set[str] = set()
    out: list[str] = []
    for item in limitations:
        label = limitation_label(str(item or "").strip())
        if not label:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(label)
    return tuple(out)


def render_coverage_confidence_limitations(
    *,
    coverage_rows: Sequence[Any] = (),
    confidence: str | None = None,
    confidence_label: str | None = None,
    confidence_note: str | None = None,
    limitations: Sequence[str] = (),
    coverage_fallback: str | None = None,
    assessment_coverage: Any | None = None,
) -> str:
    """Render the canonical Coverage → Confidence → Limitations trailing block.

    Always emits all three subsections in that order with identical headings and
    structure. Empty states use the shared unavailable copy. When canonical
    AssessmentCoverage is provided, it becomes the Coverage authority and pack
    detail rows are omitted to avoid duplicate coverage blocks.
    """

    canonical_rows = ()
    if assessment_coverage is not None:
        from codestrata.application.assessment_heads.coverage import (
            coverage_summary_rows,
        )
        from codestrata.domain.assessment_heads.assessment_coverage import (
            AssessmentCoverage,
        )

        if isinstance(assessment_coverage, AssessmentCoverage):
            canonical_rows = coverage_summary_rows(assessment_coverage)
        elif isinstance(assessment_coverage, dict):
            try:
                model = AssessmentCoverage.model_validate(assessment_coverage)
                canonical_rows = coverage_summary_rows(model)
            except Exception:
                canonical_rows = ()

    rows = canonical_rows or coverage_rows
    parts: list[str] = [
        f'<div class="{CCL_BLOCK_CLASS}" data-canonical="coverage-confidence-limitations">\n'
        f'{_render_coverage(rows, fallback=coverage_fallback)}\n'
        f"{_render_confidence(confidence, confidence_label, note=confidence_note)}\n"
        f"{_render_limitations(limitations)}\n"
        "</div>"
    ]
    return "".join(parts)


def _render_coverage(
    coverage_rows: Sequence[Any],
    *,
    fallback: str | None,
) -> str:
    rows_html = _coverage_table_rows(coverage_rows)
    if rows_html:
        body = (
            '<div class="table-wrap"><table>\n'
            "<thead><tr><th>Area</th><th>Status</th><th>Display</th><th>Note</th></tr></thead>\n"
            f"<tbody>{rows_html}</tbody>\n"
            "</table></div>"
        )
    else:
        message = (fallback or COVERAGE_UNAVAILABLE).strip() or COVERAGE_UNAVAILABLE
        body = f'<p class="muted">{escape_html(message)}</p>'
    return (
        f'<div class="{CCL_BLOCK_CLASS}-group" data-group="{CCL_COVERAGE_GROUP}">\n'
        "<h4>Coverage</h4>\n"
        f"{body}\n"
        "</div>"
    )


def _coverage_table_rows(coverage_rows: Sequence[Any]) -> str:
    rows: list[str] = []
    for item in coverage_rows:
        label = str(getattr(item, "label", "") or "").strip()
        status = str(getattr(item, "status", "") or "").strip()
        display = str(getattr(item, "display", "") or "").strip()
        note = getattr(item, "note", None)
        if not label and not status and not display:
            # Support plain (label, status, display, note) tuples.
            if isinstance(item, (tuple, list)) and len(item) >= 3:
                label = str(item[0] or "").strip()
                status = str(item[1] or "").strip()
                display = str(item[2] or "").strip()
                note = item[3] if len(item) > 3 else None
        if not label:
            continue
        note_text = str(note).strip() if note is not None and str(note).strip() else ""
        rows.append(
            "<tr>"
            f"<td>{escape_html(label)}</td>"
            f"<td>{escape_html(status) if status else '—'}</td>"
            f"<td>{escape_html(display) if display else '—'}</td>"
            f"<td>{escape_html(note_text) if note_text else '—'}</td>"
            "</tr>"
        )
    return "".join(rows)


def _render_confidence(
    confidence: str | None,
    confidence_label: str | None,
    *,
    note: str | None,
) -> str:
    display = normalize_confidence_display(confidence, confidence_label)
    note_html = (
        f'\n<p class="muted">{escape_html(note.strip())}</p>'
        if note and str(note).strip()
        else ""
    )
    return (
        f'<div class="{CCL_BLOCK_CLASS}-group" data-group="{CCL_CONFIDENCE_GROUP}">\n'
        "<h4>Confidence</h4>\n"
        f"<p>{escape_html(display)}</p>"
        f"{note_html}\n"
        "</div>"
    )


def _render_limitations(limitations: Sequence[str]) -> str:
    items = dedupe_limitations(limitations)
    if items:
        body = '<ul class="plain">' + "".join(
            f"<li>{escape_html(item)}</li>" for item in items
        ) + "</ul>"
    else:
        body = f'<p class="muted">{escape_html(LIMITATIONS_UNAVAILABLE)}</p>'
    return (
        f'<div class="{CCL_BLOCK_CLASS}-group" data-group="{CCL_LIMITATIONS_GROUP}">\n'
        "<h4>Limitations</h4>\n"
        f"{body}\n"
        "</div>"
    )


def coverage_rows_from_assessment_head(section: Any) -> tuple[Any, ...]:
    """Project a single coverage row from AssessmentHeadSectionView fields."""

    title = str(getattr(section, "title", "") or "Assessment").strip() or "Assessment"
    status = str(getattr(section, "status", "") or "not_available").strip()
    evidence = str(getattr(section, "evidence_state", "") or "unavailable").strip()
    findings = int(getattr(section, "findings_count", 0) or 0)
    recommendations = int(getattr(section, "recommendations_count", 0) or 0)
    display = (
        f"findings: {findings}; recommendations: {recommendations}; evidence: {evidence}"
    )
    return (
        simple_coverage_row(
            label=title,
            status=status,
            display=display,
            note=str(getattr(section, "status_label", "") or "").strip() or None,
        ),
    )


class _SimpleCoverageRow:
    __slots__ = ("label", "status", "display", "note")

    def __init__(
        self,
        *,
        label: str,
        status: str,
        display: str,
        note: str | None = None,
    ) -> None:
        self.label = label
        self.status = status
        self.display = display
        self.note = note


def simple_coverage_row(
    *,
    label: str,
    status: str,
    display: str,
    note: str | None = None,
) -> _SimpleCoverageRow:
    return _SimpleCoverageRow(
        label=label, status=status, display=display, note=note
    )
