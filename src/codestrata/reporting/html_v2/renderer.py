"""Self-contained CodeStrata Engineering Assessment HTML report renderer.

Presentation only — no analysis or enrichment business logic.
"""

from __future__ import annotations

import re

from codestrata.design_system.tokens import DESIGN_SYSTEM_REF
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
    brand_mark_svg,
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
    ASSESSMENT_RESULTS_TITLE,
    LEGACY_PACK_SECTION_ALIASES,
    AssessmentHead,
    assessment_head_anchor,
    assessment_head_title,
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
from codestrata.reporting.html_v2.styles import REPORT_CSS
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
from codestrata.reporting.testing.models import TestingReportSection

CONTENT_SECURITY_POLICY = (
    "default-src 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "frame-ancestors 'none'; "
    "img-src data:; "
    "font-src 'none'; "
    "connect-src 'none'; "
    "object-src 'none'; "
    "script-src 'none'; "
    "style-src 'unsafe-inline'"
)

_TOP_FINDINGS = 5
_SEVERITY_ORDER = ("critical", "high", "medium", "low", "informational")


class HtmlReportRenderer:
    """Render HtmlReportViewModel to a complete HTML document.

    Contains no analysis or enrichment business logic.
    """

    def render(self, view: HtmlReportViewModel) -> str:
        """Render HtmlReportViewModel to a complete HTML document.

        Contains no analysis or enrichment business logic.
        """

        evidence_scope = begin_evidence_anchor_scope()
        try:
            parts = [
                "<!DOCTYPE html>",
                '<html lang="en">',
                "<head>",
                '<meta charset="utf-8">',
                f'<meta http-equiv="Content-Security-Policy" content="{CONTENT_SECURITY_POLICY}">',
                '<meta name="viewport" content="width=device-width, initial-scale=1">',
                '<meta name="color-scheme" content="light dark">',
                (
                    f'<meta name="generator" content="{escape_html(BRAND_NAME)} '
                    f'{escape_html(BRAND_REPORT_NAME)}">'
                ),
                f"<title>{escape_html(BRAND_NAME)} {escape_html(BRAND_REPORT_NAME)} — "
                f"{escape_html(view.summary.repository_name)}</title>",
                f"<style>{_CSS}</style>",
                "</head>",
                "<body>",
                '<a class="skip-link" href="#main-content">Skip to main content</a>',
                '<div class="report-shell">',
                (
                    '<header class="report-product-bar" role="banner">'
                    f'<span class="report-product-mark" aria-hidden="true">{brand_mark_svg()}</span>'
                    f'<span class="report-product-name">{escape_html(BRAND_NAME)}</span>'
                    f'<span class="report-product-label">{escape_html(BRAND_REPORT_NAME)}</span>'
                    "</header>"
                ),
                '<div class="page">',
                '<main id="main-content" role="main">',
                _render_hero(view),
                _render_toc(view),
                _render_leadership_verdict(view),
                _section(
                    "Executive Summary",
                    _render_executive_summary_section(view),
                    section_id="executive-summary",
                    eyebrow="01",
                    note="Leadership narrative for the assessed repository.",
                ),
                _section(
                    assessment_head_title(AssessmentHead.ENGINEERING_INTELLIGENCE),
                    _render_engineering_intelligence_summary(view),
                    section_id=assessment_head_anchor(AssessmentHead.ENGINEERING_INTELLIGENCE),
                    eyebrow="02",
                    note=(
                        "One-page synthesis of enabled assessment heads. "
                        "Does not introduce new conclusions."
                    ),
                ),
                _section(
                    "Key Takeaways",
                    _render_key_takeaways(view),
                    section_id="key-takeaways",
                    eyebrow="03",
                    note="Concise leadership bullets for scanning and handoff.",
                ),
                _section(
                    "Priority Actions",
                    _render_roadmap(
                        view.priority_actions if view.priority_actions else view.recommendations,
                        total_actions=view.priority_actions_total or len(view.priority_actions),
                        as_priority_actions=True,
                    ),
                    section_id="priority-actions",
                    eyebrow="04",
                    note=(
                        "Priority-ordered actions linked to findings. "
                        "Order matches the Roadmap section below."
                    ),
                ),
                _section(
                    "Engineering Risks",
                    _render_engineering_risks(view),
                    section_id="engineering-risks",
                    eyebrow="05",
                    note="Meaningful risks grouped by theme.",
                ),
                _render_assessment_results(view),
            ]
            if view.roadmap_report is not None:
                parts.append(
                    _section(
                        "Roadmap",
                        _render_phased_roadmap(view),
                        section_id="phased-modernization-plan",
                        eyebrow="07",
                        note=(
                            "Engine assess sequencing of Priority Actions "
                            "(Stabilize → Secure → Modernize → Optimize). "
                            "This is not CodeStrata Platform Strategic Roadmap."
                        ),
                    )
                )
            if view.ai_enrichment is not None:
                parts.append(
                    _section(
                        "Optional AI Enhancements",
                        _render_ai(view.ai_enrichment),
                        section_id="modernization-advisor",
                        eyebrow="08",
                        note=(
                            "Optional AI interpretation when enabled. "
                            "AI enhances—does not replace—deterministic Engineering Intelligence. "
                            "Not merged into findings or recommendations."
                        ),
                        css_class="section section-ai",
                    )
                )
            parts.append(
                _section(
                    "Technical Appendix",
                    _render_technical_details(view),
                    section_id="technical-appendix",
                    eyebrow="09",
                    note=(
                        "Engineering reference: unclassified results, evidence, graphs, "
                        "artifacts, metadata, and rule IDs."
                    ),
                )
            )
            parts.extend(
                [
                    "</main>",
                    # Outside <main> so the footer exposes the contentinfo landmark.
                    _render_footer(view),
                    "</div>",  # .page
                    "</div>",  # .report-shell
                    "</body>",
                    "</html>",
                    "",
                ]
            )
            return _ensure_table_semantics(_ensure_responsive_tables("\n".join(parts)))
        finally:
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
    note_html = f'<p class="section-note">{escape_html(note)}</p>' if note else ""
    eyebrow_html = ""
    if eyebrow:
        eyebrow_html = (
            f'<p class="section-eyebrow" aria-hidden="true">'
            f"<span>{escape_html(eyebrow)}</span> // "
            f"{escape_html(title.upper())}</p>\n"
        )
    return (
        f'<section class="{css_class}" id="{escape_html(section_id)}">\n'
        f"{eyebrow_html}"
        f'<div class="section-head"><h2>{escape_html(title)}</h2></div>\n'
        f"{note_html}"
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


def _render_toc(view: HtmlReportViewModel) -> str:
    if not view.outline:
        return ""
    items = "".join(
        f'<li><a href="#{escape_html(entry.section_id)}">{escape_html(entry.title)}</a></li>\n'
        for entry in view.outline
    )
    return (
        '<nav class="toc" id="contents" aria-label="Table of contents">\n'
        '<p class="section-eyebrow" aria-hidden="true"><span>00</span> // CONTENTS</p>\n'
        '<div class="section-head"><h2>Contents</h2></div>\n'
        f"<ol>\n{items}</ol>\n"
        "</nav>"
    )


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
        return (
            '<p class="muted">No executive summary was produced for this assessment.</p>'
        )
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
            f"<td>{escape_html(item.title)}</td>"
            f"<td>{escape_html(item.status_label)}</td>"
            f"<td>{item.findings_count}</td>"
            f"<td>{item.recommendations_count}</td>"
            "</tr>"
            for item in view.assessment_heads
        )
        parts.append(
            "<h3>Assessment areas</h3>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr><th>Area</th><th>Status</th>"
            "<th>Findings</th><th>Recommendations</th></tr></thead>\n"
            f"<tbody>{area_rows}</tbody>\n</table></div>"
        )
    return "\n".join(parts)


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
            f"<td>{escape_html(fact.label)}</td>"
            f"<td>{escape_html(fact.value)}</td>"
            f"<td>{escape_html(fact.note) if fact.note else '—'}</td>"
            "</tr>"
            for fact in section.overview_facts
        )
        parts.append(
            '<div class="eis-intel-group" data-group="overall_status">\n'
            "<h3>Overall assessment status</h3>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr><th>Fact</th><th>Value</th><th>Note</th></tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    if section.head_summaries:
        rows = "".join(
            "<tr>"
            f'<td><a class="id-link" href="#{escape_html(item.anchor)}">'
            f"{escape_html(item.title)}</a></td>"
            f"<td>{escape_html(item.status_label)}</td>"
            f"<td>{item.finding_count}</td>"
            f"<td>{item.recommendation_count}</td>"
            f"<td>{escape_html(item.confidence_label)}</td>"
            f"<td>{escape_html(item.coverage)}</td>"
            "</tr>"
            for item in section.head_summaries
        )
        parts.append(
            '<div class="eis-intel-group" data-group="assessment_heads">\n'
            "<h3>Assessment heads assessed</h3>\n"
            '<p class="muted">Status and counts from each assessment head. '
            "Detailed findings remain in Assessment Results.</p>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Assessment head</th><th>Status</th><th>Findings</th>"
            "<th>Recommendations</th><th>Confidence</th><th>Coverage</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    if section.observations:
        items = "".join(f"<li>{escape_html(item)}</li>" for item in section.observations)
        parts.append(
            '<div class="eis-intel-group" data-group="observations">\n'
            "<h3>High-level engineering observations</h3>\n"
            f'<ul class="plain">{items}</ul>\n'
            "</div>"
        )

    if section.cross_head_facts:
        rows = "".join(
            "<tr>"
            f"<td>{escape_html(fact.label)}</td>"
            f"<td>{escape_html(fact.value)}</td>"
            f"<td>{escape_html(fact.note) if fact.note else '—'}</td>"
            "</tr>"
            for fact in section.cross_head_facts
        )
        parts.append(
            '<div class="eis-intel-group" data-group="cross_head">\n'
            "<h3>Cross-head summary</h3>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr><th>Fact</th><th>Value</th><th>Note</th></tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    pa_priority = "".join(
        f"<li>{escape_html(item.label)}: {item.count}</li>"
        for item in section.priority_by_priority
    ) or "<li>None</li>"
    pa_horizon = "".join(
        f"<li>{escape_html(item.label)}: {item.count}</li>"
        for item in section.priority_by_horizon
    ) or "<li>None</li>"
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

    parts.append(
        render_coverage_confidence_limitations(
            coverage_rows=section.coverage_rows,
            confidence=section.confidence,
            confidence_label=section.confidence_label,
            confidence_note=(
                "Weakest contributing Assessment-Head Confidence across assessed heads."
            ),
            limitations=section.limitations,
        )
    )

    return "\n".join(parts)


def _render_assessment_results(view: HtmlReportViewModel) -> str:
    heads = view.assessment_heads
    if not heads:
        body = (
            '<p class="muted">No assessment-head sections were available '
            "for this assessment.</p>"
        )
    else:
        body = "\n".join(
            _render_assessment_head_section(view, section) for section in heads
        )
    return _section(
        ASSESSMENT_RESULTS_TITLE,
        body,
        section_id=ASSESSMENT_RESULTS_ANCHOR,
        eyebrow="06",
        note=(
            "Customer-facing assessment heads with coverage, pack content, "
            "and linked findings or recommendations."
        ),
        css_class="section assessment-results",
    )


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
            pack_body = _render_architecture_intelligence(view.architecture_intelligence)
        elif view.architecture_report is not None:
            pack_body = _render_architecture(view.architecture_report)
    elif head is AssessmentHead.TECHNICAL_DEBT_INTELLIGENCE:
        if view.technical_debt_intelligence is not None:
            pack_body = _render_technical_debt_intelligence(
                view.technical_debt_intelligence
            )
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
            f"<h4>{escape_html(severity.title())} findings</h4>\n"
            f'<div class="card-stack">\n{cards}\n</div>\n'
            "</div>"
        )
    # Any unexpected severities
    for severity, group in by_severity.items():
        if severity in _SEVERITY_ORDER:
            continue
        cards = "\n".join(_render_finding_card(item, compact=True) for item in group)
        blocks.append(
            f'<div class="assessment-head-findings">\n'
            f"<h4>{escape_html(severity.title())} findings</h4>\n"
            f'<div class="card-stack">\n{cards}\n</div>\n'
            "</div>"
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
        f'<p class="trace-line"><a href="#{escape_html(recommendation_anchor(item.recommendation_id))}">'
        "View recommendation details</a></p>\n"
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
            or (
                head is AssessmentHead.CLOUD_READINESS
                and view.cloud_intelligence is not None
            )
            or (
                head is AssessmentHead.AI_READINESS
                and view.ai_readiness_intelligence is not None
            )
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
            f"{_render_technology(view)}"
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
            "under the activated assessment checks. This does not certify that the "
            "repository is free of risks.</p>"
        )
    blocks: list[str] = []
    for theme in view.engineering_risks:
        items = "".join(f"<li>{escape_html(item)}</li>" for item in theme.items)
        blocks.append(
            f'<div class="risk-theme"><h3>{escape_html(theme.theme)}</h3>'
            f'<ul class="plain">{items}</ul></div>'
        )
    return "\n".join(blocks)


def _render_modernization_opportunities(view: HtmlReportViewModel) -> str:
    if not view.modernization_opportunities:
        return (
            '<p class="muted">No additional modernization opportunities were '
            "identified beyond Priority Actions and capability assessments.</p>"
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
        f"{_render_roadmap(actions, total_actions=view.priority_actions_total or len(actions), as_priority_actions=True)}\n"
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
        "replace Engineering Intelligence results.</p>\n"
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


def _render_hero(view: HtmlReportViewModel) -> str:
    summary = view.summary
    meta = view.metadata
    severity_tone = _severity_tone(summary.highest_finding_severity)
    generated = _humanize_timestamp(meta.generated_at_utc)
    meta_items = [
        ("Repository", meta.repository_name or summary.repository_name),
        ("Generated", generated),
        ("Report version", meta.report_version),
        ("Assessment mode", summary.assessment_mode_label),
        ("AI status", meta.ai_status),
    ]
    meta_html = "".join(
        '<div class="meta-item"><span class="meta-label">'
        f"{escape_html(label)}</span>"
        f'<span class="meta-value">{escape_and_wrap(str(value))}</span></div>\n'
        for label, value in meta_items
        if value and str(value).strip() not in {"—", "-", "Unknown", ""}
    )
    return (
        '<header class="hero" id="cover">\n'
        '<div class="hero-brand">\n'
        f'<p class="brand-lockup">{brand_mark_svg()}'
        f'<span class="brand-word">{escape_html(BRAND_NAME)}</span></p>\n'
        '<p class="hero-eyebrow">'
        f"Community Edition · {escape_html(summary.assessment_mode_label)}</p>\n"
        f'<h1 class="report-title">{escape_html(BRAND_REPORT_NAME)}</h1>\n'
        '<p class="hero-lede">Engineering Intelligence for the current '
        "repository state. Optional AI enhancements do not replace findings or "
        "recommendations.</p>\n"
        "</div>\n"
        f'<div class="hero-meta report-identity">\n{meta_html}</div>\n'
        '<div class="hero-kpis">\n'
        f"{_kpi('Highest Finding Severity', summary.highest_finding_severity, '', severity_tone)}"
        f"{_kpi('Cloud Enablement Signals', _cloud_primary(view), _cloud_status(view), 'cloud')}"
        f"{_kpi('CI/CD', _cicd_value(view), '', 'cicd')}"
        "</div>\n"
        "</header>"
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
            "repository scan. Confirm language manifests are present and re-run "
            "assessment if needed.</p>"
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
            f"<td>{escape_html(item.label)}</td>"
            f"<td>{escape_and_wrap(item.value)}</td>"
            f"<td>{escape_html(item.kind)}</td>"
            "</tr>"
            for item in view.version_highlights
        )
        highlights = (
            '<div class="table-card">\n'
            "<h3>Runtime and platform versions</h3>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr><th>Label</th><th>Value</th><th>Kind</th></tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
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


def _render_technology_inventory(view: HtmlReportViewModel, inventory) -> str:
    parts: list[str] = []
    if inventory.fact_count == 0 and inventory.composition is None:
        parts.append(
            '<p class="muted">No supported technology evidence was available for this '
            "repository scan.</p>"
        )
    for group in inventory.groups:
        if not group.facts:
            continue
        rows = "".join(
            "<tr>"
            f"<td>{escape_html(fact.name)}</td>"
            f"<td>{escape_html(fact.category.replace('_', ' '))}</td>"
            f"<td>{escape_html(fact.version) if fact.version else '—'}</td>"
            f"<td>{escape_html(_version_state_label(fact.version_state))}</td>"
            f"<td>{escape_html(fact.confidence_label.replace('_', ' ').title())}</td>"
            f"<td>{_render_inventory_evidence(fact.evidence_paths, fact.source)}</td>"
            "</tr>"
            for fact in group.facts
        )
        parts.append(
            f'<div class="tech-inventory-group" data-group="{escape_html(group.group_id)}">\n'
            f"<h4>{escape_html(group.title)}</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Name</th><th>Type</th><th>Version</th>"
            "<th>Version state</th><th>Confidence</th><th>Evidence</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    composition = inventory.composition
    if composition is not None:
        parts.append(_render_repository_composition(composition))

    if view.version_highlights:
        rows = "".join(
            "<tr>"
            f"<td>{escape_html(item.label)}</td>"
            f"<td>{escape_and_wrap(item.value)}</td>"
            f"<td>{escape_html(item.kind)}</td>"
            "</tr>"
            for item in view.version_highlights
        )
        parts.append(
            '<div class="table-card">\n'
            "<h4>Runtime and platform version highlights</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr><th>Label</th><th>Value</th><th>Kind</th></tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    # Canonical Coverage → Confidence → Limitations (Slice 3.11).
    coverage_rows = ()
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
    return "\n".join(parts) if parts else (
        '<p class="muted">No supported technology evidence was available.</p>'
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


def _render_repository_composition(composition) -> str:
    rows: list[str] = []
    if composition.total_files is not None:
        rows.append(
            f"<tr><td>Total analyzed files</td><td>{composition.total_files}</td></tr>"
        )
    if composition.source_files is not None:
        rows.append(
            f"<tr><td>Source files observed</td><td>{composition.source_files}</td></tr>"
        )
    if composition.test_files is not None:
        rows.append(
            f"<tr><td>Test files observed</td><td>{composition.test_files}</td></tr>"
        )
    if composition.application_count is not None:
        rows.append(
            f"<tr><td>Application / service indicators</td>"
            f"<td>{composition.application_count}</td></tr>"
        )
    if composition.modules:
        rows.append(
            "<tr><td>Modules / components</td>"
            f"<td>{escape_html(', '.join(composition.modules))}</td></tr>"
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
            f"<td>{escape_html(', '.join(composition.ecosystems))}</td></tr>"
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
            "This does not certify that the repository is free of issues.</p>"
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
                f"{len(view.findings)}. Full list in Technical Details.</p>"
            )
    return f'<div class="severity-grid">{meters}</div>\n<h3>Priority findings</h3>\n{cards}'


def _render_finding_card(item: FindingView, *, compact: bool) -> str:
    nodes = _id_list(item.affected_nodes) or '<span class="muted">None</span>'
    # Anchors live only on full detail cards (appendix) to avoid duplicate IDs.
    anchor_attr = (
        f' id="{escape_html(finding_anchor(item.finding_id))}"' if not compact else ""
    )
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
            f"<div><dt>Finding ID</dt>"
            f'<dd><code class="trace-id">{escape_and_wrap(item.finding_id)}</code></dd></div>\n'
            f"<div><dt>Rule ID</dt>"
            f'<dd><code class="trace-id" title="Rule ID">{escape_and_wrap(item.rule_id)}'
            "</code></dd></div>\n"
            f"<div><dt>Category</dt><dd>{escape_html(item.category)}</dd></div>\n"
            f"<div><dt>Evidence</dt><dd>{escape_html(completeness)}</dd></div>\n"
            f"{_severity_basis_meta_rows(item)}"
            f"{_finding_confidence_meta_rows(item)}"
            f"<div><dt>Affected nodes</dt><dd>{nodes}</dd></div>\n"
            f"<div><dt>Related recommendation</dt><dd>{supported}</dd></div>\n"
            f"<div><dt>Priority Actions influenced</dt><dd>{influenced}</dd></div>\n"
            f"{_related_findings_meta_rows(item)}"
            "</dl>\n"
            f"{limitations}"
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
            "View evidence details</a></p>\n"
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
        escape_html(label)
        for label in item.correlation_relationship_labels[:3]
        if label
    )
    relationship = (
        f"<div><dt>Relationship</dt><dd>{labels}</dd></div>\n" if labels else ""
    )
    return (
        f"<div><dt>Related findings</dt><dd>{links}</dd></div>\n"
        f"{relationship}"
    )


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
            f"{escape_html(item.finding_confidence_level.replace('_', ' ').title())}"
            "</dd></div>\n"
        )
    if item.rule_confidence_level:
        rows.append(
            "<div><dt>Rule confidence</dt><dd>"
            f"{escape_html(item.rule_confidence_level.replace('_', ' ').title())}"
            "</dd></div>\n"
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
            f"{escape_html(primary_evidence_level.replace('_', ' ').title())}"
            "</dd></div>\n"
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
            "Findings may still appear above when present.</p>"
        )
    total = total_actions if total_actions is not None else len(display_all)
    display = display_all[:_LEADERSHIP_ACTION_DISPLAY_LIMIT]
    subset_note = ""
    if total > len(display):
        subset_note = (
            f'<p class="section-note">Showing {len(display)} of {total} prioritized '
            "actions. Complete Priority Action details are in the Technical Appendix.</p>\n"
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
            f'<div class="roadmap-lane">\n'
            f'<h3>{escape_html(name)} <span class="count-pill">{len(group)}</span></h3>\n'
            f'<div class="card-stack">{cards}</div>\n'
            "</div>"
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
            primary = (
                f'<a class="id-link" href="#{escape_html(finding_anchor(item.primary_finding_id))}">'
                f"{escape_html(_title_for_id(item.primary_finding_id, item.related_finding_ids, item.related_finding_titles))}"
                "</a>"
            )
        else:
            primary = '<span class="muted">None</span>'
        actions = (
            "".join(
                "<li>"
                f"<strong>{action.order}. {escape_html(action.title)}</strong>"
                f" — {escape_html(action.description)}"
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
        detail = (
            f"<p><em>Rationale:</em> {escape_html(item.rationale)}</p>\n"
            '<dl class="meta">\n'
            f"<div><dt>{'Priority Action' if is_pa else 'Recommendation'} ID</dt>"
            f"<dd><code>{escape_and_wrap(item.recommendation_id)}</code></dd></div>\n"
            f"<div><dt>Category</dt><dd>{escape_html(item.category)}</dd></div>\n"
            f"<div><dt>Evidence</dt>"
            f"<dd>{escape_html(completeness_label(item.evidence_completeness))}</dd></div>\n"
            f"{_recommendation_confidence_meta_row(item)}"
            f"{_priority_basis_meta_rows(item)}"
            f"<div><dt>Supported by</dt><dd>{related}</dd></div>\n"
            f"<div><dt>Primary finding</dt><dd>{primary}</dd></div>\n"
            "</dl>\n"
            f"{limitations}"
            "<h4>Actions</h4>\n"
            f'<ol class="actions">{actions}</ol>\n'
            f"{_render_evidence_details(item.evidence)}\n"
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
        f'<p><a href="#{escape_html(recommendation_anchor(item.recommendation_id))}">'
        "View recommendation details</a></p>\n"
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
            f'<a class="id-link" href="#{escape_html(finding_anchor(fid))}">'
            f"{escape_html(fid)}</a>"
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


def _render_architecture_intelligence(section: ArchitectureIntelligenceSection) -> str:
    """Epic 3 Slice 3.3 Architecture Intelligence pack body."""

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
            f"<td>{escape_html(fact.label)}</td>"
            f"<td>{escape_html(fact.value)}</td>"
            f"<td>{escape_html(fact.note) if fact.note else '—'}</td>"
            "</tr>"
            for fact in section.overview_facts
        )
        parts.append(
            '<div class="arch-intel-group" data-group="architecture_overview">\n'
            "<h4>Architecture overview</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr><th>Fact</th><th>Value</th><th>Note</th></tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    if section.inventory_items:
        rows = "".join(
            "<tr>"
            f"<td>{escape_html(item.name)}</td>"
            f"<td>{escape_html(item.kind.replace('_', ' '))}</td>"
            f"<td>{escape_html(item.detail) if item.detail else '—'}</td>"
            "</tr>"
            for item in section.inventory_items
        )
        parts.append(
            '<div class="arch-intel-group" data-group="structural_inventory">\n'
            "<h4>Structural inventory</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr><th>Name</th><th>Kind</th><th>Detail</th></tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    if section.conclusions:
        conclusions = _dedupe_architecture_conclusions(tuple(section.conclusions))
        body = "".join(_architecture_conclusion_card(item) for item in conclusions)
        parts.extend(["<h4>Architecture conclusions</h4>", body])

    if section.findings:
        rows = "".join(
            "<tr>"
            f"<td><a class='id-link' href='#{escape_html(finding_anchor(item.finding_id))}'>"
            f"{escape_html(item.title)}</a></td>"
            f"<td>{escape_html(item.severity)}</td>"
            f"<td>{escape_html(item.confidence)}</td>"
            f"<td>{_render_id_links(item.evidence_ids, evidence_anchor)}</td>"
            f"<td>{escape_html(', '.join(item.affected_scope[:3]) or '—')}</td>"
            "</tr>"
            for item in section.findings
        )
        parts.append(
            '<div class="arch-intel-group" data-group="key_architecture_findings">\n'
            "<h4>Key architecture findings</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Finding</th><th>Severity</th><th>Confidence</th>"
            "<th>Evidence</th><th>Scope</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )
    elif section.empty_findings_message:
        parts.append(f"<p class='muted'>{escape_html(section.empty_findings_message)}</p>")

    if section.recommendations:
        rows = "".join(
            "<tr>"
            f"<td><a class='id-link' href='#{escape_html(recommendation_anchor(item.recommendation_id))}'>"
            f"{escape_html(item.title)}</a></td>"
            f"<td>{escape_html(item.priority) if item.priority else '—'}</td>"
            f"<td>{_render_id_links(item.finding_ids, finding_anchor)}</td>"
            "</tr>"
            for item in section.recommendations
        )
        parts.append(
            '<div class="arch-intel-group" data-group="architecture_recommendations">\n'
            "<h4>Architecture recommendations</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Recommendation</th><th>Priority</th><th>Supporting findings</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    if section.graph_evidence:
        rows = "".join(
            "<tr>"
            f"<td>{escape_html(item.identity)}</td>"
            f"<td>{escape_html(item.relationship_type) if item.relationship_type else '—'}</td>"
            f"<td>{escape_html(item.reference_kind) if item.reference_kind else '—'}</td>"
            f"<td>{escape_html(item.cycle_id) if item.cycle_id else '—'}</td>"
            f"<td>{('<code class=\"trace-id\">' + escape_html(item.location) + '</code>') if item.location else '—'}</td>"
            f"<td>{('<code class=\"trace-id\">' + escape_html(item.graph_artifact_ref) + '</code>') if item.graph_artifact_ref else '—'}</td>"
            "</tr>"
            for item in section.graph_evidence
        )
        parts.append(
            '<div class="arch-intel-group" data-group="graph_evidence">\n'
            "<h4>Graph and relationship evidence</h4>\n"
            '<p class="muted">Compact graph references only. Full graph payloads are not embedded.</p>\n'
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Identity</th><th>Relationship</th><th>Kind</th>"
            "<th>Cycle</th><th>Location</th><th>Graph ref</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    if section.measurements:
        rows = "".join(
            "<tr>"
            f"<td>{escape_html(item.metric_name)}</td>"
            f"<td>{escape_html(item.observed_value)}</td>"
            f"<td>{escape_html(item.operator) if item.operator else '—'}</td>"
            f"<td>{escape_html(item.threshold) if item.threshold else '—'}</td>"
            f"<td>{escape_html(item.scope) if item.scope else '—'}</td>"
            f"<td>{escape_html(', '.join(item.limitations) if item.limitations else '—')}</td>"
            "</tr>"
            for item in section.measurements
        )
        parts.append(
            '<div class="arch-intel-group" data-group="architecture_metrics">\n'
            "<h4>Architecture measurements</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Metric</th><th>Observed</th><th>Operator</th>"
            "<th>Threshold</th><th>Scope</th><th>Limitations</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
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


def _render_id_links(ids: tuple[str, ...], anchor_fn) -> str:
    if not ids:
        return "—"
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
        finding_id = str(
            getattr(item, "finding_id", None) or getattr(item, "id", "") or ""
        ).strip().lower()
        if finding_id:
            if finding_id in seen_findings:
                continue
            seen_findings.add(finding_id)
        finding_rows.append(
            "<tr>"
            f"<td>{escape_html(item.title)}</td>"
            f"<td>{escape_html(item.severity)}</td>"
            f"<td>{escape_html(', '.join(item.affected_scope[:3]) or '—')}</td>"
            "</tr>"
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
                "<th>Finding</th><th>Severity</th>"
                "<th>Scope</th>"
                "</tr></thead><tbody>"
                f"{findings}</tbody></table>",
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
            f"<td>{escape_html(fact.label)}</td>"
            f"<td>{escape_html(fact.value)}</td>"
            f"<td>{escape_html(fact.note) if fact.note else '—'}</td>"
            "</tr>"
            for fact in section.overview_facts
        )
        parts.append(
            '<div class="td-intel-group" data-group="technical_debt_overview">\n'
            "<h4>Technical debt overview</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr><th>Fact</th><th>Value</th><th>Note</th></tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    if section.measurements:
        rows = "".join(
            "<tr>"
            f"<td>{escape_html(item.metric_name)}</td>"
            f"<td>{escape_html(item.observed_value)}</td>"
            f"<td>{escape_html(item.operator) if item.operator else '—'}</td>"
            f"<td>{escape_html(item.threshold) if item.threshold else '—'}</td>"
            f"<td>{escape_html(item.scope) if item.scope else '—'}</td>"
            f"<td>{('<code class=\"trace-id\">' + escape_html(item.location) + '</code>') if item.location else '—'}</td>"
            f"<td>{escape_html(item.availability)}</td>"
            f"<td>{escape_html(', '.join(item.limitations) if item.limitations else '—')}</td>"
            "</tr>"
            for item in section.measurements
        )
        parts.append(
            '<div class="td-intel-group" data-group="technical_debt_measurements">\n'
            "<h4>Technical debt measurements</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Metric</th><th>Observed</th><th>Operator</th>"
            "<th>Threshold</th><th>Scope</th><th>Location</th>"
            "<th>Availability</th><th>Limitations</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    if section.hotspots:
        rows = "".join(
            "<tr>"
            f"<td><code class='trace-id'>{escape_html(item.path)}</code></td>"
            f"<td>{escape_html(item.symbol)}</td>"
            f"<td>{escape_html(item.metric_name)}</td>"
            f"<td>{escape_html(item.observed_value)}</td>"
            f"<td>{escape_html(item.threshold) if item.threshold else '—'}</td>"
            f"<td>{escape_html(item.severity)}</td>"
            f"<td>{escape_html(item.confidence)}</td>"
            f"<td><a class='id-link' href='#{escape_html(finding_anchor(item.finding_id))}'>"
            f"{escape_html(item.finding_id)}</a></td>"
            f"<td>{_render_id_links(item.evidence_ids, evidence_anchor)}</td>"
            "</tr>"
            for item in section.hotspots
        )
        parts.append(
            '<div class="td-intel-group" data-group="technical_debt_hotspots">\n'
            "<h4>Technical debt hotspots</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Path</th><th>Symbol</th><th>Metric</th><th>Value</th>"
            "<th>Threshold</th><th>Severity</th><th>Confidence</th>"
            "<th>Finding</th><th>Evidence</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    if section.findings:
        rows = "".join(
            "<tr>"
            f"<td><a class='id-link' href='#{escape_html(finding_anchor(item.finding_id))}'>"
            f"{escape_html(item.title)}</a></td>"
            f"<td>{escape_html(item.severity)}</td>"
            f"<td>{escape_html(item.confidence)}</td>"
            f"<td>{_render_id_links(item.evidence_ids, evidence_anchor)}</td>"
            f"<td>{escape_html(', '.join(item.affected_scope[:3]) or '—')}</td>"
            "</tr>"
            for item in section.findings
        )
        parts.append(
            '<div class="td-intel-group" data-group="key_technical_debt_findings">\n'
            "<h4>Key technical debt findings</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Finding</th><th>Severity</th><th>Confidence</th>"
            "<th>Evidence</th><th>Scope</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )
    elif section.empty_findings_message:
        parts.append(f"<p class='muted'>{escape_html(section.empty_findings_message)}</p>")

    if section.recommendations:
        rows = "".join(
            "<tr>"
            f"<td><a class='id-link' href='#{escape_html(recommendation_anchor(item.recommendation_id))}'>"
            f"{escape_html(item.title)}</a></td>"
            f"<td>{escape_html(item.priority) if item.priority else '—'}</td>"
            f"<td>{_render_id_links(item.finding_ids, finding_anchor)}</td>"
            "</tr>"
            for item in section.recommendations
        )
        parts.append(
            '<div class="td-intel-group" data-group="technical_debt_recommendations">\n'
            "<h4>Technical debt recommendations</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Recommendation</th><th>Priority</th><th>Supporting findings</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
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
            "technical debt. Broader technical debt categories were not evaluated.</p>"
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
                "<th>Theme</th><th>Rule</th><th>Findings</th>"
                "<th>High</th><th>Medium</th>"
                "</tr></thead><tbody>"
                f"{themes}</tbody></table>",
            ]
        )
    if hotspots:
        parts.extend(
            [
                "<h4>Top production hotspots</h4>",
                "<table><thead><tr>"
                "<th>#</th><th>Path</th><th>Unit</th><th>Highest severity</th>"
                "<th>Findings</th><th>Rules</th><th>Metrics</th>"
                "</tr></thead><tbody>"
                f"{hotspots}</tbody></table>",
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
                f"<tbody>{coverage}</tbody></table>",
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
            f"<td>{escape_html(fact.label)}</td>"
            f"<td>{escape_html(fact.value)}</td>"
            f"<td>{escape_html(fact.note) if fact.note else '—'}</td>"
            "</tr>"
            for fact in section.overview_facts
        )
        parts.append(
            '<div class="dep-intel-group" data-group="dependency_overview">\n'
            "<h4>Dependency overview</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr><th>Fact</th><th>Value</th><th>Note</th></tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    if section.ecosystems:
        rows = "".join(
            "<tr>"
            f"<td>{escape_html(item.name)}</td>"
            f"<td>{item.manifest_count}</td>"
            f"<td>{item.declaration_count if item.declaration_count is not None else '—'}</td>"
            f"<td>{escape_html(item.parse_status) if item.parse_status else '—'}</td>"
            f"<td>{escape_html(item.version_availability) if item.version_availability else '—'}</td>"
            f"<td>{escape_html(item.note) if item.note else '—'}</td>"
            "</tr>"
            for item in section.ecosystems
        )
        parts.append(
            '<div class="dep-intel-group" data-group="dependency_ecosystems">\n'
            "<h4>Ecosystems</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Ecosystem</th><th>Manifests</th><th>Declarations</th>"
            "<th>Parse status</th><th>Version availability</th><th>Note</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    if section.manifests:
        rows = "".join(
            "<tr>"
            f"<td><code class='trace-id'>{escape_html(item.path)}</code></td>"
            f"<td>{escape_html(item.ecosystem)}</td>"
            f"<td>{escape_html(item.manifest_type)}</td>"
            f"<td>{escape_html(item.parse_status) if item.parse_status else '—'}</td>"
            f"<td>{item.finding_count if item.finding_count is not None else '—'}</td>"
            f"<td>{escape_html(', '.join(item.limitations) if item.limitations else '—')}</td>"
            "</tr>"
            for item in section.manifests
        )
        parts.append(
            '<div class="dep-intel-group" data-group="dependency_manifest_inventory">\n'
            "<h4>Manifest inventory</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Path</th><th>Ecosystem</th><th>Manifest type</th>"
            "<th>Parse status</th><th>Findings</th><th>Limitations</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    if section.findings:
        rows = "".join(
            "<tr>"
            f"<td><a class='id-link' href='#{escape_html(finding_anchor(item.finding_id))}'>"
            f"{escape_html(item.title)}</a></td>"
            f"<td>{escape_html(item.severity)}</td>"
            f"<td>{escape_html(item.confidence)}</td>"
            f"<td><code>{escape_html(item.rule_id)}</code></td>"
            f"<td>{('<code class=\"trace-id\">' + escape_html(item.path) + '</code>') if item.path else '—'}</td>"
            f"<td>{escape_html(item.ecosystem) if item.ecosystem else '—'}</td>"
            f"<td>{_render_id_links(item.evidence_ids, evidence_anchor)}</td>"
            "</tr>"
            for item in section.findings
        )
        parts.append(
            '<div class="dep-intel-group" data-group="dependency_hygiene_findings">\n'
            "<h4>Hygiene findings</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Finding</th><th>Severity</th><th>Confidence</th>"
            "<th>Rule</th><th>Path</th><th>Ecosystem</th><th>Evidence</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )
    elif section.empty_findings_message:
        parts.append(f"<p class='muted'>{escape_html(section.empty_findings_message)}</p>")

    if section.recommendations:
        rows = "".join(
            "<tr>"
            f"<td><a class='id-link' href='#{escape_html(recommendation_anchor(item.recommendation_id))}'>"
            f"{escape_html(item.title)}</a></td>"
            f"<td>{escape_html(item.priority) if item.priority else '—'}</td>"
            f"<td>{_render_id_links(item.finding_ids, finding_anchor)}</td>"
            "</tr>"
            for item in section.recommendations
        )
        parts.append(
            '<div class="dep-intel-group" data-group="dependency_recommendations">\n'
            "<h4>Dependency recommendations</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Recommendation</th><th>Priority</th><th>Supporting findings</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
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
                "scope. Only declaration hygiene was assessed. Zero findings do "
                "not mean a healthy or secure dependency posture."
            )
        production_findings = f"<p>{escape_html(none_stmt)}</p>"
    else:
        production_findings = (
            "".join(
                "<article class='card'>"
                f"<h4>{escape_html(item.title)}</h4>"
                f"<p>{escape_html(item.explanation)}</p>"
                f"<p><strong>Remediation:</strong> {escape_html(item.remediation)}</p>"
                "<p class='muted'>"
                f"ID: <code>{escape_html(item.finding_id)}</code> · "
                f"Rule: <code>{escape_html(item.rule_id)}</code> · "
                f"Severity: {escape_html(item.severity)} · "
                f"Confidence: {escape_html(item.confidence)} · "
                f"Source role: {escape_html(item.source_role)}"
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
            f"<h4>{escape_html(item.title)}</h4>"
            f"<p>{escape_html(item.explanation)}</p>"
            f"<p><strong>Remediation:</strong> {escape_html(item.remediation)}</p>"
            "<p class='muted'>"
            f"ID: <code>{escape_html(item.finding_id)}</code> · "
            f"Rule: <code>{escape_html(item.rule_id)}</code> · "
            f"Source role: {escape_html(item.source_role)}"
            + (f" · Path: <code>{escape_html(item.path)}</code>" if item.path else "")
            + "</p>"
            "</article>"
            for item in test_obs.findings
        )
        test_block = (
            f"<h4>{escape_html(test_obs.title)}</h4>"
            f"<p>{escape_html(test_obs.summary)}</p>"
            f"<p class='muted'>Test/fixture findings: {test_obs.finding_count}</p>"
            f"{test_findings}"
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
            f"<td>{escape_html(fact.label)}</td>"
            f"<td>{escape_html(fact.value)}</td>"
            f"<td>{escape_html(fact.note) if fact.note else '—'}</td>"
            "</tr>"
            for fact in section.overview_facts
        )
        parts.append(
            '<div class="sec-intel-group" data-group="security_overview">\n'
            "<h4>Security overview</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr><th>Fact</th><th>Value</th><th>Note</th></tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    if section.artifacts:
        rows = "".join(
            "<tr>"
            f"<td>{escape_html(item.classification)}</td>"
            f"<td>{escape_html(item.kind) if item.kind else '—'}</td>"
            f"<td>{('<code class=\"trace-id\">' + escape_html(item.path) + '</code>') if item.path else '—'}</td>"
            f"<td>{escape_html(item.note) if item.note else '—'}</td>"
            "</tr>"
            for item in section.artifacts
        )
        parts.append(
            '<div class="sec-intel-group" data-group="security_sensitive_artifacts">\n'
            "<h4>Sensitive artifact inventory</h4>\n"
            '<p class="muted">Classification and relative path only. Values are '
            "never shown.</p>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Classification</th><th>Kind</th><th>Path</th><th>Note</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    if section.config_observations:
        rows = "".join(
            "<tr>"
            f"<td>{escape_html(item.label)}</td>"
            f"<td>{('<code class=\"trace-id\">' + escape_html(item.path) + '</code>') if item.path else '—'}</td>"
            f"<td>{_render_id_links((item.evidence_id,), evidence_anchor) if item.evidence_id else '—'}</td>"
            f"<td>{escape_html(item.redacted_snippet) if item.redacted_snippet else '—'}</td>"
            f"<td>{escape_html(item.note) if item.note else '—'}</td>"
            "</tr>"
            for item in section.config_observations
        )
        parts.append(
            '<div class="sec-intel-group" data-group="security_config_observations">\n'
            "<h4>Configuration observations</h4>\n"
            '<p class="muted">Fact labels from deterministic findings only. '
            "Raw configuration values are not shown.</p>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Observation</th><th>Path</th><th>Evidence</th>"
            "<th>Redacted snippet</th><th>Note</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    if section.findings:
        rows = "".join(
            "<tr>"
            f"<td><a class='id-link' href='#{escape_html(finding_anchor(item.finding_id))}'>"
            f"{escape_html(item.title)}</a></td>"
            f"<td>{escape_html(item.severity)}</td>"
            f"<td>{escape_html(item.confidence)}</td>"
            f"<td><code>{escape_html(item.rule_id)}</code></td>"
            f"<td>{('<code class=\"trace-id\">' + escape_html(item.path) + '</code>') if item.path else '—'}</td>"
            f"<td>{_render_id_links(item.evidence_ids, evidence_anchor)}</td>"
            "</tr>"
            for item in section.findings
        )
        parts.append(
            '<div class="sec-intel-group" data-group="security_findings">\n'
            "<h4>Security findings</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Finding</th><th>Severity</th><th>Confidence</th>"
            "<th>Rule</th><th>Path</th><th>Evidence</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )
    elif section.empty_findings_message:
        parts.append(f"<p class='muted'>{escape_html(section.empty_findings_message)}</p>")

    if section.recommendations:
        rows = "".join(
            "<tr>"
            f"<td><a class='id-link' href='#{escape_html(recommendation_anchor(item.recommendation_id))}'>"
            f"{escape_html(item.title)}</a></td>"
            f"<td>{escape_html(item.priority) if item.priority else '—'}</td>"
            f"<td>{_render_id_links(item.finding_ids, finding_anchor)}</td>"
            "</tr>"
            for item in section.recommendations
        )
        parts.append(
            '<div class="sec-intel-group" data-group="security_recommendations">\n'
            "<h4>Security recommendations</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Recommendation</th><th>Priority</th><th>Supporting findings</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
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
                "repository scope. This assessment evaluated static repository "
                "evidence only. Absence of findings should not be interpreted "
                "as absence of security risk."
            )
        production_findings = f"<p>{escape_html(none_stmt)}</p>"
    else:
        production_findings = (
            "".join(
                "<article class='card'>"
                f"<h4>{escape_html(item.title)}</h4>"
                f"<p>{escape_html(item.explanation or '')}</p>"
                + (
                    f"<p><strong>Remediation:</strong> {escape_html(item.remediation)}</p>"
                    if item.remediation
                    else ""
                )
                + "<p class='muted'>"
                f"ID: <code>{escape_html(item.finding_id)}</code> · "
                f"Rule: <code>{escape_html(item.rule_id)}</code> · "
                f"Severity: {escape_html(item.severity)} · "
                f"Category: {escape_html(item.category)} · "
                f"Source role: {escape_html(item.source_role)}"
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
            f"({finding.test_finding_count} test/fixture, "
            f"{finding.unknown_finding_count} unknown). These do not contribute "
            "to the production-primary view.</p>"
            + "".join(
                "<article class='card'>"
                f"<h4>{escape_html(item.title)}</h4>"
                f"<p>{escape_html(item.explanation or '')}</p>"
                "<p class='muted'>"
                f"ID: <code>{escape_html(item.finding_id)}</code> · "
                f"Rule: <code>{escape_html(item.rule_id)}</code> · "
                f"Source role: {escape_html(item.source_role)}"
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
                f"<h5>{escape_html(item.title)}</h5>"
                f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
                f"<p>{escape_html(item.rationale)}</p>"
                f"<p class='muted'>"
                f"ID: <code>{escape_html(item.recommendation_id)}</code> · "
                f"{'Conditional' if item.conditional else 'Direct'} · "
                f"Audience: {escape_html(item.audience)}"
                "</p></article>"
                for item in group.recommendations
            )
            for group in section.recommendation_groups
        )
    else:
        recommendations = "".join(
            "<article class='card'>"
            f"<h4>{escape_html(item.title)}</h4>"
            f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
            f"<p>{escape_html(item.rationale)}</p>"
            f"<p class='muted'>"
            f"ID: <code>{escape_html(item.recommendation_id)}</code> · "
            f"{'Conditional' if item.conditional else 'Direct'} · "
            f"Audience: {escape_html(item.audience)}"
            "</p></article>"
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
                f"{section.themes_total}</p>",
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
                f"{section.conclusions_total}</p>",
                conclusions,
            ]
        )
    if recommendations:
        parts.extend(
            [
                "<h4>Recommendations</h4>",
                f"<p class='muted'>Showing {section.recommendations_displayed} of "
                f"{section.recommendations_total}</p>",
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
            "<th>Status</th><th>Findings</th></tr></thead>"
            f"<tbody>{rule_rows}</tbody></table>"
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
            f"(showing {inventory.finding_ids_displayed} of "
            f"{inventory.finding_count}):</p><ul>"
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
                f"<h5>{escape_html(item.title)}</h5>"
                f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
                f"<p>{escape_html(item.rationale)}</p>"
                f"<p class='muted'>"
                f"ID: <code>{escape_html(item.recommendation_id)}</code> · "
                f"{'Conditional' if item.conditional else 'Direct'} · "
                f"Audience: {escape_html(item.audience)}"
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
            f"<h4>{escape_html(item.title)}</h4>"
            f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
            f"<p>{escape_html(item.rationale)}</p>"
            f"<p class='muted'>"
            f"ID: <code>{escape_html(item.recommendation_id)}</code>"
            "</p></article>"
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
                f"{section.themes_total}</p>",
                themes,
            ]
        )
    if conclusions:
        parts.extend(
            [
                "<h4>Conclusions</h4>",
                f"<p class='muted'>Showing {section.conclusions_displayed} of "
                f"{section.conclusions_total}</p>",
                conclusions,
            ]
        )
    if recommendations:
        parts.extend(
            [
                "<h4>Recommendations</h4>",
                f"<p class='muted'>Showing {section.recommendations_displayed} of "
                f"{section.recommendations_total}</p>",
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
            f"<td>{escape_html(fact.label)}</td>"
            f"<td>{escape_html(fact.value)}</td>"
            f"<td>{escape_html(fact.note) if fact.note else '—'}</td>"
            "</tr>"
            for fact in section.overview_facts
        )
        parts.append(
            '<div class="cloud-intel-group" data-group="cloud_overview">\n'
            "<h4>Cloud overview</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr><th>Fact</th><th>Value</th><th>Note</th></tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    for group in section.signal_groups:
        if not group.signals:
            continue
        rows = "".join(
            "<tr>"
            f"<td>{escape_html(item.label)}</td>"
            f"<td><code>{escape_html(item.family)}</code></td>"
            f"<td>{('<code class=\"trace-id\">' + escape_html(item.path) + '</code>') if item.path else '—'}</td>"
            f"<td>{_render_id_links((item.finding_id,), finding_anchor) if item.finding_id else '—'}</td>"
            f"<td>{_render_id_links(item.evidence_ids, evidence_anchor)}</td>"
            f"<td>{escape_html(item.note) if item.note else '—'}</td>"
            "</tr>"
            for item in group.signals
        )
        parts.append(
            f'<div class="cloud-intel-group" data-group="{escape_html(group.group_id)}">\n'
            f"<h4>{escape_html(group.title)}</h4>\n"
            '<p class="muted">Repository-observable declarations only. Detected '
            "signals do not prove successful deployment.</p>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Signal</th><th>Family</th><th>Path</th>"
            "<th>Finding</th><th>Evidence</th><th>Note</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    if section.findings:
        rows = "".join(
            "<tr>"
            f"<td><a class='id-link' href='#{escape_html(finding_anchor(item.finding_id))}'>"
            f"{escape_html(item.title)}</a></td>"
            f"<td>{escape_html(item.severity)}</td>"
            f"<td>{escape_html(item.confidence)}</td>"
            f"<td><code>{escape_html(item.rule_id)}</code></td>"
            f"<td>{('<code class=\"trace-id\">' + escape_html(item.path) + '</code>') if item.path else '—'}</td>"
            f"<td>{_render_id_links(item.evidence_ids, evidence_anchor)}</td>"
            "</tr>"
            for item in section.findings
        )
        parts.append(
            '<div class="cloud-intel-group" data-group="cloud_findings">\n'
            "<h4>Cloud findings</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Finding</th><th>Severity</th><th>Confidence</th>"
            "<th>Rule</th><th>Path</th><th>Evidence</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )
    elif section.empty_findings_message:
        parts.append(f"<p class='muted'>{escape_html(section.empty_findings_message)}</p>")

    if section.recommendations:
        rows = "".join(
            "<tr>"
            f"<td><a class='id-link' href='#{escape_html(recommendation_anchor(item.recommendation_id))}'>"
            f"{escape_html(item.title)}</a></td>"
            f"<td>{escape_html(item.priority) if item.priority else '—'}</td>"
            f"<td>{_render_id_links(item.finding_ids, finding_anchor)}</td>"
            "</tr>"
            for item in section.recommendations
        )
        parts.append(
            '<div class="cloud-intel-group" data-group="cloud_recommendations">\n'
            "<h4>Cloud recommendations</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Recommendation</th><th>Priority</th><th>Supporting findings</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
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
            f"<td>{escape_html(fact.label)}</td>"
            f"<td>{escape_html(fact.value)}</td>"
            f"<td>{escape_html(fact.note) if fact.note else '—'}</td>"
            "</tr>"
            for fact in section.overview_facts
        )
        parts.append(
            '<div class="ai-intel-group" data-group="ai_readiness_overview">\n'
            "<h4>AI readiness overview</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr><th>Fact</th><th>Value</th><th>Note</th></tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    for group in section.signal_groups:
        if not group.signals:
            continue
        rows = "".join(
            "<tr>"
            f"<td>{escape_html(item.label)}</td>"
            f"<td><code>{escape_html(item.family)}</code></td>"
            f"<td>{('<code class=\"trace-id\">' + escape_html(item.path) + '</code>') if item.path else '—'}</td>"
            f"<td>{_render_id_links((item.finding_id,), finding_anchor) if item.finding_id else '—'}</td>"
            f"<td>{_render_id_links(item.evidence_ids, evidence_anchor)}</td>"
            f"<td>{escape_html(item.note) if item.note else '—'}</td>"
            "</tr>"
            for item in group.signals
        )
        parts.append(
            f'<div class="ai-intel-group" data-group="{escape_html(group.group_id)}">\n'
            f"<h4>{escape_html(group.title)}</h4>\n"
            '<p class="muted">Repository-observable AI-enablement signals only. '
            "Detected integrations do not prove production use.</p>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Signal</th><th>Family</th><th>Path</th>"
            "<th>Finding</th><th>Evidence</th><th>Note</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    if section.findings:
        rows = "".join(
            "<tr>"
            f"<td><a class='id-link' href='#{escape_html(finding_anchor(item.finding_id))}'>"
            f"{escape_html(item.title)}</a></td>"
            f"<td>{escape_html(item.severity)}</td>"
            f"<td>{escape_html(item.confidence)}</td>"
            f"<td><code>{escape_html(item.rule_id)}</code></td>"
            f"<td>{('<code class=\"trace-id\">' + escape_html(item.path) + '</code>') if item.path else '—'}</td>"
            f"<td>{_render_id_links(item.evidence_ids, evidence_anchor)}</td>"
            "</tr>"
            for item in section.findings
        )
        parts.append(
            '<div class="ai-intel-group" data-group="ai_readiness_findings">\n'
            "<h4>AI readiness findings</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Finding</th><th>Severity</th><th>Confidence</th>"
            "<th>Rule</th><th>Path</th><th>Evidence</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )
    elif section.empty_findings_message:
        parts.append(f"<p class='muted'>{escape_html(section.empty_findings_message)}</p>")

    if section.recommendations:
        rows = "".join(
            "<tr>"
            f"<td><a class='id-link' href='#{escape_html(recommendation_anchor(item.recommendation_id))}'>"
            f"{escape_html(item.title)}</a></td>"
            f"<td>{escape_html(item.priority) if item.priority else '—'}</td>"
            f"<td>{_render_id_links(item.finding_ids, finding_anchor)}</td>"
            "</tr>"
            for item in section.recommendations
        )
        parts.append(
            '<div class="ai-intel-group" data-group="ai_readiness_recommendations">\n'
            "<h4>AI readiness recommendations</h4>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Recommendation</th><th>Priority</th><th>Supporting findings</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
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
            f"<td>{escape_html(fact.label)}</td>"
            f"<td>{escape_html(fact.value)}</td>"
            f"<td>{escape_html(fact.note) if fact.note else '—'}</td>"
            "</tr>"
            for fact in section.overview_facts
        )
        parts.append(
            '<div class="mod-intel-group" data-group="modernization_overview">\n'
            "<h4>Modernization overview</h4>\n"
            '<p class="muted">Synthesis of deterministic findings, recommendations, '
            "Priority Actions, and roadmap initiatives. This is not an independent "
            "analyzer.</p>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr><th>Fact</th><th>Value</th><th>Note</th></tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    if section.contributing_heads:
        rows = "".join(
            "<tr>"
            f'<td><a class="id-link" href="#{escape_html(item.anchor)}">'
            f"{escape_html(item.title)}</a></td>"
            f"<td>{item.finding_count}</td>"
            f"<td>{item.recommendation_count}</td>"
            f"<td>{item.priority_action_count}</td>"
            "</tr>"
            for item in section.contributing_heads
        )
        parts.append(
            '<div class="mod-intel-group" data-group="contributing_heads">\n'
            "<h4>Contributing assessment heads</h4>\n"
            '<p class="muted">Entities retain their original assessment-head '
            "classification. A Security recommendation remains Security Intelligence "
            "even when it contributes to modernization.</p>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Assessment head</th><th>Findings</th>"
            "<th>Recommendations</th><th>Priority Actions</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )

    if section.priority_actions:
        rows = "".join(
            "<tr>"
            f'<td><a class="id-link" href="#{escape_html(priority_action_anchor(item.action_id))}">'
            f"{escape_html(item.title)}</a></td>"
            f"<td>{escape_html(item.priority) if item.priority else '—'}</td>"
            f"<td>{escape_html(item.presentation_bucket) if item.presentation_bucket else '—'}</td>"
            f"<td>{escape_html(item.effort) if item.effort else '—'}</td>"
            f"<td>{item.supporting_recommendation_count}</td>"
            f"<td>{item.supporting_finding_count}</td>"
            f"<td>{escape_html(item.head_title) if item.head_title else '—'}</td>"
            f"<td>{escape_html(item.evidence_completeness) if item.evidence_completeness else '—'}</td>"
            "</tr>"
            for item in section.priority_actions
        )
        parts.append(
            '<div class="mod-intel-group" data-group="priority_actions">\n'
            "<h4>Priority Actions</h4>\n"
            '<p class="muted">Canonical Priority Actions only. Full detail remains in '
            '<a class="id-link" href="#priority-actions">Priority Actions</a>.</p>\n'
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Action</th><th>Priority</th><th>Horizon</th><th>Effort</th>"
            "<th>Recs</th><th>Findings</th><th>Head</th><th>Evidence</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
        )
    elif section.empty_actions_message:
        parts.append(
            f"<p class='muted'>{escape_html(section.empty_actions_message)}</p>"
        )

    if section.roadmap_phases:
        phase_blocks: list[str] = []
        for phase in section.roadmap_phases:
            if not phase.initiatives:
                continue
            legacy_note = (
                ' <span class="muted">(includes legacy items)</span>'
                if phase.has_legacy
                else ""
            )
            rows = "".join(
                "<tr>"
                f'<td><a class="id-link" href="#{escape_html(roadmap_initiative_anchor(item.initiative_id))}">'
                f"{escape_html(item.title)}</a>"
                f'{" <span class=\"badge\">Legacy</span>" if item.is_legacy else ""}'
                "</td>"
                f"<td>{item.sequence}</td>"
                f"<td>{escape_html(item.priority) if item.priority else '—'}</td>"
                f"<td>{escape_html(item.effort) if item.effort else '—'}</td>"
                f"<td>{_render_id_links(item.supporting_priority_action_ids, priority_action_anchor) if item.supporting_priority_action_ids else ('—' if not item.is_legacy else '<span class=\"muted\">Legacy — limited traceability</span>')}</td>"
                f"<td>{escape_html(item.evidence_completeness) if item.evidence_completeness else '—'}</td>"
                "</tr>"
                for item in phase.initiatives
            )
            phase_blocks.append(
                f"<h5>{escape_html(phase.title)} "
                f"<span class='count-pill'>{phase.initiative_count}</span>"
                f"{legacy_note}</h5>\n"
                '<div class="table-wrap"><table>\n'
                "<thead><tr>"
                "<th>Initiative</th><th>Sequence</th><th>Priority</th><th>Effort</th>"
                "<th>Priority Actions</th><th>Evidence</th>"
                "</tr></thead>\n"
                f"<tbody>{rows}</tbody>\n</table></div>"
            )
        if phase_blocks:
            legacy_banner = (
                '<p class="muted">Legacy roadmap items are visibly marked and may '
                "have limited traceability. The roadmap is planning guidance, not a "
                "delivery commitment.</p>\n"
                if section.roadmap_is_legacy
                else '<p class="muted">Canonical Priority Action-backed roadmap. '
                "Full phase detail remains in "
                '<a class="id-link" href="#phased-modernization-plan">'
                "Roadmap</a>. Planning guidance, not a delivery commitment.</p>\n"
            )
            parts.append(
                '<div class="mod-intel-group" data-group="roadmap_phases">\n'
                "<h4>Roadmap phases</h4>\n"
                f"{legacy_banner}"
                f"{''.join(phase_blocks)}\n"
                "</div>"
            )

    if section.themes:
        rows = "".join(
            "<tr>"
            f'<td><a class="id-link" href="#{escape_html(item.anchor)}">'
            f"{escape_html(item.title)}</a></td>"
            f"<td>{item.priority_action_count}</td>"
            f"<td>{item.recommendation_count}</td>"
            f"<td>{escape_html('; '.join(item.top_titles)) if item.top_titles else '—'}</td>"
            "</tr>"
            for item in section.themes
        )
        parts.append(
            '<div class="mod-intel-group" data-group="modernization_themes">\n'
            "<h4>Key modernization themes</h4>\n"
            '<p class="muted">Themes are derived from assessment-head grouping of '
            "deterministic Priority Actions and recommendations. Free-form narrative "
            "themes are not invented.</p>\n"
            '<div class="table-wrap"><table>\n'
            "<thead><tr>"
            "<th>Theme (assessment head)</th><th>Priority Actions</th>"
            "<th>Recommendations</th><th>Top titles</th>"
            "</tr></thead>\n"
            f"<tbody>{rows}</tbody>\n</table></div>\n"
            "</div>"
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
            "<th>Status</th><th>Findings</th></tr></thead>"
            f"<tbody>{rule_rows}</tbody></table>"
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
            f"(showing {inventory.finding_ids_displayed} of "
            f"{inventory.finding_count}):</p><ul>"
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
                f"<h5>{escape_html(item.title)}</h5>"
                f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
                f"<p>{escape_html(item.rationale)}</p>"
                f"<p class='muted'>"
                f"ID: <code>{escape_html(item.recommendation_id)}</code> · "
                f"{'Conditional' if item.conditional else 'Direct'} · "
                f"Audience: {escape_html(item.audience)}"
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
            f"<h4>{escape_html(item.title)}</h4>"
            f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
            f"<p>{escape_html(item.rationale)}</p>"
            f"<p class='muted'>"
            f"ID: <code>{escape_html(item.recommendation_id)}</code>"
            "</p></article>"
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
                f"{section.themes_total}</p>",
                themes,
            ]
        )
    if conclusions:
        parts.extend(
            [
                "<h4>Conclusions</h4>",
                f"<p class='muted'>Showing {section.conclusions_displayed} of "
                f"{section.conclusions_total}</p>",
                conclusions,
            ]
        )
    if recommendations:
        parts.extend(
            [
                "<h4>Recommendations</h4>",
                f"<p class='muted'>Showing {section.recommendations_displayed} of "
                f"{section.recommendations_total}</p>",
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
            "<th>Status</th><th>Findings</th></tr></thead>"
            f"<tbody>{rule_rows}</tbody></table>"
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
            f"(showing {inventory.finding_ids_displayed} of "
            f"{inventory.finding_count}):</p><ul>"
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
                f"<h5>{escape_html(item.title)}</h5>"
                f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
                f"<p>{escape_html(item.rationale)}</p>"
                f"<p class='muted'>"
                f"ID: <code>{escape_html(item.recommendation_id)}</code> · "
                f"{'Conditional' if item.conditional else 'Direct'} · "
                f"Audience: {escape_html(item.audience)}"
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
            f"<h4>{escape_html(item.title)}</h4>"
            f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
            f"<p>{escape_html(item.rationale)}</p>"
            f"<p class='muted'>"
            f"ID: <code>{escape_html(item.recommendation_id)}</code>"
            "</p></article>"
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
                f"{section.themes_total}</p>",
                themes,
            ]
        )
    if conclusions:
        parts.extend(
            [
                "<h4>Conclusions</h4>",
                f"<p class='muted'>Showing {section.conclusions_displayed} of "
                f"{section.conclusions_total}</p>",
                conclusions,
            ]
        )
    if recommendations:
        parts.extend(
            [
                "<h4>Recommendations</h4>",
                f"<p class='muted'>Showing {section.recommendations_displayed} of "
                f"{section.recommendations_total}</p>",
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
    recommendation_titles = {
        item.recommendation_id: item.title for item in view.priority_actions
    }

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
            f"<h3>{escape_html(phase.title)} "
            f"<span class='count-pill'>{len(initiatives)}</span></h3>"
            f"<p class='muted'>{escape_html(phase.objective)}</p>"
            f"<div class='card-stack'>{cards}</div>"
            "</div>"
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
        f' id="{escape_html(roadmap_initiative_anchor(initiative_id))}"'
        if initiative_id
        else ""
    )

    pa_ids = tuple(getattr(item, "supporting_priority_action_ids", ()) or ())
    initiative_type = str(
        getattr(item, "initiative_type", "legacy") or "legacy"
    ).strip().lower()
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
            f"<p><em>Priority Actions</em> "
            f"{_title_links(pa_ids, pa_titles, anchor_fn=priority_action_anchor, empty='None')}"
            "</p>\n"
        )
    elif is_legacy:
        pa_html = (
            '<p class="muted"><em>Legacy roadmap item</em> — Limited traceability</p>\n'
        )

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
    legacy_badge = (
        '<span class="badge">Legacy roadmap item</span> ' if is_legacy else ""
    )
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
            "<th>Status</th><th>Findings</th></tr></thead>"
            f"<tbody>{rule_rows}</tbody></table>"
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
            f"(showing {inventory.finding_ids_displayed} of "
            f"{inventory.finding_count}):</p><ul>"
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
                f"<h5>{escape_html(item.title)}</h5>"
                f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
                f"<p>{escape_html(item.rationale)}</p>"
                f"<p class='muted'>"
                f"ID: <code>{escape_html(item.recommendation_id)}</code> · "
                f"{'Conditional' if item.conditional else 'Direct'} · "
                f"Audience: {escape_html(item.audience)}"
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
            f"<h4>{escape_html(item.title)}</h4>"
            f"<p><strong>Action:</strong> {escape_html(item.action)}</p>"
            f"<p>{escape_html(item.rationale)}</p>"
            f"<p class='muted'>"
            f"ID: <code>{escape_html(item.recommendation_id)}</code>"
            "</p></article>"
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
                f"{section.themes_total}</p>",
                themes,
            ]
        )
    if conclusions:
        parts.extend(
            [
                "<h4>Conclusions</h4>",
                f"<p class='muted'>Showing {section.conclusions_displayed} of "
                f"{section.conclusions_total}</p>",
                conclusions,
            ]
        )
    if recommendations:
        parts.extend(
            [
                "<h4>Recommendations</h4>",
                f"<p class='muted'>Showing {section.recommendations_displayed} of "
                f"{section.recommendations_total}</p>",
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


def _render_ai(ai: AiEnrichmentView) -> str:
    themes = (
        "".join(
            "<li>"
            f"<strong>{escape_html(theme.title)}</strong> — {escape_html(theme.summary)}"
            f"<div class='ids'>Findings: {_id_list(theme.related_finding_ids) or '—'}"
            f" · Recommendations: {_id_list(theme.related_recommendation_ids) or '—'}</div>"
            "</li>"
            for theme in ai.themes
        )
        or "<li>None</li>"
    )
    priorities = (
        "".join(
            "<li>"
            f'<span class="badge priority-{escape_html(item.priority)}">'
            f"{escape_html(item.priority)}</span> "
            f"<strong>{escape_html(item.title)}</strong> — {escape_html(item.rationale)}"
            f"<div class='ids'>Findings: {_id_list(item.related_finding_ids) or '—'}"
            f" · Recommendations: {_id_list(item.related_recommendation_ids) or '—'}</div>"
            "</li>"
            for item in ai.priorities
        )
        or "<li>None</li>"
    )
    risks = (
        "".join(
            "<li>"
            f'<span class="badge severity-{escape_html(item.severity)}">'
            f"{escape_html(item.severity)}</span> "
            f"<strong>{escape_html(item.title)}</strong> — {escape_html(item.summary)}"
            "</li>"
            for item in ai.risks
        )
        or "<li>None</li>"
    )
    steps = (
        "".join(
            f"<li><strong>{step.order}. {escape_html(step.title)}</strong> — "
            f"{escape_html(step.summary)}</li>"
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


def _appendix_findings(view: HtmlReportViewModel):
    """Findings for the All Findings appendix — excludes unclassified (shown above).

    Slice 3.12: unclassified full cards own the canonical finding/evidence ids in
    Unclassified Results; duplicating them in All Findings created duplicate HTML ids.
    """

    unclassified_ids = {
        item.finding_id for item in (view.unclassified_findings or ())
    }
    if not unclassified_ids:
        return view.findings
    return tuple(
        item for item in view.findings if item.finding_id not in unclassified_ids
    )


def _appendix_recommendations(view: HtmlReportViewModel):
    """Recommendations for All Recommendations — excludes unclassified (shown above)."""

    unclassified_ids = {
        item.recommendation_id for item in (view.unclassified_recommendations or ())
    }
    if not unclassified_ids:
        return view.recommendations
    return tuple(
        item
        for item in view.recommendations
        if item.recommendation_id not in unclassified_ids
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
            "<summary>Unclassified Results</summary>\n"
            f'<p class="muted">{limitation}</p>\n'
            "<h4>Unclassified findings</h4>\n"
            f"{unclassified_findings}\n"
            "<h4>Unclassified recommendations</h4>\n"
            f"{unclassified_recommendations}\n"
            "</details>\n"
        )

    additional_packs = ""
    pack_parts: list[str] = []
    if view.testing_report is not None:
        pack_parts.append(
            "<h4>Testing Assessment</h4>\n"
            f"{_render_testing(view.testing_report)}"
        )
    if view.performance_report is not None:
        pack_parts.append(
            "<h4>Performance Assessment</h4>\n"
            f"{_render_performance(view.performance_report)}"
        )
    if pack_parts:
        packs_body = "\n".join(pack_parts)
        additional_packs = (
            '<details class="tech-block" id="additional-domain-packs">\n'
            "<summary>Additional domain packs</summary>\n"
            f"{packs_body}\n"
            "</details>\n"
        )

    findings_body = (
        "\n".join(
            _render_finding_card(item, compact=False)
            for item in _appendix_findings(view)
        )
        if _appendix_findings(view)
        else (
            '<p class="muted">No findings were produced for this run. '
            "This does not certify that the repository is free of issues.</p>"
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
        '<footer class="site-footer">\n'
        f"<p>{escape_html(BRAND_FOOTER_LINE)}</p>\n"
        f"<p>{escape_html(BRAND_REPORT_NAME)} — current-state Engineering Intelligence. "
        f"Mode: {escape_html(mode)}. AI status: "
        f'<code class="trace-id">{escape_html(ai_status)}</code> '
        "(optional; does not replace deterministic results).</p>\n"
        "<p>This Community report does not include CodeStrata Platform portfolio, "
        "executive, or Strategic Roadmap outputs.</p>\n"
        f"<p>Report {escape_html(report_version)} · Engine {escape_html(engine)} · "
        f'Design System: <span class="trace-id">{escape_html(DESIGN_SYSTEM_REF)}</span></p>\n'
        f'<p class="copyright">© {escape_html(BRAND_NAME)}</p>\n'
        "</footer>"
    )


def _render_evidence_details(evidence: tuple[object, ...]) -> str:
    if not evidence:
        return (
            '<details class="evidence"><summary>Evidence</summary>'
            '<p class="muted">None</p></details>'
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
    anchor_fn,
    empty: str = "",
) -> str:
    if not ids:
        return f'<span class="muted">{escape_html(empty)}</span>' if empty else ""
    parts = []
    for index, eid in enumerate(ids):
        label = titles[index] if index < len(titles) else eid
        parts.append(
            f'<a class="id-link" href="#{escape_html(anchor_fn(eid))}">{escape_html(label)}</a>'
        )
    return ", ".join(parts)


def _render_limitations_block(limitations: tuple[str, ...] | object, *, title: str) -> str:
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


_CSS = REPORT_CSS
