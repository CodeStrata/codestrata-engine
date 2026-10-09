"""P02 reconciliation: current health, file populations, and scoped M27 lines."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.application.incremental.trend_comparisons import _scope_m27
from codestrata.reporting.engineering_health.models import (
    CochangePairView,
    CochangeSectionView,
)
from codestrata.reporting.engineering_health.trend_current_health import (
    load_priority_actions,
    project_slot_headline_outcomes,
    slot_file_populations,
)
from codestrata.reporting.engineering_health.trend_report import (
    ChangeScopeView,
    ComparisonView,
    MovementView,
    OutcomeCard,
    SlotView,
    TrendReportView,
    _cochange_list,
    _five_state_section,
    _html,
    _modernization,
    _priority_actions,
)

PRESERVED_S3 = Path(
    "/Users/satish_byndr/Documents/workspace-codestrata/p02-evidence-1593bcb9/snapshots/s3"
)


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _finding(finding_id: str, category: str) -> dict[str, str]:
    return {
        "id": finding_id,
        "rule_id": f"{category}.sample",
        "title": finding_id,
        "description": finding_id,
        "severity": "medium",
        "category": category,
    }


def test_headline_projection_uses_customer_findings_not_analysis_counts(tmp_path: Path) -> None:
    slot = tmp_path / "slot"
    _write(
        slot / "findings.json",
        {
            "finding_count": 10,
            "findings": [
                *[_finding(f"arch-{index}", "architecture") for index in range(2)],
                *[_finding(f"sec-{index}", "security") for index in range(3)],
                *[_finding(f"debt-{index}", "maintainability") for index in range(4)],
                _finding("dependency-only", "dependency"),
            ],
        },
    )
    for name, status in (
        ("architecture.json", "succeeded"),
        ("security.json", "partially_succeeded"),
        ("testing.json", "succeeded"),
        ("technical-debt.json", "succeeded"),
    ):
        _write(slot / "heads" / name, {"status": status, "conclusions": []})
    _write(
        slot / "analysis-result.json",
        {
            "findings": [_finding("analysis-only", "security")],
            "metadata": {"canonical_limitations": ["feed_missing", "cannot_prove_clean"]},
        },
    )

    outcomes = project_slot_headline_outcomes(slot)
    assert outcomes is not None
    by_family = {item[0]: item for item in outcomes}
    assert by_family["architecture"] == (
        "architecture",
        "Architecture",
        "Needs attention",
        2,
        "complete",
    )
    assert by_family["security"][2:4] == ("Insufficient evidence", 3)
    assert by_family["quality"] == (
        "quality",
        "Quality",
        "No material issues observed",
        0,
        "complete",
    )
    assert by_family["maintainability"][2:4] == ("Needs attention", 4)
    assert all(item[3] != 1 for item in outcomes)


def test_missing_customer_findings_do_not_invent_headline_counts(tmp_path: Path) -> None:
    slot = tmp_path / "slot"
    _write(
        slot / "analysis-result.json",
        {"findings": [_finding("analysis-only", "security")]},
    )
    assert project_slot_headline_outcomes(slot) is None


def test_file_populations_stay_distinct(tmp_path: Path) -> None:
    slot = tmp_path / "slot"
    _write(slot / "scan-boundary-diagnostics.json", {"included_files": 2, "excluded_files": 1})
    _write(slot / "analysis-result.json", {"repository": {"total_files": 2}})
    inventory, assessed = slot_file_populations(slot, ["a", "b", "c", "d", "e"])
    assert inventory == 5
    assert assessed == 2

    bare = tmp_path / "bare"
    assert slot_file_populations(bare, ["only-inventory"]) == (1, None)


@pytest.mark.skipif(
    not (PRESERVED_S3 / "findings.json").is_file(),
    reason="optional local P02 s3 bundle is not present",
)
def test_optional_preserved_s3_matches_baseline_headlines_and_file_populations() -> None:
    outcomes = project_slot_headline_outcomes(PRESERVED_S3)
    assert outcomes is not None
    by_family = {item[0]: item for item in outcomes}
    assert by_family["architecture"][:4] == (
        "architecture",
        "Architecture",
        "Needs attention",
        9,
    )
    assert by_family["security"][:4] == (
        "security",
        "Security",
        "Insufficient evidence",
        62,
    )
    assert by_family["quality"][:4] == ("quality", "Quality", "Needs attention", 1)
    assert by_family["maintainability"][:4] == (
        "maintainability",
        "Maintainability & Technical Debt",
        "Needs attention",
        889,
    )
    slot = json.loads((PRESERVED_S3 / "slot.json").read_text(encoding="utf-8"))
    assert slot_file_populations(PRESERVED_S3, slot.get("file_paths")) == (2332, 2000)


def _file(
    path: str,
    *,
    added: int | None,
    deleted: int | None,
    component: str | None = None,
) -> dict[str, object]:
    return {
        "path": path,
        "status": "modified",
        "binary": False,
        "added_lines": added,
        "deleted_lines": deleted,
        "component_id": component,
    }


def test_priority_actions_use_supplied_horizon_and_ignore_scores(tmp_path: Path) -> None:
    slot = tmp_path / "slot"
    _write(
        slot / "recommendations.json",
        {
            "recommendations": [
                {
                    "title": "Later modularization",
                    "priority": "low",
                    "presentation_bucket": "future",
                    "category": "maintainability",
                    "priority_assessment": {"score": 99},
                },
                {
                    "title": "Establish CI gates",
                    "priority": "high",
                    "presentation_bucket": "near_term",
                    "category": "ci_cd",
                    "priority_assessment": {"score": 80},
                },
            ]
        },
    )
    actions = load_priority_actions(slot)
    assert actions == (
        ("Establish CI gates", "high", "Near Term", "ci_cd"),
        ("Later modularization", "low", "Future", "maintainability"),
    )
    assert load_priority_actions(tmp_path / "missing") is None


def _outcome(family: str, title: str, label: str) -> OutcomeCard:
    return OutcomeCard(
        family=family,
        title=title,
        label=label,
        finding_count=1,
        coverage_status="complete",
    )


def _slot(slot: int, label: str) -> SlotView:
    return SlotView(
        slot=slot,
        name=f"s{slot}",
        status="available",
        sha=None,
        source_revision=f"abc{slot}",
        source_digest=None,
        result_digest=None,
        engine_version=None,
        config_digest=None,
        feed_digest=None,
        limitations=(),
        file_count=5,
        assessed_file_count=2,
        outcomes=(
            _outcome("architecture", "Architecture", label),
            _outcome("security", "Security", "Insufficient evidence"),
            _outcome("quality", "Quality", "Needs attention"),
            _outcome("maintainability", "Maintainability & Technical Debt", "Needs attention"),
        ),
    )


def test_five_state_change_view_and_priority_actions_are_portable() -> None:
    slots = tuple(_slot(index, "Needs attention") for index in range(1, 6))
    comparison = ComparisonView(
        id="s1-s2",
        kind="adjacent",
        title="S1 → S2 · adjacent",
        status="available",
        unavailable_reason=None,
        computed=True,
        base_slot=1,
        candidate_slot=2,
        base_sha="a",
        candidate_sha="b",
        movements=(
            MovementView(
                family="architecture",
                title="Architecture",
                verdict="stable",
                label="Stable",
                reason=None,
            ),
        ),
        lifecycle=None,
        change=ChangeScopeView(
            file_count=0,
            files=(),
            components=(),
            completeness="full",
            limitations=(),
            test_touch=False,
            test_touch_paths=(),
            boundary_spread_status="unknown",
            boundary_spread_count=None,
            text_line_count=0,
        ),
        blast=None,
        deltas=(),
        cause=None,
    )
    view = TrendReportView(
        repository_id="demo",
        series_id="series",
        head_sha="abc5",
        head_branch="launch",
        repository_name="platform",
        dirty_notice=None,
        profile={},
        slots=slots,
        comparisons=(comparison,),
        head_outcomes=slots[-1].outcomes,
        hotspots=None,
        ownership=None,
        cochange=None,
        trust_rows=(),
        architecture_available=False,
        architecture_reason="unavailable",
        architecture_node_count=None,
        architecture_edge_count=None,
        priority_actions=(("Establish CI gates", "high", "Near Term", "ci_cd"),),
    )
    trend = _five_state_section(view)
    assert "<th>S1</th>" in trend and "<th>S5</th>" in trend
    assert trend.count("Needs attention") == 15
    assert "Insufficient evidence" in trend
    assert "Changed files: 0" in trend
    assert "changed text lines: 0" in trend
    assert "Stable" in trend
    actions = _priority_actions(view)
    assert "Establish CI gates" in actions
    assert "Near Term" in actions
    assert "99" not in actions
    modernization = _modernization(view)
    assert "Business context was not supplied" in modernization
    html = _html(view)
    assert 'id="trend"' in html
    assert 'id="actions"' in html
    assert 'id="concentration"' in html
    assert 'id="modernization"' in html
    assert "commerce-service" not in html
    assert "health score" not in html.lower()


def test_scope_drops_out_of_scope_line_totals() -> None:
    payload = {
        "changed_text_lines": 2656,
        "changed_component_ids": ["engine", "platform"],
        "files": [
            _file("engine/a.py", added=100, deleted=20, component="engine"),
            _file("releases/notes.md", added=4, deleted=2, component="docs"),
        ],
        "changed_file_ids": ["engine/a.py", "releases/notes.md"],
        "test_touch_paths": [],
        "limitations": [],
    }
    scoped = _scope_m27(payload, "platform")
    assert scoped["changed_file_count"] == 0
    assert scoped["changed_text_lines"] == 0
    assert scoped["changed_component_ids"] == []
    assert scoped["changed_text_lines"] != payload["changed_text_lines"]


def test_scope_keeps_only_in_scope_lines_and_unknown_lines_stay_unknown() -> None:
    payload = {
        "changed_text_lines": 608,
        "files": [
            _file("platform/src/app.py", added=3, deleted=1, component="api"),
            _file("engine/a.py", added=500, deleted=100, component="engine"),
        ],
        "test_touch_paths": ["engine/test_a.py"],
        "limitations": [],
    }
    scoped = _scope_m27(payload, "platform")
    assert scoped["changed_file_count"] == 1
    assert scoped["changed_text_lines"] == 4
    assert scoped["changed_component_ids"] == ["api"]

    unknown = _scope_m27(
        {
            "changed_text_lines": 10,
            "files": [_file("platform/src/app.py", added=None, deleted=1)],
            "test_touch_paths": [],
            "limitations": [],
        },
        "platform",
    )
    assert unknown["changed_file_count"] == 1
    assert unknown["changed_text_lines"] is None

    unscoped = _scope_m27(
        {"changed_text_lines": 10, "files": [_file("app.py", added=1, deleted=1)]},
        "",
    )
    assert unscoped["changed_text_lines"] == 10


def _pair(
    left: str,
    *,
    supported: bool | None,
    jaccard: str,
    support: int = 2,
    union: int = 2,
) -> CochangePairView:
    return CochangePairView(
        scope="repository",
        left=left,
        right="other",
        support=support,
        union=union,
        jaccard=jaccard,
        supported_relation=supported,
        qualified_incomplete_window=True,
        unavailable_reason="window_incomplete" if supported is None else None,
    )


def test_cochange_status_labels_do_not_treat_jaccard_as_support() -> None:
    section = CochangeSectionView(
        available=True,
        items=(
            _pair("false-perfect", supported=False, jaccard="1.000000"),
            _pair("supported", supported=True, jaccard="0.200000", support=1, union=5),
            _pair("unspecified", supported=None, jaccard="1.000000"),
        ),
    )
    html = _cochange_list(section)
    false_at = html.index("false-perfect")
    supported_at = html.index(">supported<")
    unspecified_at = html.index("unspecified")
    assert false_at < supported_at < unspecified_at
    assert "Not a supported relation" in html
    assert "Supported relation" in html
    assert "Support not supplied" in html
    assert "Jaccard 1.000000" in html
    assert "support 2 / union 2" in html
    assert "scope repository" in html
    assert "incomplete window True" in html
    assert "window_incomplete" in html
    assert "Jaccard is copied and does not decide support." in html
    false_card = html[false_at : html.index(">supported<")]
    assert "Not a supported relation" in false_card
    assert "Supported relation" not in false_card.replace("Not a supported relation", "")
