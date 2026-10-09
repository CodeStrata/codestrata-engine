"""Row alignment, honest AI states, and the failed-slot timeline.

The populated AI object below is a test fixture. It is not assessment evidence.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from codestrata.reporting.engineering_health.trend_report import (
    OUTCOME_TITLES,
    OutcomeCard,
    SlotView,
    _ai_summary_section,
    _health_timeline,
    _outcome_card,
)
from codestrata.reporting.html_v2.models import AiEnrichmentView, AiNextStepView, AiPriorityView
from codestrata.reporting.html_v2.renderer import (
    AI_NOT_REQUESTED,
    _render_ai_summary_populated,
    _render_ai_summary_section,
)

_SHELL = (
    Path(__file__).resolve().parents[2]
    / "src/codestrata/reporting/html_v2/assets/r2_shell.css"
)


def test_named_card_rows_stretch_without_a_fixed_height() -> None:
    css = _SHELL.read_text(encoding="utf-8")
    assert "grid-template-rows: subgrid" in css
    assert ".outcome-grid > .health-card { grid-row: span 4; }" in css
    assert ".pair-grid > .pair-card { grid-row: span 6; }" in css
    assert ".attention-row" in css
    assert "align-items: stretch" in css
    assert "min-height: 12rem" not in css
    assert "height: 220px" not in css


def test_outcome_card_keeps_title_status_count_and_evidence_separate() -> None:
    card = OutcomeCard(
        family="architecture",
        title="Maintainability & Technical Debt",
        label="Needs attention",
        finding_count=3,
        coverage_status="complete",
    )
    html = _outcome_card(card)
    assert html.index("<h3>") < html.index('class="card-status"')
    assert html.index('class="card-status"') < html.index('class="card-count"')
    assert html.index('class="card-count"') < html.index('class="card-evidence"')
    assert "Outcome evidence" in html


def test_absent_ai_state_invents_no_plan() -> None:
    html = _render_ai_summary_section(SimpleNamespace(ai_enrichment=None))
    assert AI_NOT_REQUESTED in html
    assert "No generated summary or improvement plan is included." in html
    assert "Executive interpretation" not in html
    assert 'id="modernization-advisor"' not in html
    trend = _ai_summary_section()
    assert AI_NOT_REQUESTED in trend
    assert "no AI result contract" in trend
    assert "Proposed improvement plan" not in trend


def test_populated_ai_fixture_stays_separate_from_engine_facts() -> None:
    fixture = AiEnrichmentView(
        headline="TEST FIXTURE interpretation",
        narrative="TEST FIXTURE narrative only.",
        priorities=(
            AiPriorityView(
                title="TEST FIXTURE priority",
                rationale="because the fixture says so",
                priority="suggested",
            ),
        ),
        suggested_next_steps=(
            AiNextStepView(
                order=1,
                title="TEST FIXTURE step",
                summary="not an engine horizon",
            ),
        ),
        referenced_finding_ids=("TEST-F1",),
        referenced_recommendation_ids=("TEST-R1",),
        provider="test-fixture",
        model_id="test-fixture-model",
        limitations=("TEST FIXTURE limitation",),
    )
    html = _render_ai_summary_populated(fixture)
    assert "TEST FIXTURE interpretation" in html
    assert "Executive interpretation" in html
    assert "Suggested priorities and rationale" in html
    assert "Proposed improvement plan" in html
    assert "TEST-<wbr>F1" in html
    assert "TEST FIXTURE limitation" in html
    assert "does not overwrite Engine outcomes" in html
    assert "Calibrated recommendation horizons stay as supplied." in html
    assert "health score" not in html.lower()


def _slot(number: int, status: str) -> SlotView:
    available = status == "available"
    outcomes = tuple(
        OutcomeCard(
            family=family,
            title=title,
            label="Needs attention" if available else "UNKNOWN",
            finding_count=number if available else None,
            coverage_status="complete" if available else "UNKNOWN",
        )
        for family, title in OUTCOME_TITLES
    )
    return SlotView(
        slot=number,
        name=f"s{number}",
        status=status,
        sha="abc1234def" if available else None,
        source_revision="abc1234def" if available else None,
        source_digest=None,
        result_digest=None,
        engine_version=None,
        config_digest=None,
        feed_digest=None,
        limitations=() if available else ("TEST FIXTURE repository was not found",),
        file_count=4 if available else None,
        assessed_file_count=4 if available else None,
        outcomes=outcomes,
    )


def test_failed_slots_are_timeline_gaps_without_a_score() -> None:
    view = SimpleNamespace(
        slots=(
            _slot(1, "failed"),
            _slot(2, "available"),
            _slot(3, "failed"),
            _slot(4, "failed"),
            _slot(5, "available"),
        )
    )
    html = _health_timeline(view)
    assert "Engineering health across five commits" in html
    assert "No score is assigned" in html
    assert "S5 · HEAD" in html
    assert html.count('class="lane-gap') == 12
    assert "Unavailable" in html
    assert "<polyline" not in html
    assert "Supplied finding counts" in html
    assert "not a numeric series" in html
    assert "TEST FIXTURE" not in html.split("Supplied finding counts", 1)[0]
