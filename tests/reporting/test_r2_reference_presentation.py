"""R2 reference-shell presentation: hierarchy, limits, honesty, and offline controls."""

from __future__ import annotations

from codestrata.reporting.engineering_health.models import (
    ArchitectureMapView,
    CochangePairView,
    CochangeSectionView,
    EngineeringHotspotView,
    HotspotSectionView,
)
from codestrata.reporting.html_v2.r2_shell import (
    PRINT_CONTROL_SCRIPT,
    content_security_policy,
    script_source_hash,
)
from codestrata.reporting.html_v2.renderer import (
    _MAIN_COCHANGE_SUPPORTED_LIMIT,
    _MAIN_HOTSPOT_CARD_LIMIT,
    CONTENT_SECURITY_POLICY,
    _render_architecture_map,
    _render_engineering_hotspots,
    _render_temporal_cochange,
    begin_rendered_evidence_ids,
    end_rendered_evidence_ids,
)


def _hotspot(index: int) -> EngineeringHotspotView:
    return EngineeringHotspotView(
        record_id=f"hs-{index}",
        subject_id=f"<file {index}>.py",
        list_kind="file",
        ranking_value=str(index),
        contributors=(),
        evidence_ids=("m16.function", "m24.file_churn", "component.mapping", "evidence:source:aa"),
    )


def test_hotspot_main_flow_is_bounded_and_escaped() -> None:
    section = HotspotSectionView(
        available=True,
        items=tuple(_hotspot(index) for index in range(40)),
    )
    html = _render_engineering_hotspots(section)
    assert html.count('class="card hotspot-card"') == _MAIN_HOTSPOT_CARD_LIMIT
    assert "Showing 12 of 40" in html
    assert "does not calculate a new rank" in html
    assert "canonical JSON" in html
    assert "<file 0>.py" not in html
    assert "&lt;file 0&gt;.py" in html
    assert "hs-39" not in html
    assert 'href="#evidence-m16.function"' not in html
    assert "m16.function (evidence not attached)" in html
    assert "component.mapping (evidence not attached)" in html
    assert 'href="#evidence-evidence:source:aa"' not in html
    token = begin_rendered_evidence_ids(("evidence:source:aa",))
    try:
        linked = _render_engineering_hotspots(section)
    finally:
        end_rendered_evidence_ids(token)
    assert 'href="#evidence-evidence:source:aa"' in linked
    assert "m24.file_churn (evidence not attached)" in linked


def test_cochange_separates_supported_pairs_and_discloses_the_limit() -> None:
    items = []
    for index in range(20):
        items.append(
            CochangePairView(
                scope="repository",
                left=f"left-{index}",
                right=f"right-{index}",
                support=index,
                union=index + 3,
                jaccard="0.250000",
                supported_relation=index % 2 == 0,
            )
        )
    html = _render_temporal_cochange(CochangeSectionView(available=True, items=tuple(items)))
    assert "Supported relation" in html
    assert "Not a supported relation" in html
    assert html.count("Supported relation") >= 1
    assert "Jaccard is copied, not calculated here." in html
    assert str(_MAIN_COCHANGE_SUPPORTED_LIMIT) in html
    assert "canonical JSON" in html
    assert "<script" not in html


def test_missing_component_grouping_stays_unavailable() -> None:
    view = ArchitectureMapView(
        available=True,
        grouping="file",
        canonical_node_count=2,
        canonical_edge_count=1,
        displayed_node_count=2,
        nodes=(),
        edges=(),
    )
    html = _render_architecture_map(view)
    assert "Component grouping is unavailable" in html
    assert "No component boundary or dependency was inferred." in html


def test_graph_absence_is_explicit() -> None:
    html = _render_architecture_map(None)
    assert "Canonical repository graph is unavailable" in html
    assert "<svg" not in html


def test_print_script_is_hashed_and_has_no_report_text() -> None:
    assert "canonical" not in PRINT_CONTROL_SCRIPT
    assert "<" not in PRINT_CONTROL_SCRIPT
    assert f"'sha256-{script_source_hash(PRINT_CONTROL_SCRIPT)}'" in CONTENT_SECURITY_POLICY
    assert CONTENT_SECURITY_POLICY == content_security_policy(PRINT_CONTROL_SCRIPT)
    assert "font-src data:" in CONTENT_SECURITY_POLICY
    assert "font-src 'none'" not in CONTENT_SECURITY_POLICY
    assert "connect-src 'none'" in CONTENT_SECURITY_POLICY
    assert "https://" not in CONTENT_SECURITY_POLICY
