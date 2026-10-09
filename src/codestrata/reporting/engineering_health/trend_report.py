"""Five-commit trend HTML projection.

Reads durable P07/P08 artifacts only. Current health uses the baseline
assessment-head contract. Comparison lifecycle, deltas, movement, blast
radius, and graph topology are projected from supplied records and are not
recalculated here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codestrata.application.incremental.trend_bundle import (
    COMPARISON_FILENAME,
    COMPARISON_PAIRS,
    SLOT_STATUS_FILENAME,
    TrendBundlePaths,
)
from codestrata.application.incremental.trend_comparisons import (
    load_slot_analysis,
    load_slot_graph,
)
from codestrata.reporters.html_rendering import escape_html
from codestrata.reporting.branding import BRAND_FOOTER_LINE, BRAND_NAME, brand_favicon_link_tag
from codestrata.reporting.engineering_health.architecture_map import project_architecture_map
from codestrata.reporting.engineering_health.baseline import (
    CHECKOUT_DIGEST_NOTE,
    project_cochange_section,
    project_coverage_trust,
    project_hotspot_section,
    project_ownership_section,
)
from codestrata.reporting.engineering_health.models import (
    CochangePairView,
    CochangeSectionView,
    HotspotSectionView,
    OwnershipSectionView,
)
from codestrata.reporting.engineering_health.trend_current_health import (
    load_priority_actions,
    project_slot_headline_outcomes,
    slot_file_populations,
)
from codestrata.reporting.html_v2.r2_shell import (
    PRINT_CONTROL_SCRIPT,
    content_security_policy,
    print_script_tag,
    reference_shell_css,
    report_chrome,
)

OUTCOME_TITLES: tuple[tuple[str, str], ...] = (
    ("architecture", "Architecture"),
    ("security", "Security"),
    ("quality", "Quality"),
    ("maintainability", "Maintainability & Technical Debt"),
)
_VERDICT_LABELS = {
    "improved": "Improved",
    "deteriorated": "Deteriorated",
    "mixed": "Mixed",
    "insufficient": "Insufficient",
    "stable": "Stable",
    "not_applicable": "Not applicable",
    "unknown": "UNKNOWN",
    "unavailable": "Unavailable",
}
_TREND_CSS = """
.attention-grid, .slot-grid, .metric-grid {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
}
.slot-card.slot-status-unknown, .slot-card.slot-status-failed,
.comparison-panel.comparison-unavailable {
  border-color: var(--warn);
  background: var(--surface);
  color: var(--ink);
}
.comparison-panel.comparison-span { border-left: 3px solid var(--info); }
.comparison-panel.comparison-adjacent { border-left: 3px solid var(--teal); }
.trust-list { columns: 2; gap: 1rem; }
table.deltas th, table.deltas td { border-bottom: 1px solid var(--line); }
.noscript-note { display: none; }
noscript .noscript-note { display: block; }
.coverage-gap { margin: 0.75rem 0 1rem; }
.outcome-group { margin: 0.75rem 0 1rem; }
.failure-reasons li, .slot-card li { overflow-wrap: anywhere; }
"""


@dataclass(frozen=True, slots=True)
class OutcomeCard:
    family: str
    title: str
    label: str
    finding_count: int | None
    coverage_status: str | None


@dataclass(frozen=True, slots=True)
class SlotView:
    slot: int
    name: str
    status: str
    sha: str | None
    source_revision: str | None
    source_digest: str | None
    result_digest: str | None
    engine_version: str | None
    config_digest: str | None
    feed_digest: str | None
    limitations: tuple[str, ...]
    file_count: int | None
    assessed_file_count: int | None
    outcomes: tuple[OutcomeCard, ...]


@dataclass(frozen=True, slots=True)
class MovementView:
    family: str
    title: str
    verdict: str
    label: str
    reason: str | None


@dataclass(frozen=True, slots=True)
class LifecycleView:
    new: int | None
    resolved: int | None
    unchanged: int | None
    unknown: int | None
    new_titles: tuple[str, ...]
    resolved_titles: tuple[str, ...]
    note: str


@dataclass(frozen=True, slots=True)
class ChangeScopeView:
    file_count: int | None
    files: tuple[str, ...]
    components: tuple[str, ...]
    completeness: str | None
    limitations: tuple[str, ...]
    test_touch: bool | None
    test_touch_paths: tuple[str, ...]
    boundary_spread_status: str | None
    boundary_spread_count: int | None
    text_line_count: int | None


@dataclass(frozen=True, slots=True)
class BlastView:
    seeds: tuple[str, ...]
    affected_components: int | None
    affected_tests: int | None
    max_depth: int | None
    cutoff: bool | None
    cutoff_reason: str | None
    lower_bound: bool | None
    test_coverage_status: str | None
    note: str


@dataclass(frozen=True, slots=True)
class DeltaView:
    metric_name: str
    before: str
    after: str
    delta: str
    unit: str
    compatible: str
    reason: str | None


@dataclass(frozen=True, slots=True)
class CauseView:
    attribution: str
    label: str
    changed_dimensions: tuple[str, ...]
    base_digests: dict[str, str | None]
    candidate_digests: dict[str, str | None]


@dataclass(frozen=True, slots=True)
class ComparisonView:
    id: str
    kind: str
    title: str
    status: str
    unavailable_reason: str | None
    computed: bool
    base_slot: int
    candidate_slot: int
    base_sha: str | None
    candidate_sha: str | None
    movements: tuple[MovementView, ...]
    lifecycle: LifecycleView | None
    change: ChangeScopeView | None
    blast: BlastView | None
    deltas: tuple[DeltaView, ...]
    cause: CauseView | None


@dataclass(frozen=True, slots=True)
class TrendReportView:
    repository_id: str
    series_id: str
    head_sha: str | None
    head_branch: str | None
    repository_name: str | None
    dirty_notice: str | None
    profile: dict[str, Any]
    slots: tuple[SlotView, ...]
    comparisons: tuple[ComparisonView, ...]
    head_outcomes: tuple[OutcomeCard, ...]
    hotspots: HotspotSectionView | None
    ownership: OwnershipSectionView | None
    cochange: CochangeSectionView | None
    trust_rows: tuple[tuple[str, str], ...]
    architecture_available: bool
    architecture_reason: str | None
    architecture_node_count: int | None
    architecture_edge_count: int | None
    priority_actions: tuple[tuple[str, str, str, str], ...] | None = None


def render_trend_html(bundle: TrendBundlePaths) -> str:
    """Render five-commit trend HTML from durable series files only."""

    view = load_trend_report(bundle)
    return _html(view)


def load_trend_report(bundle: TrendBundlePaths) -> TrendReportView:
    index = _read_json(bundle.index_json) or {}
    slots = tuple(_slot_view(bundle, index, slot) for slot in range(1, 6))
    comparisons = tuple(
        _comparison_view(bundle, left, right, name) for left, right, name in COMPARISON_PAIRS
    )
    head = next((slot for slot in slots if slot.slot == 5), None)
    analysis = None
    if head is not None and head.status == "available":
        analysis = load_slot_analysis(bundle.slot_directory(5))
    metadata = dict(getattr(analysis, "metadata", {}) or {}) if analysis is not None else {}
    try:
        hotspots = project_hotspot_section(metadata)
    except (TypeError, ValueError, KeyError):
        hotspots = None
    try:
        ownership = project_ownership_section(metadata)
    except (TypeError, ValueError, KeyError):
        ownership = None
    try:
        cochange = project_cochange_section(metadata)
    except (TypeError, ValueError, KeyError):
        cochange = None
    try:
        trust = project_coverage_trust(metadata)
    except (TypeError, ValueError, KeyError):
        trust = None
    graph_payload = None
    if head is not None and head.status == "available":
        graph_payload = load_slot_graph(bundle.slot_directory(5))
    snapshot = None
    if isinstance(graph_payload, dict):
        from codestrata.domain.graph.models import GraphSnapshot

        try:
            snapshot = GraphSnapshot.model_validate(graph_payload)
        except (TypeError, ValueError):
            snapshot = None
    architecture = project_architecture_map(snapshot)
    repository = getattr(analysis, "repository", None) if analysis is not None else None
    repository_name = getattr(repository, "name", None) if repository is not None else None
    return TrendReportView(
        repository_id=str(index.get("repository_id") or bundle.repository_id),
        series_id=str(index.get("series_id") or bundle.series_id),
        head_sha=None if index.get("head_sha") is None else str(index.get("head_sha")),
        head_branch=None if index.get("head_branch") is None else str(index.get("head_branch")),
        repository_name=None if not repository_name else str(repository_name),
        dirty_notice=None if not index.get("dirty_notice") else str(index.get("dirty_notice")),
        profile=dict(index.get("profile") or {}),
        slots=slots,
        comparisons=comparisons,
        head_outcomes=head.outcomes if head is not None else _unknown_outcomes(),
        hotspots=hotspots,
        ownership=ownership,
        cochange=cochange,
        trust_rows=tuple((row.label, row.value) for row in trust.rows) if trust is not None else (),
        architecture_available=architecture.available,
        architecture_reason=architecture.unavailable_reason,
        architecture_node_count=(
            architecture.canonical_node_count if architecture.available else None
        ),
        architecture_edge_count=(
            architecture.canonical_edge_count if architecture.available else None
        ),
        priority_actions=(
            load_priority_actions(bundle.slot_directory(5))
            if head is not None and head.status == "available"
            else None
        ),
    )


def _slot_view(bundle: TrendBundlePaths, index: dict[str, Any], slot: int) -> SlotView:
    payload = _read_json(bundle.slot_directory(slot) / SLOT_STATUS_FILENAME) or {}
    index_row: dict[str, Any] = {}
    for row in index.get("slots") or ():
        if isinstance(row, dict) and row.get("slot") == slot:
            index_row = row
            break
    status = str(payload.get("status") or index_row.get("status") or "UNKNOWN")
    directory = bundle.slot_directory(slot)
    files = payload.get("file_paths")
    inventory, assessed = slot_file_populations(
        directory,
        files if isinstance(files, list) else None,
    )
    projected = project_slot_headline_outcomes(directory) if status == "available" else None
    return SlotView(
        slot=slot,
        name=f"s{slot}",
        status=status,
        sha=_text(payload.get("sha") or index_row.get("sha")),
        source_revision=_text(payload.get("source_revision") or index_row.get("source_revision")),
        source_digest=_text(payload.get("source_digest") or index_row.get("source_digest")),
        result_digest=_text(payload.get("result_digest") or index_row.get("result_digest")),
        engine_version=_text(payload.get("engine_version") or index_row.get("engine_version")),
        config_digest=_text(payload.get("config_digest") or index_row.get("config_digest")),
        feed_digest=_text(payload.get("feed_digest") or index_row.get("feed_digest")),
        limitations=tuple(str(item) for item in (payload.get("limitations") or ())),
        file_count=inventory,
        assessed_file_count=assessed,
        outcomes=_headline_cards(projected),
    )


def _comparison_view(bundle: TrendBundlePaths, left: int, right: int, name: str) -> ComparisonView:
    payload = _read_json(bundle.comparison_directory(name) / COMPARISON_FILENAME) or {}
    kind = "span" if name == "s1-s5" else "adjacent"
    title = (
        f"S{left} → S{right} · oldest to HEAD"
        if kind == "span"
        else f"S{left} → S{right} · adjacent"
    )
    raw_comparison = payload.get("comparison")
    comparison: dict[str, Any] = raw_comparison if isinstance(raw_comparison, dict) else {}
    return ComparisonView(
        id=name,
        kind=kind,
        title=title,
        status=str(payload.get("status") or "not_computable"),
        unavailable_reason=_text(payload.get("unavailable_reason")),
        computed=bool(payload.get("computed")),
        base_slot=left,
        candidate_slot=right,
        base_sha=_text(payload.get("base_sha")),
        candidate_sha=_text(payload.get("candidate_sha")),
        movements=_movements(payload),
        lifecycle=_lifecycle(comparison) if comparison else None,
        change=_change_scope(_as_dict(payload.get("m27"))),
        blast=_blast(_as_dict(comparison.get("blast_radius"))),
        deltas=_deltas(payload.get("metric_deltas") or comparison.get("metric_deltas") or ()),
        cause=_cause(_as_dict(comparison.get("cause_attribution"))),
    )


def _unknown_outcomes() -> tuple[OutcomeCard, ...]:
    return tuple(
        OutcomeCard(
            family=family,
            title=title,
            label="UNKNOWN",
            finding_count=None,
            coverage_status="UNKNOWN",
        )
        for family, title in OUTCOME_TITLES
    )


def _headline_cards(
    projected: tuple[tuple[str, str, str, int, str | None], ...] | None,
) -> tuple[OutcomeCard, ...]:
    if projected is None:
        return _unknown_outcomes()
    return tuple(
        OutcomeCard(
            family=family,
            title=title,
            label=label,
            finding_count=count,
            coverage_status=coverage or "UNKNOWN",
        )
        for family, title, label, count, coverage in projected
    )


def _movements(payload: dict[str, Any]) -> tuple[MovementView, ...]:
    raw = payload.get("public_outcome_verdicts")
    if not isinstance(raw, dict):
        comparison = payload.get("comparison")
        raw = comparison.get("outcome_verdicts") if isinstance(comparison, dict) else {}
    if not isinstance(raw, dict):
        raw = {}
    items: list[MovementView] = []
    for family, title in OUTCOME_TITLES:
        verdict_payload = raw.get(family)
        if not isinstance(verdict_payload, dict):
            items.append(
                MovementView(
                    family=family,
                    title=title,
                    verdict="unknown",
                    label="UNKNOWN",
                    reason=None,
                )
            )
            continue
        verdict = str(verdict_payload.get("verdict") or "unknown").lower()
        items.append(
            MovementView(
                family=family,
                title=title,
                verdict=verdict,
                label=_VERDICT_LABELS.get(verdict, verdict.replace("_", " ")),
                reason=_text(verdict_payload.get("reason")),
            )
        )
    return tuple(items)


def _lifecycle(comparison: dict[str, Any]) -> LifecycleView:
    raw_summary = comparison.get("summary")
    summary: dict[str, Any] = raw_summary if isinstance(raw_summary, dict) else {}
    return LifecycleView(
        new=_int(summary.get("new_findings")),
        resolved=_int(summary.get("resolved_findings")),
        unchanged=_int(summary.get("unchanged_findings")),
        unknown=_int(summary.get("unknown_findings")),
        new_titles=tuple(_title_of(item) for item in comparison.get("new_findings") or ()),
        resolved_titles=tuple(
            _title_of(item) for item in comparison.get("resolved_findings") or ()
        ),
        note=(
            "These counts are AnalysisResult identities. They are not the "
            "assessment-head population shown as current health. Equal counts "
            "are not a Stable verdict."
        ),
    )


def _change_scope(m27: dict[str, Any] | None) -> ChangeScopeView | None:
    if m27 is None:
        return None
    files = tuple(str(item) for item in (m27.get("changed_file_ids") or ()))
    if not files:
        files = tuple(
            str(item.get("path"))
            for item in (m27.get("files") or ())
            if isinstance(item, dict) and item.get("path")
        )
    return ChangeScopeView(
        file_count=_int(m27.get("changed_file_count")),
        files=files,
        components=tuple(str(item) for item in (m27.get("changed_component_ids") or ())),
        completeness=_text(m27.get("comparison_completeness")),
        limitations=tuple(str(item) for item in (m27.get("limitations") or ())),
        test_touch=None if "test_touch" not in m27 else bool(m27.get("test_touch")),
        test_touch_paths=tuple(str(item) for item in (m27.get("test_touch_paths") or ())),
        boundary_spread_status=_text(m27.get("boundary_spread_status")),
        boundary_spread_count=_int(m27.get("boundary_spread_count")),
        text_line_count=_int(m27.get("changed_text_lines")),
    )


def _blast(payload: dict[str, Any] | None) -> BlastView | None:
    if payload is None:
        return None
    return BlastView(
        seeds=tuple(
            str(item) for item in (payload.get("seeds") or payload.get("changed_seeds") or ())
        ),
        affected_components=_int(payload.get("affected_component_count")),
        affected_tests=_int(payload.get("affected_test_count")),
        max_depth=_int(payload.get("max_depth")),
        cutoff=None if "cutoff" not in payload else bool(payload.get("cutoff")),
        cutoff_reason=_text(payload.get("cutoff_reason")),
        lower_bound=None if "lower_bound" not in payload else bool(payload.get("lower_bound")),
        test_coverage_status=_text(payload.get("test_coverage_status")),
        note="Static bounded reach only. This is not a runtime impact.",
    )


def _deltas(raw: Any) -> tuple[DeltaView, ...]:
    if not isinstance(raw, list):
        return ()
    items: list[DeltaView] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        compatible = item.get("compatible")
        items.append(
            DeltaView(
                metric_name=str(item.get("metric_name") or "unnamed"),
                before=_display(item.get("base_value")),
                after=_display(item.get("candidate_value")),
                delta=_display(item.get("delta")),
                unit=str(item.get("unit") or ""),
                compatible=(
                    "compatible"
                    if compatible is True
                    else "incompatible"
                    if compatible is False
                    else "UNKNOWN"
                ),
                reason=_text(item.get("compatibility_reason")),
            )
        )
    return tuple(items)


def _cause(payload: dict[str, Any] | None) -> CauseView | None:
    if payload is None:
        return None
    return CauseView(
        attribution=str(payload.get("attribution") or "undetermined"),
        label=str(payload.get("label") or payload.get("attribution") or "undetermined"),
        changed_dimensions=tuple(str(item) for item in (payload.get("changed_dimensions") or ())),
        base_digests={
            str(key): None if value is None else str(value)
            for key, value in dict(payload.get("base_digests") or {}).items()
        },
        candidate_digests={
            str(key): None if value is None else str(value)
            for key, value in dict(payload.get("candidate_digests") or {}).items()
        },
    )


_TREND_COMPARISON_SCRIPT = (
    "(function(){var s=document.getElementById('comparison-select');if(!s)return;"
    "function show(){var id=s.value;document.querySelectorAll('.comparison-panel').forEach("
    "function(el){el.hidden=el.id!==('comparison-'+id);});}"
    "s.addEventListener('change',show);show();})();"
)


def _html(view: TrendReportView) -> str:
    favicon = brand_favicon_link_tag()
    policy = content_security_policy(PRINT_CONTROL_SCRIPT, _TREND_COMPARISON_SCRIPT)
    return "".join(
        [
            '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width,initial-scale=1">',
            f'<meta http-equiv="Content-Security-Policy" content="{policy}">',
            f"<title>Five-commit health trend · {escape_html(BRAND_NAME)}</title>",
            favicon,
            f"<style>{reference_shell_css()}\n{_TREND_CSS}</style></head><body>",
            report_chrome(
                active_label="5-commit trend",
                download_href="trend-index.json",
                download_label="Download JSON",
            ),
            '<main id="main" class="page trend-layout">',
            '<div class="hero"><div><div class="eyebrow">Repository engineering health</div>',
            "<h1>Five-commit health trend</h1>",
            _identity(view),
            "<p>HEAD plus four first-parent predecessors · series "
            f"{escape_html(view.series_id)}</p>",
            '<p class="note">Execution success is not a health verdict. '
            "HTML projects supplied artifacts only.</p>",
            _dirty(view),
            "</div></div>",
            _health_timeline(view),
            _nav(),
            _overview(view),
            _ai_summary_section(),
            _head_health_section(view),
            _five_state_section(view),
            _slots(view),
            _comparisons(view),
            _context(view),
            _concentration(view),
            _priority_actions(view),
            _modernization(view),
            _trust(view),
            _appendix(view),
            '<footer class="footer">'
            "<span>CodeStrata · Engineering decisions, grounded in code.</span>"
            f"<span>{escape_html(BRAND_FOOTER_LINE)}</span></footer>",
            "</main>",
            print_script_tag(),
            _script(),
            "</body></html>\n",
        ]
    )


def _nav() -> str:
    links = (
        ("overview", "Attention now"),
        ("ai-summary", "AI Summary"),
        ("current-health", "HEAD health"),
        ("trend", "Five-state change"),
        ("source-states", "Five snapshots"),
        ("comparisons", "Comparisons"),
        ("hotspots", "Hotspot map"),
        ("concentration", "Concentration"),
        ("actions", "Priority actions"),
        ("modernization", "Modernization inputs"),
        ("trust", "Coverage & Trust"),
        ("evidence", "Evidence"),
    )
    items = "".join(f'<a href="#{anchor}">{escape_html(label)}</a>' for anchor, label in links)
    return f'<nav class="section-nav" aria-label="Report sections">{items}</nav>'


def _identity(view: TrendReportView) -> str:
    name = view.repository_name or "UNKNOWN"
    branch = view.head_branch or "UNKNOWN"
    sha = view.head_sha or "UNKNOWN"
    return (
        f"<p>Repository <strong>{escape_html(name)}</strong> · "
        f"branch <code>{escape_html(branch)}</code> · "
        f"HEAD <code>{escape_html(sha)}</code></p>"
    )


def _dirty(view: TrendReportView) -> str:
    if not view.dirty_notice:
        return ""
    return f'<p class="note" id="dirty-notice">{escape_html(view.dirty_notice)}</p>'


def _overview(view: TrendReportView) -> str:
    span = next((item for item in view.comparisons if item.kind == "span"), None)
    adjacent = next((item for item in view.comparisons if item.id == "s4-s5"), None)
    return (
        '<section id="overview" class="report-section">'
        "<h2>What changed across the five commits</h2>"
        "<p>Oldest → HEAD is the span comparison. S4 → S5 is the latest adjacent change. "
        "They are not interchangeable. A failed source state makes that comparison "
        "unavailable.</p>"
        "<p>Public outcomes: Architecture, Security, Quality, "
        "and Maintainability &amp; Technical Debt. Composite scoring is not used.</p>"
        "<p>Current health uses the assessment-head finding population. "
        "Comparison lifecycle uses AnalysisResult identities and is a "
        "different population.</p>"
        f"{_failed_coverage_notice(view)}"
        f"{_head_outcome_group(view)}"
        f"{_pair_summary(span, 'Oldest → HEAD')}"
        f"{_pair_summary(adjacent, 'Latest adjacent')}"
        "</section>"
    )


def _join_slot_names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + ", and " + names[-1]


def _failed_coverage_notice(view: TrendReportView) -> str:
    """One notice for failed slots. Exact supplied reasons stay in a disclosure."""

    failed = [slot for slot in view.slots if slot.status != "available"]
    if not failed:
        return ""
    joined = _join_slot_names([slot.name.upper() for slot in failed])
    items: list[str] = []
    for slot in failed:
        supplied = [item.strip() for item in slot.limitations if item and item.strip()]
        label = escape_html(slot.name.upper())
        if not supplied:
            items.append(
                f"<li><strong>{label}</strong>: No failure detail was supplied. "
                "The slot stays unavailable.</li>"
            )
            continue
        items.extend(
            f"<li><strong>{label}</strong>: {escape_html(reason)}</li>" for reason in supplied
        )
    return (
        '<aside class="notice coverage-gap">'
        f"<p><strong>{escape_html(joined)} unavailable for comparison.</strong> "
        "This is not a clean or no-issue result. "
        "Failed slots are not a successful trend comparison.</p>"
        '<details class="failure-reasons"><summary>Supplied failure reasons</summary>'
        f"<ul>{''.join(items)}</ul></details></aside>"
    )


def _head_outcome_group(view: TrendReportView) -> str:
    cards = view.head_outcomes or _unknown_outcomes()
    body = "".join(_outcome_card(card) for card in cards)
    return (
        '<div class="outcome-group">'
        "<h3>HEAD outcomes</h3>"
        f'<div class="outcome-grid">{body}</div></div>'
    )


def _pair_summary(pair: ComparisonView | None, heading: str) -> str:
    if pair is None:
        return f'<article class="card"><h3>{escape_html(heading)}</h3><p>UNKNOWN</p></article>'
    if pair.status != "available":
        reason = pair.unavailable_reason or pair.status
        unknown = "".join(
            f"<li>{escape_html(title)}: UNKNOWN</li>" for _family, title in OUTCOME_TITLES
        )
        return (
            f'<article class="card comparison-unavailable">'
            f"<h3>{escape_html(heading)}</h3>"
            f"<p>Comparison {escape_html(pair.id)} is {escape_html(pair.status)}.</p>"
            f'<p class="note">{escape_html(reason)}</p>'
            f"<ul>{unknown}</ul></article>"
        )
    movements = "".join(
        f"<li>{escape_html(item.title)}: {escape_html(item.label)}</li>" for item in pair.movements
    )
    files = (
        "UNKNOWN"
        if pair.change is None or pair.change.file_count is None
        else str(pair.change.file_count)
    )
    return (
        f'<article class="card comparison-{escape_html(pair.kind)}">'
        f"<h3>{escape_html(heading)}</h3>"
        f"<p>Changed files (supplied M27): {escape_html(files)}</p>"
        f"<ul>{movements}</ul></article>"
    )


def _slot_failure_note(slot: SlotView) -> str:
    """Show the supplied failure text. Do not invent a successful result."""

    if slot.status == "available":
        return ""
    supplied = [item.strip() for item in slot.limitations if item and item.strip()]
    if not supplied:
        return (
            "<p>No failure detail was supplied with this source state. "
            "The slot stays visible and is not treated as clean.</p>"
        )
    items = "".join(f"<li>{escape_html(item)}</li>" for item in supplied)
    return f"<p>Supplied failure:</p><ul>{items}</ul>"


def _head_health_section(view: TrendReportView) -> str:
    cards = view.head_outcomes or _unknown_outcomes()
    body = "".join(_outcome_card(card, evidence_href="#slot-s5") for card in cards)
    notice = ""
    if not view.head_outcomes or all(card.label == "UNKNOWN" for card in cards):
        notice = (
            "<p>HEAD Engineering Health labels are UNKNOWN where the HEAD "
            "source state or coverage was not available.</p>"
        )
    return (
        '<section id="current-health" class="report-section">'
        "<h2>Current HEAD Engineering Health</h2>"
        "<p>Four public outcomes only. Inventory, Dependencies, and Git are "
        "supporting evidence, not headline peers. Counts are assessment-head "
        "findings, not comparison lifecycle identities.</p>"
        f"{notice}"
        f'<div class="outcome-grid">{body}</div></section>'
    )


def _outcome_card(card: OutcomeCard, *, evidence_href: str = "#current-health") -> str:
    count = "UNKNOWN" if card.finding_count is None else str(card.finding_count)
    coverage = card.coverage_status or "UNKNOWN"
    return (
        '<article class="card health-card">'
        f"<h3>{escape_html(card.title)}</h3>"
        f'<p class="card-status">{escape_html(card.label)}</p>'
        f'<p class="card-count">Supplied findings: {escape_html(count)} · '
        f"coverage: {escape_html(coverage)}</p>"
        f'<p class="card-evidence"><a href="{escape_html(evidence_href)}">Outcome evidence</a></p>'
        "</article>"
    )


def _ai_summary_section() -> str:
    """Trend has no AI enrichment contract. Show only the honest absent state."""

    return (
        '<section id="ai-summary" class="report-section">'
        "<h2>AI Summary</h2>"
        '<p class="note">Interpretation only. Engine findings, UNKNOWN results, and '
        "calibrated recommendation horizons stay unchanged. "
        "This local trend report has no AI result contract.</p>"
        '<div class="ai-panel ai-absent">'
        "<p>AI interpretation not requested for this local assessment.</p>"
        '<p class="muted">No generated summary or improvement plan is included.</p>'
        "</div></section>"
    )


def _health_timeline(view: TrendReportView) -> str:
    """Categorical lanes for S1–S5. Failed slots are gaps and are not connected."""

    commits = []
    for slot in view.slots:
        identity = slot.source_revision or slot.sha or ""
        short = identity[:7] if identity else "UNKNOWN"
        head = slot.slot == 5
        klass = "commit-id commit-head" if head else "commit-id"
        label = "S5 · HEAD" if head else slot.name.upper()
        commits.append(
            f'<div class="{klass}"><strong>{escape_html(label)}</strong>'
            f"<div><code>{escape_html(short)}</code></div></div>"
        )
    lanes = []
    count_rows = []
    for family, title in OUTCOME_TITLES:
        cells = [f'<div class="lane-name">{escape_html(title)}</div>']
        counts = [f"<th scope=\"row\">{escape_html(title)}</th>"]
        for slot in view.slots:
            head_class = " lane-head" if slot.slot == 5 else ""
            if slot.status != "available":
                cells.append(
                    f'<div class="lane-gap{head_class}">Unavailable</div>'
                )
                counts.append("<td>UNKNOWN</td>")
                continue
            match = next((item for item in slot.outcomes if item.family == family), None)
            label = match.label if match is not None else "UNKNOWN"
            if match is None or match.finding_count is None:
                count = "UNKNOWN"
            else:
                count = str(match.finding_count)
            cells.append(f'<div class="lane-state{head_class}">{escape_html(label)}</div>')
            counts.append(f"<td>{escape_html(count)}</td>")
        lanes.append("".join(cells))
        count_rows.append("<tr>" + "".join(counts) + "</tr>")
    headers = "".join(
        f'<th scope="col">{escape_html(slot.name.upper())}</th>' for slot in view.slots
    )
    return (
        '<section id="five-commit-health" class="report-section" '
        'aria-label="Engineering health across five commits">'
        "<h2>Engineering health across five commits</h2>"
        "<p>Categorical states only. No score is assigned and the lanes do not show improvement. "
        "A failed or missing slot is a gap. Gaps are not connected.</p>"
        '<div class="health-timeline">'
        '<div class="lane-name">Outcome</div>'
        + "".join(commits)
        + "".join(lanes)
        + "</div>"
        '<details><summary>Supplied finding counts</summary>'
        "<p>Counts stay with the snapshot. Failed slots have no comparable count, "
        "so this is not a numeric series.</p>"
        '<div class="table-wrap" tabindex="0" role="region" aria-label="Supplied finding counts">'
        "<table><thead><tr><th scope=\"col\">Outcome</th>"
        f"{headers}</tr></thead><tbody>{''.join(count_rows)}</tbody></table></div></details>"
        "</section>"
    )


def _slots(view: TrendReportView) -> str:
    cards = []
    for slot in view.slots:
        sha = slot.source_revision or slot.sha or "UNKNOWN"
        inventory = "UNKNOWN" if slot.file_count is None else str(slot.file_count)
        assessed = "UNKNOWN" if slot.assessed_file_count is None else str(slot.assessed_file_count)
        outcomes = (
            "".join(
                f"<li>{escape_html(item.title)}: {escape_html(item.label)}</li>"
                for item in slot.outcomes
            )
            or "<li>Outcome labels unavailable for this snapshot.</li>"
        )
        cards.append(
            f'<article class="slot-card slot-status-'
            f'{escape_html(slot.status.lower())}" '
            f'id="slot-{escape_html(slot.name)}">'
            f"<h3>{escape_html(slot.name)}</h3>"
            f'<p><span class="badge badge-'
            f'{escape_html(slot.status.lower())}">'
            f"{escape_html(slot.status)}</span></p>"
            f"<p>Source revision: <code>{escape_html(sha)}</code></p>"
            f"{_slot_failure_note(slot)}"
            f"<p>Committed files in assessment scope: {escape_html(inventory)}</p>"
            f"<p>Assessed files: {escape_html(assessed)}</p>"
            '<p class="note">Assessed files are those admitted by the scan '
            "boundary. The committed-file count is not assessed coverage.</p>"
            f"<ul>{outcomes}</ul>"
            f'<p class="note"><a href="#evidence-{escape_html(slot.name)}">'
            f"Evidence for {escape_html(slot.name)}</a></p>"
            "</article>"
        )
    return (
        '<section id="source-states" class="report-section">'
        "<h2>Health across the last five commits</h2>"
        "<p>Oldest is S1. HEAD is S5. Missing or failed slots stay visible "
        "and are not treated as clean.</p>"
        f'<div class="slot-grid">{"".join(cards)}</div></section>'
    )


def _comparisons(view: TrendReportView) -> str:
    options = "".join(
        f'<option value="{escape_html(item.id)}">{escape_html(item.title)}</option>'
        for item in view.comparisons
    )
    panels = "".join(_comparison_panel(item) for item in view.comparisons)
    return (
        '<section id="comparisons" class="report-section">'
        "<h2>Adjacent and oldest-to-HEAD comparisons</h2>"
        "<p>Use the selector to focus one pair. Adjacent change is teal. "
        "Oldest → HEAD is blue. All five pairs remain in this file.</p>"
        '<p class="note">Static bounded reach only. This is not a runtime impact. '
        "Missing M29 evidence stays UNKNOWN and is never inferred.</p>"
        f'<label for="comparison-select">Compare commits</label> '
        f'<select id="comparison-select">{options}</select>'
        '<noscript><p class="noscript-note note">JavaScript is disabled. '
        "All comparison panels are shown below.</p></noscript>"
        f"{panels}</section>"
    )


def _comparison_panel(item: ComparisonView) -> str:
    status_class = (
        "comparison-unavailable" if item.status != "available" else f"comparison-{item.kind}"
    )
    if item.status != "available":
        body = (
            f"<p>This comparison is {escape_html(item.status)}.</p>"
            f'<p class="note">{escape_html(item.unavailable_reason or "not_computable")}</p>'
            "<p>Movement, lifecycle, deltas, and blast radius are "
            "unavailable. They were not inferred.</p>"
        )
    else:
        body = "".join(
            [
                _movement_block(item),
                _lifecycle_block(item.lifecycle),
                _change_block(item.change),
                _blast_block(item.blast),
                _delta_block(item.deltas),
                _cause_block(item.cause),
            ]
        )
    return (
        f'<article id="comparison-{escape_html(item.id)}" '
        f'class="comparison-panel {status_class}">'
        f"<h3>{escape_html(item.title)}</h3>"
        f'<p><span class="badge badge-{escape_html(item.kind)}">'
        f"{escape_html(item.kind)}</span> "
        f'<span class="badge badge-{escape_html(item.status)}">'
        f"{escape_html(item.status)}</span></p>"
        f"<p>Before SHA: <code>{escape_html(item.base_sha or 'UNKNOWN')}</code><br>"
        f"After SHA: <code>{escape_html(item.candidate_sha or 'UNKNOWN')}</code></p>"
        f"{body}</article>"
    )


def _movement_block(item: ComparisonView) -> str:
    rows = "".join(
        f"<li>{escape_html(move.title)}: <strong>{escape_html(move.label)}</strong>"
        f"{'' if not move.reason else ' · ' + escape_html(move.reason)}"
        "</li>"
        for move in item.movements
    )
    return f"<h4>Outcome movement</h4><ul>{rows}</ul>"


def _lifecycle_block(lifecycle: LifecycleView | None) -> str:
    if lifecycle is None:
        return "<h4>Finding lifecycle</h4><p>UNKNOWN. Lifecycle identities were not supplied.</p>"
    return (
        "<h4>Finding lifecycle</h4>"
        f"<p>New: {_display(lifecycle.new)} · Resolved: {_display(lifecycle.resolved)} · "
        f"Persisting: {_display(lifecycle.unchanged)} · Unknown: {_display(lifecycle.unknown)}</p>"
        f'<p class="note">{escape_html(lifecycle.note)}</p>'
        f"<p>New identities: "
        f"{escape_html(', '.join(lifecycle.new_titles) or 'None supplied')}</p>"
        f"<p>Resolved identities: "
        f"{escape_html(', '.join(lifecycle.resolved_titles) or 'None supplied')}</p>"
    )


def _change_block(change: ChangeScopeView | None) -> str:
    if change is None:
        return "<h4>Change summary</h4><p>UNKNOWN. M27 change facts were not supplied.</p>"
    files = (
        "".join(f"<li><code>{escape_html(path)}</code></li>" for path in change.files)
        or "<li>None supplied</li>"
    )
    test = "UNKNOWN" if change.test_touch is None else str(change.test_touch)
    components = ", ".join(change.components) or "None supplied"
    tests = ", ".join(change.test_touch_paths) or "None supplied"
    limits = ", ".join(change.limitations) or "None supplied"
    return (
        "<h4>Change summary</h4>"
        f"<p>Changed files: {_display(change.file_count)} · "
        f"changed text lines: {_display(change.text_line_count)} · "
        f"completeness: {escape_html(change.completeness or 'UNKNOWN')} · "
        f"test touch: {escape_html(test)}</p>"
        '<p class="note">Changed text lines are the supplied scoped M27 total. '
        "HTML does not recompute them.</p>"
        f"<p>Changed components: {escape_html(components)}</p>"
        f"<p>Changed tests: {escape_html(tests)}</p>"
        f"<p>Boundary spread: "
        f"{escape_html(change.boundary_spread_status or 'UNKNOWN')} "
        f"({_display(change.boundary_spread_count)})</p>"
        f'<p class="note">Limitations: {escape_html(limits)}</p>'
        f"<ul>{files}</ul>"
    )


def _blast_block(blast: BlastView | None) -> str:
    if blast is None:
        return "<h4>Static impact</h4><p>UNKNOWN. M29 static blast radius was not supplied.</p>"
    cutoff = "UNKNOWN" if blast.cutoff is None else str(blast.cutoff)
    lower = "UNKNOWN" if blast.lower_bound is None else str(blast.lower_bound)
    return (
        "<h4>Static impact</h4>"
        f"<p>{escape_html(blast.note)}</p>"
        f"<p>Seeds: {escape_html(', '.join(blast.seeds) or 'None supplied')}</p>"
        f"<p>Affected components: {_display(blast.affected_components)} · "
        f"affected tests: {_display(blast.affected_tests)}</p>"
        f"<p>Max depth: {_display(blast.max_depth)} · "
        f"cutoff: {escape_html(cutoff)} · lower bound: {escape_html(lower)}</p>"
        f'<p class="note">Cutoff reason: '
        f"{escape_html(blast.cutoff_reason or 'none')} · test coverage: "
        f"{escape_html(blast.test_coverage_status or 'UNKNOWN')}</p>"
    )


def _delta_block(deltas: tuple[DeltaView, ...]) -> str:
    if not deltas:
        return "<h4>Before / After / Delta</h4><p>No named MetricDelta records were supplied.</p>"
    rows = []
    for item in deltas:
        gap = ""
        if item.compatible != "compatible":
            gap = f" Gap: {escape_html(item.reason or item.compatible)}"
        rows.append(
            "<tr>"
            f"<td>{escape_html(item.metric_name)}</td>"
            f"<td>{escape_html(item.before)}</td>"
            f"<td>{escape_html(item.after)}</td>"
            f"<td>{escape_html(item.delta)}</td>"
            f"<td>{escape_html(item.unit)}</td>"
            f"<td>{escape_html(item.compatible)}{gap}</td>"
            "</tr>"
        )
    return (
        "<h4>Before / After / Delta</h4>"
        '<p class="note">Values are copied from supplied MetricDelta records. '
        "HTML does not subtract.</p>"
        '<table class="deltas"><thead><tr>'
        "<th>Metric</th><th>Before</th><th>After</th>"
        "<th>Delta</th><th>Unit</th><th>Compatibility</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _cause_block(cause: CauseView | None) -> str:
    if cause is None:
        return "<h4>Cause attribution</h4><p>UNKNOWN. M31 attribution was not supplied.</p>"
    dims = ", ".join(cause.changed_dimensions) or "None supplied"
    return (
        "<h4>Cause attribution</h4>"
        f"<p>{escape_html(cause.label)} ({escape_html(cause.attribution)})</p>"
        f"<p>Changed dimensions: {escape_html(dims)}</p>"
        f'<p class="note">Base digests: '
        f"{escape_html(_digest_line(cause.base_digests))}</p>"
        f'<p class="note">Candidate digests: '
        f"{escape_html(_digest_line(cause.candidate_digests))}</p>"
    )


_HOTSPOT_LIMIT = 12
_OWNERSHIP_LIMIT = 12
_COCHANGE_LIMIT = 8


def _bounded_note(shown: int, total: int) -> str:
    if total <= shown:
        return ""
    return (
        f'<p class="note">Showing {shown} of {total} supplied records. '
        "The remainder stays in the sealed artifact.</p>"
    )


def _hotspot_list(section: HotspotSectionView | None) -> str:
    if section is None or not section.available:
        reason = None if section is None else section.unavailable_reason
        return f"<p>Engineering Hotspots unavailable: {escape_html(reason or 'UNKNOWN')}</p>"
    shown = section.items[:_HOTSPOT_LIMIT]
    rows = "".join(
        "<li><code>"
        f"{escape_html(item.subject_id)}</code> · {escape_html(item.list_kind)}"
        + (f" · {escape_html(item.priority_explanation)}" if item.priority_explanation else "")
        + "</li>"
        for item in shown
    )
    return f"<ul>{rows}</ul>{_bounded_note(len(shown), len(section.items))}"


def _ownership_list(section: OwnershipSectionView | None) -> str:
    if section is None or not section.available:
        reason = None if section is None else section.unavailable_reason
        return f"<p>Ownership concentration unavailable: {escape_html(reason or 'UNKNOWN')}</p>"
    shown = section.items[:_OWNERSHIP_LIMIT]
    rows = "".join(
        f"<li><code>{escape_html(item.subject_id)}</code> · "
        f"{escape_html(item.serialized_ratio or 'ratio UNKNOWN')} · "
        f"status {escape_html(item.status or 'UNKNOWN')}</li>"
        for item in shown
    )
    return f"<ul>{rows}</ul>{_bounded_note(len(shown), len(section.items))}"


def _cochange_status(item: CochangePairView) -> str:
    """Copy the supplied support boolean. Jaccard does not decide this label."""

    if item.supported_relation is True:
        return "Supported relation"
    if item.supported_relation is False:
        return "Not a supported relation"
    return "Support not supplied"


def _cochange_list(section: CochangeSectionView | None) -> str:
    if section is None or not section.available:
        reason = None if section is None else section.unavailable_reason
        return f"<p>Temporal co-change unavailable: {escape_html(reason or 'UNKNOWN')}</p>"
    shown = section.items[:_COCHANGE_LIMIT]
    rows = "".join(
        "<li>"
        f"<code>{escape_html(item.left)}</code> ↔ <code>{escape_html(item.right)}</code> · "
        f"{escape_html(_cochange_status(item))} · "
        f"support {_display(item.support)} / union {_display(item.union)} · "
        f"Jaccard {escape_html(item.jaccard or 'UNKNOWN')} · "
        f"scope {escape_html(item.scope)} · "
        f"incomplete window {escape_html(str(item.qualified_incomplete_window))}"
        + (f" · {escape_html(item.unavailable_reason)}" if item.unavailable_reason else "")
        + "</li>"
        for item in shown
    )
    return (
        '<p class="note">Support status is the supplied boolean. '
        "Jaccard is copied and does not decide support. "
        "Order is the sealed record order.</p>"
        f"<ul>{rows}</ul>{_bounded_note(len(shown), len(section.items))}"
    )


def _context(view: TrendReportView) -> str:
    hotspots = _hotspot_list(view.hotspots)
    cochange = _cochange_list(view.cochange)
    if view.architecture_available:
        architecture = (
            f"<p>Canonical nodes: {_display(view.architecture_node_count)} · "
            f"canonical edges: {_display(view.architecture_edge_count)}</p>"
        )
    else:
        architecture = (
            "<p>Architecture Map unavailable: "
            f"{escape_html(view.architecture_reason or 'UNKNOWN')}</p>"
        )
    return (
        '<section id="hotspots" class="report-section">'
        "<h2>Component hotspot map</h2>"
        "<p>HEAD snapshot only. These lists copy sealed records and do not "
        "rank or invent pairs.</p>"
        "<h3>Where complexity meets frequent change</h3>"
        f"{hotspots}"
        "<h3>Temporal co-change</h3>"
        f"{cochange}"
        "<h3>Architecture Map</h3>"
        f"{architecture}"
        "</section>"
    )


def _five_state_section(view: TrendReportView) -> str:
    headers = "".join(f"<th>{escape_html(slot.name.upper())}</th>" for slot in view.slots)
    rows: list[str] = []
    for family, title in OUTCOME_TITLES:
        cells = "".join(
            f"<td>{escape_html(_slot_outcome_label(slot, family))}</td>" for slot in view.slots
        )
        rows.append(f"<tr><th>{escape_html(title)}</th>{cells}</tr>")
    changes = "".join(_change_strip(pair) for pair in view.comparisons)
    return (
        '<section id="trend" class="report-section">'
        "<h2>Health across the last five commits</h2>"
        "<p>Five ordered source states. Labels are the assessment-head "
        "projection for each snapshot. No composite score is calculated. "
        "A missing snapshot stays UNKNOWN.</p>"
        '<table class="deltas"><thead><tr><th>Outcome</th>'
        f"{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
        "<h3>Change between those states</h3>"
        "<p>Adjacent pairs and the oldest-to-HEAD span. Movement, files, and "
        "text lines are copied from the supplied comparison. HTML does not "
        "subtract.</p>"
        f"{changes}</section>"
    )


def _slot_outcome_label(slot: SlotView, family: str) -> str:
    if slot.status != "available":
        return "UNKNOWN"
    for outcome in slot.outcomes:
        if outcome.family == family:
            return outcome.label or "UNKNOWN"
    return "UNKNOWN"


def _change_strip(pair: ComparisonView) -> str:
    if pair.status != "available" or pair.change is None:
        reason = pair.unavailable_reason or pair.status
        return (
            f'<article class="card"><h3>{escape_html(pair.title)}</h3>'
            f"<p>{escape_html(reason)}. Change was not inferred.</p></article>"
        )
    movements = "".join(
        f"<li>{escape_html(item.title)}: {escape_html(item.label)}</li>" for item in pair.movements
    )
    return (
        f'<article class="card"><h3>{escape_html(pair.title)}</h3>'
        f"<ul>{movements or '<li>Movement UNKNOWN</li>'}</ul>"
        f"<p>Changed files: {_display(pair.change.file_count)} · "
        f"changed text lines: {_display(pair.change.text_line_count)}</p></article>"
    )


def _concentration(view: TrendReportView) -> str:
    return (
        '<section id="concentration" class="report-section">'
        "<h2>Where observations concentrate</h2>"
        "<p>HEAD ownership records only. A missing ratio stays UNKNOWN. "
        "HTML does not calculate a concentration percentage.</p>"
        f"{_ownership_list(view.ownership)}</section>"
    )


def _priority_actions(view: TrendReportView) -> str:
    if view.priority_actions is None:
        body = (
            "<p>Priority actions unavailable. No recommendation record was supplied for HEAD.</p>"
        )
    elif not view.priority_actions:
        body = "<p>The HEAD recommendation record supplied no priority actions.</p>"
    else:
        shown = view.priority_actions[:12]
        items = "".join(
            "<li><strong>"
            f"{escape_html(title)}</strong> · {escape_html(horizon)} · "
            f"priority {escape_html(priority)} · {escape_html(category)}</li>"
            for title, priority, horizon, category in shown
        )
        note = _bounded_note(len(shown), len(view.priority_actions))
        body = (
            "<p>HEAD recommendations in the supplied presentation horizon. "
            "This list does not assign a new rank.</p>"
            f"<ul>{items}</ul>{note}"
        )
    return f'<section id="actions" class="report-section"><h2>Priority actions</h2>{body}</section>'


def _modernization(view: TrendReportView) -> str:
    del view
    return (
        '<section id="modernization" class="report-section">'
        "<h2>One assessment foundation</h2>"
        "<h3>Awaiting business context</h3>"
        "<p>Business context was not supplied. Modernization constraints, "
        "decision horizons, and business-impact inputs remain unavailable.</p>"
        "<p>Technical recommendations that exist are listed under Priority "
        "actions. They are not a modernization roadmap.</p></section>"
    )


def _trust(view: TrendReportView) -> str:
    profile = view.profile
    rows = "".join(
        f"<li><strong>{escape_html(label)}</strong>: {escape_html(value)}</li>"
        for label, value in view.trust_rows
    )
    extra = (
        f"<li><strong>Pinned Engine</strong>: "
        f"{escape_html(str(profile.get('engine_version') or 'UNKNOWN'))}</li>"
        f"<li><strong>Pinned ruleset</strong>: "
        f"{escape_html(str(profile.get('ruleset_version') or 'UNKNOWN'))}</li>"
        f"<li><strong>Pinned config digest</strong>: "
        f"{escape_html(str(profile.get('config_digest') or 'UNKNOWN'))}</li>"
        f"<li><strong>Pinned feed digest</strong>: "
        f"{escape_html(str(profile.get('feed_digest') or 'UNKNOWN'))}</li>"
        f"<li><strong>HEAD SHA</strong>: {escape_html(view.head_sha or 'UNKNOWN')}</li>"
    )
    return (
        '<section id="trust" class="report-section">'
        "<h2>Coverage &amp; Trust</h2>"
        "<p>Same pinned Engine, rules, config, and feed identity across "
        "available snapshots.</p>"
        f"<p>{escape_html(CHECKOUT_DIGEST_NOTE)}</p>"
        f'<ul class="trust-list">{extra}{rows}</ul></section>'
    )


def _appendix(view: TrendReportView) -> str:
    slots = []
    for slot in view.slots:
        slots.append(
            f'<article id="evidence-{escape_html(slot.name)}" class="card">'
            f"<h3>Snapshot {escape_html(slot.name)}</h3>"
            f"<p>Status: {escape_html(slot.status)}</p>"
            f"<p>SHA: <code>{escape_html(slot.sha or 'UNKNOWN')}</code></p>"
            f"<p>Source digest: <code>{escape_html(slot.source_digest or 'UNKNOWN')}</code></p>"
            f"<p>Result digest: <code>{escape_html(slot.result_digest or 'UNKNOWN')}</code></p>"
            f"<p>Engine / config / feed: "
            f"<code>{escape_html(slot.engine_version or 'UNKNOWN')}</code> / "
            f"<code>{escape_html(slot.config_digest or 'UNKNOWN')}</code> / "
            f"<code>{escape_html(slot.feed_digest or 'UNKNOWN')}</code></p>"
            "</article>"
        )
    pairs = []
    for item in view.comparisons:
        pairs.append(
            f"<li>{escape_html(item.id)}: {escape_html(item.status)} · "
            f"{escape_html(item.base_sha or 'UNKNOWN')} → "
            f"{escape_html(item.candidate_sha or 'UNKNOWN')}</li>"
        )
    return (
        '<section id="evidence" class="report-section">'
        "<h2>Source-state-bound evidence</h2>"
        "<p>Every displayed claim is bound to a snapshot or to an explicit comparison pair.</p>"
        f"{''.join(slots)}"
        "<h3>Comparison identity</h3>"
        f"<ul>{''.join(pairs)}</ul>"
        '<p><a href="trend-index.json">Download trend-index.json</a></p>'
        "</section>"
    )


def _script() -> str:
    return f"<script>{_TREND_COMPARISON_SCRIPT}</script>"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _as_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _display(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    return str(value)


def _title_of(item: Any) -> str:
    if isinstance(item, dict):
        return str(
            item.get("title") or item.get("identity_key") or item.get("rule_id") or "finding"
        )
    return str(getattr(item, "title", None) or "finding")


def _digest_line(payload: dict[str, str | None]) -> str:
    if not payload:
        return "UNKNOWN"
    return ", ".join(f"{key}={value or 'UNKNOWN'}" for key, value in sorted(payload.items()))
