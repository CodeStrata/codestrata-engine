"""Self-contained CodeStrata Engineering Assessment HTML report renderer.

Presentation only — no analysis or enrichment business logic.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from contextvars import ContextVar
from typing import Any

from codestrata.design_system.embedded_fonts import font_license_html_comment
from codestrata.reporters.html_rendering import escape_and_wrap, escape_html, wrap_table
from codestrata.reporting.ai_readiness.intelligence import (
    scrub_soft_ai_readiness_claims,
)
from codestrata.reporting.ai_readiness.intelligence_models import (
    AiReadinessIntelligenceSection,
)
from codestrata.reporting.ai_readiness.models import AiReadinessReportSection
from codestrata.reporting.architecture.intelligence_models import ArchitectureIntelligenceSection
from codestrata.reporting.architecture.models import ArchitectureReportSection
from codestrata.reporting.branding import (
    BRAND_FOOTER_LINE,
    BRAND_NAME,
    BRAND_REPORT_NAME,
    BRAND_VERSION,
    brand_favicon_link_tag,
)
from codestrata.reporting.cloud.intelligence import (
    scrub_soft_cloud_claims,
)
from codestrata.reporting.cloud.intelligence_models import CloudIntelligenceSection
from codestrata.reporting.cloud.models import CloudReportSection
from codestrata.reporting.dependency.intelligence_models import (
    DependencyIntelligenceSection,
)
from codestrata.reporting.dependency.models import DependencyReportSection
from codestrata.reporting.engineering_health.models import (
    ArchitectureMapView,
    AttentionSummaryView,
    CochangeSectionView,
    HotspotSectionView,
    OwnershipSectionView,
)
from codestrata.reporting.engineering_intelligence.intelligence_models import (
    EngineeringIntelligenceSection,
)
from codestrata.reporting.html_v2.anchors import (
    evidence_anchor,
    finding_anchor,
    priority_action_anchor,
    recommendation_anchor,
    roadmap_initiative_anchor,
)
from codestrata.reporting.html_v2.assessment_heads import (
    ASSESSMENT_RESULTS_ANCHOR,
    LEGACY_PACK_SECTION_ALIASES,
    AssessmentHead,
    assessment_head_anchor,
    assessment_head_title,
    engineering_health_outcome_title,
)
from codestrata.reporting.html_v2.coverage_confidence_limitations import (
    coverage_rows_from_assessment_head,
    render_coverage_confidence_limitations,
    simple_coverage_row,
)
from codestrata.reporting.html_v2.evidence_presentation import (
    begin_evidence_anchor_scope,
    end_evidence_anchor_scope,
    render_evidence_ref_panel,
)
from codestrata.reporting.html_v2.labels import completeness_label, limitation_label
from codestrata.reporting.html_v2.models import (
    AiEnrichmentView,
    AssessmentHeadSectionView,
    FindingView,
    HtmlReportViewModel,
    RecommendationView,
)
from codestrata.reporting.html_v2.r2_shell import (
    PRINT_CONTROL_SCRIPT,
    content_security_policy,
    print_script_tag,
    reference_shell_css,
    report_chrome,
)
from codestrata.reporting.modernization.intelligence_models import (
    ModernizationIntelligenceSection,
)
from codestrata.reporting.performance.models import PerformanceReportSection
from codestrata.reporting.security.intelligence_models import (
    SecurityIntelligenceSection,
)
from codestrata.reporting.security.models import SecurityReportSection
from codestrata.reporting.technical_debt.intelligence_models import (
    TechnicalDebtIntelligenceSection,
)
from codestrata.reporting.technical_debt.models import TechnicalDebtReportSection
from codestrata.reporting.technology.models import (
    RepositoryCompositionView,
    TechnologyInventorySection,
)
from codestrata.reporting.testing.models import TestingReportSection

CONTENT_SECURITY_POLICY = content_security_policy(PRINT_CONTROL_SCRIPT)

# Evidence ids that this document will actually emit as anchors. Capability
# labels that are not in the set stay visible as non-link text.
_rendered_evidence_ids: ContextVar[frozenset[str] | None] = ContextVar(
    "codestrata_rendered_evidence_ids",
    default=None,
)
_rendered_recommendation_ids: ContextVar[frozenset[str] | None] = ContextVar(
    "codestrata_rendered_recommendation_ids",
    default=None,
)

_TOP_FINDINGS = 5
_MAIN_HOTSPOT_CARD_LIMIT = 12
_MAIN_COCHANGE_SUPPORTED_LIMIT = 8
_MAIN_COCHANGE_UNSUPPORTED_LIMIT = 4
_MAIN_OWNERSHIP_ROW_LIMIT = 12
_SEVERITY_ORDER = ("critical", "high", "medium", "low", "informational")


def _optional_code_td(value: str | None) -> str:
    if not value:
        return "<td>—</td>"
    return f'<td><code class="trace-id">{escape_html(value)}</code></td>'


def _optional_text_td(value: str | None) -> str:
    if not value:
        return "<td>—</td>"
    return f"<td>{escape_html(value)}</td>"


def _optional_id_links_td(ids: Sequence[str], anchor: Callable[[str], str]) -> str:
    if not ids:
        return "<td>—</td>"
    return f"<td>{_render_id_links(ids, anchor)}</td>"


def _roadmap_supporting_td(item: Any) -> str:
    if item.supporting_priority_action_ids:
        return (
            "<td>"
            + f"{_render_id_links(item.supporting_priority_action_ids, priority_action_anchor)}"
            + "</td>"
        )
    if item.is_legacy:
        return '<td><span class="muted">Legacy — limited traceability</span></td>'
    return "<td>—</td>"


def _recommendation_detail_available(recommendation_id: str) -> bool:
    """True when a full recommendation card will emit this fragment.

    An unset scope keeps the previous always-link behavior for isolated helpers.
    A render installs the set of ids that actually receive ``recommendation_anchor``.
    """

    rendered = _rendered_recommendation_ids.get()
    if rendered is None:
        return True
    return recommendation_id in rendered


def _recommendation_detail_markup(recommendation_id: str, label: str) -> str:
    text = escape_html(label)
    if _recommendation_detail_available(recommendation_id):
        href = escape_html(recommendation_anchor(recommendation_id))
        return f'<a class="id-link" href="#{href}">{text}</a>'
    return (
        f'<span class="evidence-unavailable">{text} '
        "(recommendation detail not attached)</span>"
    )


def _recommendation_td(recommendation_id: str, title: str) -> str:
    return f"<td>{_recommendation_detail_markup(recommendation_id, title)}</td>"


class HtmlReportRenderer:
    """Render HtmlReportViewModel to a complete HTML document.

    Contains no analysis or enrichment business logic.
    """

    def render(self, view: HtmlReportViewModel) -> str:
        """Render HtmlReportViewModel to a complete HTML document.

        Contains no analysis or enrichment business logic.
        """

        evidence_scope = begin_evidence_anchor_scope()
        rendered_ids = _rendered_evidence_ids.set(_collect_rendered_evidence_ids(view))
        rendered_recommendations = _rendered_recommendation_ids.set(
            _collect_rendered_recommendation_ids(view)
        )
        try:
            parts = [
                "<!DOCTYPE html>",
                '<html lang="en">',
                "<head>",
                '<meta charset="utf-8">',
                f'<meta http-equiv="Content-Security-Policy" content="{CONTENT_SECURITY_POLICY}">',
                '<meta name="viewport" content="width=device-width, initial-scale=1">',
                '<meta name="color-scheme" content="light">',
                (
                    f'<meta name="generator" content="{escape_html(BRAND_NAME)} '
                    + f'{escape_html(BRAND_REPORT_NAME)}">'
                ),
                f"<title>{escape_html(BRAND_NAME)} Current-code baseline — "
                + f"{escape_html(view.summary.repository_name)}</title>",
                brand_favicon_link_tag(),
                font_license_html_comment(),
                f"<style>{_CSS}</style>",
                "</head>",
                "<body>",
                report_chrome(
                    active_label="Current baseline",
                    download_href="canonical-report.json",
                    download_label="Download JSON",
                ),
                '<main id="main" class="page">',
                _render_hero(view),
                _render_section_nav(),
                _section(
                    "What deserves attention now",
                    _render_attention_first(view),
                    section_id="attention-first",
                    eyebrow="01 · Attention first",
                    note="Start with the decision, then follow the attached evidence.",
                ),
                _render_ai_summary_section(view),
                _render_assessment_results(view),
                _section(
                    "Architecture Map",
                    _render_architecture_map(view.architecture_map),
                    section_id="architecture-map",
                    eyebrow="03 · Architecture Map",
                    note="Canonical repository-graph nodes and edges only. Layout is presentation.",
                ),
                _section(
                    "Engineering Hotspots",
                    _render_engineering_hotspots(view.engineering_hotspots),
                    section_id="engineering-hotspots",
                    eyebrow="04 · Engineering focus",
                    note="Sealed M22 records. Ranking is not calculated in this report.",
                ),
                _section(
                    "Ownership concentration",
                    _render_ownership_concentration(view.ownership_concentration),
                    section_id="ownership-concentration",
                    eyebrow="05 · Ownership",
                    note="Sealed M25 records. Ratios are copied, not divided here.",
                ),
                _section(
                    "Temporal co-change",
                    _render_temporal_cochange(view.temporal_cochange),
                    section_id="temporal-co-change",
                    eyebrow="06 · Co-change",
                    note="Sealed M26 pairs. Jaccard is displayed, never computed here.",
                ),
                _section(
                    "Priority Actions",
                    _render_roadmap(
                        view.priority_actions if view.priority_actions else view.recommendations,
                        total_actions=view.priority_actions_total or len(view.priority_actions),
                        as_priority_actions=True,
                    ),
                    section_id="priority-actions",
                    eyebrow="07 · Recommendations",
                    note="Recommendation-backed actions. Hotspot rank is not action order.",
                ),
                _section(
                    "Coverage & Trust",
                    _render_coverage_trust(view),
                    section_id="coverage-and-trust",
                    eyebrow="08 · Coverage & Trust",
                    note="Capability coverage, freshness, and material limitations for this run.",
                ),
            ]
            supporting = _render_supporting_and_appendix(view) + _render_technical_details(view)
            if view.roadmap_report is not None:
                supporting += _section(
                    "Roadmap",
                    _render_phased_roadmap(view),
                    section_id="phased-modernization-plan",
                    eyebrow="Supporting",
                    note=(
                        "Engine assess sequencing of Priority Actions "
                        + "(Stabilize → Secure → Modernize → Optimize). "
                        + "This is not CodeStrata Platform Strategic Roadmap."
                    ),
                )
            parts.append(
                _section(
                    "Technical Appendix",
                    supporting,
                    section_id="technical-appendix",
                    eyebrow="09 · Evidence",
                    note=(
                        "Supporting evidence, inventory, dependencies, Git/trust detail, "
                        + "and legacy Cloud/AI/Modernization packs."
                    ),
                )
            )
            parts.extend(
                [
                    "</main>",
                    _render_footer(view),
                    print_script_tag(),
                    "</body>",
                    "</html>",
                    "",
                ]
            )
            return _ensure_table_semantics(_ensure_responsive_tables("\n".join(parts)))
        finally:
            _rendered_evidence_ids.reset(rendered_ids)
            _rendered_recommendation_ids.reset(rendered_recommendations)
            end_evidence_anchor_scope(evidence_scope)


def _ensure_responsive_tables(html: str) -> str:
    """Wrap bare tables in scroll containers without double-wrapping."""

    pieces: list[str] = []
    index = 0
    lower = html.lower()
    while True:
        start = lower.find("<table", index)
        if start < 0:
            pieces.append(html[index:])
            break
        lookbehind = lower[max(0, start - 96) : start]
        end = lower.find("</table>", start)
        if end < 0:
            pieces.append(html[index:])
            break
        end += len("</table>")
        pieces.append(html[index:start])
        if any(
            marker in lookbehind for marker in ("table-wrap", "responsive-table", "table-wrapper")
        ):
            pieces.append(html[start:end])
        else:
            pieces.append('<div class="table-wrap responsive-table">')
            pieces.append(html[start:end])
            pieces.append("</div>")
        index = end
    return "".join(pieces)


_THEAD_BLOCK = re.compile(r"<thead>(.*?)</thead>", re.IGNORECASE | re.DOTALL)
_TH_WITHOUT_SCOPE = re.compile(r"<th(?![^>]*\bscope=)([^>]*)>", re.IGNORECASE)
_TH_COLUMN_SCOPE = r'<th scope="col"\1>'
_TABLE_WRAPPERS: tuple[str, ...] = (
    '<div class="table-wrap responsive-table">',
    '<div class="table-wrap">',
    '<div class="table-wrapper">',
)


def _ensure_table_semantics(html: str) -> str:
    """Associate header cells with their columns and let keyboards scroll wide tables.

    Header cells are emitted per section; declaring ``scope`` centrally keeps the
    association correct without touching table data. ``tabindex`` is required
    because a horizontally scrolling container is otherwise unreachable without a
    pointer.
    """

    def _scope_header_row(match: re.Match[str]) -> str:
        scoped = _TH_WITHOUT_SCOPE.sub(_TH_COLUMN_SCOPE, match.group(1))
        return f"<thead>{scoped}</thead>"

    html = _THEAD_BLOCK.sub(_scope_header_row, html)
    for wrapper in _TABLE_WRAPPERS:
        html = html.replace(wrapper, f'{wrapper[:-1]} tabindex="0">')
    return html


def _section(
    title: str,
    body: str,
    *,
    section_id: str,
    note: str | None = None,
    css_class: str = "section",
    eyebrow: str | None = None,
) -> str:
    note_html = f'<p class="muted">{escape_html(note)}</p>' if note else ""
    eyebrow_html = f'<div class="eyebrow">{escape_html(eyebrow)}</div>' if eyebrow else ""
    return (
        f'<section class="report-section {css_class}" id="{escape_html(section_id)}">\n'
        '<div class="section-heading">'
        f"{eyebrow_html}"
        f"<h2>{escape_html(title)}</h2>"
        f"{note_html}</div>\n"
        f"{body}\n"
        "</section>"
    )


def _subsection(
    title: str,
    body: str,
    *,
    section_id: str,
    note: str | None = None,
) -> str:
    note_html = f'<p class="section-note">{escape_html(note)}</p>' if note else ""
    return (
        f'<section class="subsection" id="{escape_html(section_id)}">\n'
        f'<div class="section-head"><h3>{escape_html(title)}</h3></div>\n'
        f"{note_html}"
        f"{body}\n"
        "</section>"
    )


def _render_section_nav() -> str:
    links = (
        ("attention-first", "Attention first"),
        ("ai-summary", "AI Summary"),
        ("assessment-results", "Outcomes"),
        ("architecture-map", "Architecture Map"),
        ("engineering-hotspots", "Hotspot map"),
        ("ownership-concentration", "Ownership"),
        ("temporal-co-change", "Co-change"),
        ("priority-actions", "Priority actions"),
        ("coverage-and-trust", "Coverage & Trust"),
        ("technical-appendix", "Evidence"),
    )
    items = "".join(
        f'<a href="#{escape_html(anchor)}">{escape_html(label)}</a>' for anchor, label in links
    )
    return f'<nav class="section-nav" id="contents" aria-label="Report sections">{items}</nav>'


def _render_leadership_verdict(view: HtmlReportViewModel) -> str:
    text = (view.leadership_verdict or "").strip()
    if not text:
        return ""
    return (
        '<section class="section section-verdict" '
        'id="leadership-verdict">\n'
        '<div class="section-head"><h2>Leadership Verdict</h2></div>\n'
        f'<p class="verdict-body">{escape_html(text)}</p>\n'
        "</section>"
    )


def _render_executive_summary_section(view: HtmlReportViewModel) -> str:
    """Standalone Executive Summary narrative (Epic 3 Slice 3.10 placement)."""

    narrative = view.executive_summary
    if narrative is None:
        return '<p class="muted">No executive summary was produced for this assessment.</p>'
    return (
        '<div class="exec-narrative">\n'
        "<h3>Should I care?</h3>\n"
        f"<p>{escape_html(narrative.should_i_care)}</p>\n"
        "<h3>Why now?</h3>\n"
        f"<p>{escape_html(narrative.why_now)}</p>\n"
        "<h3>What should my team do next?</h3>\n"
        f"<p>{escape_html(narrative.what_next)}</p>\n"
        "</div>"
    )


def _render_engineering_intelligence_summary(view: HtmlReportViewModel) -> str:
    """Epic 3 Slice 3.10 Engineering Intelligence Summary — synthesis only."""

    section = view.engineering_intelligence
    if section is not None:
        return _render_engineering_intelligence(section)
    # Compatibility fallback when intelligence projection is absent.
    summary = view.assessment_summary
    highest = escape_html(view.summary.highest_finding_severity or "None Detected")
    parts: list[str] = [
        '<div class="split">\n'
        "<div>\n"
        f"<p><strong>Checks assessed:</strong> {summary.rules_evaluated}</p>\n"
        f"<p><strong>Findings:</strong> {summary.findings_count}</p>\n"
        f"<p><strong>Recommendations:</strong> {summary.recommendations_count}</p>\n"
        f"<p><strong>Highest finding severity:</strong> {highest}</p>\n"
        "</div>\n"
        "</div>"
    ]
    if view.assessment_heads:
        area_rows = "".join(
            "<tr>"
            + f"<td>{escape_html(item.title)}</td>"
            + f"<td>{escape_html(item.status_label)}</td>"
            + f"<td>{item.findings_count}</td>"
            + f"<td>{item.recommendations_count}</td>"
            + "</tr>"
            for item in view.assessment_heads
        )
        parts.append(
            "<h3>Assessment areas</h3>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr><th>Area</th><th>Status</th>"
            + "<th>Findings</th><th>Recommendations</th></tr></thead>\n"
            + f"<tbody>{area_rows}</tbody>\n</table></div>"
        )
    return "\n".join(parts)


_OVERVIEW_LIMITATION_KEEP = frozenset(
    {
        "based only on enabled assessment heads.",
        "runtime behavior not evaluated.",
        "disabled heads reduce completeness.",
        "some assessment heads were not enabled or not available, which reduces completeness.",
    }
)
_ASSESSED_HEAD_STATUSES = frozenset(
    {
        "assessed",
        "partially_assessed",
    }
)
_NOT_ASSESSED_OVERVIEW = (
    ("cloud_readiness", "Cloud readiness"),
    ("ai_readiness", "AI readiness"),
    ("performance", "Performance"),
)


def _overview_limitations(limitations: tuple[str, ...]) -> tuple[str, ...]:
    """Keep the overview limitation list short; head sections keep their own notes."""

    kept = tuple(note for note in limitations if note.strip().lower() in _OVERVIEW_LIMITATION_KEEP)
    if kept:
        return kept
    return (
        "Based only on enabled assessment heads.",
        "Runtime behavior not evaluated.",
        "Disabled heads reduce completeness.",
    )


def _not_assessed_overview_table(head_summaries: Sequence[Any]) -> str:
    by_id = {str(getattr(item, "head_id", "") or ""): item for item in head_summaries}
    rows: list[str] = []
    for head_id, label in _NOT_ASSESSED_OVERVIEW:
        item = by_id.get(head_id)
        if item is not None and str(getattr(item, "status", "") or "").strip().lower() in (
            _ASSESSED_HEAD_STATUSES
        ):
            continue
        if item is None:
            reason = "Not assessed"
        else:
            reason = str(getattr(item, "status_label", "") or "").strip() or "Not assessed"
        rows.append(f"<tr><td>{escape_html(label)}</td><td>{escape_html(reason)}</td></tr>")
    if not rows:
        return ""
    body = "".join(rows)
    return (
        '<div class="eis-intel-group" data-group="not_assessed">\n'
        "<h3>Not assessed</h3>\n"
        '<div class="table-wrap"><table>\n'
        "<thead><tr><th>Area</th><th>Reason</th></tr></thead>\n"
        f"<tbody>{body}</tbody>\n</table></div>\n"
        "</div>"
    )


def _render_engineering_intelligence(section: EngineeringIntelligenceSection) -> str:
    """Render the Engineering Intelligence Summary pack body."""

    parts: list[str] = [
        "<div class='domain-header'>"
        f"<span class='{_status_badge_class(section.status_label)}'>"
        f"{escape_html(section.status_label)}</span>"
        f"<span class='muted'>{escape_html(section.status_summary)}</span>"
        "</div>"
    ]

    if section.overview_facts:
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(fact.label)}</td>"
            + f"<td>{escape_html(fact.value)}</td>"
            + f"<td>{escape_html(fact.note) if fact.note else '—'}</td>"
            + "</tr>"
            for fact in section.overview_facts
        )
        parts.append(
            '<div class="eis-intel-group" data-group="overall_status">\n'
            + "<h3>Overall assessment status</h3>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr><th>Fact</th><th>Value</th><th>Note</th></tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    if section.head_summaries:
        rows = "".join(
            "<tr>"
            + f'<td><a class="id-link" href="#{escape_html(item.anchor)}">'
            + f"{escape_html(item.title)}</a></td>"
            + f"<td>{escape_html(item.status_label)}</td>"
            + f"<td>{item.finding_count}</td>"
            + f"<td>{item.recommendation_count}</td>"
            + f"<td>{escape_html(item.confidence_label)}</td>"
            + f"<td>{escape_html(item.coverage)}</td>"
            + "</tr>"
            for item in section.head_summaries
        )
        parts.append(
            '<div class="eis-intel-group" data-group="assessment_heads">\n'
            + "<h3>Assessment heads assessed</h3>\n"
            + '<p class="muted">Status and counts from each assessment head. '
            + "Detailed findings remain in Assessment Results.</p>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Assessment head</th><th>Status</th><th>Findings</th>"
            + "<th>Recommendations</th><th>Confidence</th><th>Coverage</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    if section.observations:
        items = "".join(f"<li>{escape_html(item)}</li>" for item in section.observations)
        parts.append(
            '<div class="eis-intel-group" data-group="observations">\n'
            + "<h3>High-level engineering observations</h3>\n"
            + f'<ul class="plain">{items}</ul>\n'
            + "</div>"
        )

    if section.cross_head_facts:
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(fact.label)}</td>"
            + f"<td>{escape_html(fact.value)}</td>"
            + f"<td>{escape_html(fact.note) if fact.note else '—'}</td>"
            + "</tr>"
            for fact in section.cross_head_facts
        )
        parts.append(
            '<div class="eis-intel-group" data-group="cross_head">\n'
            + "<h3>Cross-head summary</h3>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr><th>Fact</th><th>Value</th><th>Note</th></tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    pa_priority = (
        "".join(
            f"<li>{escape_html(item.label)}: {item.count}</li>"
            for item in section.priority_by_priority
        )
        or "<li>None</li>"
    )
    pa_horizon = (
        "".join(
            f"<li>{escape_html(item.label)}: {item.count}</li>"
            for item in section.priority_by_horizon
        )
        or "<li>None</li>"
    )
    parts.append(
        '<div class="eis-intel-group" data-group="priority_actions">\n'
        "<h3>Priority Action summary</h3>\n"
        f"<p><strong>Total actions:</strong> {section.priority_action_total}. "
        'Full detail remains in <a class="id-link" href="#priority-actions">'
        "Priority Actions</a>.</p>\n"
        '<div class="split">\n'
        "<div><h4>By priority</h4>"
        f'<ul class="plain">{pa_priority}</ul></div>\n'
        "<div><h4>By horizon</h4>"
        f'<ul class="plain">{pa_horizon}</ul></div>\n'
        "</div>\n"
        "</div>"
    )

    not_assessed = _not_assessed_overview_table(section.head_summaries)
    if not_assessed:
        parts.append(not_assessed)

    parts.append(
        render_coverage_confidence_limitations(
            coverage_rows=section.coverage_rows,
            confidence=section.confidence,
            confidence_label=section.confidence_label,
            confidence_note=(
                "Weakest contributing Assessment-Head Confidence across assessed heads."
            ),
            limitations=_overview_limitations(section.limitations),
        )
    )

    return "\n".join(parts)


def _render_assessment_results(view: HtmlReportViewModel) -> str:
    heads = view.headline_outcomes or tuple(
        section for section in view.assessment_heads if section.role == "headline"
    )
    if not heads:
        body = (
            '<p class="muted">No assessment-head sections were available for this assessment.</p>'
        )
    else:
        by_head = {section.head: section for section in view.assessment_heads}
        cards = _render_outcome_status_cards(heads)
        detail = "\n".join(
            _render_headline_evidence_section(view, by_head.get(section.head, section), section)
            for section in heads
        )
        body = (
            '<h3 class="subsection">Current engineering health</h3>\n'
            '<p class="small muted">Assessment Results. Exactly four outcomes. '
            "These packs are not additional headline outcomes.</p>\n"
            f"{cards}\n"
            '<details class="outcome-evidence">\n'
            "<summary>Outcome evidence</summary>\n"
            '<p class="small muted">Detailed Intelligence-pack evidence for the four '
            "outcomes. These packs are not additional headline outcomes.</p>\n"
            f"{detail}\n"
            "</details>"
        )
    return _section(
        "Current outcomes",
        body,
        section_id=ASSESSMENT_RESULTS_ANCHOR,
        eyebrow="02 · Engineering health",
        note=(
            "Exactly four outcomes. Display labels are presentation mappings, "
            + "not a composite score."
        ),
        css_class="section assessment-results",
    )


def _outcome_tag(label: str) -> tuple[str, str]:
    text = label.lower()
    if "insufficient" in text or "not applicable" in text or "unknown" in text:
        return "neutral", " unknown"
    if "no material" in text:
        return "good", ""
    if "needs attention" in text:
        return "warn", ""
    return "neutral", ""


def _render_outcome_status_cards(heads: Sequence[AssessmentHeadSectionView]) -> str:
    cards = []
    for section in heads:
        label = section.display_label or section.status_label
        tone, modifier = _outcome_tag(label)
        cards.append(
            f'<article class="card health-card{modifier}">'
            f"<h3>{escape_html(section.title)}</h3>"
            f'<p class="card-status"><span class="tag {tone}">{escape_html(label)}</span></p>'
            f'<p class="card-count">Findings: {section.findings_count}</p>'
            '<p class="card-evidence">'
            f'<a class="evidence-link" href="#{escape_html(section.anchor)}">'
            "Open evidence</a></p>"
            "</article>"
        )
    return '<div class="grid four outcome-grid">' + "".join(cards) + "</div>"


def _render_headline_evidence_section(
    view: HtmlReportViewModel,
    source: AssessmentHeadSectionView,
    headline: AssessmentHeadSectionView,
) -> str:
    """Render Intelligence-pack evidence as subordinate detail, not a peer outcome."""

    try:
        head = AssessmentHead(source.head)
        evidence_title = f"{engineering_health_outcome_title(head)} evidence"
        pack_name = assessment_head_title(head)
    except ValueError:
        evidence_title = f"{headline.title} evidence"
        pack_name = source.title
    rendered = _render_assessment_head_section(
        view,
        source.model_copy(
            update={
                "title": evidence_title,
                "display_label": headline.display_label or source.display_label,
                "status_label": headline.status_label or source.status_label,
            }
        ),
    )
    caption = (
        f'<p class="muted">{escape_html(pack_name)} pack — supporting evidence, '
        "not a headline Engineering Health outcome.</p>\n"
    )
    return caption + rendered


def _verdict_sentences(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    for index, char in enumerate(text):
        if char != ".":
            continue
        if index + 1 < len(text) and text[index + 1] not in {" ", "\n"}:
            continue
        sentence = text[start : index + 1].strip()
        if sentence:
            parts.append(sentence)
        start = index + 1
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts or [text.strip()]


def _present_supplied_verdict(text: str) -> str:
    """Lay out a supplied verdict without rewriting its conclusion.

    The heading is the existing primary-risk phrase when that phrase is present.
    Severity, counts, and the calibrated next step stay separate. The complete
    original text remains in a disclosure.
    """

    original = text.strip()
    if not original:
        return '<p class="muted">No attention summary was attached to this baseline.</p>'
    sentences = _verdict_sentences(original)
    heading = ""
    marker = "Primary engineering risk: "
    for sentence in sentences:
        if marker not in sentence:
            continue
        phrase = sentence.split(marker, 1)[1]
        for separator in (",", "."):
            if separator in phrase:
                phrase = phrase.split(separator, 1)[0]
        heading = phrase.strip()
        break
    if not heading:
        heading = sentences[0].rstrip(".")
    next_markers = (
        "Address the highest risk",
        "Next:",
        "Next ",
        "Recommendation:",
        "Future-horizon",
        "Have the team",
    )
    support: list[str] = []
    following: list[str] = []
    for sentence in sentences:
        if any(sentence.startswith(marker_text) for marker_text in next_markers):
            following.append(sentence)
        else:
            support.append(sentence)
    support_html = "".join(f"<p>{escape_html(part)}</p>" for part in support)
    next_html = f"<p>{escape_html(' '.join(following))}</p>" if following else ""
    return (
        '<div class="eyebrow">Current-code baseline</div>'
        f"<h3>{escape_html(heading)}</h3>"
        f"{support_html}"
        f"{next_html}"
        '<details class="verdict-original">'
        "<summary>Complete supplied verdict</summary>"
        f"<p>{escape_html(original)}</p>"
        "</details>"
    )


def _render_attention_first(view: HtmlReportViewModel) -> str:
    """One attention narrative.

    ``id="executive-summary"`` stays nested on that narrative so older links
    resolve. It is not a second section and it does not repeat the retired
    "Should I care?" copy.
    """

    summary = view.attention_summary
    verdict = (view.leadership_verdict or "").strip()
    if summary is None and not verdict:
        return '<p class="muted">No attention summary was attached to this baseline.</p>'
    headline = verdict or (summary.headline if summary is not None else "")
    return _render_attention_board(summary, view, headline=headline)


def _render_attention_board(
    summary: AttentionSummaryView | None,
    view: HtmlReportViewModel,
    *,
    headline: str,
) -> str:
    action_lookup = {item.recommendation_id: item for item in view.priority_actions}
    action_items = []
    action_ids = summary.top_priority_action_ids if summary is not None else ()
    for action_id in action_ids:
        action = action_lookup.get(action_id)
        href = escape_html(priority_action_anchor(action_id))
        title = escape_html(action.title if action is not None else action_id)
        action_items.append(f'<li><a href="#{href}">{title}</a></li>')
    if not action_items:
        action_items.append("<li>No recommendation-backed Priority Actions were supplied.</li>")
    needing = (
        "".join(
            f'<li><a href="#{escape_html(item.anchor)}">{escape_html(item.title)}</a>'
            f" — {escape_html(item.display_label)}</li>"
            for item in (summary.outcomes_needing_attention if summary is not None else ())
        )
        or "<li>No outcome currently mapped to Needs attention.</li>"
    )
    uncertain = (
        "".join(
            f'<li><a href="#{escape_html(item.anchor)}">{escape_html(item.title)}</a>'
            f" — {escape_html(item.display_label)}</li>"
            for item in (summary.unavailable_evidence if summary is not None else ())
        )
        or "<li>No headline reported unavailable required evidence.</li>"
    )
    comparison = (
        summary.comparison_state
        if summary is not None
        else "No comparison or trend was requested for this baseline assessment."
    )
    return (
        '<div class="attention-board" id="executive-summary">\n'
        '<article class="attention-main card">'
        f"{_present_supplied_verdict(headline)}"
        "</article>\n"
        "</div>\n"
        '<div class="attention-row">\n'
        '<article class="card"><h3>Where attention is concentrated</h3>'
        f"<ul>{needing}</ul></article>\n"
        '<article class="card"><h3>What remains uncertain</h3>'
        f"<ul>{uncertain}</ul></article>\n"
        '<article class="card"><h3>Grounded Priority Actions</h3>'
        f"<ul>{''.join(action_items)}</ul></article>\n"
        "</div>\n"
        '<article class="card" id="baseline-state">'
        "<h3>No comparison requested</h3>"
        f"<p>{escape_html(comparison)}</p>"
        '<p class="small muted">This is the starting baseline. Outcome movement, '
        "new or resolved findings, and change impact are not available.</p>"
        "</article>"
    )


def _render_architecture_map(section: ArchitectureMapView | None) -> str:
    if section is None or not section.available:
        reason = (
            section.unavailable_reason
            if section is not None
            else "Canonical repository graph is unavailable."
        )
        return (
            f'<p class="muted">{escape_html(reason or "")}</p>'
            "<p>Architecture Map is not inferred when the graph is absent.</p>"
        )
    displayed_nodes = [item for item in section.nodes if item.displayed]
    displayed_edges = [item for item in section.edges if item.displayed]
    limit_note = ""
    if section.display_limit_disclosed:
        limit_note = (
            f"<p>Showing {section.displayed_node_count} of "
            f"{section.canonical_node_count} canonical nodes "
            f"(visual limit {section.display_node_limit}). "
            "Downloadable graph JSON is unchanged.</p>"
        )
    grouping_note = ""
    if section.grouping != "module":
        grouping_note = (
            '<p class="notice">Component grouping is unavailable. '
            "The map shows canonical file nodes only. "
            "No component boundary or dependency was inferred.</p>"
        )
    counts = (
        f"<p>Canonical nodes: {section.canonical_node_count}. "
        f"Canonical edges: {section.canonical_edge_count}. "
        f"Grouping: {escape_html(section.grouping)}. "
        f"Artifact: <code>{escape_html(section.downloadable_artifact)}</code></p>"
        f"{grouping_note}"
    )
    svg = _architecture_map_svg(displayed_nodes, displayed_edges)
    legend = (
        '<p class="chart-legend"><span><b></b>File node</span>'
        "<span>Line: supplied canonical edge</span></p>"
        '<p class="chart-note">Purpose: see which displayed files connect. '
        "Paths and evidence are in the drill-down. "
        f"Scope: {section.displayed_node_count} displayed of "
        f"{section.canonical_node_count} canonical nodes. "
        "No component boundary is drawn when grouping is file-level.</p>"
    )
    if "<svg" not in svg:
        legend = ""
    rows = []
    for item in displayed_nodes:
        finding_links = (
            " ".join(
                f'<a href="#{escape_html(finding_anchor(fid))}">{escape_html(fid)}</a>'
                for fid in item.finding_ids
            )
            or "—"
        )
        evidence_links = _render_evidence_references(item.evidence_ids) or "—"
        hotspot_links = (
            " ".join(
                f'<a href="#hotspot-{escape_html(rid)}">{escape_html(rid)}</a>'
                for rid in item.hotspot_record_ids
            )
            or "—"
        )
        rows.append(
            "<tr>"
            f'<td id="architecture-node-{escape_html(item.node_id)}">'
            f"<code>{escape_html(item.node_id)}</code></td>"
            f"<td>{escape_html(item.node_type)}</td>"
            f"<td>{escape_html(item.label)}</td>"
            f"<td>{escape_html(item.path or '—')}</td>"
            f"<td>{escape_html(item.parent_id or '—')}</td>"
            f"<td>{hotspot_links}</td>"
            f"<td>{finding_links}</td>"
            f"<td>{evidence_links}</td>"
            "</tr>"
        )
    table = (
        "<table><thead><tr><th>node</th><th>type</th><th>label</th><th>path</th>"
        "<th>canonical parent</th><th>hotspots</th><th>findings</th><th>evidence</th>"
        "</tr></thead><tbody>"
        + ("".join(rows) or "<tr><td colspan='8'>No displayed nodes.</td></tr>")
        + "</tbody></table>"
    )
    linked = [
        item for item in displayed_nodes if item.finding_ids or item.hotspot_record_ids
    ]
    preview_rows = "".join(
        "<tr>"
        f"<td>{escape_html(item.path or item.label)}</td>"
        f"<td>{len(item.finding_ids)}</td>"
        f"<td>{len(item.hotspot_record_ids)}</td>"
        f'<td><a href="#architecture-node-{escape_html(item.node_id)}">Drill-down</a></td>'
        "</tr>"
        for item in linked[:12]
    )
    preview = ""
    if preview_rows:
        preview = (
            "<h3>Files with findings or hotspots</h3>"
            "<p class='chart-note'>Shown in sealed graph order. This is not a new rank. "
            f"{len(linked)} displayed nodes have a finding or hotspot.</p>"
            "<table><thead><tr><th>Path</th><th>Findings</th><th>Hotspots</th>"
            "<th>Record</th></tr></thead><tbody>"
            f"{preview_rows}</tbody></table>"
        )
    return (
        f"{counts}{limit_note}{legend}{svg}{preview}"
        '<details class="outcome-evidence"><summary>File and node drill-down</summary>'
        f"{table}</details>"
    )


def _architecture_map_svg(
    nodes: Sequence[Any],
    edges: Sequence[Any],
) -> str:
    if not nodes:
        return '<p class="muted">No canonical nodes are in the displayed set.</p>'
    width, height, pad = 640.0, 360.0, 48.0
    xs = [item.x for item in nodes]
    ys = [item.y for item in nodes]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1.0)

    def _pt(x: float, y: float) -> tuple[float, float]:
        px = pad + ((x - min_x) / span_x) * (width - 2 * pad)
        py = pad + ((y - min_y) / span_y) * (height - 2 * pad)
        return (round(px, 2), round(py, 2))

    points = {item.node_id: _pt(item.x, item.y) for item in nodes}
    lines = []
    for edge in edges:
        start = points.get(edge.source_node_id)
        end = points.get(edge.target_node_id)
        if start is None or end is None:
            continue
        lines.append(
            f'<line x1="{start[0]}" y1="{start[1]}" x2="{end[0]}" y2="{end[1]}" '
            f'data-edge-id="{escape_html(edge.edge_id)}" '
            f'data-relationship="{escape_html(edge.relationship_type)}" />'
        )
    if len(nodes) > 16:
        return (
            '<p class="chart-note">A plotted map is omitted for '
            f"{len(nodes)} file nodes. Identical circles would not name a path. "
            "The drill-down table lists every displayed node, its path, and its evidence.</p>"
        )
    show_labels = len(nodes) <= 12
    marks = []
    for item in nodes:
        x, y = points[item.node_id]
        href = escape_html(f"#architecture-node-{item.node_id}")
        label = ""
        if show_labels:
            label = f'<text x="{x}" y="{y + 24}">{escape_html(item.label[:28])}</text>'
        marks.append(
            f'<a href="{href}">'
            f'<circle cx="{x}" cy="{y}" r="10" data-node-id="{escape_html(item.node_id)}" />'
            f"{label}"
            "</a>"
        )
    label_note = ""
    if not show_labels:
        label_note = (
            f'<p class="visual-limit">Node labels are omitted for {len(nodes)} displayed '
            "nodes. Names stay in the file and node drill-down. "
            "This does not remove canonical nodes.</p>"
        )
    return (
        f"{label_note}"
        '<svg class="architecture-map" viewBox="0 0 640 360" role="img" '
        'aria-label="Architecture Map from canonical repository graph">'
        '<text class="plot-axis" x="24" y="22">Canonical files</text>'
        f"{''.join(lines)}{''.join(marks)}</svg>"
    )


def _render_engineering_hotspots(section: HotspotSectionView | None) -> str:
    if section is None or not section.available:
        reason = (
            section.unavailable_reason
            if section is not None
            else "Engineering Hotspots unavailable: m22_records_not_attached."
        )
        return f'<p class="muted">{escape_html(reason or "")} Ranking is not calculated here.</p>'
    shown = section.items[:_MAIN_HOTSPOT_CARD_LIMIT]
    hidden = len(section.items) - len(shown)
    limit_note = (
        f'<p class="visual-limit notice">Showing {len(shown)} of {len(section.items)} '
        "sealed hotspot records in sealed list order. "
        "Remaining records stay in canonical JSON. "
        "This report does not calculate a new rank.</p>"
        if hidden
        else (
            f'<p class="visual-limit">Showing all {len(section.items)} '
            "sealed hotspot records. Marker size does not add a rank.</p>"
        )
    )
    blocks = []
    for item in shown:
        contributors = "".join(
            "<li>"
            f"{escape_html(part.name)} role={escape_html(part.role)} "
            f"value={escape_html(part.value or '—')}"
            "</li>"
            for part in item.contributors
        )
        finding_links = (
            " ".join(
                f'<a href="#{escape_html(finding_anchor(fid))}">{escape_html(fid)}</a>'
                for fid in item.active_finding_ids
            )
            or "—"
        )
        evidence_links = _render_evidence_references(item.evidence_ids) or "—"
        complexity = next(
            (part.value for part in item.contributors if part.name == "complexity"), "—"
        )
        churn = next((part.value for part in item.contributors if part.name == "churn"), "—")
        blocks.append(
            f'<article id="hotspot-{escape_html(item.record_id)}" class="card hotspot-card">'
            f"<h3>{escape_html(item.subject_id)}</h3>"
            f"<p>list_kind: {escape_html(item.list_kind)}</p>"
            f"<p>ranking_value: {escape_html(item.ranking_value or '—')}</p>"
            f"<p>complexity: {escape_html(complexity or '—')}</p>"
            f"<p>churn: {escape_html(churn or '—')}</p>"
            f"<p>history_window: {escape_html(item.history_window or '—')}</p>"
            f"<p>priority_explanation: {escape_html(item.priority_explanation or '—')}</p>"
            f"<ul>{contributors}</ul>"
            f"<p>findings: {finding_links}</p>"
            f"<p>evidence: {evidence_links}</p>"
            "</article>"
        )
    scatter = f'<div class="chart-panel">{_hotspot_scatter(shown)}</div>'
    rows = []
    for index, item in enumerate(shown, start=1):
        complexity = next(
            (part.value for part in item.contributors if part.name == "complexity"), "—"
        )
        churn = next((part.value for part in item.contributors if part.name == "churn"), "—")
        identifier = f"H{index}"
        rows.append(
            "<tr>"
            f'<td><a href="#hotspot-{escape_html(item.record_id)}">'
            f"{escape_html(identifier)}</a></td>"
            f'<td><a href="#hotspot-{escape_html(item.record_id)}">'
            f"{escape_html(item.subject_id)}</a></td>"
            f"<td>{escape_html(complexity or '—')}</td>"
            f"<td>{escape_html(churn or '—')}</td>"
            f"<td>{escape_html(item.ranking_value or '—')}</td>"
            "</tr>"
        )
    table = (
        "<table>"
        "<thead><tr>"
        '<th scope="col">Identifier</th><th scope="col">Path</th>'
        '<th scope="col">Complexity</th><th scope="col">Churn</th>'
        '<th scope="col">Supplied ranking value</th></tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table>"
    )
    caption = (
        '<p id="hotspot-table-caption" class="table-caption">'
        "Displayed hotspots, sealed list order. "
        "H1, H2, and the following labels are display identifiers, not ranks. "
        "Complexity and churn are supplied contributor values. "
        "Ranking value is copied and is not a new rank.</p>"
    )
    scroller = (
        '<div class="table-wrap" tabindex="0" role="region" '
        'aria-labelledby="hotspot-table-caption">'
        f"{table}</div>"
    )
    return (
        limit_note
        + '<p class="chart-note">Purpose: see where supplied complexity and churn '
        "occur together. Marker size is constant. "
        "Scope: sealed M22 records in this assessment.</p>"
        + '<div class="hotspot-layout">'
        + scatter
        + '<div class="hotspot-table">'
        + caption
        + scroller
        + "</div></div>"
        + '<details class="outcome-evidence"><summary>Hotspot contributors and evidence</summary>'
        + '<div class="grid">'
        + "".join(blocks)
        + "</div></details>"
    )


def _axis_tick(value: float) -> str:
    rounded = round(value)
    if abs(value - rounded) < 0.05:
        return str(int(rounded))
    return f"{value:.1f}"


def _hotspot_scatter(items: Sequence[Any]) -> str:
    points = []
    for index, item in enumerate(items, start=1):
        complexity = next(
            (part.value for part in item.contributors if part.name == "complexity"), None
        )
        churn = next((part.value for part in item.contributors if part.name == "churn"), None)
        if complexity is None or churn is None:
            continue
        try:
            x = float(complexity)
            y = float(churn)
        except (TypeError, ValueError):
            continue
        points.append((index, item, x, y))
    if not points:
        return (
            "<p>A plotted chart is omitted because the displayed records do not "
            "include numeric complexity and churn. The table lists the supplied values.</p>"
        )
    max_x = max(point[2] for point in points) or 1.0
    max_y = max(point[3] for point in points) or 1.0
    left, right, top, bottom = 78.0, 560.0, 28.0, 286.0
    marks = []
    for index, item, x, y in points:
        identifier = f"H{index}"
        px = left + (x / max_x) * (right - left)
        py = bottom - (y / max_y) * (bottom - top)
        path = escape_html(item.subject_id)
        marks.append(
            f'<a href="#hotspot-{escape_html(item.record_id)}">'
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="6">'
            f"<title>Identifier {identifier}, not a rank. {path}</title>"
            "</circle>"
            f'<text class="plot-id" x="{px + 8:.1f}" y="{py - 8:.1f}">'
            f"{identifier}</text></a>"
        )
    ticks = []
    for fraction in (0.0, 0.5, 1.0):
        x_value = max_x * fraction
        y_value = max_y * fraction
        tx = left + fraction * (right - left)
        ty = bottom - fraction * (bottom - top)
        ticks.append(
            f'<text class="plot-axis" x="{tx:.1f}" y="304" text-anchor="middle">'
            f"{_axis_tick(x_value)}</text>"
            f'<text class="plot-axis" x="68" y="{ty + 4:.1f}" text-anchor="end">'
            f"{_axis_tick(y_value)}</text>"
        )
    return (
        "<h3>Where complexity meets frequent change</h3>"
        '<svg class="hotspot-scatter" viewBox="0 0 600 340" role="img" '
        'aria-label="Hotspot complexity and churn from sealed M22 records. '
        'H labels are identifiers, not ranks.">'
        '<line class="plot-axis-line" x1="78" y1="286" x2="560" y2="286" />'
        '<line class="plot-axis-line" x1="78" y1="28" x2="78" y2="286" />'
        '<text class="plot-axis" x="319" y="328" text-anchor="middle">'
        "Complexity (supplied)</text>"
        '<text class="plot-axis" x="16" y="157" text-anchor="middle" '
        'transform="rotate(-90 16 157)">Churn (supplied)</text>'
        f"{''.join(ticks)}{''.join(marks)}</svg>"
        '<p class="chart-legend"><span><b></b>One sealed record</span></p>'
        "<p>Marker positions use supplied complexity and churn only. "
        "Size is constant and does not add a hidden rank. "
        "H1, H2, and the following labels are display identifiers, not ranks. "
        "Each identifier links to the same path in the table. "
        "Contributor detail stays in the disclosure.</p>"
    )


def _render_ownership_concentration(section: OwnershipSectionView | None) -> str:
    if section is None or not section.available:
        reason = (
            section.unavailable_reason
            if section is not None
            else "Ownership concentration unavailable: records were not attached."
        )
        return f'<p class="muted">{escape_html(reason or "")}</p>'
    shown = section.items[:_MAIN_OWNERSHIP_ROW_LIMIT]
    hidden = len(section.items) - len(shown)
    note = ""
    if hidden:
        note = (
            f'<p class="visual-limit notice">Showing {len(shown)} of {len(section.items)} '
            "ownership records in sealed list order. "
            "Remaining records stay in canonical JSON. Ratios are not recalculated.</p>"
        )
    rows = []
    for item in shown:
        evidence = _render_evidence_references(item.evidence_ids) or "—"
        rows.append(
            "<tr>"
            f"<td>{escape_html(item.scope)}</td>"
            f"<td>{escape_html(item.subject_id)}</td>"
            f"<td>{escape_html('—' if item.numerator is None else str(item.numerator))}</td>"
            f"<td>{escape_html('—' if item.denominator is None else str(item.denominator))}</td>"
            f"<td>{escape_html(item.serialized_ratio or '—')}</td>"
            f"<td>{escape_html(item.history_profile_id or '—')}</td>"
            f"<td>{escape_html(item.status or '—')}</td>"
            f"<td>{escape_html(item.notes or '—')}</td>"
            f"<td>{evidence}</td>"
            "</tr>"
        )
    return (
        note + "<table><thead><tr><th>scope</th><th>subject</th><th>numerator</th>"
        "<th>denominator</th><th>ratio</th><th>history</th><th>status</th>"
        "<th>limitations</th><th>evidence</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _render_temporal_cochange(section: CochangeSectionView | None) -> str:
    if section is None or not section.available:
        reason = (
            section.unavailable_reason
            if section is not None
            else (
                "Temporal co-change unavailable. "
                "No pair, support, or union denominator was supplied."
            )
        )
        return f'<p class="muted">{escape_html(reason or "")}</p>'
    supported = [item for item in section.items if item.supported_relation is True]
    unsupported = [item for item in section.items if item.supported_relation is False]
    unspecified = [item for item in section.items if item.supported_relation is None]
    shown_supported = supported[:_MAIN_COCHANGE_SUPPORTED_LIMIT]
    shown_unsupported = unsupported[:_MAIN_COCHANGE_UNSUPPORTED_LIMIT]
    shown_unspecified = unspecified[:_MAIN_COCHANGE_UNSUPPORTED_LIMIT]

    def _pair_card(item: Any, relation: str) -> str:
        support = "—" if item.support is None else str(item.support)
        union = "—" if item.union is None else str(item.union)
        return (
            '<article class="card pair-card">'
            f"<h3>{escape_html(item.left)} + {escape_html(item.right)}</h3>"
            f'<p class="stat">{escape_html(support)} / {escape_html(union)}</p>'
            "<p>Support / union denominator, as supplied.</p>"
            f"<p>Supplied Jaccard: {escape_html(item.jaccard or '—')}</p>"
            f"<p>{escape_html(relation)}</p>"
            f'<p class="small muted">Scope: {escape_html(item.scope)}. '
            f"Incomplete window: {escape_html(str(item.qualified_incomplete_window))}."
            f" {escape_html(item.unavailable_reason or '')}</p>"
            "</article>"
        )

    hidden = (
        len(section.items) - len(shown_supported) - len(shown_unsupported) - len(shown_unspecified)
    )
    note = (
        f'<p class="visual-limit notice">Showing {len(shown_supported)} supported, '
        f"{len(shown_unsupported)} unsupported, and {len(shown_unspecified)} "
        f"unspecified pairs from {len(section.items)} sealed pairs. "
        f"{hidden} remaining pairs stay in canonical JSON. "
        "Supported and unsupported pairs are separate. "
        "Jaccard is copied, not calculated here. "
        "Order within each group follows the sealed record order.</p>"
    )
    supported_html = (
        "".join(_pair_card(item, "Supported relation") for item in shown_supported)
        or '<p class="muted">No supported co-change pair was supplied.</p>'
    )
    unsupported_html = "".join(
        _pair_card(item, "Not a supported relation") for item in shown_unsupported
    )
    unspecified_html = "".join(
        _pair_card(item, "Support not supplied") for item in shown_unspecified
    )
    return (
        note
        + "<h3>Supported co-change</h3>"
        + f'<div class="pair-grid">{supported_html}</div>'
        + "<h3>Unsupported co-change</h3>"
        + (
            f'<div class="pair-grid">{unsupported_html}</div>'
            if unsupported_html
            else '<p class="muted">No unsupported co-change pair is in the displayed set.</p>'
        )
        + (
            f'<h3>Support not supplied</h3><div class="pair-grid">{unspecified_html}</div>'
            if unspecified_html
            else ""
        )
    )


def _render_coverage_trust(view: HtmlReportViewModel) -> str:
    section = view.coverage_trust
    if section is None:
        return '<p class="muted">Coverage and trust records were not attached.</p>'
    rows = "".join(
        f"<tr><td>{escape_html(item.label)}</td><td>{escape_html(item.value)}</td></tr>"
        for item in section.rows
    )
    cap_rows = []
    for item in section.capability_rows:
        cap_rows.append(
            "<tr>"
            f"<td>{escape_html(str(item.get('capability_id') or '—'))}</td>"
            f"<td>{escape_html(str(item.get('scope') or '—'))}</td>"
            f"<td>{escape_html(str(item.get('execution_state') or '—'))}</td>"
            f"<td>{escape_html(str(item.get('coverage_ratio') or '—'))}</td>"
            f"<td>{escape_html(str(item.get('coverage_reason') or '—'))}</td>"
            f"<td>{escape_html(str(item.get('freshness') or '—'))}</td>"
            f"<td>{escape_html(str(item.get('freshness_reason') or '—'))}</td>"
            "</tr>"
        )
    limitations = "".join(f"<li>{escape_html(item)}</li>" for item in section.material_limitations)
    if not limitations:
        limitations = "<li>No additional material limitations were sealed for this run.</li>"
    identity = ""
    if section.identity_note:
        identity = f'<p class="section-note">{escape_html(section.identity_note)}</p>'
    return (
        f"<p>{escape_html(section.comparison_state)}</p>"
        "<table><thead><tr><th>trust field</th><th>value</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        f"{identity}"
        "<h3>Capability coverage</h3>"
        "<table><thead><tr><th>capability</th><th>scope</th><th>execution</th>"
        "<th>coverage</th><th>reason</th><th>freshness</th><th>freshness reason</th>"
        "</tr></thead><tbody>"
        + ("".join(cap_rows) or "<tr><td colspan='7'>No capability coverage rows.</td></tr>")
        + "</tbody></table>"
        "<h3>Material limitations</h3>"
        f"<ul>{limitations}</ul>"
    )


def _render_repository_facts(view: HtmlReportViewModel) -> str:
    """Existing inventory metrics, kept out of the attention-first hero."""

    summary = view.summary
    return (
        '<section class="subsection" id="repository-facts">\n'
        "<h3>Repository facts</h3>\n"
        '<p class="small muted">Supporting inventory. Not a composite score.</p>\n'
        '<div class="grid three">\n'
        + _kpi(
            "Highest Finding Severity",
            summary.highest_finding_severity,
            "",
            _severity_tone(summary.highest_finding_severity),
        )
        + _kpi("Cloud Enablement Signals", _cloud_primary(view), _cloud_status(view), "cloud")
        + _kpi("CI/CD", _cicd_value(view), "", "cicd")
        + "</div>\n"
        + "</section>"
    )


def _render_supporting_and_appendix(view: HtmlReportViewModel) -> str:
    parts: list[str] = [_render_repository_facts(view)]
    parts.append(
        _section(
            assessment_head_title(AssessmentHead.ENGINEERING_INTELLIGENCE),
            _render_engineering_intelligence_summary(view),
            section_id=assessment_head_anchor(AssessmentHead.ENGINEERING_INTELLIGENCE),
            note="Supporting synthesis. Not a fifth headline outcome.",
        )
    )
    parts.append(
        _section(
            "Engineering Risks",
            _render_engineering_risks(view),
            section_id="engineering-risks",
            note="Findings without recommendation-backed Priority Actions.",
        )
    )
    supporting = view.supporting_heads or tuple(
        item for item in view.assessment_heads if item.role == "supporting"
    )
    appendix = view.appendix_heads or tuple(
        item for item in view.assessment_heads if item.role == "appendix"
    )
    for section in (*supporting, *appendix):
        parts.append(_render_assessment_head_section(view, section))
    return "\n".join(parts)


def _evidence_state_label(value: str) -> str:
    key = str(value or "").strip().lower()
    return {
        "unavailable": "Evidence unavailable",
        "none_reported": "No findings reported",
        "available": "Evidence available",
        "legacy_or_inline": "Legacy or inline evidence",
    }.get(key, key.replace("_", " ").title() or "Evidence unavailable")


def _render_assessment_head_status_meta(section: AssessmentHeadSectionView) -> str:
    """Compact status meta — Coverage/Confidence/Limitations render at section end."""

    return (
        '<div class="assessment-head-coverage">\n'
        '<dl class="meta">\n'
        f"<div><dt>Status</dt><dd>{escape_html(section.status_label)}</dd></div>\n"
        f"<div><dt>Findings</dt><dd>{section.findings_count}</dd></div>\n"
        f"<div><dt>Recommendations</dt><dd>{section.recommendations_count}</dd></div>\n"
        f"<div><dt>Evidence</dt><dd>{escape_html(_evidence_state_label(section.evidence_state))}"
        "</dd></div>\n"
        "</dl>\n"
        "</div>"
    )


def _head_provides_canonical_ccl(
    view: HtmlReportViewModel,
    section: AssessmentHeadSectionView,
) -> bool:
    """True when the pack body already ends with the shared CCL block.

    When canonical AssessmentCoverage is present on the head, the head-level CCL
    is the authority and pack-local CCL is stripped.
    """

    if getattr(section, "assessment_coverage", None):
        return False
    try:
        head = AssessmentHead(section.head)
    except ValueError:
        return False
    if head is AssessmentHead.TECHNOLOGY_INVENTORY:
        return view.technology_inventory is not None
    if head is AssessmentHead.ARCHITECTURE_INTELLIGENCE:
        return view.architecture_intelligence is not None
    if head is AssessmentHead.TECHNICAL_DEBT_INTELLIGENCE:
        return view.technical_debt_intelligence is not None
    if head is AssessmentHead.DEPENDENCY_INTELLIGENCE:
        return view.dependency_intelligence is not None
    if head is AssessmentHead.SECURITY_INTELLIGENCE:
        return view.security_intelligence is not None
    if head is AssessmentHead.CLOUD_READINESS:
        return view.cloud_intelligence is not None
    if head is AssessmentHead.AI_READINESS:
        return view.ai_readiness_intelligence is not None
    if head is AssessmentHead.MODERNIZATION_ASSESSMENT:
        return view.modernization_intelligence is not None
    return False


def _strip_trailing_ccl(html: str) -> str:
    """Remove a trailing Coverage/Confidence/Limitations block from pack HTML."""

    marker = 'data-canonical="coverage-confidence-limitations"'
    idx = html.rfind(marker)
    if idx < 0:
        return html
    start = html.rfind("<div", 0, idx)
    if start < 0:
        return html
    return html[:start].rstrip()


def _render_assessment_head_coverage(section: AssessmentHeadSectionView) -> str:
    """Backward-compatible alias — status meta only (CCL is canonical at end)."""

    return _render_assessment_head_status_meta(section)


def _render_head_pack_content(
    view: HtmlReportViewModel,
    section: AssessmentHeadSectionView,
) -> str:
    """Inner pack HTML only — no outer section ids (head already has the TOC id)."""

    try:
        head = AssessmentHead(section.head)
    except ValueError:
        return ""

    if head is AssessmentHead.TECHNOLOGY_INVENTORY:
        pack = _render_technology(view)
        if section.assessment_coverage:
            pack = _strip_trailing_ccl(pack)
        return f'<div class="assessment-head-pack">\n{pack}\n</div>'

    pack_body = ""
    if head is AssessmentHead.ARCHITECTURE_INTELLIGENCE:
        if view.architecture_intelligence is not None:
            pack_body = _render_architecture_intelligence(
                view.architecture_intelligence,
                health_label=section.display_label or None,
                execution_label=view.architecture_intelligence.status_label,
            )
        elif view.architecture_report is not None:
            pack_body = _render_architecture(view.architecture_report)
    elif head is AssessmentHead.TECHNICAL_DEBT_INTELLIGENCE:
        if view.technical_debt_intelligence is not None:
            pack_body = _render_technical_debt_intelligence(view.technical_debt_intelligence)
        elif view.technical_debt_report is not None:
            pack_body = _render_technical_debt(view.technical_debt_report)
    elif head is AssessmentHead.DEPENDENCY_INTELLIGENCE:
        if view.dependency_intelligence is not None:
            pack_body = _render_dependency_intelligence(view.dependency_intelligence)
        elif view.dependency_report is not None:
            pack_body = _render_dependency(view.dependency_report)
    elif head is AssessmentHead.SECURITY_INTELLIGENCE:
        if view.security_intelligence is not None:
            pack_body = _render_security_intelligence(view.security_intelligence)
        elif view.security_report is not None:
            pack_body = _render_security(view.security_report)
    elif head is AssessmentHead.CLOUD_READINESS:
        if view.cloud_intelligence is not None:
            pack_body = _render_cloud_intelligence(view.cloud_intelligence)
        elif view.cloud_report is not None:
            pack_body = _render_cloud(view.cloud_report)
    elif head is AssessmentHead.AI_READINESS:
        if view.ai_readiness_intelligence is not None:
            pack_body = _render_ai_readiness_intelligence(view.ai_readiness_intelligence)
        elif view.ai_readiness_report is not None:
            pack_body = _render_ai_readiness(view.ai_readiness_report)
    elif head is AssessmentHead.MODERNIZATION_ASSESSMENT:
        if view.modernization_intelligence is not None:
            pack_body = _render_modernization_intelligence(view.modernization_intelligence)
        else:
            pack_body = _render_modernization_opportunities(view)

    if not pack_body:
        return ""
    if section.assessment_coverage:
        pack_body = _strip_trailing_ccl(pack_body)
    return f'<div class="assessment-head-pack">\n{pack_body}\n</div>'


def _render_head_compact_findings(section: AssessmentHeadSectionView) -> str:
    if not section.findings:
        return ""
    by_severity: dict[str, list[FindingView]] = {}
    for item in section.findings:
        by_severity.setdefault(item.severity.lower(), []).append(item)
    blocks: list[str] = []
    for severity in _SEVERITY_ORDER:
        group = by_severity.get(severity)
        if not group:
            continue
        cards = "\n".join(_render_finding_card(item, compact=True) for item in group)
        blocks.append(
            f'<div class="assessment-head-findings" data-severity="{escape_html(severity)}">\n'
            + f"<h4>{escape_html(severity.title())} findings</h4>\n"
            + f'<div class="card-stack">\n{cards}\n</div>\n'
            + "</div>"
        )
    # Any unexpected severities
    for severity, group in by_severity.items():
        if severity in _SEVERITY_ORDER:
            continue
        cards = "\n".join(_render_finding_card(item, compact=True) for item in group)
        blocks.append(
            '<div class="assessment-head-findings">\n'
            + f"<h4>{escape_html(severity.title())} findings</h4>\n"
            + f'<div class="card-stack">\n{cards}\n</div>\n'
            + "</div>"
        )
    return "\n".join(blocks)


def _render_head_compact_recommendations(section: AssessmentHeadSectionView) -> str:
    if not section.recommendations:
        return ""
    cards = "".join(
        "<article class='item-card recommendation'>\n"
        f'<header class="item-header">'
        f'<span class="badge priority-{escape_html(item.presentation_bucket or item.priority)}">'
        f"{escape_html(_roadmap_bucket(item))}</span> "
        f"<strong>{escape_html(item.title)}</strong>"
        f"</header>\n"
        f'<p class="trace-line">'
        f"{_recommendation_detail_markup(item.recommendation_id, 'View recommendation details')}"
        "</p>\n"
        "</article>\n"
        for item in section.recommendations
    )
    return (
        '<div class="assessment-head-findings">\n'
        "<h4>Recommendations</h4>\n"
        f'<div class="card-stack">\n{cards}</div>\n'
        "</div>"
    )


def _render_legacy_pack_section_alias(section: AssessmentHeadSectionView) -> str:
    """Hidden compatibility anchor for pre–Epic 3 Domain Intelligence section ids.

    Emitted only when pack content is present. Does not create a second visible
    section or a second canonical assessment-head id.
    """

    if not section.pack_content_available:
        return ""
    try:
        head = AssessmentHead(section.head)
    except ValueError:
        return ""
    alias = LEGACY_PACK_SECTION_ALIASES.get(head)
    if alias is None:
        return ""
    legacy_id, legacy_title = alias
    # Visually hidden but not aria-hidden: legacy deep links land here, so the
    # target must stay in the accessibility tree.
    return (
        f'<span id="{escape_html(legacy_id)}" class="section-anchor-only">'
        f"{escape_html(legacy_title)}</span>\n"
    )


def _render_assessment_head_section(
    view: HtmlReportViewModel,
    section: AssessmentHeadSectionView,
) -> str:
    parts: list[str] = [_render_legacy_pack_section_alias(section)]
    parts.append(_render_assessment_head_status_meta(section))
    if section.placeholder_message:
        parts.append(f'<p class="muted">{escape_html(section.placeholder_message)}</p>')
    pack = _render_head_pack_content(view, section)
    if pack:
        parts.append(pack)
    # Architecture / Technical Debt / Dependency / Security / Cloud / AI Readiness /
    # Modernization Assessment Intelligence packs already list findings/recommendations
    # with appendix links — skip duplicate compact stacks.
    skip_compact = False
    try:
        head = AssessmentHead(section.head)
        skip_compact = (
            (
                head is AssessmentHead.ARCHITECTURE_INTELLIGENCE
                and view.architecture_intelligence is not None
            )
            or (
                head is AssessmentHead.TECHNICAL_DEBT_INTELLIGENCE
                and view.technical_debt_intelligence is not None
            )
            or (
                head is AssessmentHead.DEPENDENCY_INTELLIGENCE
                and view.dependency_intelligence is not None
            )
            or (
                head is AssessmentHead.SECURITY_INTELLIGENCE
                and view.security_intelligence is not None
            )
            or (head is AssessmentHead.CLOUD_READINESS and view.cloud_intelligence is not None)
            or (head is AssessmentHead.AI_READINESS and view.ai_readiness_intelligence is not None)
            or (
                head is AssessmentHead.MODERNIZATION_ASSESSMENT
                and view.modernization_intelligence is not None
            )
        )
    except ValueError:
        skip_compact = False
    if not skip_compact:
        findings = _render_head_compact_findings(section)
        if findings:
            parts.append(findings)
        recommendations = _render_head_compact_recommendations(section)
        if recommendations:
            parts.append(recommendations)
    # Canonical Coverage → Confidence → Limitations at the end when the pack
    # did not already emit the shared block (Slice 3.11).
    if not _head_provides_canonical_ccl(view, section):
        parts.append(
            render_coverage_confidence_limitations(
                coverage_rows=coverage_rows_from_assessment_head(section),
                confidence=section.confidence,
                confidence_label=section.confidence_label,
                limitations=section.limitations,
                assessment_coverage=section.assessment_coverage,
            )
        )
    return _subsection(
        section.title,
        "\n".join(parts),
        section_id=section.anchor or assessment_head_anchor(section.head),
    )


def _render_executive_summary(view: HtmlReportViewModel) -> str:
    narrative = view.executive_summary
    if narrative is None:
        return (
            '<p class="muted">No executive summary was produced for this assessment.</p>\n'
            + f"{_render_technology(view)}"
        )
    return (
        '<div class="exec-narrative">\n'
        "<h3>Should I care?</h3>\n"
        f"<p>{escape_html(narrative.should_i_care)}</p>\n"
        "<h3>Why now?</h3>\n"
        f"<p>{escape_html(narrative.why_now)}</p>\n"
        "<h3>What should my team do next?</h3>\n"
        f"<p>{escape_html(narrative.what_next)}</p>\n"
        "</div>\n"
        "<h3>Technology Overview</h3>\n"
        f"{_render_technology(view)}"
    )


def _render_key_takeaways(view: HtmlReportViewModel) -> str:
    if not view.key_takeaways:
        return '<p class="muted">No key takeaways were available for this assessment.</p>'
    items = "".join(f"<li>{escape_html(item)}</li>\n" for item in view.key_takeaways)
    return f'<ul class="takeaways">\n{items}</ul>'


def _render_engineering_risks(view: HtmlReportViewModel) -> str:
    if not view.engineering_risks:
        return (
            '<p class="muted">No medium-or-higher engineering risks were highlighted '
            + "under the activated assessment checks. This does not certify that the "
            + "repository is free of risks.</p>"
        )
    blocks: list[str] = []
    for theme in view.engineering_risks:
        items = "".join(f"<li>{escape_html(item)}</li>" for item in theme.items)
        blocks.append(
            f'<div class="risk-theme"><h3>{escape_html(theme.theme)}</h3>'
            + f'<ul class="plain">{items}</ul></div>'
        )
    return "\n".join(blocks)


def _render_modernization_opportunities(view: HtmlReportViewModel) -> str:
    if not view.modernization_opportunities:
        return (
            '<p class="muted">No additional modernization opportunities were '
            + "identified beyond Priority Actions and capability assessments.</p>"
        )
    items = "".join(f"<li>{escape_html(item)}</li>" for item in view.modernization_opportunities)
    return f'<ul class="plain">{items}</ul>'


def _render_repository_overview(view: HtmlReportViewModel) -> str:
    return (
        f"{_render_assessment_scope(view)}\n"
        "<h3>Technology Overview</h3>\n"
        f"{_render_technology(view)}"
    )


def _render_assessment_summary_bundle(view: HtmlReportViewModel) -> str:
    verdict = (view.leadership_verdict or "").strip()
    verdict_html = (
        f'<p class="verdict-body">{escape_html(verdict)}</p>'
        if verdict
        else '<p class="muted">No leadership verdict was recorded for this run.</p>'
    )
    return (
        "<h3>Leadership Verdict</h3>\n"
        f"{verdict_html}\n"
        "<h3>Key Takeaways</h3>\n"
        f"{_render_key_takeaways(view)}\n"
        "<h3>Engineering Risks</h3>\n"
        f"{_render_engineering_risks(view)}"
    )


def _render_recommendations_bundle(view: HtmlReportViewModel) -> str:
    actions = view.priority_actions if view.priority_actions else view.recommendations
    return (
        "<h3>Priority Actions</h3>\n"
        f"{
            _render_roadmap(
                actions,
                total_actions=view.priority_actions_total or len(actions),
                as_priority_actions=True,
            )
        }\n"
        "<h3>Modernization Opportunities</h3>\n"
        f"{_render_modernization_opportunities(view)}"
    )


def _render_engineering_conclusion(view: HtmlReportViewModel) -> str:
    verdict = (view.leadership_verdict or "").strip()
    mode = escape_html(view.summary.assessment_mode_label)
    ai_status = escape_html(view.metadata.ai_status)
    findings = view.summary.total_findings
    recommendations = view.summary.total_recommendations
    body = (
        f"<p>This <strong>Engineering Assessment</strong> summarizes the current state "
        f"of <strong>{escape_html(view.summary.repository_name)}</strong> "
        f"({findings} findings, {recommendations} recommendations).</p>\n"
        f"<p>Assessment mode: <strong>{mode}</strong>. AI status: "
        f'<code class="trace-id">{ai_status}</code>. AI is optional and does not '
        "replace Engineering Health results.</p>\n"
    )
    if verdict:
        body += f'<p class="verdict-body">{escape_html(verdict)}</p>\n'
    body += (
        '<p class="muted">Next steps are in Recommendations / Priority Actions. '
        "Engine Implementation Sequence (when present) sequences those actions. "
        "CodeStrata Platform Strategic Roadmap is a separate Platform capability "
        "and is not part of this Community Engineering Assessment report.</p>"
    )
    return body


def _render_assessment_scope(view: HtmlReportViewModel) -> str:
    scope = view.assessment_scope
    if scope is None:
        return '<p class="muted">Assessment scope was not recorded for this run.</p>'
    assessed = (
        "".join(f"<li>{escape_html(label)}</li>" for label in scope.assessed_packs)
        or "<li>None</li>"
    )
    skipped_rows = (
        "".join(
            f"<tr><td>{escape_html(label)}</td><td>{escape_html(reason)}</td></tr>"
            for label, reason in scope.not_assessed_packs
        )
        or '<tr><td colspan="2">None</td></tr>'
    )
    return (
        "<p>Packs included in this assessment and packs intentionally not assessed.</p>\n"
        '<div class="split">\n'
        "<div>\n<h3>Assessed</h3>\n"
        f'<ul class="plain">{assessed}</ul>\n'
        "</div>\n"
        "<div>\n<h3>Not assessed</h3>\n"
        '<div class="table-wrap"><table>\n'
        "<thead><tr><th>Area</th><th>Reason</th></tr></thead>\n"
        f"<tbody>{skipped_rows}</tbody>\n</table></div>\n"
        "</div>\n"
        "</div>"
    )


def _render_engineering_modernization_assessment(view: HtmlReportViewModel) -> str:
    summary_text = escape_html(view.assessment_summary.summary_text)
    return (
        f'<p class="ema-lede">{summary_text}</p>\n'
        f"{_render_executive_cards(view)}\n"
        "<h3>Technology Overview</h3>\n"
        f"{_render_technology(view)}"
    )


def _trust_value(view: HtmlReportViewModel, label: str) -> str:
    section = view.coverage_trust
    if section is None:
        return ""
    for row in section.rows:
        if row.label == label:
            return row.value
    return ""


def _short_revision(value: str) -> str:
    text = value.strip()
    if len(text) >= 12 and all(char in "0123456789abcdef" for char in text.lower()):
        return text[:12]
    return text


def _render_hero(view: HtmlReportViewModel) -> str:
    summary = view.summary
    name = view.repository.name or summary.repository_name
    branch = (view.repository.default_branch or "").strip()
    revision = _short_revision(
        _trust_value(view, "Git HEAD") or _trust_value(view, "Source revision")
    )
    working = _trust_value(view, "Working state").strip().lower()
    if working == "clean":
        state = "Clean working state"
    elif working == "dirty":
        state = "Dirty working state"
    else:
        state = "Working state UNKNOWN"
    meta_bits = [f"<strong>{escape_html(name)}</strong>"]
    if branch:
        meta_bits.append(f"<span>{escape_html(branch)}</span>")
    if revision and revision.upper() != "UNKNOWN":
        meta_bits.append(f"<code>{escape_html(revision)}</code>")
    meta_bits.append(f"<span>{escape_html(state)}</span>")
    return (
        '<div class="hero" id="cover">'
        "<div>"
        '<div class="eyebrow">Repository engineering health</div>'
        "<h1>Current-code baseline</h1>"
        f'<div class="meta">{"".join(meta_bits)}</div>'
        "</div>"
        '<div class="hero-status">'
        "<div>No comparison supplied</div>"
        f'<div class="small muted">{escape_html(summary.assessment_mode_label)}</div>'
        "</div>"
        "</div>"
    )


def _humanize_timestamp(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return "—"
    # Prefer date + time without fractional seconds / Z clutter.
    if "T" in text:
        date_part, _, time_part = text.partition("T")
        time_part = time_part.rstrip("Z")
        if "." in time_part:
            time_part = time_part.split(".", 1)[0]
        if len(time_part) >= 5:
            return f"{date_part} {time_part[:5]} UTC"
        return date_part
    return text


def _severity_tone(label: str) -> str:
    key = label.lower().replace(" ", "-")
    if key in {"critical", "high", "medium", "low", "informational", "none-detected", "unknown"}:
        return f"severity-{key}"
    return "mode"


def _cloud_primary(view: HtmlReportViewModel) -> str:
    metrics = view.summary.metrics
    if metrics is None:
        return "Unknown"
    return metrics.cloud_signals_primary


def _cloud_status(view: HtmlReportViewModel) -> str:
    metrics = view.summary.metrics
    if metrics is None:
        return "Unknown"
    if metrics.cloud_signals_primary == "Unknown":
        return ""
    return metrics.cloud_signals_status


def _cicd_value(view: HtmlReportViewModel) -> str:
    metrics = view.summary.metrics
    if metrics is None:
        return "Unknown"
    return metrics.cicd_label


def _kpi(label: str, value: str, hint: str, tone: str) -> str:
    hint_html = f'<span class="kpi-hint">{escape_html(hint)}</span>' if hint else ""
    return (
        f'<article class="kpi kpi-{escape_html(tone)}">'
        f'<p class="kpi-label">{escape_html(label)}</p>'
        f'<p class="kpi-value">{escape_html(value)}</p>'
        f"{hint_html}"
        "</article>\n"
    )


def _mode_short(label: str) -> str:
    lower = label.lower()
    if "ai enhanced" in lower or (
        label.startswith("AI") and "fallback" not in lower and "requested" not in lower
    ):
        return "AI"
    if "deterministic" in lower:
        return "Deterministic"
    return label


def _render_executive_cards(view: HtmlReportViewModel) -> str:
    metrics = view.summary.metrics
    file_count = metrics.file_count if metrics else view.repository.file_count
    tech_count = metrics.technology_count if metrics else len(view.summary.technologies)
    findings = metrics.findings_count if metrics else view.summary.total_findings
    recommendations = (
        metrics.recommendations_count if metrics else view.summary.total_recommendations
    )
    tests = metrics.test_files_label if metrics else ""
    cicd = metrics.cicd_label if metrics else ""
    cloud_primary = metrics.cloud_signals_primary if metrics else ""
    cloud_status = (
        metrics.cloud_signals_status
        if metrics and metrics.cloud_signals_primary not in {"", "Unknown"}
        else ""
    )
    size = metrics.repository_size_label if metrics else f"{file_count} files"
    highest = view.summary.highest_finding_severity
    cards = [
        _stat_card("Files", str(file_count)),
        _stat_card("Technologies", str(tech_count)),
        _stat_card("Findings", str(findings)),
        _stat_card("Recommendations", str(recommendations)),
    ]
    if tests and tests != "Unknown":
        cards.append(_stat_card("Test Files Detected", tests))
    if cicd and cicd != "Unknown":
        cards.append(_stat_card("CI/CD", cicd))
    if cloud_primary and cloud_primary != "Unknown":
        cards.append(_stat_card("Cloud Enablement Signals", cloud_primary, cloud_status))
    if size and size != "Unknown":
        cards.append(_stat_card("Repository Size", size))
    if highest and highest != "Unknown":
        cards.append(_stat_card("Highest Finding Severity", highest))
    return '<div class="stat-grid">\n' + "".join(cards) + "</div>"


def _stat_card(label: str, value: str, hint: str = "") -> str:
    hint_html = f'<p class="stat-hint">{escape_html(hint)}</p>' if hint else ""
    return (
        f'<article class="stat-card"><p class="stat-label">{escape_html(label)}</p>'
        f'<p class="stat-value">{escape_html(value)}</p>'
        f"{hint_html}"
        "</article>\n"
    )


def _render_technology(view: HtmlReportViewModel) -> str:
    inventory = view.technology_inventory
    if inventory is not None:
        return _render_technology_inventory(view, inventory)
    if not view.technologies and not view.version_highlights:
        return (
            '<p class="muted">No supported technology evidence was available for this '
            + "repository scan. Confirm language manifests are present and re-run "
            + "assessment if needed.</p>"
        )
    badges = (
        "".join(
            f'<span class="tech-badge">{escape_html(item.name)}'
            + (f"<em>{escape_html(item.version)}</em>" if item.version else "")
            + "</span>"
            for item in view.technologies
        )
        or '<span class="muted">None detected</span>'
    )
    highlights = ""
    if view.version_highlights:
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(item.label)}</td>"
            + f"<td>{escape_and_wrap(item.value)}</td>"
            + f"<td>{escape_html(item.kind)}</td>"
            + "</tr>"
            for item in view.version_highlights
        )
        highlights = (
            '<div class="table-card">\n'
            + "<h3>Runtime and platform versions</h3>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr><th>Label</th><th>Value</th><th>Kind</th></tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )
    return f'<div class="tech-badges">{badges}</div>\n{highlights}'


def _version_state_label(state: str) -> str:
    return {
        "exact": "Exact detected version",
        "range": "Version range",
        "inferred": "Inferred version",
        "unavailable": "Version unavailable",
        "conflicting": "Conflicting versions",
    }.get(state, "Version unavailable")


def _render_technology_inventory(
    view: HtmlReportViewModel, inventory: TechnologyInventorySection
) -> str:
    parts: list[str] = []
    if inventory.fact_count == 0 and inventory.composition is None:
        parts.append(
            '<p class="muted">No supported technology evidence was available for this '
            + "repository scan.</p>"
        )
    for group in inventory.groups:
        if not group.facts:
            continue
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(fact.name)}</td>"
            + f"<td>{escape_html(fact.category.replace('_', ' '))}</td>"
            + f"<td>{escape_html(fact.version) if fact.version else '—'}</td>"
            + f"<td>{escape_html(_version_state_label(fact.version_state))}</td>"
            + f"<td>{escape_html(fact.confidence_label.replace('_', ' ').title())}</td>"
            + f"<td>{_render_inventory_evidence(fact.evidence_paths, fact.source)}</td>"
            + "</tr>"
            for fact in group.facts
        )
        parts.append(
            f'<div class="tech-inventory-group" data-group="{escape_html(group.group_id)}">\n'
            + f"<h4>{escape_html(group.title)}</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Name</th><th>Type</th><th>Version</th>"
            + "<th>Version state</th><th>Confidence</th><th>Evidence</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    composition = inventory.composition
    if composition is not None:
        parts.append(_render_repository_composition(composition))

    if view.version_highlights:
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(item.label)}</td>"
            + f"<td>{escape_and_wrap(item.value)}</td>"
            + f"<td>{escape_html(item.kind)}</td>"
            + "</tr>"
            for item in view.version_highlights
        )
        parts.append(
            '<div class="table-card">\n'
            + "<h4>Runtime and platform version highlights</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr><th>Label</th><th>Value</th><th>Kind</th></tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    # Canonical Coverage → Confidence → Limitations (Slice 3.11).
    coverage_rows: tuple[object, ...] = ()
    if inventory.fact_count or inventory.composition is not None:
        coverage_rows = (
            simple_coverage_row(
                label="Technology inventory",
                status=str(inventory.status),
                display=f"{inventory.fact_count} inventoried fact(s)",
                note=str(inventory.status_label),
            ),
        )
    parts.append(
        render_coverage_confidence_limitations(
            coverage_rows=coverage_rows,
            confidence=inventory.confidence,
            confidence_label=inventory.confidence_label,
            limitations=inventory.limitations,
            coverage_fallback=(
                "No supported technology evidence was available for this repository scan."
                if inventory.fact_count == 0
                else None
            ),
        )
    )
    return (
        "\n".join(parts)
        if parts
        else ('<p class="muted">No supported technology evidence was available.</p>')
    )


def _render_inventory_evidence(paths: tuple[str, ...], source: str | None) -> str:
    links: list[str] = []
    for path in paths:
        safe = path.strip()
        if not safe or safe.startswith("/") or safe.startswith("file:"):
            continue
        # Repository-relative path text (appendix holds full evidence panels).
        links.append(f'<code class="trace-id">{escape_html(safe)}</code>')
    if links:
        return ", ".join(links)
    if source and not str(source).startswith("/") and not str(source).startswith("file:"):
        return f'<span class="muted">{escape_html(str(source))}</span>'
    return "—"


def _render_repository_composition(composition: RepositoryCompositionView) -> str:
    rows: list[str] = []
    if composition.total_files is not None:
        rows.append(f"<tr><td>Total analyzed files</td><td>{composition.total_files}</td></tr>")
    if composition.source_files is not None:
        rows.append(f"<tr><td>Source files observed</td><td>{composition.source_files}</td></tr>")
    if composition.test_files is not None:
        rows.append(f"<tr><td>Test files observed</td><td>{composition.test_files}</td></tr>")
    if composition.application_count is not None:
        rows.append(
            "<tr><td>Application / service indicators</td>"
            + f"<td>{composition.application_count}</td></tr>"
        )
    if composition.modules:
        rows.append(
            "<tr><td>Modules / components</td>"
            + f"<td>{escape_html(', '.join(composition.modules))}</td></tr>"
        )
    if composition.manifest_paths:
        paths = ", ".join(
            f'<code class="trace-id">{escape_html(path)}</code>'
            for path in composition.manifest_paths
        )
        rows.append(f"<tr><td>Dependency manifests</td><td>{paths}</td></tr>")
    if composition.build_file_paths:
        paths = ", ".join(
            f'<code class="trace-id">{escape_html(path)}</code>'
            for path in composition.build_file_paths
        )
        rows.append(f"<tr><td>Build files</td><td>{paths}</td></tr>")
    if composition.ecosystems:
        rows.append(
            "<tr><td>Dependency ecosystems</td>"
            + f"<td>{escape_html(', '.join(composition.ecosystems))}</td></tr>"
        )
    if not rows:
        return ""
    return (
        '<div class="tech-inventory-group" data-group="repository_composition">\n'
        "<h4>Repository composition</h4>\n"
        f'<p class="muted">{escape_html(composition.scope_note)}</p>\n'
        '<div class="table-wrap"><table>\n'
        "<thead><tr><th>Metric</th><th>Value</th></tr></thead>\n"
        f"<tbody>{''.join(rows)}</tbody>\n</table></div>\n"
        "</div>"
    )


def _severity_counts(view: HtmlReportViewModel) -> dict[str, int]:
    counts = {key: 0 for key in _SEVERITY_ORDER}
    for name, count in view.summary.findings_by_severity:
        key = name.lower()
        if key in {"info", "informational"}:
            counts["informational"] += count
        elif key in counts:
            counts[key] += count
    return counts


def _render_findings_overview(view: HtmlReportViewModel) -> str:
    counts = _severity_counts(view)
    meters = "".join(
        f'<article class="severity-card severity-{escape_html(name)}">'
        f'<p class="severity-label">{escape_html(name if name != "informational" else "info")}</p>'
        f'<p class="severity-count">{counts[name]}</p>'
        "</article>\n"
        for name in _SEVERITY_ORDER
    )
    top = view.findings[:_TOP_FINDINGS]
    if not top:
        cards = (
            '<p class="muted">No findings were produced for this run. '
            + "This does not certify that the repository is free of issues.</p>"
        )
    else:
        cards = (
            '<div class="card-stack">\n'
            + "\n".join(_render_finding_card(item, compact=True) for item in top)
            + "\n</div>"
        )
        if len(view.findings) > _TOP_FINDINGS:
            cards += (
                f'<p class="muted more-note">Showing top {_TOP_FINDINGS} of '
                + f"{len(view.findings)}. Full list in Technical Details.</p>"
            )
    return f'<div class="severity-grid">{meters}</div>\n<h3>Priority findings</h3>\n{cards}'


def _render_finding_card(item: FindingView, *, compact: bool) -> str:
    nodes = _id_list(item.affected_nodes) or '<span class="muted">None</span>'
    # Anchors live only on full detail cards (appendix) to avoid duplicate IDs.
    anchor_attr = f' id="{escape_html(finding_anchor(item.finding_id))}"' if not compact else ""
    evidence = ""
    if not compact:
        evidence = render_evidence_ref_panel(
            item.evidence_refs,
            primary_evidence_id=item.primary_evidence_id,
        )
        if not evidence and item.evidence:
            evidence = _render_evidence_details(item.evidence)
    meta = ""
    if not compact:
        completeness = completeness_label(item.evidence_completeness)
        limitations = _render_limitations_block(item.limitations, title="Evidence limitations")
        supported = _title_links(
            item.driven_recommendation_ids,
            item.driven_recommendation_titles,
            anchor_fn=recommendation_anchor,
            empty="None",
        )
        influenced = _title_links(
            item.influenced_priority_action_ids,
            item.influenced_priority_action_titles,
            anchor_fn=priority_action_anchor,
            empty="None",
        )
        meta = (
            '<dl class="meta">\n'
            + "<div><dt>Finding ID</dt>"
            + f'<dd><code class="trace-id">{escape_and_wrap(item.finding_id)}</code></dd></div>\n'
            + "<div><dt>Rule ID</dt>"
            + f'<dd><code class="trace-id" title="Rule ID">{escape_and_wrap(item.rule_id)}'
            + "</code></dd></div>\n"
            + f"<div><dt>Category</dt><dd>{escape_html(item.category)}</dd></div>\n"
            + f"<div><dt>Evidence</dt><dd>{escape_html(completeness)}</dd></div>\n"
            + f"{_severity_basis_meta_rows(item)}"
            + f"{_finding_confidence_meta_rows(item)}"
            + f"<div><dt>Affected nodes</dt><dd>{nodes}</dd></div>\n"
            + f"<div><dt>Related recommendation</dt><dd>{supported}</dd></div>\n"
            + f"<div><dt>Priority Actions influenced</dt><dd>{influenced}</dd></div>\n"
            + f"{_related_findings_meta_rows(item)}"
            + "</dl>\n"
            + f"{limitations}"
        )
    description = ""
    if not compact:
        description = f'<p class="card-desc">{escape_html(item.description)}</p>\n'
    trace = (
        f'<p class="trace-line"><span class="meta-label">Rule</span> '
        f'<code class="trace-id" title="Rule ID">{escape_and_wrap(item.rule_id)}</code></p>\n'
        if compact
        else ""
    )
    detail_link = ""
    if compact:
        detail_link = (
            f'<p class="trace-line"><a href="#{escape_html(finding_anchor(item.finding_id))}">'
            + "View evidence details</a></p>\n"
        )
    return (
        f'<article class="item-card finding"{anchor_attr}>\n'
        f'<header class="item-header">'
        f'<span class="badge severity-{escape_html(item.severity)}">'
        '<span class="sr-only">Severity: </span>'
        f"{escape_html(item.severity)}</span> "
        f"<strong>{escape_html(item.title)}</strong>"
        f"</header>\n"
        f"{description}"
        f"{trace}"
        f"{detail_link}"
        f"{meta}"
        f"{evidence}\n"
        "</article>"
    )


def _related_findings_meta_rows(item: FindingView) -> str:
    if not item.correlated_finding_ids:
        return ""
    links = _title_links(
        item.correlated_finding_ids,
        item.correlated_finding_titles,
        anchor_fn=finding_anchor,
        empty="None",
    )
    labels = "; ".join(
        escape_html(label) for label in item.correlation_relationship_labels[:3] if label
    )
    relationship = f"<div><dt>Relationship</dt><dd>{labels}</dd></div>\n" if labels else ""
    return f"<div><dt>Related findings</dt><dd>{links}</dd></div>\n{relationship}"


def _severity_basis_meta_rows(item: FindingView) -> str:
    labels = tuple(item.severity_basis_labels[:4])
    if not labels:
        return ""
    text = "; ".join(escape_html(label) for label in labels)
    return f"<div><dt>Severity basis</dt><dd>{text}</dd></div>\n"


def _finding_confidence_meta_rows(item: FindingView) -> str:
    rows: list[str] = []
    if item.finding_confidence_level:
        rows.append(
            "<div><dt>Finding confidence</dt><dd>"
            + f"{escape_html(item.finding_confidence_level.replace('_', ' ').title())}"
            + "</dd></div>\n"
        )
    if item.rule_confidence_level:
        rows.append(
            "<div><dt>Rule confidence</dt><dd>"
            + f"{escape_html(item.rule_confidence_level.replace('_', ' ').title())}"
            + "</dd></div>\n"
        )
    primary_evidence_level = None
    for ref in item.evidence_refs:
        if item.primary_evidence_id and ref.evidence_id == item.primary_evidence_id:
            primary_evidence_level = ref.evidence_confidence_level
            break
    if primary_evidence_level is None and item.evidence_refs:
        primary_evidence_level = item.evidence_refs[0].evidence_confidence_level
    if primary_evidence_level:
        rows.append(
            "<div><dt>Evidence confidence</dt><dd>"
            + f"{escape_html(primary_evidence_level.replace('_', ' ').title())}"
            + "</dd></div>\n"
        )
    return "".join(rows)


def _recommendation_confidence_meta_row(item: RecommendationView) -> str:
    if not item.recommendation_confidence_level:
        return ""
    return (
        "<div><dt>Recommendation confidence</dt><dd>"
        f"{escape_html(item.recommendation_confidence_level.replace('_', ' ').title())}"
        "</dd></div>\n"
    )


def _priority_basis_meta_rows(item: RecommendationView) -> str:
    priority = (item.priority or "").replace("_", " ").title()
    rows = (
        f"<div><dt>Recommendation priority</dt><dd>{escape_html(priority)}</dd></div>\n"
        if priority
        else ""
    )
    labels = tuple(getattr(item, "priority_basis_labels", ()) or ())[:4]
    if labels:
        text = "; ".join(escape_html(label) for label in labels)
        rows += f"<div><dt>Priority basis</dt><dd>{text}</dd></div>\n"
    return rows


def _roadmap_bucket(item: RecommendationView) -> str:
    from codestrata.reporting.prioritization import BUCKET_LABELS

    bucket = (item.presentation_bucket or "").strip().lower()
    if bucket in BUCKET_LABELS:
        return BUCKET_LABELS[bucket]
    key = item.priority.lower()
    if key in {"immediate", "critical"}:
        return "Immediate"
    if key in {"high", "medium"}:
        return "Near Term"
    return "Future"


_LEADERSHIP_ACTION_DISPLAY_LIMIT = 8


def _render_roadmap(
    items: tuple[RecommendationView, ...],
    *,
    total_actions: int | None = None,
    as_priority_actions: bool = False,
) -> str:
    display_all = tuple(item for item in items if item.related_finding_ids)
    if not display_all:
        return (
            '<p class="muted">No Priority Actions were produced for this assessment. '
            + "Findings may still appear above when present.</p>"
        )
    total = total_actions if total_actions is not None else len(display_all)
    display = display_all[:_LEADERSHIP_ACTION_DISPLAY_LIMIT]
    subset_note = ""
    if total > len(display):
        subset_note = (
            f'<p class="section-note">Showing {len(display)} of {total} prioritized '
            + "actions. Complete Priority Action details are in the Technical Appendix.</p>\n"
        )
    buckets: dict[str, list[RecommendationView]] = {
        "Immediate": [],
        "Near Term": [],
        "Future": [],
    }
    for item in display:
        buckets[_roadmap_bucket(item)].append(item)
    parts: list[str] = [subset_note, '<div class="roadmap">']
    for name, group in buckets.items():
        if not group:
            continue
        cards = "\n".join(
            _render_recommendation_card(
                item,
                compact=True,
                as_priority_action=as_priority_actions,
            )
            for item in group
        )
        parts.append(
            '<div class="roadmap-lane">\n'
            + f'<h3>{escape_html(name)} <span class="count-pill">{len(group)}</span></h3>\n'
            + f'<div class="card-stack">{cards}</div>\n'
            + "</div>"
        )
    parts.append("</div>")
    return "\n".join(parts)


def _business_value(item: RecommendationView) -> str:
    risk = (item.risk or "").lower()
    if risk == "high" or item.priority.lower() in {"immediate", "critical", "high"}:
        return "High"
    if risk == "medium" or item.priority.lower() == "medium":
        return "Medium"
    return "Incremental"


def _effort_label(item: RecommendationView) -> str:
    effort = (item.effort or "").lower()
    labels = {
        "small": "Small",
        "xs": "Small",
        "s": "Small",
        "medium": "Medium",
        "m": "Medium",
        "large": "Larger",
        "l": "Larger",
        "extra_large": "Larger",
        "xl": "Larger",
    }
    if effort in labels:
        return labels[effort]
    actions = len(item.actions)
    if actions <= 1:
        return "Small"
    if actions <= 3:
        return "Medium"
    return "Larger"


def _render_recommendation_card(
    item: RecommendationView,
    *,
    compact: bool,
    as_priority_action: bool = False,
) -> str:
    is_pa = as_priority_action or item.action_type is not None
    # Anchors only on full (appendix) cards to avoid duplicate fragment IDs.
    if not compact and is_pa:
        anchor_attr = f' id="{escape_html(priority_action_anchor(item.recommendation_id))}"'
    elif not compact and not is_pa:
        anchor_attr = f' id="{escape_html(recommendation_anchor(item.recommendation_id))}"'
    else:
        anchor_attr = ""
    alias = ""

    related_titles = ""
    if item.related_finding_titles and not is_pa:
        related_titles = (
            '<p class="related-findings"><em>Supported by</em> '
            + _title_links(
                item.related_finding_ids,
                item.related_finding_titles,
                anchor_fn=finding_anchor,
                empty="None",
            )
            + "</p>\n"
        )
    why_action = _render_why_this_action(item) if is_pa else ""
    chips = (
        '<div class="chip-row">\n'
        f'<span class="chip"><em>Horizon</em> {escape_html(_roadmap_bucket(item))}</span>\n'
        f'<span class="chip"><em>Business impact</em> '
        f"{escape_html(_business_value(item))}</span>\n"
        f'<span class="chip"><em>Effort</em> {escape_html(_effort_label(item))}</span>\n'
        f'<span class="chip"><em>Evidence</em> '
        f"{escape_html(completeness_label(item.evidence_completeness))}</span>\n"
        "</div>\n"
        f'<p class="outcome"><em>Business outcome</em> {escape_html(item.summary)}</p>\n'
        f"{related_titles}"
        f"{why_action}"
    )
    detail = ""
    if not compact:
        related = _title_links(
            item.related_finding_ids,
            item.related_finding_titles,
            anchor_fn=finding_anchor,
            empty="None",
        )
        if item.primary_finding_id:
            fid = item.primary_finding_id
            href = escape_html(finding_anchor(fid))
            title = escape_html(
                _title_for_id(
                    fid,
                    item.related_finding_ids,
                    item.related_finding_titles,
                )
            )
            primary = f'<a class="id-link" href="#{href}">{title}</a>'
        else:
            primary = '<span class="muted">None</span>'
        actions = (
            "".join(
                "<li>"
                + f"<strong>{action.order}. {escape_html(action.title)}</strong>"
                + f" — {escape_html(action.description)}"
                + (
                    f' <code class="cmd">{escape_and_wrap(action.command)}</code>'
                    if action.command
                    else ""
                )
                + "</li>"
                for action in item.actions
            )
            or "<li>None</li>"
        )
        limitations = _render_limitations_block(
            item.limitations,
            title="Traceability limitations",
        )
        rationale_row = (
            ""
            if is_pa and (item.rationale or "").strip()
            else f"<p><em>Rationale:</em> {escape_html(item.rationale)}</p>\n"
        )
        detail = (
            rationale_row
            + '<dl class="meta">\n'
            + f"<div><dt>{'Priority Action' if is_pa else 'Recommendation'} ID</dt>"
            + f"<dd><code>{escape_and_wrap(item.recommendation_id)}</code></dd></div>\n"
            + f"<div><dt>Category</dt><dd>{escape_html(item.category)}</dd></div>\n"
            + "<div><dt>Evidence</dt>"
            + f"<dd>{escape_html(completeness_label(item.evidence_completeness))}</dd></div>\n"
            + f"{_recommendation_confidence_meta_row(item)}"
            + f"{_priority_basis_meta_rows(item)}"
            + f"<div><dt>Supported by</dt><dd>{related}</dd></div>\n"
            + f"<div><dt>Primary finding</dt><dd>{primary}</dd></div>\n"
            + "</dl>\n"
            + f"{limitations}"
            + "<h4>Actions</h4>\n"
            + f'<ol class="actions">{actions}</ol>\n'
            + f"{_render_evidence_details(item.evidence)}\n"
        )
    if is_pa:
        horizon = _roadmap_bucket(item)
        priority = (item.priority or "").strip()
        meta = f"Horizon {escape_html(horizon)}"
        if priority and priority.lower() != horizon.lower():
            meta += f" · Priority {escape_html(priority)}"
        rationale = (item.rationale or "").strip()
        summary = (item.summary or "").strip()
        visible = rationale or summary
        outcome = ""
        if summary and summary != rationale:
            outcome = f"<p><em>Business outcome</em> {escape_html(summary)}</p>\n"
        return (
            f'<article class="item-card recommendation"{anchor_attr}>\n'
            f"<h3>{escape_html(item.title)}</h3>\n"
            f'<p class="action-meta">{meta}</p>\n'
            f"<p>{escape_html(visible)}</p>\n"
            '<details class="action-support">\n'
            "<summary>Supporting findings and evidence</summary>\n"
            f"{outcome}{why_action}{detail}"
            "</details>\n"
            "</article>"
        )
    return (
        f'<article class="item-card recommendation"{anchor_attr}>\n'
        f"{alias}"
        f'<header class="item-header">'
        f'<span class="badge priority-{escape_html(item.presentation_bucket or item.priority)}">'
        f"{escape_html(_roadmap_bucket(item))}</span> "
        f"<strong>{escape_html(item.title)}</strong>"
        f"</header>\n"
        f"{chips}"
        f"{detail}"
        "</article>"
    )


def _render_why_this_action(item: RecommendationView) -> str:
    rec_titles = item.supporting_recommendation_titles or ()
    if not rec_titles and item.supporting_recommendation_ids:
        rec_titles = item.supporting_recommendation_ids
    supported = _title_links(
        item.supporting_recommendation_ids or (item.recommendation_id,),
        rec_titles or (item.title,),
        anchor_fn=recommendation_anchor,
        empty="None",
    )
    finding_count = len(item.related_finding_ids)
    limitations = _render_limitations_block(
        item.limitations,
        title="Evidence limitations",
    )
    finding_links = _title_links(
        item.related_finding_ids,
        item.related_finding_titles,
        anchor_fn=finding_anchor,
        empty="None",
    )
    return (
        '<div class="why-action">\n'
        "<h4>Why this action</h4>\n"
        f"<p><em>Supported by</em> {supported}</p>\n"
        f"<p><em>Supporting findings</em> {finding_count} — {finding_links}</p>\n"
        f"<p><em>Evidence</em> {escape_html(completeness_label(item.evidence_completeness))}</p>\n"
        "<p>"
        f"{_recommendation_detail_markup(item.recommendation_id, 'View recommendation details')}"
        "</p>\n"
        f"{limitations}"
        "</div>\n"
    )


def _is_blank_or_unknown(value: object) -> bool:
    text = str(value or "").strip().lower()
    return text in {"", "unavailable", "unknown", "not_assessed", "—", "-"}


def _limitation_items(limitations: object) -> str:
    """Render limitation rows; omit diagnostic unavailable/unknown category noise."""

    rows: tuple[object, ...]
    if limitations is None:
        rows = ()
    elif isinstance(limitations, tuple):
        rows = limitations
    else:
        rows = tuple(limitations)  # type: ignore[arg-type]
    items = []
    for item in rows:
        category = str(getattr(item, "category", "") or "")
        summary = str(getattr(item, "summary", "") or "")
        cat_l = category.lower()
        if "unavailable" in cat_l or cat_l in {"unknown", "not_assessed"}:
            continue
        if _is_blank_or_unknown(summary):
            continue
        summary_l = summary.lower()
        if "business impact remains unknown" in summary_l or "business impact unknown" in cat_l:
            continue
        if "phase " in summary_l and ("collector" in summary_l or "unsupported" in summary_l):
            continue
        if "deterministic" in summary_l or "phase 4" in summary_l or "phase 5" in summary_l:
            continue
        if "inventory does not re-run rules" in summary_l:
            continue
        label = category.replace("-", " ").replace("_", " ").strip().title() or "Note"
        items.append(f"<li><strong>{escape_html(label)}</strong> — {escape_html(summary)}</li>")
    return "".join(items)


def _status_badge_class(status_label: str) -> str:
    """Map domain status labels to semantic status badge classes (Slice 14.8).

    Domain truth is unchanged. ``not-assessed`` must not match success via the
    substring ``assessed``.
    """
    key = (status_label or "").strip().lower().replace(" ", "-").replace("_", "-")
    if not key:
        return "status-badge"
    if any(
        token in key
        for token in (
            "not-assessed",
            "not-available",
            "not-enabled",
            "unavailable",
            "unknown",
            "disabled",
        )
    ) or key.startswith("not-"):
        if "partial" in key:
            return "status-badge status-badge-partial"
        return "status-badge status-badge-not-assessed"
    if any(token in key for token in ("fail", "error")):
        return "status-badge status-badge-failed"
    if any(token in key for token in ("partial", "limited", "degraded")):
        return "status-badge status-badge-partial"
    if key in {"assessed", "succeeded", "success", "complete", "ok", "ready"}:
        return "status-badge status-badge-succeeded"
    if any(token in key for token in ("success", "complete", "ready")):
        return "status-badge status-badge-succeeded"
    return "status-badge"


def _domain_status_header(section: object) -> str:
    label = str(getattr(section, "status_label", "") or "")
    summary = str(getattr(section, "status_summary", "") or "")
    if not label and not summary:
        return ""
    badge = (
        f"<span class='{_status_badge_class(label)}'>{escape_html(label)}</span>" if label else ""
    )
    summary_html = f"<span class='muted'>{escape_html(summary)}</span>" if summary else ""
    return f"<div class='domain-header'>{badge}{summary_html}</div>"


def _metric_tile(label: str, value: str, note: str | None = None) -> str:
    note_html = f'<p class="muted">{escape_html(note)}</p>' if note else ""
    return (
        "<div class='metric-card card'>"
        f"<div class='label'>{escape_html(label)}</div>"
        f"<div class='value'>{escape_html(value)}</div>"
        f"{note_html}"
        "</div>"
    )


def _responsive_table(table_html: str) -> str:
    return wrap_table(table_html, css_class="table-wrap responsive-table")


def _architecture_conclusion_meta(item: object) -> str:
    bits: list[str] = []
    confidence = getattr(item, "confidence", None)
    business_impact = getattr(item, "business_impact", None)
    if not _is_blank_or_unknown(confidence):
        bits.append(f"Confidence: {confidence}")
    if not _is_blank_or_unknown(business_impact) and str(business_impact).lower() not in {
        "unknown",
        "not assessed",
        "not_assessed",
    }:
        bits.append(f"Business impact: {business_impact}")
    return escape_html(" · ".join(bits)) if bits else ""


def _architecture_conclusion_card(item: object) -> str:
    meta = _architecture_conclusion_meta(item)
    meta_html = f"<p class='muted technical-metadata'>{meta}</p>" if meta else ""
    scope_values = tuple(getattr(item, "affected_scope", ()) or ())
    # Prefer package/module roots over exhaustive file lists for leadership readability.
    scope = ", ".join(scope_values[:4]) or "—"
    if len(scope_values) > 4:
        scope = f"{scope} (+{len(scope_values) - 4} more)"
    finding_ids = tuple(getattr(item, "supporting_finding_ids", ()) or ())
    primary = getattr(item, "primary_finding_id", None)
    link_ids = []
    if primary:
        link_ids.append(str(primary))
    for fid in finding_ids:
        if str(fid) not in link_ids:
            link_ids.append(str(fid))
    links = ""
    if link_ids:
        anchors = ", ".join(
            f'<a class="id-link" href="#{escape_html(finding_anchor(fid))}">{escape_html(fid)}</a>'
            for fid in link_ids[:6]
        )
        links = f'<p class="trace-line">Supporting findings: {anchors}</p>'
    return (
        "<article class='content-card conclusion-card card'>"
        f"<h4>{escape_html(getattr(item, 'title', ''))}</h4>"
        f"<p>{escape_html(getattr(item, 'summary', ''))}</p>"
        f"{meta_html}"
        f"<p class='muted'>{escape_html(getattr(item, 'severity_summary', '') or '')}</p>"
        f"<p class='muted'>Scope: {escape_html(scope)}</p>"
        f"{links}"
        "</article>"
    )


def _dedupe_architecture_conclusions(items: tuple[object, ...]) -> tuple[object, ...]:
    seen: set[str] = set()
    out: list[object] = []
    for item in items:
        title = str(getattr(item, "title", "") or "").strip().lower()
        if not title or title in seen:
            continue
        seen.add(title)
        out.append(item)
    return tuple(out)


def _architecture_overview_facts(
    section: ArchitectureIntelligenceSection,
    *,
    health_label: str | None,
    execution_label: str | None,
) -> tuple[Any, ...]:
    facts = section.overview_facts
    if not health_label:
        return facts
    rewritten = []
    for fact in facts:
        if fact.label != "Assessment status":
            rewritten.append(fact)
            continue
        rewritten.append(
            fact.model_copy(
                update={
                    "label": "Engineering Health",
                    "value": health_label,
                    "note": "Outcome conclusion, not analyzer execution",
                }
            )
        )
        rewritten.append(
            fact.model_copy(
                update={
                    "label": "Execution",
                    "value": execution_label or fact.value,
                    "note": "Analyzer execution completed; not a health conclusion",
                }
            )
        )
    return tuple(rewritten)


def _render_architecture_intelligence(
    section: ArchitectureIntelligenceSection,
    *,
    health_label: str | None = None,
    execution_label: str | None = None,
) -> str:
    """Epic 3 Slice 3.3 Architecture Intelligence pack body."""

    health = health_label or section.status_label
    parts: list[str] = [
        "<div class='domain-header'>"
        f"<span class='{_status_badge_class(health)}'>"
        f"{escape_html(health)}</span>"
        f"<span class='muted'>{escape_html(section.status_summary)}</span>"
        "</div>"
    ]

    overview_facts = _architecture_overview_facts(
        section, health_label=health_label, execution_label=execution_label
    )
    if overview_facts:
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(fact.label)}</td>"
            + f"<td>{escape_html(fact.value)}</td>"
            + f"<td>{escape_html(fact.note) if fact.note else '—'}</td>"
            + "</tr>"
            for fact in overview_facts
        )
        parts.append(
            '<div class="arch-intel-group" data-group="architecture_overview">\n'
            + "<h4>Architecture overview</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr><th>Fact</th><th>Value</th><th>Note</th></tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    if section.inventory_items:
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(item.name)}</td>"
            + f"<td>{escape_html(item.kind.replace('_', ' '))}</td>"
            + f"<td>{escape_html(item.detail) if item.detail else '—'}</td>"
            + "</tr>"
            for item in section.inventory_items
        )
        parts.append(
            '<div class="arch-intel-group" data-group="structural_inventory">\n'
            + "<h4>Structural inventory</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr><th>Name</th><th>Kind</th><th>Detail</th></tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    if section.conclusions:
        conclusions = _dedupe_architecture_conclusions(tuple(section.conclusions))
        body = "".join(_architecture_conclusion_card(item) for item in conclusions)
        parts.extend(["<h4>Architecture conclusions</h4>", body])

    if section.findings:
        rows = "".join(
            "<tr>"
            + f"<td><a class='id-link' href='#{escape_html(finding_anchor(item.finding_id))}'>"
            + f"{escape_html(item.title)}</a></td>"
            + f"<td>{escape_html(item.severity)}</td>"
            + f"<td>{escape_html(item.confidence)}</td>"
            + f"<td>{_render_id_links(item.evidence_ids, evidence_anchor)}</td>"
            + f"<td>{escape_html(', '.join(item.affected_scope[:3]) or '—')}</td>"
            + "</tr>"
            for item in section.findings
        )
        parts.append(
            '<div class="arch-intel-group" data-group="key_architecture_findings">\n'
            + "<h4>Key architecture findings</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Finding</th><th>Severity</th><th>Confidence</th>"
            + "<th>Evidence</th><th>Scope</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )
    elif section.empty_findings_message:
        parts.append(f"<p class='muted'>{escape_html(section.empty_findings_message)}</p>")

    if section.recommendations:
        rows = "".join(
            "<tr>"
            + _recommendation_td(item.recommendation_id, item.title)
            + f"<td>{escape_html(item.priority) if item.priority else '—'}</td>"
            + f"<td>{_render_id_links(item.finding_ids, finding_anchor)}</td>"
            + "</tr>"
            for item in section.recommendations
        )
        parts.append(
            '<div class="arch-intel-group" data-group="architecture_recommendations">\n'
            + "<h4>Architecture recommendations</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Recommendation</th><th>Priority</th><th>Supporting findings</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    if section.graph_evidence:
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(item.identity)}</td>"
            + f"<td>{escape_html(item.relationship_type) if item.relationship_type else '—'}</td>"
            + f"<td>{escape_html(item.reference_kind) if item.reference_kind else '—'}</td>"
            + f"<td>{escape_html(item.cycle_id) if item.cycle_id else '—'}</td>"
            + _optional_code_td(item.location)
            + _optional_code_td(item.graph_artifact_ref)
            + "</tr>"
            for item in section.graph_evidence
        )
        parts.append(
            '<div class="arch-intel-group" data-group="graph_evidence">\n'
            + "<h4>Graph and relationship evidence</h4>\n"
            + '<p class="muted">Compact graph references only. '
            + "Full graph payloads are not embedded.</p>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Identity</th><th>Relationship</th><th>Kind</th>"
            + "<th>Cycle</th><th>Location</th><th>Graph ref</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    if section.measurements:
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(item.metric_name)}</td>"
            + f"<td>{escape_html(item.observed_value)}</td>"
            + f"<td>{escape_html(item.operator) if item.operator else '—'}</td>"
            + f"<td>{escape_html(item.threshold) if item.threshold else '—'}</td>"
            + f"<td>{escape_html(item.scope) if item.scope else '—'}</td>"
            + f"<td>{escape_html(', '.join(item.limitations) if item.limitations else '—')}</td>"
            + "</tr>"
            for item in section.measurements
        )
        parts.append(
            '<div class="arch-intel-group" data-group="architecture_metrics">\n'
            + "<h4>Architecture measurements</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Metric</th><th>Observed</th><th>Operator</th>"
            + "<th>Threshold</th><th>Scope</th><th>Limitations</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    parts.append(
        render_coverage_confidence_limitations(
            coverage_rows=section.coverage_rows,
            confidence=section.confidence,
            confidence_label=section.confidence_label,
            limitations=section.limitations,
        )
    )

    return "\n".join(parts)


def _collect_rendered_evidence_ids(view: HtmlReportViewModel) -> frozenset[str]:
    """Evidence-card identities this document will anchor.

    Full finding cards emit those anchors. Capability labels stored on hotspot
    and ownership records are not evidence records and are omitted here.
    """

    ids: list[str] = []
    for item in (*view.findings, *(view.unclassified_findings or ())):
        for ref in item.evidence_refs:
            if ref.evidence_id.strip():
                ids.append(ref.evidence_id)
    return frozenset(ids)


def _collect_rendered_recommendation_ids(view: HtmlReportViewModel) -> frozenset[str]:
    """Recommendation ids that receive a ``recommendation_anchor`` fragment.

    Full non-priority cards in Unclassified Results and All Recommendations
    emit that fragment. Compact cards and priority-action cards do not.
    """

    ids: list[str] = []
    for item in view.unclassified_recommendations or ():
        if item.action_type is None and item.recommendation_id.strip():
            ids.append(item.recommendation_id)
    for item in _appendix_recommendations(view):
        if item.action_type is None and item.recommendation_id.strip():
            ids.append(item.recommendation_id)
    return frozenset(ids)


def begin_rendered_evidence_ids(ids: Iterable[str]) -> object:
    """Test hook: claim which evidence identities have rendered anchors."""

    return _rendered_evidence_ids.set(frozenset(item for item in ids if item.strip()))


def end_rendered_evidence_ids(token: object) -> None:
    _rendered_evidence_ids.reset(token)  # type: ignore[arg-type]


def _evidence_reference(evidence_id: str) -> str:
    """Link a real rendered evidence record, or say the record is not attached."""

    label = escape_html(evidence_id)
    rendered = _rendered_evidence_ids.get()
    if rendered is not None and evidence_id in rendered:
        href = escape_html(evidence_anchor(evidence_id))
        return f'<a class="id-link" href="#{href}">{label}</a>'
    return f'<span class="evidence-unavailable">{label} (evidence not attached)</span>'


def _render_evidence_references(ids: Sequence[str]) -> str:
    return " ".join(_evidence_reference(item) for item in ids)


def _render_id_links(ids: Sequence[str], anchor_fn: Callable[[str], str]) -> str:
    if not ids:
        return "—"
    if anchor_fn is evidence_anchor:
        return ", ".join(_evidence_reference(item) for item in ids[:6])
    if anchor_fn is recommendation_anchor:
        return ", ".join(_recommendation_detail_markup(item, item) for item in ids[:6])
    return ", ".join(
        f'<a class="id-link" href="#{escape_html(anchor_fn(item))}">{escape_html(item)}</a>'
        for item in ids[:6]
    )


def _render_architecture(section: ArchitectureReportSection) -> str:
    """Legacy pack-body renderer retained as fallback when intelligence is absent."""

    metrics = "".join(
        _metric_tile(item.label, item.value, item.note)
        for item in section.key_metrics
        if str(item.value).strip().lower() not in {"unavailable", "unknown", "—", "-"}
        and "coverage" not in item.label.lower()
    )
    conclusions = _dedupe_architecture_conclusions(tuple(section.conclusions))
    conclusions_body = "".join(_architecture_conclusion_card(item) for item in conclusions)
    recommendations_body = "".join(
        "<article class='content-card recommendation-card card'>"
        f"<h4>{escape_html(item.title)}</h4>"
        f"<p><strong>Objective:</strong> {escape_html(item.objective)}</p>"
        f"<p>{escape_html(item.rationale)}</p>"
        "</article>"
        for item in section.recommendation_groups
    )
    # Dedupe supporting findings by Finding ID only (Slice 5.11 — never title-only).
    finding_rows: list[str] = []
    seen_findings: set[str] = set()
    for item in section.findings:
        finding_id = (
            str(getattr(item, "finding_id", None) or getattr(item, "id", "") or "").strip().lower()
        )
        if finding_id:
            if finding_id in seen_findings:
                continue
            seen_findings.add(finding_id)
        finding_rows.append(
            "<tr>"
            + f"<td>{escape_html(item.title)}</td>"
            + f"<td>{escape_html(item.severity)}</td>"
            + f"<td>{escape_html(', '.join(item.affected_scope[:3]) or '—')}</td>"
            + "</tr>"
        )
    findings = "".join(finding_rows)
    limitations = _limitation_items(
        tuple(
            item
            for item in section.limitations
            if "business impact unknown" not in str(getattr(item, "summary", item)).lower()
            and "phase " not in str(getattr(item, "summary", item)).lower()
        )
    )
    has_substance = bool(conclusions_body or recommendations_body or findings or limitations)
    if not has_substance and not metrics:
        return (
            _domain_status_header(section)
            + "<p class='muted'>No architecture findings were produced within the "
            "assessed scope. Runtime architecture was not assessed.</p>"
        )
    parts = [
        _domain_status_header(section),
        f"<p>{escape_html(section.executive_summary)}</p>",
    ]
    if metrics:
        parts.append(f"<div class='metric-grid grid'>{metrics}</div>")
    if conclusions_body:
        parts.extend(["<h4>Architecture conclusions</h4>", conclusions_body])
    if recommendations_body:
        parts.extend(["<h4>Recommended actions</h4>", recommendations_body])
    if findings:
        parts.extend(
            [
                "<h4>Supporting findings</h4>",
                "<table><thead><tr>"
                + "<th>Finding</th><th>Severity</th>"
                + "<th>Scope</th>"
                + "</tr></thead><tbody>"
                + f"{findings}</tbody></table>",
            ]
        )
    if limitations:
        parts.extend(["<h4>Limitations</h4>", f"<ul>{limitations}</ul>"])
    return "\n".join(parts)


def _render_technical_debt_intelligence(section: TechnicalDebtIntelligenceSection) -> str:
    """Epic 3 Slice 3.4 Technical Debt Intelligence pack body."""

    parts: list[str] = [
        "<div class='domain-header'>"
        f"<span class='{_status_badge_class(section.status_label)}'>"
        f"{escape_html(section.status_label)}</span>"
        f"<span class='muted'>{escape_html(section.status_summary)}</span>"
        "</div>"
    ]

    if section.overview_facts:
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(fact.label)}</td>"
            + f"<td>{escape_html(fact.value)}</td>"
            + f"<td>{escape_html(fact.note) if fact.note else '—'}</td>"
            + "</tr>"
            for fact in section.overview_facts
        )
        parts.append(
            '<div class="td-intel-group" data-group="technical_debt_overview">\n'
            + "<h4>Technical debt overview</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr><th>Fact</th><th>Value</th><th>Note</th></tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    if section.measurements:
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(item.metric_name)}</td>"
            + f"<td>{escape_html(item.observed_value)}</td>"
            + f"<td>{escape_html(item.operator) if item.operator else '—'}</td>"
            + f"<td>{escape_html(item.threshold) if item.threshold else '—'}</td>"
            + f"<td>{escape_html(item.scope) if item.scope else '—'}</td>"
            + _optional_code_td(item.location)
            + f"<td>{escape_html(item.availability)}</td>"
            + f"<td>{escape_html(', '.join(item.limitations) if item.limitations else '—')}</td>"
            + "</tr>"
            for item in section.measurements
        )
        parts.append(
            '<div class="td-intel-group" data-group="technical_debt_measurements">\n'
            + "<h4>Technical debt measurements</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Metric</th><th>Observed</th><th>Operator</th>"
            + "<th>Threshold</th><th>Scope</th><th>Location</th>"
            + "<th>Availability</th><th>Limitations</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    if section.hotspots:
        rows = "".join(
            "<tr>"
            + f"<td><code class='trace-id'>{escape_html(item.path)}</code></td>"
            + f"<td>{escape_html(item.symbol)}</td>"
            + f"<td>{escape_html(item.metric_name)}</td>"
            + f"<td>{escape_html(item.observed_value)}</td>"
            + f"<td>{escape_html(item.threshold) if item.threshold else '—'}</td>"
            + f"<td>{escape_html(item.severity)}</td>"
            + f"<td>{escape_html(item.confidence)}</td>"
            + f"<td><a class='id-link' href='#{escape_html(finding_anchor(item.finding_id))}'>"
            + f"{escape_html(item.finding_id)}</a></td>"
            + f"<td>{_render_id_links(item.evidence_ids, evidence_anchor)}</td>"
            + "</tr>"
            for item in section.hotspots
        )
        parts.append(
            '<div class="td-intel-group" data-group="technical_debt_hotspots">\n'
            + "<h4>Technical debt hotspots</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Path</th><th>Symbol</th><th>Metric</th><th>Value</th>"
            + "<th>Threshold</th><th>Severity</th><th>Confidence</th>"
            + "<th>Finding</th><th>Evidence</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    if section.findings:
        rows = "".join(
            "<tr>"
            + f"<td><a class='id-link' href='#{escape_html(finding_anchor(item.finding_id))}'>"
            + f"{escape_html(item.title)}</a></td>"
            + f"<td>{escape_html(item.severity)}</td>"
            + f"<td>{escape_html(item.confidence)}</td>"
            + f"<td>{_render_id_links(item.evidence_ids, evidence_anchor)}</td>"
            + f"<td>{escape_html(', '.join(item.affected_scope[:3]) or '—')}</td>"
            + "</tr>"
            for item in section.findings
        )
        parts.append(
            '<div class="td-intel-group" data-group="key_technical_debt_findings">\n'
            + "<h4>Key technical debt findings</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Finding</th><th>Severity</th><th>Confidence</th>"
            + "<th>Evidence</th><th>Scope</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )
    elif section.empty_findings_message:
        parts.append(f"<p class='muted'>{escape_html(section.empty_findings_message)}</p>")

    if section.recommendations:
        rows = "".join(
            "<tr>"
            + _recommendation_td(item.recommendation_id, item.title)
            + f"<td>{escape_html(item.priority) if item.priority else '—'}</td>"
            + f"<td>{_render_id_links(item.finding_ids, finding_anchor)}</td>"
            + "</tr>"
            for item in section.recommendations
        )
        parts.append(
            '<div class="td-intel-group" data-group="technical_debt_recommendations">\n'
            + "<h4>Technical debt recommendations</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Recommendation</th><th>Priority</th><th>Supporting findings</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    parts.append(
        render_coverage_confidence_limitations(
            coverage_rows=section.coverage_rows,
            confidence=section.confidence,
            confidence_label=section.confidence_label,
            limitations=section.limitations,
        )
    )

    return "\n".join(parts)


def _render_technical_debt(section: TechnicalDebtReportSection) -> str:
    metrics = "".join(
        _metric_tile(item.label, item.value, item.note)
        for item in section.key_metrics
        if str(item.value).strip().lower() not in {"unavailable", "unknown", "—", "-"}
    )
    themes = "".join(
        "<tr>"
        f"<td>{escape_html(item.title)}</td>"
        f"<td><code>{escape_html(item.rule_id)}</code></td>"
        f"<td>{item.finding_count}</td>"
        f"<td>{item.high_severity_count}</td>"
        f"<td>{item.medium_severity_count}</td>"
        "</tr>"
        for item in section.significant_themes
    )
    hotspots = "".join(
        "<tr>"
        f"<td>{item.presentation_order}</td>"
        f"<td><code>{escape_html(item.path)}</code></td>"
        f"<td>{escape_html(item.source_unit)}</td>"
        f"<td>{escape_html(item.highest_severity)}</td>"
        f"<td>{item.finding_count}</td>"
        f"<td>{escape_html(', '.join(item.rule_ids) or '—')}</td>"
        f"<td>{escape_html(item.metric_summary)}</td>"
        "</tr>"
        for item in section.top_production_hotspots
    )
    conclusions = "".join(
        "<article class='content-card conclusion-card card'>"
        f"<h4>{escape_html(item.title)}</h4>"
        f"<p>{escape_html(item.summary)}</p>"
        "<p class='muted'>"
        f"Kind: {escape_html(item.kind)} · "
        f"Audience: {escape_html(item.audience)} · "
        f"Confidence: {escape_html(item.confidence)} · "
        f"Findings: {item.finding_count} · Hotspots: {item.hotspot_count}"
        "</p>"
        "</article>"
        for item in section.conclusions
    )
    recommendations = "".join(
        "<article class='content-card recommendation-card card'>"
        f"<h4>{escape_html(item.title)}</h4>"
        f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
        f"<p>{escape_html(item.rationale)}</p>"
        f"<p class='muted'>"
        f"{'Conditional' if item.conditional else 'Direct'} · "
        f"Audience: {escape_html(item.audience)}"
        "</p>"
        "</article>"
        for item in section.recommendations
    )
    test_obs = section.test_observation
    test_block = (
        "<div class='card td-test-observation'>"
        f"<h4>{escape_html(test_obs.title)}</h4>"
        f"<p>{escape_html(test_obs.summary)}</p>"
        f"<p class='muted'>Test findings: {test_obs.finding_count}</p>"
        "</div>"
        if test_obs.present
        else ""
    )
    coverage = "".join(
        "<tr>"
        f"<td>{escape_html(item.label)}</td>"
        f"<td>{escape_html(item.status)}</td>"
        f"<td>{escape_html(item.display)}</td>"
        "</tr>"
        for item in section.coverage_summary
        if str(item.status).strip().lower() not in {"unavailable", "unknown"}
        and str(item.display).strip().lower() not in {"unavailable", "unknown"}
    )
    limitations = _limitation_items(section.limitations)
    has_substance = bool(
        themes
        or hotspots
        or conclusions
        or recommendations
        or test_block
        or coverage
        or limitations
    )
    if not has_substance and not metrics:
        return (
            _domain_status_header(section)
            + "<p class='muted'>No complexity-related technical debt findings were "
            "produced within the assessed scope. Zero findings do not mean low "
            + "technical debt. Broader technical debt categories were not evaluated.</p>"
        )
    parts = [
        _domain_status_header(section),
        f"<p>{escape_html(section.executive_summary)}</p>",
    ]
    if metrics:
        parts.append(f"<div class='metric-grid grid'>{metrics}</div>")
    if themes:
        parts.extend(
            [
                "<h3>Significant production themes</h3>",
                "<table><thead><tr>"
                + "<th>Theme</th><th>Rule</th><th>Findings</th>"
                + "<th>High</th><th>Medium</th>"
                + "</tr></thead><tbody>"
                + f"{themes}</tbody></table>",
            ]
        )
    if hotspots:
        parts.extend(
            [
                "<h4>Top production hotspots</h4>",
                "<table><thead><tr>"
                + "<th>#</th><th>Path</th><th>Unit</th><th>Highest severity</th>"
                + "<th>Findings</th><th>Rules</th><th>Metrics</th>"
                + "</tr></thead><tbody>"
                + f"{hotspots}</tbody></table>",
            ]
        )
    if conclusions:
        parts.extend(["<h4>Conclusions</h4>", conclusions])
    if recommendations:
        parts.extend(["<h4>Recommendations</h4>", recommendations])
    if test_block:
        parts.extend(["<h3>Test-maintainability observation</h3>", test_block])
        parts.append("<p class='muted'>Test findings are not production health signals.</p>")
    if coverage:
        parts.extend(
            [
                "<h4>Coverage</h4>",
                "<table><thead><tr><th>Area</th><th>Status</th><th>Detail</th></tr></thead>"
                + f"<tbody>{coverage}</tbody></table>",
            ]
        )
    if limitations:
        parts.extend(["<h4>Limitations</h4>", f"<ul>{limitations}</ul>"])
    return "\n".join(parts)


def _render_dependency_intelligence(section: DependencyIntelligenceSection) -> str:
    """Epic 3 Slice 3.5 Dependency Intelligence pack body."""

    parts: list[str] = [
        "<div class='domain-header'>"
        f"<span class='{_status_badge_class(section.status_label)}'>"
        f"{escape_html(section.status_label)}</span>"
        f"<span class='muted'>{escape_html(section.status_summary)}</span>"
        "</div>"
    ]

    if section.overview_facts:
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(fact.label)}</td>"
            + f"<td>{escape_html(fact.value)}</td>"
            + f"<td>{escape_html(fact.note) if fact.note else '—'}</td>"
            + "</tr>"
            for fact in section.overview_facts
        )
        parts.append(
            '<div class="dep-intel-group" data-group="dependency_overview">\n'
            + "<h4>Dependency overview</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr><th>Fact</th><th>Value</th><th>Note</th></tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    if section.ecosystems:
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(item.name)}</td>"
            + f"<td>{item.manifest_count}</td>"
            + f"<td>{item.declaration_count if item.declaration_count is not None else '—'}</td>"
            + f"<td>{escape_html(item.parse_status) if item.parse_status else '—'}</td>"
            + _optional_text_td(item.version_availability)
            + f"<td>{escape_html(item.note) if item.note else '—'}</td>"
            + "</tr>"
            for item in section.ecosystems
        )
        parts.append(
            '<div class="dep-intel-group" data-group="dependency_ecosystems">\n'
            + "<h4>Ecosystems</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Ecosystem</th><th>Manifests</th><th>Declarations</th>"
            + "<th>Parse status</th><th>Version availability</th><th>Note</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    if section.manifests:
        rows = "".join(
            "<tr>"
            + f"<td><code class='trace-id'>{escape_html(item.path)}</code></td>"
            + f"<td>{escape_html(item.ecosystem)}</td>"
            + f"<td>{escape_html(item.manifest_type)}</td>"
            + f"<td>{escape_html(item.parse_status) if item.parse_status else '—'}</td>"
            + f"<td>{item.finding_count if item.finding_count is not None else '—'}</td>"
            + f"<td>{escape_html(', '.join(item.limitations) if item.limitations else '—')}</td>"
            + "</tr>"
            for item in section.manifests
        )
        parts.append(
            '<div class="dep-intel-group" data-group="dependency_manifest_inventory">\n'
            + "<h4>Manifest inventory</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Path</th><th>Ecosystem</th><th>Manifest type</th>"
            + "<th>Parse status</th><th>Findings</th><th>Limitations</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    if section.findings:
        rows = "".join(
            "<tr>"
            + f"<td><a class='id-link' href='#{escape_html(finding_anchor(item.finding_id))}'>"
            + f"{escape_html(item.title)}</a></td>"
            + f"<td>{escape_html(item.severity)}</td>"
            + f"<td>{escape_html(item.confidence)}</td>"
            + f"<td><code>{escape_html(item.rule_id)}</code></td>"
            + _optional_code_td(item.path)
            + f"<td>{escape_html(item.ecosystem) if item.ecosystem else '—'}</td>"
            + f"<td>{_render_id_links(item.evidence_ids, evidence_anchor)}</td>"
            + "</tr>"
            for item in section.findings
        )
        parts.append(
            '<div class="dep-intel-group" data-group="dependency_hygiene_findings">\n'
            + "<h4>Hygiene findings</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Finding</th><th>Severity</th><th>Confidence</th>"
            + "<th>Rule</th><th>Path</th><th>Ecosystem</th><th>Evidence</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )
    elif section.empty_findings_message:
        parts.append(f"<p class='muted'>{escape_html(section.empty_findings_message)}</p>")

    if section.recommendations:
        rows = "".join(
            "<tr>"
            + _recommendation_td(item.recommendation_id, item.title)
            + f"<td>{escape_html(item.priority) if item.priority else '—'}</td>"
            + f"<td>{_render_id_links(item.finding_ids, finding_anchor)}</td>"
            + "</tr>"
            for item in section.recommendations
        )
        parts.append(
            '<div class="dep-intel-group" data-group="dependency_recommendations">\n'
            + "<h4>Dependency recommendations</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Recommendation</th><th>Priority</th><th>Supporting findings</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    parts.append(
        render_coverage_confidence_limitations(
            coverage_rows=section.coverage_rows,
            confidence=section.confidence,
            confidence_label=section.confidence_label,
            limitations=section.limitations,
        )
    )

    return "\n".join(parts)


def _render_dependency(section: DependencyReportSection) -> str:
    landscape_rows = "".join(
        "<tr>"
        f"<td>{escape_html(item.label)}</td>"
        f"<td>{item.count}</td>"
        f"<td>{escape_html(item.group)}</td>"
        "</tr>"
        for item in section.landscape
    )
    landscape_table = (
        "<table><thead><tr><th>Metric</th><th>Count</th><th>Group</th></tr></thead>"
        f"<tbody>{landscape_rows}</tbody></table>"
        if landscape_rows
        else ""
    )
    production = section.production_health
    if production.finding_count == 0 and production.none_detected_statement:
        none_stmt = production.none_detected_statement
        lowered = none_stmt.lower()
        soft_fragments = (
            "healthy",
            "secure dependency",
            "secure supply",
            "safe supply chain",
            "no dependency risk",
            "no dependency risks",
        )
        if any(fragment in lowered for fragment in soft_fragments):
            none_stmt = (
                "No dependency hygiene findings were produced within the assessed "
                + "scope. Only declaration hygiene was assessed. Zero findings do "
                + "not mean a healthy or secure dependency posture."
            )
        production_findings = f"<p>{escape_html(none_stmt)}</p>"
    else:
        production_findings = (
            "".join(
                "<article class='card'>"
                + f"<h4>{escape_html(item.title)}</h4>"
                + f"<p>{escape_html(item.explanation)}</p>"
                + f"<p><strong>Remediation:</strong> {escape_html(item.remediation)}</p>"
                + "<p class='muted'>"
                + f"ID: <code>{escape_html(item.finding_id)}</code> · "
                + f"Rule: <code>{escape_html(item.rule_id)}</code> · "
                + f"Severity: {escape_html(item.severity)} · "
                + f"Confidence: {escape_html(item.confidence)} · "
                + f"Source role: {escape_html(item.source_role)}"
                + (f" · Path: <code>{escape_html(item.path)}</code>" if item.path else "")
                + (
                    f" · Identity: <code>{escape_html(item.normalized_identity)}</code>"
                    if item.normalized_identity
                    else ""
                )
                + "</p>"
                "</article>"
                for item in production.findings
            )
            or "<p class='muted'>No production hygiene findings displayed.</p>"
        )
    production_block = (
        f"<p class='muted'>Production findings: {production.finding_count}"
        f" (showing {production.findings_displayed})</p>"
        f"{production_findings}"
    )
    test_obs = section.test_observations
    if test_obs.present:
        test_findings = "".join(
            "<article class='card'>"
            + f"<h4>{escape_html(item.title)}</h4>"
            + f"<p>{escape_html(item.explanation)}</p>"
            + f"<p><strong>Remediation:</strong> {escape_html(item.remediation)}</p>"
            + "<p class='muted'>"
            + f"ID: <code>{escape_html(item.finding_id)}</code> · "
            + f"Rule: <code>{escape_html(item.rule_id)}</code> · "
            + f"Source role: {escape_html(item.source_role)}"
            + (f" · Path: <code>{escape_html(item.path)}</code>" if item.path else "")
            + "</p>"
            "</article>"
            for item in test_obs.findings
        )
        test_block = (
            f"<h4>{escape_html(test_obs.title)}</h4>"
            + f"<p>{escape_html(test_obs.summary)}</p>"
            + f"<p class='muted'>Test/fixture findings: {test_obs.finding_count}</p>"
            + f"{test_findings}"
        )
    else:
        test_block = ""
    hotspots = "".join(
        "<tr>"
        f"<td>{item.presentation_order}</td>"
        f"<td><code>{escape_html(item.path)}</code></td>"
        f"<td>{escape_html(item.source_role)}</td>"
        f"<td>{escape_html(item.ecosystem)}</td>"
        f"<td>{escape_html(item.manifest_type)}</td>"
        f"<td>{item.active_declaration_count}</td>"
        f"<td>{item.dependency_management_count}</td>"
        f"<td>{item.plugin_count}</td>"
        f"<td>{item.hygiene_finding_count}</td>"
        f"<td>{item.distinct_rule_count}</td>"
        f"<td>{escape_html(item.highest_severity)}</td>"
        f"<td>{item.diagnostics_count}</td>"
        "</tr>"
        for item in section.manifest_hotspots
    )
    hotspots_table = (
        "<table><thead><tr>"
        "<th>#</th><th>Path</th><th>Source role</th><th>Ecosystem</th>"
        "<th>Manifest type</th><th>Active</th><th>Management</th><th>Plugins</th>"
        "<th>Findings</th><th>Rules</th><th>Highest severity</th><th>Diagnostics</th>"
        "</tr></thead><tbody>"
        f"{hotspots}</tbody></table>"
        if hotspots
        else ""
    )
    conclusions = "".join(
        "<article class='content-card conclusion-card card'>"
        f"<h4>{escape_html(item.title)}</h4>"
        f"<p>{escape_html(item.summary)}</p>"
        "<p class='muted'>"
        f"ID: <code>{escape_html(item.conclusion_id)}</code> · "
        f"Kind: {escape_html(item.kind)} · "
        f"Audience: {escape_html(item.audience)} · "
        f"Confidence: {escape_html(item.confidence)} · "
        f"Findings: {item.finding_count}"
        "</p>"
        "</article>"
        for item in section.conclusions
    )
    recommendations = "".join(
        "<article class='content-card recommendation-card card'>"
        f"<h4>{escape_html(item.title)}</h4>"
        f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
        f"<p>{escape_html(item.rationale)}</p>"
        f"<p class='muted'>"
        f"ID: <code>{escape_html(item.recommendation_id)}</code> · "
        f"{'Conditional' if item.conditional else 'Direct'} · "
        f"Audience: {escape_html(item.audience)}"
        "</p>"
        "</article>"
        for item in section.recommendations
    )
    coverage = section.coverage
    coverage_rows = (
        "<tr><td>Manifests discovered / supported / parsed / failed</td>"
        f"<td>{coverage.manifests_discovered} / {coverage.manifests_supported} / "
        f"{coverage.manifests_parsed} / {coverage.manifests_failed}</td></tr>"
        "<tr><td>Production parse failures</td>"
        f"<td>{coverage.production_parse_failures}</td></tr>"
        "<tr><td>Test/fixture parse failures</td>"
        f"<td>{coverage.test_fixture_parse_failures}</td></tr>"
        "<tr><td>Unsupported constructs</td>"
        f"<td>{coverage.unsupported_construct_count}</td></tr>"
        "<tr><td>Proven unresolved</td>"
        f"<td>{coverage.proven_unresolved_count}</td></tr>"
        "<tr><td>Unsupported resolution</td>"
        f"<td>{coverage.unsupported_resolution_count}</td></tr>"
        "<tr><td>Diagnostics (samples / total)</td>"
        f"<td>{len(coverage.diagnostic_samples)} / {coverage.diagnostic_total}</td></tr>"
    )
    coverage_table = (
        "<table><thead><tr><th>Coverage</th><th>Detail</th></tr></thead>"
        f"<tbody>{coverage_rows}</tbody></table>"
        f"<p class='muted'>{escape_html(coverage.note)}</p>"
    )
    diagnostic_samples = "".join(
        "<li>"
        f"<code>{escape_html(item.diagnostic_code)}</code> — "
        f"{escape_html(item.message)}"
        + (f" (<code>{escape_html(item.path)}</code>)" if item.path else "")
        + f" · source role: {escape_html(item.source_role)}"
        "</li>"
        for item in coverage.diagnostic_samples
    )
    diagnostics_block = (
        f"<details><summary>Diagnostic samples "
        f"({len(coverage.diagnostic_samples)} of {coverage.diagnostic_total})"
        "</summary><ul>"
        f"{diagnostic_samples or '<li>None</li>'}"
        "</ul></details>"
        if coverage.diagnostic_total
        else ""
    )
    limitations = _limitation_items(section.limitations)
    limitations_block = f"<ul>{limitations}</ul>" if limitations else ""
    trace = ""
    parts = [
        _domain_status_header(section),
        "<h3>Executive Summary</h3>",
        f"<p>{escape_html(section.executive_summary)}</p>",
    ]
    if landscape_table:
        parts.extend(["<h3>Dependency Landscape</h3>", landscape_table])
    parts.extend(["<h3>Production Dependency Hygiene</h3>", production_block])
    if test_block:
        parts.extend(
            [
                "<h3>Test and Fixture Observations</h3>",
                "<p class='muted'>Test/fixture findings are not production health signals.</p>",
                test_block,
            ]
        )
    if hotspots_table:
        parts.extend(
            [
                "<h3>Manifest Hotspots</h3>",
                f"<p class='muted'>{escape_html(section.hotspot_presentation_note)}</p>",
                hotspots_table,
            ]
        )
    if conclusions:
        parts.extend(["<h4>Conclusions</h4>", conclusions])
    if recommendations:
        parts.extend(["<h4>Recommendations</h4>", recommendations])
    parts.extend(["<h3>Coverage and Limitations</h3>", coverage_table])
    if diagnostics_block:
        parts.append(diagnostics_block)
    if limitations_block:
        parts.append(limitations_block)
    if trace:
        parts.extend(["<h3>Traceability</h3>", trace])
    return "\n".join(parts)


def _render_security_intelligence(section: SecurityIntelligenceSection) -> str:
    """Epic 3 Slice 3.6 Security Intelligence pack body."""

    parts: list[str] = [
        "<div class='domain-header'>"
        f"<span class='{_status_badge_class(section.status_label)}'>"
        f"{escape_html(section.status_label)}</span>"
        f"<span class='muted'>{escape_html(section.status_summary)}</span>"
        "</div>"
    ]

    if section.overview_facts:
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(fact.label)}</td>"
            + f"<td>{escape_html(fact.value)}</td>"
            + f"<td>{escape_html(fact.note) if fact.note else '—'}</td>"
            + "</tr>"
            for fact in section.overview_facts
        )
        parts.append(
            '<div class="sec-intel-group" data-group="security_overview">\n'
            + "<h4>Security overview</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr><th>Fact</th><th>Value</th><th>Note</th></tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    if section.artifacts:
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(item.classification)}</td>"
            + f"<td>{escape_html(item.kind) if item.kind else '—'}</td>"
            + _optional_code_td(item.path)
            + f"<td>{escape_html(item.note) if item.note else '—'}</td>"
            + "</tr>"
            for item in section.artifacts
        )
        parts.append(
            '<div class="sec-intel-group" data-group="security_sensitive_artifacts">\n'
            + "<h4>Sensitive artifact inventory</h4>\n"
            + '<p class="muted">Classification and relative path only. Values are '
            + "never shown.</p>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Classification</th><th>Kind</th><th>Path</th><th>Note</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    if section.config_observations:
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(item.label)}</td>"
            + _optional_code_td(item.path)
            + _optional_id_links_td(
                (item.evidence_id,) if item.evidence_id else (),
                evidence_anchor,
            )
            + f"<td>{escape_html(item.redacted_snippet) if item.redacted_snippet else '—'}</td>"
            + f"<td>{escape_html(item.note) if item.note else '—'}</td>"
            + "</tr>"
            for item in section.config_observations
        )
        parts.append(
            '<div class="sec-intel-group" data-group="security_config_observations">\n'
            + "<h4>Configuration observations</h4>\n"
            + '<p class="muted">Fact labels from deterministic findings only. '
            + "Raw configuration values are not shown.</p>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Observation</th><th>Path</th><th>Evidence</th>"
            + "<th>Redacted snippet</th><th>Note</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    if section.findings:
        rows = "".join(
            "<tr>"
            + f"<td><a class='id-link' href='#{escape_html(finding_anchor(item.finding_id))}'>"
            + f"{escape_html(item.title)}</a></td>"
            + f"<td>{escape_html(item.severity)}</td>"
            + f"<td>{escape_html(item.confidence)}</td>"
            + f"<td><code>{escape_html(item.rule_id)}</code></td>"
            + _optional_code_td(item.path)
            + f"<td>{_render_id_links(item.evidence_ids, evidence_anchor)}</td>"
            + "</tr>"
            for item in section.findings
        )
        parts.append(
            '<div class="sec-intel-group" data-group="security_findings">\n'
            + "<h4>Security findings</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Finding</th><th>Severity</th><th>Confidence</th>"
            + "<th>Rule</th><th>Path</th><th>Evidence</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )
    elif section.empty_findings_message:
        parts.append(f"<p class='muted'>{escape_html(section.empty_findings_message)}</p>")

    if section.recommendations:
        rows = "".join(
            "<tr>"
            + _recommendation_td(item.recommendation_id, item.title)
            + f"<td>{escape_html(item.priority) if item.priority else '—'}</td>"
            + f"<td>{_render_id_links(item.finding_ids, finding_anchor)}</td>"
            + "</tr>"
            for item in section.recommendations
        )
        parts.append(
            '<div class="sec-intel-group" data-group="security_recommendations">\n'
            + "<h4>Security recommendations</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Recommendation</th><th>Priority</th><th>Supporting findings</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    parts.append(
        render_coverage_confidence_limitations(
            coverage_rows=section.coverage_rows,
            confidence=section.confidence,
            confidence_label=section.confidence_label,
            limitations=section.limitations,
        )
    )

    return "\n".join(parts)


def _render_security(section: SecurityReportSection) -> str:
    coverage = section.coverage_summary
    finding = section.finding_summary
    coverage_rows = (
        "<tr><td>Evidence status</td>"
        f"<td>{escape_html(coverage.evidence_status or '—')}</td></tr>"
        "<tr><td>Candidate artifacts discovered / inspected</td>"
        f"<td>{coverage.candidate_artifacts_discovered} / "
        f"{coverage.artifacts_inspected}</td></tr>"
        "<tr><td>Structured files parsed / configuration facts</td>"
        f"<td>{coverage.structured_files_parsed} / "
        f"{coverage.configuration_facts_collected}</td></tr>"
        "<tr><td>Rules registered / executed</td>"
        f"<td>{coverage.rules_registered} / {coverage.rules_executed}</td></tr>"
        "<tr><td>Malformed / unsupported / skipped files</td>"
        f"<td>{coverage.malformed_files} / {coverage.unsupported_binaries} / "
        f"{coverage.skipped_files}</td></tr>"
        "<tr><td>Source roles represented</td>"
        f"<td>{escape_html(', '.join(coverage.source_roles_represented) or '—')}</td></tr>"
        "<tr><td>Formats represented</td>"
        f"<td>{escape_html(', '.join(coverage.formats_represented) or '—')}</td></tr>"
    )
    coverage_table = (
        "<table><thead><tr><th>Coverage</th><th>Detail</th></tr></thead>"
        f"<tbody>{coverage_rows}</tbody></table>"
        f"<p class='muted'>{escape_html(coverage.note)}</p>"
    )
    status_block = (
        f"<p><strong>Assessment status:</strong> "
        f"{escape_html(section.assessment_status)}</p>"
        f"{coverage_table}"
    )
    if finding.production_finding_count == 0 and finding.none_detected_statement:
        none_stmt = finding.none_detected_statement
        lowered = none_stmt.lower()
        soft_fragments = (
            "secure repository",
            "repository appears secure",
            "security posture is healthy",
            "secure implementation",
            "low security risk",
            "low risk",
            "production secure",
            "no vulnerabilities",
            "no security issues",
            "no significant security risks",
            "compliant",
            "hardened",
            "security passed",
            "safe to deploy",
            "vulnerability-free",
        )
        if any(fragment in lowered for fragment in soft_fragments):
            none_stmt = (
                "No security findings were produced within the assessed "
                + "repository scope. This assessment evaluated static repository "
                + "evidence only. Absence of findings should not be interpreted "
                + "as absence of security risk."
            )
        production_findings = f"<p>{escape_html(none_stmt)}</p>"
    else:
        production_findings = (
            "".join(
                "<article class='card'>"
                + f"<h4>{escape_html(item.title)}</h4>"
                + f"<p>{escape_html(item.explanation or '')}</p>"
                + (
                    f"<p><strong>Remediation:</strong> {escape_html(item.remediation)}</p>"
                    if item.remediation
                    else ""
                )
                + "<p class='muted'>"
                f"ID: <code>{escape_html(item.finding_id)}</code> · "
                + f"Rule: <code>{escape_html(item.rule_id)}</code> · "
                + f"Severity: {escape_html(item.severity)} · "
                + f"Category: {escape_html(item.category)} · "
                + f"Source role: {escape_html(item.source_role)}"
                + (f" · Path: <code>{escape_html(item.path)}</code>" if item.path else "")
                + "</p></article>"
                for item in finding.production_findings
            )
            or "<p class='muted'>No production-role findings displayed.</p>"
        )
    production_block = (
        f"<p class='muted'>Production findings: "
        f"{finding.production_finding_count} "
        f"(showing {finding.production_findings_displayed})</p>"
        f"{production_findings}"
    )
    if finding.additional_observations:
        additional_block = (
            "<p class='muted'>Test, fixture, and unknown-role observations "
            + f"({finding.test_finding_count} test/fixture, "
            + f"{finding.unknown_finding_count} unknown). These do not contribute "
            + "to the production-primary view.</p>"
            + "".join(
                "<article class='card'>"
                + f"<h4>{escape_html(item.title)}</h4>"
                + f"<p>{escape_html(item.explanation or '')}</p>"
                + "<p class='muted'>"
                + f"ID: <code>{escape_html(item.finding_id)}</code> · "
                + f"Rule: <code>{escape_html(item.rule_id)}</code> · "
                + f"Source role: {escape_html(item.source_role)}"
                + (f" · Path: <code>{escape_html(item.path)}</code>" if item.path else "")
                + "</p></article>"
                for item in finding.additional_observations
            )
        )
    else:
        additional_block = ""
    themes = "".join(
        "<article class='content-card conclusion-card card'>"
        f"<h4>{escape_html(item.title)}</h4>"
        f"<p>{escape_html(item.summary)}</p>"
        "<p class='muted'>"
        f"ID: <code>{escape_html(item.theme_id)}</code> · "
        f"Kind: {escape_html(item.kind)} · "
        f"Scope: {escape_html(item.scope)} · "
        f"Source role: {escape_html(item.source_role)} · "
        f"Findings: {item.finding_count}"
        "</p></article>"
        for item in section.themes
    )
    hotspots = "".join(
        "<tr>"
        f"<td>{item.presentation_order}</td>"
        f"<td><code>{escape_html(item.path)}</code></td>"
        f"<td>{item.production_finding_count}</td>"
        f"<td>{item.test_finding_count}</td>"
        f"<td>{item.unknown_finding_count}</td>"
        f"<td>{item.total_finding_count}</td>"
        f"<td>{escape_html(item.highest_severity)}</td>"
        f"<td>{escape_html(', '.join(item.rule_ids) or '—')}</td>"
        f"<td>{escape_html(', '.join(item.categories) or '—')}</td>"
        "</tr>"
        for item in section.hotspots
    )
    hotspots_table = (
        "<table><thead><tr>"
        "<th>#</th><th>Location</th><th>Production</th><th>Test/fixture</th>"
        "<th>Unknown</th><th>Total</th><th>Highest severity</th>"
        "<th>Rules</th><th>Categories</th>"
        "</tr></thead><tbody>"
        f"{hotspots}</tbody></table>"
        if hotspots
        else ""
    )
    conclusions = "".join(
        "<article class='content-card conclusion-card card'>"
        f"<h4>{escape_html(item.title)}</h4>"
        f"<p>{escape_html(item.summary)}</p>"
        "<p class='muted'>"
        f"ID: <code>{escape_html(item.conclusion_id)}</code> · "
        f"Kind: {escape_html(item.kind)} · "
        f"Audience: {escape_html(item.audience)} · "
        f"Confidence: {escape_html(item.confidence)} · "
        f"Findings: {item.finding_count}"
        "</p></article>"
        for item in section.conclusions
    )
    if section.recommendation_groups:
        recommendations = "".join(
            f"<h4>{escape_html(group.group)}</h4>"
            + "".join(
                "<article class='card'>"
                + f"<h5>{escape_html(item.title)}</h5>"
                + f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
                + f"<p>{escape_html(item.rationale)}</p>"
                + "<p class='muted'>"
                + f"ID: <code>{escape_html(item.recommendation_id)}</code> · "
                + f"{'Conditional' if item.conditional else 'Direct'} · "
                + f"Audience: {escape_html(item.audience)}"
                + "</p></article>"
                for item in group.recommendations
            )
            for group in section.recommendation_groups
        )
    else:
        recommendations = "".join(
            "<article class='card'>"
            + f"<h4>{escape_html(item.title)}</h4>"
            + f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
            + f"<p>{escape_html(item.rationale)}</p>"
            + "<p class='muted'>"
            + f"ID: <code>{escape_html(item.recommendation_id)}</code> · "
            + f"{'Conditional' if item.conditional else 'Direct'} · "
            + f"Audience: {escape_html(item.audience)}"
            + "</p></article>"
            for item in section.recommendations
        )
    diagnostics_block = ""
    limitations = _limitation_items(section.limitations)
    limitations_block = f"<ul>{limitations}</ul>" if limitations else ""
    trace = ""
    parts = [
        _domain_status_header(section),
        "<h3>Executive Summary</h3>",
        f"<p>{escape_html(section.executive_summary)}</p>",
        "<h3>Assessment and Coverage Status</h3>",
        status_block,
        "<h3>Production-Primary Findings</h3>",
        production_block,
    ]
    if additional_block:
        parts.extend(
            [
                "<h3>Additional Test/Fixture/Unknown Observations</h3>",
                additional_block,
            ]
        )
    if themes:
        parts.extend(
            [
                "<h3>Security Themes</h3>",
                f"<p class='muted'>Showing {section.themes_displayed} of "
                + f"{section.themes_total}</p>",
                themes,
            ]
        )
    if hotspots_table:
        parts.extend(
            [
                "<h3>Finding Hotspots</h3>",
                f"<p class='muted'>{escape_html(section.hotspot_presentation_note)}</p>",
                hotspots_table,
            ]
        )
    if conclusions:
        parts.extend(
            [
                "<h4>Conclusions</h4>",
                f"<p class='muted'>Showing {section.conclusions_displayed} of "
                + f"{section.conclusions_total}</p>",
                conclusions,
            ]
        )
    if recommendations:
        parts.extend(
            [
                "<h4>Recommendations</h4>",
                f"<p class='muted'>Showing {section.recommendations_displayed} of "
                + f"{section.recommendations_total}</p>",
                recommendations,
            ]
        )
    if diagnostics_block:
        parts.extend(["<h3>Coverage Diagnostics</h3>", diagnostics_block])
    if limitations_block:
        parts.extend(["<h4>Limitations</h4>", limitations_block])
    if trace:
        parts.extend(["<h3>Traceability</h3>", trace])
    return "\n".join(parts)


def _render_testing(section: TestingReportSection) -> str:
    coverage = section.coverage_summary
    execution = section.execution_summary
    inventory = section.inventory_summary
    coverage_rows = "".join(
        "<tr>"
        f"<td><code>{escape_html(area.area_id)}</code></td>"
        f"<td>{escape_html(area.status)}</td>"
        f"<td>{area.numerator if area.numerator is not None else '—'}"
        f" / {area.denominator if area.denominator is not None else '—'}</td>"
        f"<td>{escape_html(area.maturity)}</td>"
        "</tr>"
        for area in coverage.areas
    )
    coverage_table = (
        "<table><thead><tr><th>Area</th><th>Status</th>"
        "<th>Numerator / Denominator</th><th>Maturity</th></tr></thead>"
        f"<tbody>{coverage_rows or '<tr><td colspan="4">—</td></tr>'}"
        "</tbody></table>"
        f"<p class='muted'>{escape_html(coverage.note)}</p>"
    )
    execution_rows = (
        "<tr><td>Rules planned / executed</td>"
        f"<td>{execution.rules_planned} / {execution.rules_executed}</td></tr>"
        "<tr><td>Matched / not matched / not applicable / failed</td>"
        f"<td>{execution.rules_matched} / {execution.rules_not_matched} / "
        f"{execution.rules_not_applicable} / {execution.rules_failed}</td></tr>"
        "<tr><td>Findings / themes / conclusions / recommendations</td>"
        f"<td>{execution.total_finding_count} / {execution.theme_count} / "
        f"{execution.conclusion_count} / {execution.recommendation_count}</td></tr>"
    )
    rule_rows = "".join(
        "<tr>"
        f"<td><code>{escape_html(item.rule_id)}</code></td>"
        f"<td>{'yes' if item.executed else 'no'}</td>"
        f"<td>{escape_html(item.evaluation_status)}</td>"
        f"<td>{item.finding_count}</td>"
        "</tr>"
        for item in execution.entries
    )
    execution_table = (
        "<table><thead><tr><th>Metric</th><th>Value</th></tr></thead>"
        f"<tbody>{execution_rows}</tbody></table>"
        + (
            "<table><thead><tr><th>Rule</th><th>Executed</th>"
            + "<th>Status</th><th>Findings</th></tr></thead>"
            + f"<tbody>{rule_rows}</tbody></table>"
            if rule_rows
            else ""
        )
        + f"<p class='muted'>{escape_html(execution.note)}</p>"
    )
    bucket_block = (
        "<p class='muted'>By rule: "
        + escape_html(", ".join(f"{item.key}={item.count}" for item in inventory.by_rule) or "—")
        + "</p><p class='muted'>By severity: "
        + escape_html(
            ", ".join(f"{item.key}={item.count}" for item in inventory.by_severity) or "—"
        )
        + "</p><p class='muted'>By confidence: "
        + escape_html(
            ", ".join(f"{item.key}={item.count}" for item in inventory.by_confidence) or "—"
        )
        + "</p>"
    )
    if inventory.finding_count == 0 and inventory.none_detected_statement:
        inventory_body = f"<p>{escape_html(inventory.none_detected_statement)}</p>"
    else:
        inventory_body = (
            "<p class='muted'>Finding IDs "
            + f"(showing {inventory.finding_ids_displayed} of "
            + f"{inventory.finding_count}):</p><ul>"
            + "".join(
                f"<li><code>{escape_html(finding_id)}</code></li>"
                for finding_id in inventory.finding_ids
            )
            + "</ul>"
        )
    themes = "".join(
        "<article class='content-card conclusion-card card'>"
        f"<h4>{escape_html(item.title)}</h4>"
        f"<p>{escape_html(item.summary)}</p>"
        "<p class='muted'>"
        f"ID: <code>{escape_html(item.theme_id)}</code> · "
        f"Kind: {escape_html(item.kind)} · "
        f"Scope: {escape_html(item.scope)} · "
        f"Findings: {item.finding_count}"
        "</p></article>"
        for item in section.themes
    )
    conclusions = "".join(
        "<article class='content-card conclusion-card card'>"
        f"<h4>{escape_html(item.title)}</h4>"
        f"<p>{escape_html(item.summary)}</p>"
        "<p class='muted'>"
        f"ID: <code>{escape_html(item.conclusion_id)}</code> · "
        f"Kind: {escape_html(item.kind)} · "
        f"Audience: {escape_html(item.audience)} · "
        f"Confidence: {escape_html(item.confidence)} · "
        f"Findings: {item.finding_count}"
        "</p></article>"
        for item in section.conclusions
    )
    if section.recommendation_groups:
        recommendations = "".join(
            f"<h4>{escape_html(group.group)}</h4>"
            + "".join(
                "<article class='card'>"
                + f"<h5>{escape_html(item.title)}</h5>"
                + f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
                + f"<p>{escape_html(item.rationale)}</p>"
                + "<p class='muted'>"
                + f"ID: <code>{escape_html(item.recommendation_id)}</code> · "
                + f"{'Conditional' if item.conditional else 'Direct'} · "
                + f"Audience: {escape_html(item.audience)}"
                + (
                    " · Findings: "
                    + ", ".join(f"<code>{escape_html(fid)}</code>" for fid in item.finding_ids)
                    if item.finding_ids
                    else ""
                )
                + "</p></article>"
                for item in group.recommendations
            )
            for group in section.recommendation_groups
        )
    else:
        recommendations = "".join(
            "<article class='card'>"
            + f"<h4>{escape_html(item.title)}</h4>"
            + f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
            + f"<p>{escape_html(item.rationale)}</p>"
            + "<p class='muted'>"
            + f"ID: <code>{escape_html(item.recommendation_id)}</code>"
            + "</p></article>"
            for item in section.recommendations
        )
    diagnostics_block = ""
    limitations = _limitation_items(section.limitations)
    limitations_block = f"<ul>{limitations}</ul>" if limitations else ""
    trace = ""
    parts = [
        _domain_status_header(section),
        "<h3>Overall Test Posture</h3>",
        f"<p>{escape_html(section.overall_posture_summary or section.executive_summary)}</p>",
        "<h3>Executive Summary</h3>",
        f"<p>{escape_html(section.executive_summary)}</p>",
        "<h3>Assessment and Coverage Status</h3>",
        f"<p><strong>Assessment status:</strong> {escape_html(section.assessment_status)}</p>",
        coverage_table,
        "<h3>Rule Execution Summary</h3>",
        execution_table,
        "<h3>Inventory Summary</h3>",
        bucket_block,
        inventory_body,
    ]
    if themes:
        parts.extend(
            [
                "<h4>Themes</h4>",
                f"<p class='muted'>Showing {section.themes_displayed} of "
                + f"{section.themes_total}</p>",
                themes,
            ]
        )
    if conclusions:
        parts.extend(
            [
                "<h4>Conclusions</h4>",
                f"<p class='muted'>Showing {section.conclusions_displayed} of "
                + f"{section.conclusions_total}</p>",
                conclusions,
            ]
        )
    if recommendations:
        parts.extend(
            [
                "<h4>Recommendations</h4>",
                f"<p class='muted'>Showing {section.recommendations_displayed} of "
                + f"{section.recommendations_total}</p>",
                recommendations,
            ]
        )
    if diagnostics_block:
        parts.extend(["<h3>Diagnostics</h3>", diagnostics_block])
    if limitations_block:
        parts.extend(["<h4>Limitations</h4>", limitations_block])
    if trace:
        parts.extend(["<h3>Traceability</h3>", trace])
    return "\n".join(parts)


def _render_cloud_intelligence(section: CloudIntelligenceSection) -> str:
    """Epic 3 Slice 3.7 Cloud Readiness Intelligence pack body."""

    parts: list[str] = [
        "<div class='domain-header'>"
        f"<span class='{_status_badge_class(section.status_label)}'>"
        f"{escape_html(section.status_label)}</span>"
        f"<span class='muted'>{escape_html(section.status_summary)}</span>"
        "</div>"
    ]

    if section.overview_facts:
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(fact.label)}</td>"
            + f"<td>{escape_html(fact.value)}</td>"
            + f"<td>{escape_html(fact.note) if fact.note else '—'}</td>"
            + "</tr>"
            for fact in section.overview_facts
        )
        parts.append(
            '<div class="cloud-intel-group" data-group="cloud_overview">\n'
            + "<h4>Cloud overview</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr><th>Fact</th><th>Value</th><th>Note</th></tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    for group in section.signal_groups:
        if not group.signals:
            continue
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(item.label)}</td>"
            + f"<td><code>{escape_html(item.family)}</code></td>"
            + _optional_code_td(item.path)
            + _optional_id_links_td(
                (item.finding_id,) if item.finding_id else (),
                finding_anchor,
            )
            + f"<td>{_render_id_links(item.evidence_ids, evidence_anchor)}</td>"
            + f"<td>{escape_html(item.note) if item.note else '—'}</td>"
            + "</tr>"
            for item in group.signals
        )
        parts.append(
            f'<div class="cloud-intel-group" data-group="{escape_html(group.group_id)}">\n'
            + f"<h4>{escape_html(group.title)}</h4>\n"
            + '<p class="muted">Repository-observable declarations only. Detected '
            + "signals do not prove successful deployment.</p>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Signal</th><th>Family</th><th>Path</th>"
            + "<th>Finding</th><th>Evidence</th><th>Note</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    if section.findings:
        rows = "".join(
            "<tr>"
            + f"<td><a class='id-link' href='#{escape_html(finding_anchor(item.finding_id))}'>"
            + f"{escape_html(item.title)}</a></td>"
            + f"<td>{escape_html(item.severity)}</td>"
            + f"<td>{escape_html(item.confidence)}</td>"
            + f"<td><code>{escape_html(item.rule_id)}</code></td>"
            + _optional_code_td(item.path)
            + f"<td>{_render_id_links(item.evidence_ids, evidence_anchor)}</td>"
            + "</tr>"
            for item in section.findings
        )
        parts.append(
            '<div class="cloud-intel-group" data-group="cloud_findings">\n'
            + "<h4>Cloud findings</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Finding</th><th>Severity</th><th>Confidence</th>"
            + "<th>Rule</th><th>Path</th><th>Evidence</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )
    elif section.empty_findings_message:
        parts.append(f"<p class='muted'>{escape_html(section.empty_findings_message)}</p>")

    if section.recommendations:
        rows = "".join(
            "<tr>"
            + _recommendation_td(item.recommendation_id, item.title)
            + f"<td>{escape_html(item.priority) if item.priority else '—'}</td>"
            + f"<td>{_render_id_links(item.finding_ids, finding_anchor)}</td>"
            + "</tr>"
            for item in section.recommendations
        )
        parts.append(
            '<div class="cloud-intel-group" data-group="cloud_recommendations">\n'
            + "<h4>Cloud recommendations</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Recommendation</th><th>Priority</th><th>Supporting findings</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    parts.append(
        render_coverage_confidence_limitations(
            coverage_rows=section.coverage_rows,
            confidence=section.confidence,
            confidence_label=section.confidence_label,
            limitations=section.limitations,
        )
    )

    return "\n".join(parts)


def _render_ai_readiness_intelligence(section: AiReadinessIntelligenceSection) -> str:
    """Epic 3 Slice 3.8 AI Readiness Intelligence pack body."""

    parts: list[str] = [
        "<div class='domain-header'>"
        f"<span class='{_status_badge_class(section.status_label)}'>"
        f"{escape_html(section.status_label)}</span>"
        f"<span class='muted'>{escape_html(section.status_summary)}</span>"
        "</div>"
    ]

    if section.overview_facts:
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(fact.label)}</td>"
            + f"<td>{escape_html(fact.value)}</td>"
            + f"<td>{escape_html(fact.note) if fact.note else '—'}</td>"
            + "</tr>"
            for fact in section.overview_facts
        )
        parts.append(
            '<div class="ai-intel-group" data-group="ai_readiness_overview">\n'
            + "<h4>AI readiness overview</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr><th>Fact</th><th>Value</th><th>Note</th></tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    for group in section.signal_groups:
        if not group.signals:
            continue
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(item.label)}</td>"
            + f"<td><code>{escape_html(item.family)}</code></td>"
            + _optional_code_td(item.path)
            + _optional_id_links_td(
                (item.finding_id,) if item.finding_id else (),
                finding_anchor,
            )
            + f"<td>{_render_id_links(item.evidence_ids, evidence_anchor)}</td>"
            + f"<td>{escape_html(item.note) if item.note else '—'}</td>"
            + "</tr>"
            for item in group.signals
        )
        parts.append(
            f'<div class="ai-intel-group" data-group="{escape_html(group.group_id)}">\n'
            + f"<h4>{escape_html(group.title)}</h4>\n"
            + '<p class="muted">Repository-observable AI-enablement signals only. '
            + "Detected integrations do not prove production use.</p>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Signal</th><th>Family</th><th>Path</th>"
            + "<th>Finding</th><th>Evidence</th><th>Note</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    if section.findings:
        rows = "".join(
            "<tr>"
            + f"<td><a class='id-link' href='#{escape_html(finding_anchor(item.finding_id))}'>"
            + f"{escape_html(item.title)}</a></td>"
            + f"<td>{escape_html(item.severity)}</td>"
            + f"<td>{escape_html(item.confidence)}</td>"
            + f"<td><code>{escape_html(item.rule_id)}</code></td>"
            + _optional_code_td(item.path)
            + f"<td>{_render_id_links(item.evidence_ids, evidence_anchor)}</td>"
            + "</tr>"
            for item in section.findings
        )
        parts.append(
            '<div class="ai-intel-group" data-group="ai_readiness_findings">\n'
            + "<h4>AI readiness findings</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Finding</th><th>Severity</th><th>Confidence</th>"
            + "<th>Rule</th><th>Path</th><th>Evidence</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )
    elif section.empty_findings_message:
        parts.append(f"<p class='muted'>{escape_html(section.empty_findings_message)}</p>")

    if section.recommendations:
        rows = "".join(
            "<tr>"
            + _recommendation_td(item.recommendation_id, item.title)
            + f"<td>{escape_html(item.priority) if item.priority else '—'}</td>"
            + f"<td>{_render_id_links(item.finding_ids, finding_anchor)}</td>"
            + "</tr>"
            for item in section.recommendations
        )
        parts.append(
            '<div class="ai-intel-group" data-group="ai_readiness_recommendations">\n'
            + "<h4>AI readiness recommendations</h4>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Recommendation</th><th>Priority</th><th>Supporting findings</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    parts.append(
        render_coverage_confidence_limitations(
            coverage_rows=section.coverage_rows,
            confidence=section.confidence,
            confidence_label=section.confidence_label,
            limitations=section.limitations,
        )
    )

    return "\n".join(parts)


def _render_modernization_intelligence(section: ModernizationIntelligenceSection) -> str:
    """Epic 3 Slice 3.9 Modernization Assessment Intelligence pack body."""

    parts: list[str] = [
        "<div class='domain-header'>"
        f"<span class='{_status_badge_class(section.status_label)}'>"
        f"{escape_html(section.status_label)}</span>"
        f"<span class='muted'>{escape_html(section.status_summary)}</span>"
        "</div>"
    ]

    if section.overview_facts:
        rows = "".join(
            "<tr>"
            + f"<td>{escape_html(fact.label)}</td>"
            + f"<td>{escape_html(fact.value)}</td>"
            + f"<td>{escape_html(fact.note) if fact.note else '—'}</td>"
            + "</tr>"
            for fact in section.overview_facts
        )
        parts.append(
            '<div class="mod-intel-group" data-group="modernization_overview">\n'
            + "<h4>Modernization overview</h4>\n"
            + '<p class="muted">Synthesis of deterministic findings, recommendations, '
            + "Priority Actions, and roadmap initiatives. This is not an independent "
            + "analyzer.</p>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr><th>Fact</th><th>Value</th><th>Note</th></tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    if section.contributing_heads:
        rows = "".join(
            "<tr>"
            + f'<td><a class="id-link" href="#{escape_html(item.anchor)}">'
            + f"{escape_html(item.title)}</a></td>"
            + f"<td>{item.finding_count}</td>"
            + f"<td>{item.recommendation_count}</td>"
            + f"<td>{item.priority_action_count}</td>"
            + "</tr>"
            for item in section.contributing_heads
        )
        parts.append(
            '<div class="mod-intel-group" data-group="contributing_heads">\n'
            + "<h4>Contributing assessment heads</h4>\n"
            + '<p class="muted">Entities retain their original assessment-head '
            + "classification. A Security recommendation remains Security Intelligence "
            + "even when it contributes to modernization.</p>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Assessment head</th><th>Findings</th>"
            + "<th>Recommendations</th><th>Priority Actions</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    if section.priority_actions:
        rows = "".join(
            "<tr>"
            + '<td><a class="id-link" href="#'
            + f'{escape_html(priority_action_anchor(item.action_id))}">'
            + f"{escape_html(item.title)}</a></td>"
            + f"<td>{escape_html(item.priority) if item.priority else '—'}</td>"
            + (
                "<td>"
                + f"{escape_html(item.presentation_bucket) if item.presentation_bucket else '—'}"
                + "</td>"
            )
            + f"<td>{escape_html(item.effort) if item.effort else '—'}</td>"
            + f"<td>{item.supporting_recommendation_count}</td>"
            + f"<td>{item.supporting_finding_count}</td>"
            + f"<td>{escape_html(item.head_title) if item.head_title else '—'}</td>"
            + _optional_text_td(item.evidence_completeness)
            + "</tr>"
            for item in section.priority_actions
        )
        parts.append(
            '<div class="mod-intel-group" data-group="priority_actions">\n'
            + "<h4>Priority Actions</h4>\n"
            + '<p class="muted">Canonical Priority Actions only. Full detail remains in '
            + '<a class="id-link" href="#priority-actions">Priority Actions</a>.</p>\n'
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Action</th><th>Priority</th><th>Horizon</th><th>Effort</th>"
            + "<th>Recs</th><th>Findings</th><th>Head</th><th>Evidence</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )
    elif section.empty_actions_message:
        parts.append(f"<p class='muted'>{escape_html(section.empty_actions_message)}</p>")

    if section.roadmap_phases:
        phase_blocks: list[str] = []
        for phase in section.roadmap_phases:
            if not phase.initiatives:
                continue
            legacy_note = (
                ' <span class="muted">(includes legacy items)</span>' if phase.has_legacy else ""
            )
            rows = "".join(
                "<tr>"
                + '<td><a class="id-link" href="#'
                + f'{escape_html(roadmap_initiative_anchor(item.initiative_id))}">'
                + f"{escape_html(item.title)}</a>"
                + f"{' <span class="badge">Legacy</span>' if item.is_legacy else ''}"
                + "</td>"
                + f"<td>{item.sequence}</td>"
                + f"<td>{escape_html(item.priority) if item.priority else '—'}</td>"
                + f"<td>{escape_html(item.effort) if item.effort else '—'}</td>"
                + _roadmap_supporting_td(item)
                + _optional_text_td(item.evidence_completeness)
                + "</tr>"
                for item in phase.initiatives
            )
            phase_blocks.append(
                f"<h5>{escape_html(phase.title)} "
                + f"<span class='count-pill'>{phase.initiative_count}</span>"
                + f"{legacy_note}</h5>\n"
                + '<div class="table-wrap"><table>\n'
                + "<thead><tr>"
                + "<th>Initiative</th><th>Sequence</th><th>Priority</th><th>Effort</th>"
                + "<th>Priority Actions</th><th>Evidence</th>"
                + "</tr></thead>\n"
                + f"<tbody>{rows}</tbody>\n</table></div>"
            )
        if phase_blocks:
            legacy_banner = (
                '<p class="muted">Legacy roadmap items are visibly marked and may '
                + "have limited traceability. The roadmap is planning guidance, not a "
                + "delivery commitment.</p>\n"
                if section.roadmap_is_legacy
                else '<p class="muted">Canonical Priority Action-backed roadmap. '
                "Full phase detail remains in "
                + '<a class="id-link" href="#phased-modernization-plan">'
                + "Roadmap</a>. Planning guidance, not a delivery commitment.</p>\n"
            )
            parts.append(
                '<div class="mod-intel-group" data-group="roadmap_phases">\n'
                + "<h4>Roadmap phases</h4>\n"
                + f"{legacy_banner}"
                + f"{''.join(phase_blocks)}\n"
                + "</div>"
            )

    if section.themes:
        rows = "".join(
            "<tr>"
            + f'<td><a class="id-link" href="#{escape_html(item.anchor)}">'
            + f"{escape_html(item.title)}</a></td>"
            + f"<td>{item.priority_action_count}</td>"
            + f"<td>{item.recommendation_count}</td>"
            + f"<td>{escape_html('; '.join(item.top_titles)) if item.top_titles else '—'}</td>"
            + "</tr>"
            for item in section.themes
        )
        parts.append(
            '<div class="mod-intel-group" data-group="modernization_themes">\n'
            + "<h4>Key modernization themes</h4>\n"
            + '<p class="muted">Themes are derived from assessment-head grouping of '
            + "deterministic Priority Actions and recommendations. Free-form narrative "
            + "themes are not invented.</p>\n"
            + '<div class="table-wrap"><table>\n'
            + "<thead><tr>"
            + "<th>Theme (assessment head)</th><th>Priority Actions</th>"
            + "<th>Recommendations</th><th>Top titles</th>"
            + "</tr></thead>\n"
            + f"<tbody>{rows}</tbody>\n</table></div>\n"
            + "</div>"
        )

    parts.append(
        render_coverage_confidence_limitations(
            coverage_rows=section.coverage_rows,
            confidence=section.confidence,
            confidence_label=section.confidence_label,
            limitations=section.limitations,
        )
    )

    return "\n".join(parts)


def _render_cloud(section: CloudReportSection) -> str:
    coverage = section.coverage_summary
    execution = section.execution_summary
    inventory = section.inventory_summary
    families = section.technology_family_summary
    _SAFE_CLOUD_POSTURE = (
        "Repository cloud signals were assessed from static evidence only. "
        "This does not establish cloud readiness, migration readiness, or a "
        "live deployment posture."
    )
    _SAFE_NONE_DETECTED = (
        "No cloud findings were produced within the assessed repository scope. "
        "Live cloud infrastructure and runtime posture were not assessed. Absence "
        "of findings does not establish cloud readiness."
    )
    posture = scrub_soft_cloud_claims(
        section.overall_posture_summary or section.executive_summary,
        fallback=_SAFE_CLOUD_POSTURE,
    )
    none_detected = None
    if inventory.none_detected_statement:
        none_detected = scrub_soft_cloud_claims(
            inventory.none_detected_statement,
            fallback=_SAFE_NONE_DETECTED,
        )
    coverage_rows = "".join(
        "<tr>"
        f"<td><code>{escape_html(area.area_id)}</code></td>"
        f"<td>{escape_html(area.status)}</td>"
        f"<td>{area.numerator if area.numerator is not None else '—'}"
        f" / {area.denominator if area.denominator is not None else '—'}</td>"
        f"<td>{escape_html(area.maturity)}</td>"
        "</tr>"
        for area in coverage.areas
    )
    coverage_table = (
        "<table><thead><tr><th>Area</th><th>Status</th>"
        "<th>Numerator / Denominator</th><th>Maturity</th></tr></thead>"
        f"<tbody>{coverage_rows or '<tr><td colspan="4">—</td></tr>'}"
        "</tbody></table>"
        f"<p class='muted'>{escape_html(coverage.note)}</p>"
    )
    execution_rows = (
        "<tr><td>Rules planned / executed</td>"
        f"<td>{execution.rules_planned} / {execution.rules_executed}</td></tr>"
        "<tr><td>Matched / not matched / not applicable / failed</td>"
        f"<td>{execution.rules_matched} / {execution.rules_not_matched} / "
        f"{execution.rules_not_applicable} / {execution.rules_failed}</td></tr>"
        "<tr><td>Findings / themes / conclusions / recommendations</td>"
        f"<td>{execution.total_finding_count} / {execution.theme_count} / "
        f"{execution.conclusion_count} / {execution.recommendation_count}</td></tr>"
    )
    rule_rows = "".join(
        "<tr>"
        f"<td><code>{escape_html(item.rule_id)}</code></td>"
        f"<td>{'yes' if item.executed else 'no'}</td>"
        f"<td>{escape_html(item.evaluation_status)}</td>"
        f"<td>{item.finding_count}</td>"
        "</tr>"
        for item in execution.entries
    )
    execution_table = (
        "<table><thead><tr><th>Metric</th><th>Value</th></tr></thead>"
        f"<tbody>{execution_rows}</tbody></table>"
        + (
            "<table><thead><tr><th>Rule</th><th>Executed</th>"
            + "<th>Status</th><th>Findings</th></tr></thead>"
            + f"<tbody>{rule_rows}</tbody></table>"
            if rule_rows
            else ""
        )
        + f"<p class='muted'>{escape_html(execution.note)}</p>"
    )
    family_rows = "".join(
        "<tr>"
        f"<td><code>{escape_html(item.family_id)}</code></td>"
        f"<td>{'yes' if item.observed else 'no'}</td>"
        f"<td>{item.finding_count}</td>"
        f"<td>{escape_html(', '.join(item.technologies) or '—')}</td>"
        "</tr>"
        for item in families.entries
    )
    family_table = (
        f"<p class='muted'>Observed {families.families_observed} of "
        f"{families.families_total} technology families.</p>"
        "<table><thead><tr><th>Family</th><th>Observed</th>"
        "<th>Findings</th><th>Technologies</th></tr></thead>"
        f"<tbody>{family_rows or '<tr><td colspan="4">—</td></tr>'}"
        "</tbody></table>"
        f"<p class='muted'>{escape_html(families.note)}</p>"
    )
    bucket_block = (
        "<p class='muted'>By rule: "
        + escape_html(", ".join(f"{item.key}={item.count}" for item in inventory.by_rule) or "—")
        + "</p><p class='muted'>By severity: "
        + escape_html(
            ", ".join(f"{item.key}={item.count}" for item in inventory.by_severity) or "—"
        )
        + "</p><p class='muted'>By confidence: "
        + escape_html(
            ", ".join(f"{item.key}={item.count}" for item in inventory.by_confidence) or "—"
        )
        + "</p>"
    )
    if inventory.finding_count == 0 and none_detected:
        inventory_body = f"<p>{escape_html(none_detected)}</p>"
    else:
        inventory_body = (
            "<p class='muted'>Finding IDs "
            + f"(showing {inventory.finding_ids_displayed} of "
            + f"{inventory.finding_count}):</p><ul>"
            + "".join(
                f"<li><code>{escape_html(finding_id)}</code></li>"
                for finding_id in inventory.finding_ids
            )
            + "</ul>"
        )
    themes = "".join(
        "<article class='content-card conclusion-card card'>"
        f"<h4>{escape_html(item.title)}</h4>"
        f"<p>{escape_html(item.summary)}</p>"
        "<p class='muted'>"
        f"ID: <code>{escape_html(item.theme_id)}</code> · "
        f"Kind: {escape_html(item.kind)} · "
        f"Scope: {escape_html(item.scope)} · "
        f"Findings: {item.finding_count}"
        "</p></article>"
        for item in section.themes
    )
    conclusions = "".join(
        "<article class='content-card conclusion-card card'>"
        f"<h4>{escape_html(item.title)}</h4>"
        f"<p>{escape_html(item.summary)}</p>"
        "<p class='muted'>"
        f"ID: <code>{escape_html(item.conclusion_id)}</code> · "
        f"Kind: {escape_html(item.kind)} · "
        f"Audience: {escape_html(item.audience)} · "
        f"Confidence: {escape_html(item.confidence)} · "
        f"Findings: {item.finding_count}"
        "</p></article>"
        for item in section.conclusions
    )
    if section.recommendation_groups:
        recommendations = "".join(
            f"<h4>{escape_html(group.group)}</h4>"
            + "".join(
                "<article class='card'>"
                + f"<h5>{escape_html(item.title)}</h5>"
                + f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
                + f"<p>{escape_html(item.rationale)}</p>"
                + "<p class='muted'>"
                + f"ID: <code>{escape_html(item.recommendation_id)}</code> · "
                + f"{'Conditional' if item.conditional else 'Direct'} · "
                + f"Audience: {escape_html(item.audience)}"
                + (
                    " · Findings: "
                    + ", ".join(f"<code>{escape_html(fid)}</code>" for fid in item.finding_ids)
                    if item.finding_ids
                    else ""
                )
                + "</p></article>"
                for item in group.recommendations
            )
            for group in section.recommendation_groups
        )
    else:
        recommendations = "".join(
            "<article class='card'>"
            + f"<h4>{escape_html(item.title)}</h4>"
            + f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
            + f"<p>{escape_html(item.rationale)}</p>"
            + "<p class='muted'>"
            + f"ID: <code>{escape_html(item.recommendation_id)}</code>"
            + "</p></article>"
            for item in section.recommendations
        )
    diagnostics_block = ""
    limitations = _limitation_items(section.limitations)
    limitations_block = f"<ul>{limitations}</ul>" if limitations else ""
    trace = ""
    parts = [
        _domain_status_header(section),
        "<h3>Overall Cloud Posture</h3>",
        f"<p>{escape_html(posture)}</p>",
        "<h3>Executive Summary</h3>",
        f"<p>{escape_html(section.executive_summary)}</p>",
        "<h3>Assessment and Coverage Status</h3>",
        f"<p><strong>Assessment status:</strong> {escape_html(section.assessment_status)}</p>",
        coverage_table,
        "<h3>Rule Execution Summary</h3>",
        execution_table,
        "<h3>Technology Family Inventory</h3>",
        family_table,
        "<h3>Finding Inventory Summary</h3>",
        bucket_block,
        inventory_body,
    ]
    if themes:
        parts.extend(
            [
                "<h4>Themes</h4>",
                f"<p class='muted'>Showing {section.themes_displayed} of "
                + f"{section.themes_total}</p>",
                themes,
            ]
        )
    if conclusions:
        parts.extend(
            [
                "<h4>Conclusions</h4>",
                f"<p class='muted'>Showing {section.conclusions_displayed} of "
                + f"{section.conclusions_total}</p>",
                conclusions,
            ]
        )
    if recommendations:
        parts.extend(
            [
                "<h4>Recommendations</h4>",
                f"<p class='muted'>Showing {section.recommendations_displayed} of "
                + f"{section.recommendations_total}</p>",
                recommendations,
            ]
        )
    if diagnostics_block:
        parts.extend(["<h3>Diagnostics</h3>", diagnostics_block])
    if limitations_block:
        parts.extend(["<h4>Limitations</h4>", limitations_block])
    if trace:
        parts.extend(["<h3>Traceability</h3>", trace])
    return "\n".join(parts)


def _render_ai_readiness(section: AiReadinessReportSection) -> str:
    coverage = section.coverage_summary
    execution = section.execution_summary
    inventory = section.inventory_summary
    families = section.capability_family_summary
    _SAFE_AI_POSTURE = (
        "Repository-observable AI-enablement signals were assessed from static "
        "evidence only. This does not establish AI readiness, agent readiness, "
        "or RAG readiness."
    )
    _SAFE_NONE_DETECTED = (
        "No AI readiness findings were produced within the assessed repository "
        "scope. Agent execution, RAG suitability, and live AI runtime posture "
        "were not assessed. Absence of findings does not establish AI readiness."
    )
    posture = scrub_soft_ai_readiness_claims(
        section.overall_posture_summary or section.executive_summary,
        fallback=_SAFE_AI_POSTURE,
    )
    none_detected = None
    if inventory.none_detected_statement:
        none_detected = scrub_soft_ai_readiness_claims(
            inventory.none_detected_statement,
            fallback=_SAFE_NONE_DETECTED,
        )
    coverage_rows = "".join(
        "<tr>"
        f"<td><code>{escape_html(area.area_id)}</code></td>"
        f"<td>{escape_html(area.status)}</td>"
        f"<td>{area.numerator if area.numerator is not None else '—'}"
        f" / {area.denominator if area.denominator is not None else '—'}</td>"
        f"<td>{escape_html(area.maturity)}</td>"
        "</tr>"
        for area in coverage.areas
    )
    coverage_table = (
        "<table><thead><tr><th>Area</th><th>Status</th>"
        "<th>Numerator / Denominator</th><th>Maturity</th></tr></thead>"
        f"<tbody>{coverage_rows or '<tr><td colspan="4">—</td></tr>'}"
        "</tbody></table>"
        f"<p class='muted'>{escape_html(coverage.note)}</p>"
    )
    execution_rows = (
        "<tr><td>Rules planned / executed</td>"
        f"<td>{execution.rules_planned} / {execution.rules_executed}</td></tr>"
        "<tr><td>Matched / not matched / not applicable / failed</td>"
        f"<td>{execution.rules_matched} / {execution.rules_not_matched} / "
        f"{execution.rules_not_applicable} / {execution.rules_failed}</td></tr>"
        "<tr><td>Findings / themes / conclusions / recommendations</td>"
        f"<td>{execution.total_finding_count} / {execution.theme_count} / "
        f"{execution.conclusion_count} / {execution.recommendation_count}</td></tr>"
    )
    rule_rows = "".join(
        "<tr>"
        f"<td><code>{escape_html(item.rule_id)}</code></td>"
        f"<td>{'yes' if item.executed else 'no'}</td>"
        f"<td>{escape_html(item.evaluation_status)}</td>"
        f"<td>{item.finding_count}</td>"
        "</tr>"
        for item in execution.entries
    )
    execution_table = (
        "<table><thead><tr><th>Metric</th><th>Value</th></tr></thead>"
        f"<tbody>{execution_rows}</tbody></table>"
        + (
            "<table><thead><tr><th>Rule</th><th>Executed</th>"
            + "<th>Status</th><th>Findings</th></tr></thead>"
            + f"<tbody>{rule_rows}</tbody></table>"
            if rule_rows
            else ""
        )
        + f"<p class='muted'>{escape_html(execution.note)}</p>"
    )
    family_rows = "".join(
        "<tr>"
        f"<td><code>{escape_html(item.family_id)}</code></td>"
        f"<td>{'yes' if item.observed else 'no'}</td>"
        f"<td>{item.finding_count}</td>"
        f"<td>{escape_html(', '.join(item.signals) or '—')}</td>"
        "</tr>"
        for item in families.entries
    )
    family_table = (
        f"<p class='muted'>Observed {families.families_observed} of "
        f"{families.families_total} capability families.</p>"
        "<table><thead><tr><th>Family</th><th>Observed</th>"
        "<th>Findings</th><th>Signals</th></tr></thead>"
        f"<tbody>{family_rows or '<tr><td colspan="4">—</td></tr>'}"
        "</tbody></table>"
        f"<p class='muted'>{escape_html(families.note)}</p>"
    )
    bucket_block = (
        "<p class='muted'>By rule: "
        + escape_html(", ".join(f"{item.key}={item.count}" for item in inventory.by_rule) or "—")
        + "</p><p class='muted'>By severity: "
        + escape_html(
            ", ".join(f"{item.key}={item.count}" for item in inventory.by_severity) or "—"
        )
        + "</p><p class='muted'>By confidence: "
        + escape_html(
            ", ".join(f"{item.key}={item.count}" for item in inventory.by_confidence) or "—"
        )
        + "</p>"
    )
    if inventory.finding_count == 0 and none_detected:
        inventory_body = f"<p>{escape_html(none_detected)}</p>"
    else:
        inventory_body = (
            "<p class='muted'>Finding IDs "
            + f"(showing {inventory.finding_ids_displayed} of "
            + f"{inventory.finding_count}):</p><ul>"
            + "".join(
                f"<li><code>{escape_html(finding_id)}</code></li>"
                for finding_id in inventory.finding_ids
            )
            + "</ul>"
        )
    themes = "".join(
        "<article class='content-card conclusion-card card'>"
        f"<h4>{escape_html(item.title)}</h4>"
        f"<p>{escape_html(item.summary)}</p>"
        "<p class='muted'>"
        f"ID: <code>{escape_html(item.theme_id)}</code> · "
        f"Kind: {escape_html(item.kind)} · "
        f"Scope: {escape_html(item.scope)} · "
        f"Findings: {item.finding_count}"
        "</p></article>"
        for item in section.themes
    )
    conclusions = "".join(
        "<article class='content-card conclusion-card card'>"
        f"<h4>{escape_html(item.title)}</h4>"
        f"<p>{escape_html(item.summary)}</p>"
        "<p class='muted'>"
        f"ID: <code>{escape_html(item.conclusion_id)}</code> · "
        f"Kind: {escape_html(item.kind)} · "
        f"Audience: {escape_html(item.audience)} · "
        f"Confidence: {escape_html(item.confidence)} · "
        f"Findings: {item.finding_count}"
        "</p></article>"
        for item in section.conclusions
    )
    if section.recommendation_groups:
        recommendations = "".join(
            f"<h4>{escape_html(group.group)}</h4>"
            + "".join(
                "<article class='card'>"
                + f"<h5>{escape_html(item.title)}</h5>"
                + f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
                + f"<p>{escape_html(item.rationale)}</p>"
                + "<p class='muted'>"
                + f"ID: <code>{escape_html(item.recommendation_id)}</code> · "
                + f"{'Conditional' if item.conditional else 'Direct'} · "
                + f"Audience: {escape_html(item.audience)}"
                + (
                    " · Findings: "
                    + ", ".join(f"<code>{escape_html(fid)}</code>" for fid in item.finding_ids)
                    if item.finding_ids
                    else ""
                )
                + "</p></article>"
                for item in group.recommendations
            )
            for group in section.recommendation_groups
        )
    else:
        recommendations = "".join(
            "<article class='card'>"
            + f"<h4>{escape_html(item.title)}</h4>"
            + f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
            + f"<p>{escape_html(item.rationale)}</p>"
            + "<p class='muted'>"
            + f"ID: <code>{escape_html(item.recommendation_id)}</code>"
            + "</p></article>"
            for item in section.recommendations
        )
    diagnostics_block = ""
    limitations = _limitation_items(section.limitations)
    limitations_block = f"<ul>{limitations}</ul>" if limitations else ""
    trace = ""
    parts = [
        _domain_status_header(section),
        "<h3>Overall AI Readiness Posture</h3>",
        f"<p>{escape_html(posture)}</p>",
        "<h3>Executive Summary</h3>",
        f"<p>{escape_html(section.executive_summary)}</p>",
        "<h3>Assessment and Coverage Status</h3>",
        f"<p><strong>Assessment status:</strong> {escape_html(section.assessment_status)}</p>",
        coverage_table,
        "<h3>Rule Execution Summary</h3>",
        execution_table,
        "<h3>Capability Family Inventory</h3>",
        family_table,
        "<h3>Finding Inventory Summary</h3>",
        bucket_block,
        inventory_body,
    ]
    if themes:
        parts.extend(
            [
                "<h4>Themes</h4>",
                f"<p class='muted'>Showing {section.themes_displayed} of "
                + f"{section.themes_total}</p>",
                themes,
            ]
        )
    if conclusions:
        parts.extend(
            [
                "<h4>Conclusions</h4>",
                f"<p class='muted'>Showing {section.conclusions_displayed} of "
                + f"{section.conclusions_total}</p>",
                conclusions,
            ]
        )
    if recommendations:
        parts.extend(
            [
                "<h4>Recommendations</h4>",
                f"<p class='muted'>Showing {section.recommendations_displayed} of "
                + f"{section.recommendations_total}</p>",
                recommendations,
            ]
        )
    if diagnostics_block:
        parts.extend(["<h3>Diagnostics</h3>", diagnostics_block])
    if limitations_block:
        parts.extend(["<h4>Limitations</h4>", limitations_block])
    if trace:
        parts.extend(["<h3>Traceability</h3>", trace])
    return "\n".join(parts)


def _render_phased_roadmap(view: HtmlReportViewModel) -> str:
    section = view.roadmap_report
    if section is None:
        return '<p class="muted">No phased modernization plan was produced.</p>'

    finding_titles = {item.finding_id: item.title for item in view.findings}
    recommendation_titles = {item.recommendation_id: item.title for item in view.priority_actions}

    phase_blocks: list[str] = []
    for phase in section.phases:
        initiatives = tuple(
            item
            for item in phase.initiatives
            if item.supporting_priority_action_ids or item.supporting_recommendation_ids
        )
        if not initiatives:
            continue
        cards = "".join(
            _roadmap_initiative_card(
                item,
                finding_titles=finding_titles,
                recommendation_titles=recommendation_titles,
            )
            for item in initiatives
        )
        phase_blocks.append(
            "<div class='roadmap-lane'>"
            + f"<h3>{escape_html(phase.title)} "
            + f"<span class='count-pill'>{len(initiatives)}</span></h3>"
            + f"<p class='muted'>{escape_html(phase.objective)}</p>"
            + f"<div class='card-stack'>{cards}</div>"
            + "</div>"
        )
    body = (
        "".join(phase_blocks)
        if phase_blocks
        else "<p class='muted'>No phased modernization initiatives were derived.</p>"
    )
    return "\n".join(
        [
            f"<p>{escape_html(section.summary)}</p>",
            f"<div class='roadmap'>{body}</div>",
        ]
    )


def _roadmap_initiative_card(
    item: object,
    *,
    finding_titles: dict[str, str],
    recommendation_titles: dict[str, str],
) -> str:
    """Compact leadership card with Priority Action traceability anchors."""

    initiative_id = str(getattr(item, "initiative_id", "") or "").strip()
    anchor_attr = (
        f' id="{escape_html(roadmap_initiative_anchor(initiative_id))}"' if initiative_id else ""
    )

    pa_ids = tuple(getattr(item, "supporting_priority_action_ids", ()) or ())
    initiative_type = str(getattr(item, "initiative_type", "legacy") or "legacy").strip().lower()
    is_legacy = initiative_type == "legacy"

    title = str(getattr(item, "summary", "") or "").strip()
    if pa_ids and pa_ids[0] in recommendation_titles:
        title = recommendation_titles[pa_ids[0]]
    elif not title:
        raw = str(getattr(item, "title", "")).strip()
        title = raw.split(" — ", 1)[-1].strip() if " — " in raw else raw
    if not title:
        title = "Modernization initiative"

    outcome = str(getattr(item, "expected_outcome", "") or "").strip()

    # Only link real supporting_priority_action_ids — never invent PA links for legacy.
    pa_html = ""
    if pa_ids and not is_legacy:
        pa_titles = tuple(recommendation_titles.get(pid, pid) for pid in pa_ids)
        pa_html = (
            "<p><em>Priority Actions</em> "
            + f"{_title_links(pa_ids, pa_titles, anchor_fn=priority_action_anchor, empty='None')}"
            + "</p>\n"
        )
    elif is_legacy:
        pa_html = '<p class="muted"><em>Legacy roadmap item</em> — Limited traceability</p>\n'

    related_findings = [
        finding_titles[fid]
        for fid in tuple(getattr(item, "supporting_finding_ids", ()) or ())
        if fid in finding_titles
    ]
    findings_html = ""
    if related_findings:
        label = "; ".join(related_findings[:3]) + (
            f" (+{len(related_findings) - 3} more)" if len(related_findings) > 3 else ""
        )
        findings_html = f"<p class='muted'>Findings: {escape_html(label)}</p>\n"

    completeness = completeness_label(
        str(getattr(item, "evidence_completeness", "legacy") or "legacy")
    )
    limitations = _render_limitations_block(
        getattr(item, "limitations", ()) or (),
        title="Traceability limitations",
    )
    legacy_badge = '<span class="badge">Legacy roadmap item</span> ' if is_legacy else ""
    return (
        f"<article class='card item-card'{anchor_attr}>"
        f"<h4>{legacy_badge}{escape_html(title)}</h4>"
        f"<p><strong>Business outcome:</strong> {escape_html(outcome)}</p>"
        f"{pa_html}"
        f"{findings_html}"
        f"<p><em>Evidence</em> {escape_html(completeness)}</p>"
        f"{limitations}"
        "</article>"
    )


def _render_performance(section: PerformanceReportSection) -> str:
    coverage = section.coverage_summary
    execution = section.execution_summary
    inventory = section.inventory_summary
    families = section.performance_family_summary
    coverage_rows = "".join(
        "<tr>"
        f"<td><code>{escape_html(area.area_id)}</code></td>"
        f"<td>{escape_html(area.status)}</td>"
        f"<td>{area.numerator if area.numerator is not None else '—'}"
        f" / {area.denominator if area.denominator is not None else '—'}</td>"
        f"<td>{escape_html(area.maturity)}</td>"
        "</tr>"
        for area in coverage.areas
    )
    coverage_table = (
        "<table><thead><tr><th>Area</th><th>Status</th>"
        "<th>Numerator / Denominator</th><th>Maturity</th></tr></thead>"
        f"<tbody>{coverage_rows or '<tr><td colspan="4">—</td></tr>'}"
        "</tbody></table>"
        f"<p class='muted'>{escape_html(coverage.note)}</p>"
    )
    execution_rows = (
        "<tr><td>Rules planned / executed</td>"
        f"<td>{execution.rules_planned} / {execution.rules_executed}</td></tr>"
        "<tr><td>Matched / not matched / not applicable / failed</td>"
        f"<td>{execution.rules_matched} / {execution.rules_not_matched} / "
        f"{execution.rules_not_applicable} / {execution.rules_failed}</td></tr>"
        "<tr><td>Findings / themes / conclusions / recommendations</td>"
        f"<td>{execution.total_finding_count} / {execution.theme_count} / "
        f"{execution.conclusion_count} / {execution.recommendation_count}</td></tr>"
    )
    rule_rows = "".join(
        "<tr>"
        f"<td><code>{escape_html(item.rule_id)}</code></td>"
        f"<td>{'yes' if item.executed else 'no'}</td>"
        f"<td>{escape_html(item.evaluation_status)}</td>"
        f"<td>{item.finding_count}</td>"
        "</tr>"
        for item in execution.entries
    )
    execution_table = (
        "<table><thead><tr><th>Metric</th><th>Value</th></tr></thead>"
        f"<tbody>{execution_rows}</tbody></table>"
        + (
            "<table><thead><tr><th>Rule</th><th>Executed</th>"
            + "<th>Status</th><th>Findings</th></tr></thead>"
            + f"<tbody>{rule_rows}</tbody></table>"
            if rule_rows
            else ""
        )
        + f"<p class='muted'>{escape_html(execution.note)}</p>"
    )
    family_rows = "".join(
        "<tr>"
        f"<td><code>{escape_html(item.family_id)}</code></td>"
        f"<td>{'yes' if item.observed else 'no'}</td>"
        f"<td>{item.finding_count}</td>"
        f"<td>{escape_html(', '.join(item.signals) or '—')}</td>"
        "</tr>"
        for item in families.entries
    )
    family_table = (
        f"<p class='muted'>Observed {families.families_observed} of "
        f"{families.families_total} performance families.</p>"
        "<table><thead><tr><th>Family</th><th>Observed</th>"
        "<th>Findings</th><th>Signals</th></tr></thead>"
        f"<tbody>{family_rows or '<tr><td colspan="4">—</td></tr>'}"
        "</tbody></table>"
        f"<p class='muted'>{escape_html(families.note)}</p>"
    )
    bucket_block = (
        "<p class='muted'>By rule: "
        + escape_html(", ".join(f"{item.key}={item.count}" for item in inventory.by_rule) or "—")
        + "</p><p class='muted'>By severity: "
        + escape_html(
            ", ".join(f"{item.key}={item.count}" for item in inventory.by_severity) or "—"
        )
        + "</p><p class='muted'>By confidence: "
        + escape_html(
            ", ".join(f"{item.key}={item.count}" for item in inventory.by_confidence) or "—"
        )
        + "</p>"
    )
    if inventory.finding_count == 0 and inventory.none_detected_statement:
        inventory_body = f"<p>{escape_html(inventory.none_detected_statement)}</p>"
    else:
        inventory_body = (
            "<p class='muted'>Finding IDs "
            + f"(showing {inventory.finding_ids_displayed} of "
            + f"{inventory.finding_count}):</p><ul>"
            + "".join(
                f"<li><code>{escape_html(finding_id)}</code></li>"
                for finding_id in inventory.finding_ids
            )
            + "</ul>"
        )
    themes = "".join(
        "<article class='content-card conclusion-card card'>"
        f"<h4>{escape_html(item.title)}</h4>"
        f"<p>{escape_html(item.summary)}</p>"
        "<p class='muted'>"
        f"ID: <code>{escape_html(item.theme_id)}</code> · "
        f"Kind: {escape_html(item.kind)} · "
        f"Scope: {escape_html(item.scope)} · "
        f"Findings: {item.finding_count}"
        "</p></article>"
        for item in section.themes
    )
    conclusions = "".join(
        "<article class='content-card conclusion-card card'>"
        f"<h4>{escape_html(item.title)}</h4>"
        f"<p>{escape_html(item.summary)}</p>"
        "<p class='muted'>"
        f"ID: <code>{escape_html(item.conclusion_id)}</code> · "
        f"Kind: {escape_html(item.kind)} · "
        f"Audience: {escape_html(item.audience)} · "
        f"Confidence: {escape_html(item.confidence)} · "
        f"Findings: {item.finding_count}"
        "</p></article>"
        for item in section.conclusions
    )
    if section.recommendation_groups:
        recommendations = "".join(
            f"<h4>{escape_html(group.group)}</h4>"
            + "".join(
                "<article class='card'>"
                + f"<h5>{escape_html(item.title)}</h5>"
                + f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
                + f"<p>{escape_html(item.rationale)}</p>"
                + "<p class='muted'>"
                + f"ID: <code>{escape_html(item.recommendation_id)}</code> · "
                + f"{'Conditional' if item.conditional else 'Direct'} · "
                + f"Audience: {escape_html(item.audience)}"
                + (
                    " · Findings: "
                    + ", ".join(f"<code>{escape_html(fid)}</code>" for fid in item.finding_ids)
                    if item.finding_ids
                    else ""
                )
                + "</p></article>"
                for item in group.recommendations
            )
            for group in section.recommendation_groups
        )
    else:
        recommendations = "".join(
            "<article class='card'>"
            + f"<h4>{escape_html(item.title)}</h4>"
            + f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
            + f"<p>{escape_html(item.rationale)}</p>"
            + "<p class='muted'>"
            + f"ID: <code>{escape_html(item.recommendation_id)}</code>"
            + "</p></article>"
            for item in section.recommendations
        )
    diagnostics_block = ""
    limitations = _limitation_items(section.limitations)
    limitations_block = f"<ul>{limitations}</ul>" if limitations else ""
    trace = ""
    parts = [
        _domain_status_header(section),
        "<h3>Overall Performance Posture</h3>",
        f"<p>{escape_html(section.overall_posture_summary or section.executive_summary)}</p>",
        "<h3>Executive Summary</h3>",
        f"<p>{escape_html(section.executive_summary)}</p>",
        "<h3>Assessment and Coverage Status</h3>",
        f"<p><strong>Assessment status:</strong> {escape_html(section.assessment_status)}</p>",
        coverage_table,
        "<h3>Rule Execution Summary</h3>",
        execution_table,
        "<h3>Performance Family Inventory</h3>",
        family_table,
        "<h3>Finding Inventory Summary</h3>",
        bucket_block,
        inventory_body,
    ]
    if themes:
        parts.extend(
            [
                "<h4>Themes</h4>",
                f"<p class='muted'>Showing {section.themes_displayed} of "
                + f"{section.themes_total}</p>",
                themes,
            ]
        )
    if conclusions:
        parts.extend(
            [
                "<h4>Conclusions</h4>",
                f"<p class='muted'>Showing {section.conclusions_displayed} of "
                + f"{section.conclusions_total}</p>",
                conclusions,
            ]
        )
    if recommendations:
        parts.extend(
            [
                "<h4>Recommendations</h4>",
                f"<p class='muted'>Showing {section.recommendations_displayed} of "
                + f"{section.recommendations_total}</p>",
                recommendations,
            ]
        )
    if diagnostics_block:
        parts.extend(["<h3>Diagnostics</h3>", diagnostics_block])
    if limitations_block:
        parts.extend(["<h4>Limitations</h4>", limitations_block])
    if trace:
        parts.extend(["<h3>Traceability</h3>", trace])
    return "\n".join(parts)


AI_NOT_REQUESTED = "AI interpretation not requested for this local assessment."


def _render_ai_summary_section(view: HtmlReportViewModel) -> str:
    """AI interpretation after the deterministic overview. It never replaces Engine facts."""

    note = (
        "Interpretation only. Engine findings, UNKNOWN results, and calibrated "
        "recommendation horizons stay unchanged."
    )
    if view.ai_enrichment is None:
        body = (
            '<div class="ai-panel ai-absent">'
            '<p class="ai-banner">This section is AI interpretation, separate from '
            "Engine findings.</p>"
            f"<p>{escape_html(AI_NOT_REQUESTED)}</p>"
            '<p class="muted">No generated summary or improvement plan is included.</p>'
            "</div>"
        )
    else:
        body = _render_ai_summary_populated(view.ai_enrichment)
    return _section(
        "AI Summary",
        body,
        section_id="ai-summary",
        eyebrow="AI · Interpretation",
        note=note,
    )


def _render_ai_summary_populated(ai: AiEnrichmentView) -> str:
    priorities = (
        "".join(
            "<li>"
            f"<strong>{escape_html(item.title)}</strong> — {escape_html(item.rationale)} "
            f"<span class=\"tag\">{escape_html(item.priority)}</span>"
            "</li>"
            for item in ai.priorities
        )
        or "<li>None supplied.</li>"
    )
    steps = (
        "".join(
            f"<li><strong>{step.order}. {escape_html(step.title)}</strong> — "
            f"{escape_html(step.summary)}</li>"
            for step in ai.suggested_next_steps
        )
        or "<li>None supplied.</li>"
    )
    limitations = "".join(f"<li>{escape_html(item)}</li>" for item in ai.limitations) or (
        "<li>None supplied.</li>"
    )
    posture = f"<p>Posture: {escape_html(ai.posture)}</p>" if ai.posture else ""
    return (
        '<div class="ai-panel" id="modernization-advisor">'
        f'<p class="ai-banner">{escape_html(ai.disclaimer)} '
        "This Modernization Advisor text does not overwrite Engine outcomes.</p>"
        "<h3>Executive interpretation</h3>"
        f"<p><strong>{escape_html(ai.headline)}</strong></p>"
        f"<p>{escape_html(ai.narrative)}</p>"
        f"{posture}"
        "<h3>Suggested priorities and rationale</h3>"
        '<p class="muted">AI suggestions only. They do not change Engine priority or horizon.</p>'
        f"<ul>{priorities}</ul>"
        "<h3>Proposed improvement plan</h3>"
        '<p class="muted">A proposed plan only. '
        "Calibrated recommendation horizons stay as supplied.</p>"
        f"<ol>{steps}</ol>"
        "<h3>Supporting evidence references and limitations</h3>"
        f"<p>Findings: {_id_list(ai.referenced_finding_ids) or '—'}</p>"
        f"<p>Recommendations: {_id_list(ai.referenced_recommendation_ids) or '—'}</p>"
        f"<ul>{limitations}</ul>"
        "<h4>Advisor metadata</h4>"
        '<dl class="meta">'
        f"<div><dt>Provider</dt><dd>{escape_html(ai.provider)}</dd></div>"
        f"<div><dt>Model</dt><dd>{escape_html(ai.model_id)}</dd></div>"
        f"<div><dt>Advisor version</dt><dd>{escape_html(ai.advisor_version or '—')}</dd></div>"
        f"<div><dt>Prompt version</dt><dd>{escape_html(ai.prompt_version or '—')}</dd></div>"
        "</dl>"
        "</div>"
    )


def _render_ai(ai: AiEnrichmentView) -> str:
    themes = (
        "".join(
            "<li>"
            + f"<strong>{escape_html(theme.title)}</strong> — {escape_html(theme.summary)}"
            + f"<div class='ids'>Findings: {_id_list(theme.related_finding_ids) or '—'}"
            + f" · Recommendations: {_id_list(theme.related_recommendation_ids) or '—'}</div>"
            + "</li>"
            for theme in ai.themes
        )
        or "<li>None</li>"
    )
    priorities = (
        "".join(
            "<li>"
            + f'<span class="badge priority-{escape_html(item.priority)}">'
            + f"{escape_html(item.priority)}</span> "
            + f"<strong>{escape_html(item.title)}</strong> — {escape_html(item.rationale)}"
            + f"<div class='ids'>Findings: {_id_list(item.related_finding_ids) or '—'}"
            + f" · Recommendations: {_id_list(item.related_recommendation_ids) or '—'}</div>"
            + "</li>"
            for item in ai.priorities
        )
        or "<li>None</li>"
    )
    risks = (
        "".join(
            "<li>"
            + f'<span class="badge severity-{escape_html(item.severity)}">'
            + f"{escape_html(item.severity)}</span> "
            + f"<strong>{escape_html(item.title)}</strong> — {escape_html(item.summary)}"
            + "</li>"
            for item in ai.risks
        )
        or "<li>None</li>"
    )
    steps = (
        "".join(
            f"<li><strong>{step.order}. {escape_html(step.title)}</strong> — "
            + f"{escape_html(step.summary)}</li>"
            for step in ai.suggested_next_steps
        )
        or "<li>None</li>"
    )
    limitations = "".join(f"<li>{escape_html(item)}</li>" for item in ai.limitations) or (
        "<li>None</li>"
    )
    posture = f"<p><strong>Posture:</strong> {escape_html(ai.posture)}</p>" if ai.posture else ""
    return (
        '<div class="ai-panel">\n'
        f'<p class="ai-banner">{escape_html(ai.disclaimer)}</p>\n'
        f'<h3 class="ai-headline">{escape_html(ai.headline)}</h3>\n'
        f"<p>{escape_html(ai.narrative)}</p>\n"
        f"{posture}"
        "<h4>Modernization themes</h4>\n"
        f"<ul>{themes}</ul>\n"
        "<h4>Top priorities</h4>\n"
        f"<ul>{priorities}</ul>\n"
        "<h4>Major risks</h4>\n"
        f"<ul>{risks}</ul>\n"
        "<h4>Suggested next steps</h4>\n"
        f"<ol>{steps}</ol>\n"
        "<h4>Referenced IDs</h4>\n"
        f"<p>Findings: {_id_list(ai.referenced_finding_ids) or '—'}</p>\n"
        f"<p>Recommendations: {_id_list(ai.referenced_recommendation_ids) or '—'}</p>\n"
        "<h4>Advisor metadata</h4>\n"
        '<dl class="meta">\n'
        f"<div><dt>Provider</dt><dd>{escape_html(ai.provider)}</dd></div>\n"
        f"<div><dt>Model</dt><dd>{escape_html(ai.model_id)}</dd></div>\n"
        f"<div><dt>Advisor version</dt><dd>"
        f"{escape_html(ai.advisor_version or '—')}</dd></div>\n"
        f"<div><dt>Prompt version</dt><dd>"
        f"{escape_html(ai.prompt_version or '—')}</dd></div>\n"
        f"<div><dt>Generated</dt><dd>"
        f"{escape_html(ai.generated_at_utc or '—')}</dd></div>\n"
        f"<div><dt>Request ID</dt><dd>{escape_html(ai.request_id or '—')}</dd></div>\n"
        "<div><dt>Latency (ms)</dt><dd>"
        f"{ai.latency_ms if ai.latency_ms is not None else '—'}"
        "</dd></div>\n"
        f"<div><dt>Tokens in/out</dt><dd>"
        f"{ai.input_tokens if ai.input_tokens is not None else '—'} / "
        f"{ai.output_tokens if ai.output_tokens is not None else '—'}</dd></div>\n"
        "</dl>\n"
        "<h4>Limitations</h4>\n"
        f"<ul>{limitations}</ul>\n"
        "</div>"
    )


def _appendix_findings(view: HtmlReportViewModel) -> tuple[FindingView, ...]:
    """Findings for the All Findings appendix — excludes unclassified (shown above).

    Slice 3.12: unclassified full cards own the canonical finding/evidence ids in
    Unclassified Results; duplicating them in All Findings created duplicate HTML ids.
    """

    unclassified_ids = {item.finding_id for item in (view.unclassified_findings or ())}
    if not unclassified_ids:
        return view.findings
    return tuple(item for item in view.findings if item.finding_id not in unclassified_ids)


def _appendix_recommendations(view: HtmlReportViewModel) -> tuple[RecommendationView, ...]:
    """Recommendations for All Recommendations — excludes unclassified (shown above)."""

    unclassified_ids = {
        item.recommendation_id for item in (view.unclassified_recommendations or ())
    }
    if not unclassified_ids:
        return view.recommendations
    return tuple(
        item for item in view.recommendations if item.recommendation_id not in unclassified_ids
    )


def _render_technical_details(view: HtmlReportViewModel) -> str:
    unclassified_prefix = ""
    if view.unclassified_findings or view.unclassified_recommendations:
        limitation = escape_html(
            (view.unclassified_limitation or "").strip()
            or "Some assessment results could not yet be assigned to a customer-facing "
            "assessment section."
        )
        unclassified_findings = (
            "\n".join(
                _render_finding_card(item, compact=False) for item in view.unclassified_findings
            )
            if view.unclassified_findings
            else '<p class="muted">No unclassified findings.</p>'
        )
        unclassified_recommendations = (
            "\n".join(
                _render_recommendation_card(item, compact=False)
                for item in view.unclassified_recommendations
            )
            if view.unclassified_recommendations
            else '<p class="muted">No unclassified recommendations.</p>'
        )
        unclassified_prefix = (
            '<details class="tech-block" id="unclassified-results" open>\n'
            + "<summary>Unclassified Results</summary>\n"
            + f'<p class="muted">{limitation}</p>\n'
            + "<h4>Unclassified findings</h4>\n"
            + f"{unclassified_findings}\n"
            + "<h4>Unclassified recommendations</h4>\n"
            + f"{unclassified_recommendations}\n"
            + "</details>\n"
        )

    additional_packs = ""
    pack_parts: list[str] = []
    if view.testing_report is not None:
        pack_parts.append(f"<h4>Testing Assessment</h4>\n{_render_testing(view.testing_report)}")
    if view.performance_report is not None:
        pack_parts.append(
            f"<h4>Performance Assessment</h4>\n{_render_performance(view.performance_report)}"
        )
    if pack_parts:
        packs_body = "\n".join(pack_parts)
        additional_packs = (
            '<details class="tech-block" id="additional-domain-packs">\n'
            + "<summary>Additional domain packs</summary>\n"
            + f"{packs_body}\n"
            + "</details>\n"
        )

    findings_body = (
        "\n".join(_render_finding_card(item, compact=False) for item in _appendix_findings(view))
        if _appendix_findings(view)
        else (
            '<p class="muted">No findings were produced for this run. '
            + "This does not certify that the repository is free of issues.</p>"
        )
    )
    recommendations_body = (
        "\n".join(
            _render_recommendation_card(item, compact=False)
            for item in _appendix_recommendations(view)
        )
        if _appendix_recommendations(view)
        else ('<p class="muted">No recommendations were produced for this run.</p>')
    )
    priority_actions_body = (
        "\n".join(
            _render_recommendation_card(item, compact=False, as_priority_action=True)
            for item in view.priority_actions
        )
        if view.priority_actions
        else ('<p class="muted">No Priority Actions were produced for this run.</p>')
    )
    return (
        f"{unclassified_prefix}"
        f"{additional_packs}"
        '<details class="tech-block" id="repository" open>\n'
        "<summary>Repository Profile</summary>\n"
        f"{_render_repository(view)}\n"
        "</details>\n"
        '<details class="tech-block" id="appendix-assessment-summary">\n'
        "<summary>Assessment Summary</summary>\n"
        f"{_render_assessment_summary(view)}\n"
        "</details>\n"
        '<details class="tech-block" id="assessment-scope">\n'
        "<summary>Assessment Scope</summary>\n"
        f"{_render_assessment_scope(view)}\n"
        "</details>\n"
        '<details class="tech-block" id="findings-full">\n'
        "<summary>All Findings (with evidence)</summary>\n"
        f"{findings_body}\n"
        "</details>\n"
        '<details class="tech-block" id="recommendations-full">\n'
        "<summary>All Recommendations (with actions)</summary>\n"
        f"{recommendations_body}\n"
        "</details>\n"
        '<details class="tech-block" id="priority-actions-full">\n'
        "<summary>All Priority Actions (with actions)</summary>\n"
        f"{priority_actions_body}\n"
        "</details>\n"
        '<details class="tech-block" id="traceability">\n'
        "<summary>Traceability</summary>\n"
        f"{_render_traceability_appendix(view)}\n"
        "</details>\n"
        '<details class="tech-block" id="artifacts">\n'
        "<summary>Graph and Artifact References</summary>\n"
        f"{_render_artifacts(view)}\n"
        "</details>\n"
        '<details class="tech-block" id="metadata">\n'
        "<summary>Assessment Metadata</summary>\n"
        f"{_render_metadata(view)}\n"
        "</details>\n"
        f'<p class="provenance">{escape_html(view.provenance_note)}</p>'
    )


def _render_repository(view: HtmlReportViewModel) -> str:
    repo = view.repository
    rows = [
        ("Name", escape_and_wrap(repo.name)),
        ("Source", escape_html(repo.source_type)),
        ("Files", str(repo.file_count)),
    ]
    if repo.reference:
        rows.append(("Reference", escape_and_wrap(repo.reference)))
    if repo.default_branch:
        rows.append(("Default branch", escape_html(repo.default_branch)))
    return _definition_list(rows)


def _render_assessment_summary(view: HtmlReportViewModel) -> str:
    summary = view.assessment_summary
    sev = (
        "".join(
            f"<li>{escape_html(name)}: {count}</li>" for name, count in summary.findings_by_severity
        )
        or "<li>None</li>"
    )
    pri = (
        "".join(
            f"<li>{escape_html(name)}: {count}</li>"
            for name, count in summary.recommendations_by_priority
        )
        or "<li>None</li>"
    )
    return (
        f"<p>{escape_html(summary.summary_text)}</p>\n"
        '<div class="split">\n'
        "<div>\n"
        f"<p><strong>Hygiene and quality checks assessed:</strong> {summary.rules_evaluated}</p>\n"
        f"<p><strong>Findings:</strong> {summary.findings_count}</p>\n"
        f"<p><strong>Recommendations:</strong> {summary.recommendations_count}</p>\n"
        "</div>\n"
        "<div>\n<h3>By severity</h3>\n"
        f'<ul class="plain">{sev}</ul>\n'
        "<h3>By priority</h3>\n"
        f'<ul class="plain">{pri}</ul>\n</div>\n'
        "</div>"
    )


def _render_artifacts(view: HtmlReportViewModel) -> str:
    if not view.artifacts:
        return '<p class="muted">No artifact references recorded.</p>'
    rows = "".join(
        "<tr>"
        f"<td>{escape_html(item.label)}</td>"
        f"<td><code>{escape_and_wrap(item.relative_path)}</code></td>"
        "</tr>"
        for item in view.artifacts
    )
    return (
        '<div class="table-wrap"><table>\n'
        "<thead><tr><th>Artifact</th><th>Relative path</th></tr></thead>\n"
        f"<tbody>{rows}</tbody>\n</table></div>"
    )


def _render_metadata(view: HtmlReportViewModel) -> str:
    meta = view.metadata
    warnings = "".join(f"<li>{escape_html(item)}</li>" for item in meta.warnings) or (
        "<li>None</li>"
    )
    rows = [
        ("Generated at (UTC)", escape_html(meta.generated_at_utc)),
        ("Report title", escape_html(BRAND_REPORT_NAME)),
        ("Report version", escape_html(meta.report_version)),
        ("Engine version", escape_html(meta.engine_version)),
        ("Advisor version", escape_html(meta.advisor_version or "—")),
        ("Repository", escape_html(meta.repository_name or view.summary.repository_name)),
        ("Assessment mode", escape_html(view.summary.assessment_mode_label)),
        ("AI status", escape_html(meta.ai_status)),
        ("Model ID", escape_html(meta.model_id or "—")),
        ("Total ms", _fmt_ms(meta.timing_total_ms)),
        ("Scan ms", _fmt_ms(meta.timing_scan_ms)),
        ("Analysis ms", _fmt_ms(meta.timing_analysis_ms)),
        ("AI ms", _fmt_ms(meta.timing_ai_ms)),
        ("Report ms", _fmt_ms(meta.timing_report_ms)),
    ]
    if meta.organization_name:
        rows.insert(2, ("Organization", escape_html(meta.organization_name)))
    if meta.confidentiality_notice:
        rows.append(("Confidentiality", escape_html(meta.confidentiality_notice)))
    return _definition_list(rows) + f"\n<h3>Warnings</h3>\n<ul>{warnings}</ul>"


def _render_footer(view: HtmlReportViewModel | None = None) -> str:
    engine = view.metadata.engine_version if view is not None else BRAND_VERSION
    report_version = view.metadata.report_version if view is not None else "3.1"
    mode = view.summary.assessment_mode_label if view is not None else "Deterministic"
    ai_status = view.metadata.ai_status if view is not None else "not_requested"
    return (
        '<footer class="footer">'
        "<span>CodeStrata · Engineering decisions, grounded in code.</span>"
        f"<span>{escape_html(BRAND_FOOTER_LINE)} · "
        f"{escape_html(BRAND_REPORT_NAME)} · "
        f"Report {escape_html(report_version)} · Engine {escape_html(engine)} · "
        f"Mode {escape_html(mode)} · AI status {escape_html(ai_status)}</span>"
        "</footer>"
    )


def _render_evidence_details(evidence: tuple[object, ...]) -> str:
    if not evidence:
        return (
            '<details class="evidence"><summary>Evidence</summary>'
            + '<p class="muted">None</p></details>'
        )
    items = []
    for ev in evidence:
        path = getattr(ev, "path", None)
        excerpt = getattr(ev, "excerpt", None)
        node_id = getattr(ev, "node_id", None)
        bits = [
            f"<strong>{escape_html(getattr(ev, 'evidence_type', 'evidence'))}</strong>",
            f"<code>{escape_and_wrap(str(getattr(ev, 'source_id', '')))}</code>",
        ]
        if path:
            bits.append(f"path <code>{escape_and_wrap(path)}</code>")
        if node_id:
            bits.append(f"node <code>{escape_and_wrap(node_id)}</code>")
        if excerpt:
            bits.append(escape_html(excerpt))
        items.append(f"<li>{' — '.join(bits)}</li>")
    return (
        f'<details class="evidence"><summary>Evidence</summary><ul>{"".join(items)}</ul></details>'
    )


def _id_list(values: tuple[str, ...]) -> str:
    if not values:
        return ""
    return " ".join(f"<code>{escape_and_wrap(item)}</code>" for item in values)


def _title_for_id(entity_id: str, ids: tuple[str, ...], titles: tuple[str, ...]) -> str:
    for iid, title in zip(ids, titles, strict=False):
        if iid == entity_id:
            return title
    return entity_id


def _title_links(
    ids: tuple[str, ...],
    titles: tuple[str, ...],
    *,
    anchor_fn: Callable[[str], str],
    empty: str = "",
) -> str:
    if not ids:
        return f'<span class="muted">{escape_html(empty)}</span>' if empty else ""
    parts = []
    for index, eid in enumerate(ids):
        label = titles[index] if index < len(titles) else eid
        if anchor_fn is recommendation_anchor:
            parts.append(_recommendation_detail_markup(eid, label))
            continue
        parts.append(
            f'<a class="id-link" href="#{escape_html(anchor_fn(eid))}">{escape_html(label)}</a>'
        )
    return ", ".join(parts)


def _render_limitations_block(limitations: Iterable[object] | None, *, title: str) -> str:
    rows = tuple(limitations or ())
    if not rows:
        return ""
    items = "".join(f"<li>{escape_html(limitation_label(str(item)))}</li>" for item in rows)
    return f'<div class="limitations"><em>{escape_html(title)}</em><ul>{items}</ul></div>\n'


def _render_traceability_appendix(view: HtmlReportViewModel) -> str:
    from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION

    legacy_findings = sum(1 for f in view.findings if f.evidence_completeness == "legacy")
    partial = sum(1 for f in view.findings if f.evidence_completeness in {"partial", "truncated"})
    initiatives = 0
    if view.roadmap_report is not None:
        initiatives = int(
            getattr(view.roadmap_report, "initiatives_total", 0)
            or len(view.roadmap_report.initiatives)
        )
    chain = (
        "<ol>"
        "<li>Roadmap initiative → Priority Action</li>"
        "<li>Priority Action → Recommendation</li>"
        "<li>Recommendation → Finding</li>"
        "<li>Finding → Evidence</li>"
        "</ol>"
    )
    return (
        f"<p>Schema version: <code>{escape_html(ASSESSMENT_JSON_SCHEMA_VERSION)}</code></p>\n"
        "<ul>"
        f"<li>Evidence: {len(view.evidence)}</li>"
        f"<li>Findings: {len(view.findings)}</li>"
        f"<li>Recommendations: {len(view.recommendations)}</li>"
        f"<li>Priority Actions: {view.priority_actions_total or len(view.priority_actions)}</li>"
        f"<li>Roadmap initiatives: {initiatives}</li>"
        f"<li>Legacy findings: {legacy_findings}</li>"
        f"<li>Partial findings: {partial}</li>"
        "</ul>\n"
        "<p><em>Traceability chain</em></p>\n"
        f"{chain}\n"
        "<p>Evidence locations are repository-relative. Absolute paths, file:// URLs, "
        "secrets, full source files, and raw graph payloads are not shown.</p>\n"
    )


def _finding_id_links(values: tuple[str, ...]) -> str:
    """Render related finding IDs as in-page links for leadership traceability."""

    if not values:
        return ""
    return " ".join(
        f'<a class="id-link" href="#{escape_html(finding_anchor(item))}">'
        f"<code>{escape_and_wrap(item)}</code></a>"
        for item in values
    )


def _definition_list(rows: list[tuple[str, str]]) -> str:
    body = "".join(
        f"<div><dt>{escape_html(label)}</dt><dd>{value}</dd></div>" for label, value in rows
    )
    return f'<dl class="meta">{body}</dl>'


def _fmt_ms(value: float | None) -> str:
    if value is None:
        return "—"
    return str(value)


_CSS = reference_shell_css()
