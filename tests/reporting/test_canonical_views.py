"""E11.2 projections copy canonical fields and do not invent scores."""

from __future__ import annotations

from typing import Any

from codestrata.domain.contracts.enums import ResultStatus
from codestrata.domain.contracts.envelope import CanonicalEnvelope, seal_envelope
from codestrata.domain.contracts.examples import (
    example_complete,
    example_no_baseline,
    example_partial,
    example_unknown,
)
from codestrata.domain.contracts.examples_e01_3 import example_comparison
from codestrata.reporting.canonical_views import (
    CanonicalReportInput,
    CochangeView,
    dumps_canonical_json,
    project_canonical_html,
    project_canonical_json,
    project_canonical_sarif,
)
from tests.reporting.html_claims import assert_no_network_asset, claim_text


def _report(envelope: CanonicalEnvelope, **kwargs: Any) -> CanonicalReportInput:
    return CanonicalReportInput(envelope=envelope, **kwargs)


def test_html_projects_six_views_from_complete_envelope() -> None:
    envelope = example_complete()
    hotspot = envelope.body.hotspots[0]
    ownership = envelope.body.ownership[0]
    summary = envelope.body.change_summary
    assert summary is not None
    html = project_canonical_html(
        _report(
            envelope,
            comparison=example_comparison(kind="compatible"),
            cochange=(
                CochangeView(
                    scope="file",
                    left="a.java",
                    right="b.java",
                    support=3,
                    union=5,
                    jaccard="0.600000",
                    supported_relation=True,
                    qualified_incomplete_window=False,
                ),
            ),
            purpose="production",
        )
    )
    assert_no_network_asset(html)
    assert "<script" not in html
    assert 'id="engineering-hotspots"' in html
    assert hotspot.ranking_value is not None
    assert hotspot.ranking_value in html
    assert hotspot.priority_explanation in html
    assert hotspot.active_finding_ids[0] in html
    assert 'id="ownership-concentration"' in html
    assert ownership.scope.value in html
    assert str(ownership.denominator) in html
    assert ownership.history_profile_id in html
    assert 'id="temporal-co-change"' in html
    assert "a.java" in html
    assert ">3<" in html
    assert ">5<" in html
    assert 'id="change-summary"' in html
    assert str(summary.changed_file_count) in html
    assert 'id="capability-coverage"' in html
    assert envelope.body.coverage[0].capability_id in html
    assert 'id="before-after-delta"' in html
    assert "architecture.dependency-cycle" in html
    assert "class=\"healthy\"" not in html


def test_first_run_says_no_baseline_without_stable_or_zero_delta() -> None:
    html = project_canonical_html(_report(example_no_baseline()))
    assert "no baseline" in html
    assert "delta unavailable" in html
    assert "outcome movement unavailable" in html
    assert "Stable" not in html
    assert "Improved" not in html
    assert ">0<" not in html


def test_unknown_and_not_applicable_are_not_healthy() -> None:
    html = project_canonical_html(_report(example_unknown()))
    assert "unknown" in html
    assert "feed_missing" in html
    ownership = html.split('id="ownership-concentration"', 1)[1].split("</section>", 1)[0]
    assert ">0.000000<" not in ownership
    assert ">1.000000<" not in ownership
    assert "healthy" not in html
    assert "outcome-unknown" in html or "outcome-not-applicable" in html


def test_incompatible_comparison_keeps_movement_unavailable() -> None:
    html = project_canonical_html(
        _report(example_complete(), comparison=example_comparison(kind="incompatible"))
    )
    assert "insufficient" in html
    assert "outcome movement unavailable for a full verdict" in html
    assert "Stable" not in html
    assert "stable" not in html
    assert "improved" not in claim_text(html).lower()
    assert "Compatible baseline" not in html
    assert "baseline coverage:" in html
    assert "candidate coverage:" in html
    assert "see capability coverage" not in html


def test_incompatible_series_pair_keeps_unknown_not_stable() -> None:
    from codestrata.domain.contracts.enums import CompatibilityStatus

    comparison = example_comparison(kind="incompatible")
    html = project_canonical_html(_report(example_complete(), comparison=comparison))
    assert comparison.compatibility is CompatibilityStatus.INCOMPATIBLE
    assert "insufficient" in html
    assert "Stable" not in html
    assert "outcome movement unavailable for a full verdict" in html


def test_partial_missing_tests_render_unknown() -> None:
    summary = example_partial().body.change_summary
    assert summary is not None
    assert summary.affected_test_count is None
    html = project_canonical_html(_report(example_partial()))
    change = html.split('id="change-summary"', 1)[1].split("</section>", 1)[0]
    assert "affected_test_count: UNKNOWN" in change
    assert "test_association_status: UNKNOWN" in change
    assert "cutoff_reason: none" in change
    assert "affected_test_count: 0" not in change
    assert "affected_test_count: " not in change.replace("affected_test_count: UNKNOWN", "")


def test_partial_comparison_keeps_known_delta() -> None:
    html = project_canonical_html(
        _report(example_complete(), comparison=example_comparison(kind="mixed-cause"))
    )
    assert "M06" in html
    assert ">1<" in html
    assert "mixed" in html


def test_html_escapes_messages() -> None:
    html = project_canonical_html(
        _report(example_complete(), context_only_concern="<script>alert(1)</script>")
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_missing_cochange_is_unavailable() -> None:
    html = project_canonical_html(_report(example_complete()))
    assert "temporal co-change unavailable" in html


def test_json_copies_canonical_order_and_omits_score() -> None:
    envelope = example_complete()
    report = _report(
        envelope,
        purpose="preview",
        context_only_concern="narrative_only",
        cochange=(
            CochangeView(
                scope="file",
                left="a",
                right="b",
                support=None,
                union=None,
                jaccard=None,
                supported_relation=None,
                qualified_incomplete_window=True,
                unavailable_reason="shallow_history",
            ),
        ),
    )
    payload = project_canonical_json(report)
    assert dumps_canonical_json(report).endswith("\n")
    assert payload["cochange"][0]["unavailable_reason"] == "shallow_history"
    assert payload["health_score"] is None
    assert payload["preview_cannot_authorize_production"] is True
    assert [item["record_id"] for item in payload["hotspots"]] == [
        item.record_id for item in envelope.body.hotspots
    ]
    assert payload["hotspots"][0]["ranking_value"] == envelope.body.hotspots[0].ranking_value


def test_sarif_fingerprint_and_unknown_are_stable() -> None:
    envelope = example_complete()
    finding = envelope.body.findings[0].model_copy(update={"result": ResultStatus.UNKNOWN.value})
    body = envelope.body.model_copy(update={"findings": (finding,)})
    sealed = seal_envelope(body)
    report = _report(sealed)
    first = project_canonical_sarif(report)
    second = project_canonical_sarif(report)
    result = first["runs"][0]["results"][0]
    assert result["partialFingerprints"] == second["runs"][0]["results"][0]["partialFingerprints"]
    assert result["kind"] != "pass"
    assert result["message"]["text"].endswith("unknown")
    props = first["runs"][0]["properties"]
    assert props["scan_clean"] is False
    assert props["unknown_disclosed"] is True
    assert props["health_score"] is None
    assert props["hotspots"]
    assert result["properties"]["healthy_badge"] is False
    assert result["properties"]["default_severity"] == "high"
    assert result["properties"]["effective_severity"] == "high"
    absent = finding.model_copy(update={"result": ResultStatus.NOT_APPLICABLE.value})
    sealed_absent = seal_envelope(envelope.body.model_copy(update={"findings": (absent,)}))
    absent_result = project_canonical_sarif(_report(sealed_absent))["runs"][0]["results"][0]
    assert absent_result["level"] == "note"
    assert absent_result["properties"]["healthy_badge"] is False
    no_summary = seal_envelope(envelope.body.model_copy(update={"change_summary": None}))
    assert "change summary unavailable" in project_canonical_html(_report(no_summary))


def test_trend_html_source_omits_health_score() -> None:
    from codestrata.reporting.engineering_health.trend_report import TrendReportView, _html

    html = _html(
        TrendReportView(
            repository_id="demo",
            series_id="series",
            head_sha=None,
            head_branch=None,
            repository_name=None,
            dirty_notice=None,
            profile={},
            slots=(),
            comparisons=(),
            head_outcomes=(),
            hotspots=None,
            ownership=None,
            cochange=None,
            trust_rows=(),
            architecture_available=False,
            architecture_reason="unavailable",
            architecture_node_count=None,
            architecture_edge_count=None,
        )
    )
    assert "health_score" not in html
    assert "health score" not in html.lower()
    assert "Five-commit health trend" in html
