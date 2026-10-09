"""R2-P04: baseline assessment.html hierarchy and Architecture Map projection."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from tests.application.incremental.git_repo_helpers import commit_all, init_repo

from codestrata.application.assessment.canonical_records import (
    CANONICAL_COCHANGE_KEY,
    CANONICAL_HOTSPOTS_KEY,
    CANONICAL_OWNERSHIP_KEY,
    seal_assess_canonical_records,
)
from codestrata.domain.graph.enums import GraphGenerationMode, GraphStatus, GraphType
from codestrata.domain.graph.models import (
    GraphMetadata,
    GraphNode,
    GraphRelationship,
    GraphSnapshot,
)
from codestrata.models import AnalysisResult, Repository
from codestrata.reporting.engineering_health.architecture_map import (
    DISPLAY_NODE_LIMIT,
    project_architecture_map,
)
from codestrata.reporting.html_v2 import HtmlReportRenderer, build_html_report_view_model
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput
from codestrata.services.graph_assessment import GraphAssessmentPipeline

_EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "journeys"
_PINNED = datetime(2026, 9, 27, tzinfo=UTC)

_HIERARCHY = (
    "attention-first",
    "assessment-results",
    "architecture-map",
    "engineering-hotspots",
    "ownership-concentration",
    "temporal-co-change",
    "priority-actions",
    "coverage-and-trust",
    "technical-appendix",
)


def _metadata() -> GraphMetadata:
    return GraphMetadata(
        graph_id="graph:r2-p04",
        graph_type=GraphType.REPOSITORY,
        schema_version="1.0.0",
        generator_version="test",
        source_fingerprint="fp-r2-p04",
        generation_mode=GraphGenerationMode.FULL,
        status=GraphStatus.VALID,
    )


def _node(node_id: str, node_type: str, **properties: object) -> GraphNode:
    return GraphNode(
        id=node_id,
        node_type=node_type,
        schema_version="1.0.0",
        properties=properties,
    )


def _edge(edge_id: str, rel: str, source: str, target: str) -> GraphRelationship:
    return GraphRelationship(
        id=edge_id,
        relationship_type=rel,
        source_node_id=source,
        target_node_id=target,
    )


def _report(analysis: AnalysisResult) -> ModernizationReportInput:
    return ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=_PINNED,
    )


def test_architecture_map_copies_canonical_nodes_and_edges_only() -> None:
    snapshot = GraphSnapshot(
        metadata=_metadata(),
        nodes=(
            _node("repo:demo", "repository", name="demo"),
            _node("module:checkout", "module", name="checkout", path="src/checkout"),
            _node("file:cart.js", "file", name="cart.js", path="src/checkout/cart.js"),
        ),
        relationships=(
            _edge("e-contains", "contains", "module:checkout", "file:cart.js"),
            _edge("e-depends", "depends_on", "module:checkout", "repo:demo"),
        ),
    )
    view = project_architecture_map(
        snapshot,
        hotspot_subjects={"src/checkout/cart.js": ("hs-1",)},
    )
    assert view.available is True
    assert view.canonical_node_count == 3
    assert view.canonical_edge_count == 2
    assert {item.node_id for item in view.nodes} == {
        "repo:demo",
        "module:checkout",
        "file:cart.js",
    }
    assert {item.edge_id for item in view.edges} == {"e-contains", "e-depends"}
    assert view.grouping == "module"
    displayed = {item.node_id for item in view.nodes if item.displayed}
    assert displayed == {"module:checkout"}
    assert all(item.relationship_type in {"contains", "depends_on"} for item in view.edges)
    file_node = next(item for item in view.nodes if item.node_id == "file:cart.js")
    assert file_node.parent_id == "module:checkout"
    assert file_node.hotspot_record_ids == ("hs-1",)


def test_architecture_map_does_not_invent_module_edges_or_boundaries() -> None:
    snapshot = GraphSnapshot(
        metadata=_metadata(),
        nodes=(
            _node("file:a", "file", path="src/a.js"),
            _node("file:b", "file", path="src/b.js"),
        ),
        relationships=(_edge("e-imports", "imports", "file:a", "file:b"),),
    )
    view = project_architecture_map(snapshot)
    assert view.grouping == "file"
    assert {item.node_id for item in view.nodes if item.displayed} == {"file:a", "file:b"}
    assert len(view.edges) == 1
    assert view.edges[0].edge_id == "e-imports"
    assert all(item.parent_id is None for item in view.nodes)


def test_architecture_map_unavailable_and_display_limit() -> None:
    empty = project_architecture_map(None)
    assert empty.available is False
    assert empty.unavailable_reason is not None
    nodes = tuple(_node(f"module:{index}", "module", name=f"m{index}") for index in range(90))
    snapshot = GraphSnapshot(metadata=_metadata(), nodes=nodes, relationships=())
    limited = project_architecture_map(snapshot, display_node_limit=DISPLAY_NODE_LIMIT)
    assert limited.display_limit_disclosed is True
    assert limited.displayed_node_count == DISPLAY_NODE_LIMIT
    assert limited.canonical_node_count == 90
    assert sum(1 for item in limited.nodes if item.displayed) == DISPLAY_NODE_LIMIT


def test_baseline_html_hierarchy_from_complete_js_fixture(tmp_path: Path) -> None:
    repo = tmp_path / "complete-js"
    shutil.copytree(_EXAMPLES / "complete-js", repo)
    init_repo(repo)
    commit_all(repo, "pin fixture")
    analysis = seal_assess_canonical_records(
        AnalysisResult(
            repository=Repository(name="complete-js", path=repo, files=["src/app.js"]),
        ),
        repository_root=repo,
        evaluation_time=_PINNED,
    )
    graph = GraphAssessmentPipeline().run(
        Repository(name="complete-js", path=repo, files=["src/app.js"], total_files=1)
    )
    analysis.metadata["canonical_graph"] = graph.repository_graph.snapshot.model_dump(mode="json")
    document = build_html_report_view_model(_report(analysis))
    html = HtmlReportRenderer().render(document)

    positions = [html.find(f'id="{anchor}"') for anchor in _HIERARCHY]
    assert all(pos >= 0 for pos in positions), positions
    assert positions == sorted(positions)
    assert html.find('id="assessment-results"') < html.find('id="architecture-map"')
    assert html.find('id="architecture-map"') < html.find('id="priority-actions"')
    assert "Current outcomes" in html
    assert "Architecture Map" in html
    assert "Coverage &amp; Trust" in html or "Coverage & Trust" in html
    assert "No comparison or trend was requested" in html
    assert "Architecture" in html
    assert "Security" in html
    assert "Quality" in html
    assert (
        "Maintainability &amp; Technical Debt" in html or "Maintainability & Technical Debt" in html
    )
    assert "health_score" not in html
    assert "before-after-delta" not in html
    assert "Stable" not in html
    assert "<script src" not in html
    assert html.lower().count("<script") == 1
    offline = html.lower().replace("https://github.com/googlefonts/googlesans-flex", "")
    offline = offline.replace("https://openfontlicense.org", "")
    assert "https://" not in offline
    assert "cdn." not in html.lower()

    assert document.engineering_hotspots is not None
    assert document.engineering_hotspots.available is True
    assert any(item.ranking_value == "12" for item in document.engineering_hotspots.items)
    assert "ranking_value: 12" in html
    assert document.ownership_concentration is not None
    assert any(
        item.serialized_ratio == "1.000000" for item in document.ownership_concentration.items
    )
    assert "1.000000" in html
    assert document.architecture_map is not None
    assert document.architecture_map.available is True
    assert document.architecture_map.canonical_node_count == len(graph.repository_graph.nodes)
    assert document.architecture_map.canonical_edge_count == len(
        graph.repository_graph.relationships
    )
    html_node_ids = {item.node_id for item in document.architecture_map.nodes if item.displayed}
    canonical_ids = {str(node.id) for node in graph.repository_graph.nodes}
    assert html_node_ids <= canonical_ids
    html_edge_ids = {item.edge_id for item in document.architecture_map.edges}
    canonical_edge_ids = {rel.id for rel in graph.repository_graph.relationships}
    assert html_edge_ids <= canonical_edge_ids
    assert document.coverage_trust is not None
    assert "2026-09-27" in " ".join(row.value for row in document.coverage_trust.rows)


def test_missing_git_and_missing_graph_stay_explicit(tmp_path: Path) -> None:
    repo = tmp_path / "missing"
    (repo / "src").mkdir(parents=True)
    shutil.copy(_EXAMPLES / "complete-js" / "src" / "app.js", repo / "src" / "app.js")
    analysis = seal_assess_canonical_records(
        AnalysisResult(repository=Repository(name="missing", path=repo, files=["src/app.js"])),
        repository_root=repo,
        evaluation_time=_PINNED,
    )
    html = HtmlReportRenderer().render(build_html_report_view_model(_report(analysis)))
    assert 'id="architecture-map"' in html
    assert "Canonical repository graph is unavailable" in html
    assert "m22_records_not_attached" not in html or analysis.metadata[CANONICAL_HOTSPOTS_KEY]
    ownership = analysis.metadata[CANONICAL_OWNERSHIP_KEY][0]
    assert ownership["status"] == "unknown"
    assert "unknown" in html.lower()
    assert "No comparison or trend was requested" in html
    assert analysis.metadata[CANONICAL_COCHANGE_KEY] is not None


def test_outline_and_document_fields_are_r2_baseline(tmp_path: Path) -> None:
    analysis = AnalysisResult(
        repository=Repository(name="empty", path=tmp_path / "empty", files=["README.md"]),
    )
    document = build_html_report_view_model(_report(analysis))
    ordered = [entry.section_id for entry in document.outline]
    assert ordered[:2] == ["attention-first", "assessment-results"]
    for anchor in _HIERARCHY:
        assert anchor in ordered
    assert document.architecture_map is not None
    assert document.architecture_map.available is False
    assert document.engineering_hotspots is not None
    assert document.engineering_hotspots.available is False
    assert document.attention_summary is not None
    assert "comparison" in document.attention_summary.comparison_state.lower()
