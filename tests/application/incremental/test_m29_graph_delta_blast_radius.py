"""Tests for E10.2 / M29 graph delta and bounded reverse-dependency blast radius."""

from __future__ import annotations

from decimal import Decimal

from codestrata.application.evidence.testing.models import (
    AssociationConfidence,
    AssociationMethod,
    AssociationMetric,
    AssociationRecord,
    CoverageScope,
    MetricStatusName,
)
from codestrata.application.incremental.change_concerns import (
    evaluate_change_concerns,
)
from codestrata.application.incremental.graph_delta import (
    calculate_graph_delta,
    calculate_static_blast_radius,
)
from codestrata.domain.contracts.formulas import (
    m29_concern_class,
    m29_high_centrality,
    m29_high_churn,
    nearest_rank_percentile,
)


class DummyNode:
    def __init__(self, node_id: str, node_type: str = "component") -> None:
        self.id = node_id
        self.type = node_type
        self.attributes: dict[str, object] = {}


class DummyEdge:
    def __init__(
        self,
        edge_id: str,
        source: str,
        target: str,
        edge_type: str = "depends_on",
    ) -> None:
        self.id = edge_id
        self.source = source
        self.target = target
        self.type = edge_type


class DummyGraph:
    def __init__(self, nodes: list[DummyNode], edges: list[DummyEdge]) -> None:
        self.nodes = nodes
        self.edges = edges


# ---------------------------------------------------------------------------
# Graph Delta Tests
# ---------------------------------------------------------------------------


def test_graph_delta_empty_graphs() -> None:
    delta = calculate_graph_delta(None, None)
    assert delta.added_nodes == []
    assert delta.removed_nodes == []
    assert delta.added_edges == []
    assert delta.removed_edges == []
    assert len(delta.added_nodes) == 0
    assert len(delta.removed_nodes) == 0


def test_graph_delta_added_and_removed() -> None:
    base_nodes = [DummyNode("n1"), DummyNode("n2")]
    base_edges = [DummyEdge("e1", "n1", "n2")]
    base_graph = DummyGraph(base_nodes, base_edges)

    cand_nodes = [DummyNode("n2"), DummyNode("n3")]
    cand_edges = [DummyEdge("e2", "n2", "n3")]
    cand_graph = DummyGraph(cand_nodes, cand_edges)

    delta = calculate_graph_delta(base_graph, cand_graph)
    assert delta.added_nodes == ["n3"]
    assert delta.removed_nodes == ["n1"]
    assert delta.added_edges == ["e2"]
    assert delta.removed_edges == ["e1"]
    assert len(delta.added_nodes) == 1
    assert len(delta.removed_nodes) == 1


# ---------------------------------------------------------------------------
# Static Blast Radius Tests: Diamonds, Cycles, and Traversal
# ---------------------------------------------------------------------------


def test_blast_radius_diamond() -> None:
    # A -> B, A -> C, B -> D, C -> D
    # When D is modified (seed="D"), reverse dependency dependents:
    # B and C directly depend on D.
    # A depends on B and C.
    # Total affected components: D (seed), B, C, A.
    nodes = [DummyNode("A"), DummyNode("B"), DummyNode("C"), DummyNode("D")]
    edges = [
        DummyEdge("e_ab", "A", "B"),
        DummyEdge("e_ac", "A", "C"),
        DummyEdge("e_bd", "B", "D"),
        DummyEdge("e_cd", "C", "D"),
    ]
    graph = DummyGraph(nodes, edges)

    radius, summary = calculate_static_blast_radius(
        seeds=["D"],
        graph=graph,
        max_depth=4,
    )

    assert radius.seeds == ["D"]
    assert set(radius.affected_component_ids) == {"A", "B", "C", "D"}
    assert radius.affected_component_count == 4
    assert radius.cutoff is False
    assert radius.cutoff_reason is None
    assert radius.lower_bound is False


def test_blast_radius_cycle_deduplication() -> None:
    # A -> B -> C -> A (directed cycle)
    # Plus D -> C
    nodes = [DummyNode("A"), DummyNode("B"), DummyNode("C"), DummyNode("D")]
    edges = [
        DummyEdge("e_ab", "A", "B"),
        DummyEdge("e_bc", "B", "C"),
        DummyEdge("e_ca", "C", "A"),
        DummyEdge("e_dc", "D", "C"),
    ]
    graph = DummyGraph(nodes, edges)

    # When C is seed, reverse dependents:
    # B depends on C, D depends on C.
    # A depends on B.
    # C depends on A (already visited, cycle).
    radius, _ = calculate_static_blast_radius(
        seeds=["C"],
        graph=graph,
        max_depth=10,
    )

    assert set(radius.affected_component_ids) == {"A", "B", "C", "D"}
    assert radius.affected_component_count == 4
    assert radius.cutoff is False


def test_blast_radius_depth_cutoff_lower_bound() -> None:
    # Chain: A -> B -> C -> D -> E -> F
    # When F changes, reverse dependents: E (1), D (2), C (3), B (4), A (5)
    nodes = [DummyNode(x) for x in ["A", "B", "C", "D", "E", "F"]]
    edges = [
        DummyEdge("e1", "A", "B"),
        DummyEdge("e2", "B", "C"),
        DummyEdge("e3", "C", "D"),
        DummyEdge("e4", "D", "E"),
        DummyEdge("e5", "E", "F"),
    ]
    graph = DummyGraph(nodes, edges)

    radius, summary = calculate_static_blast_radius(
        seeds=["F"],
        graph=graph,
        max_depth=2,
    )

    # Depth 2 should only reach F (depth 0), E (depth 1), D (depth 2).
    # Since D has reverse neighbor C that wasn't visited, cutoff is triggered.
    assert set(radius.affected_component_ids) == {"D", "E", "F"}
    assert radius.cutoff is True
    assert radius.cutoff_reason == "depth_bound_truncated"
    assert radius.lower_bound is True


def test_blast_radius_node_budget_cutoff() -> None:
    # 1 seed with 10 reverse dependents, but max_visited_nodes = 3
    nodes = [DummyNode("root")] + [DummyNode(f"dep_{i}") for i in range(10)]
    edges = [DummyEdge(f"e_{i}", f"dep_{i}", "root") for i in range(10)]
    graph = DummyGraph(nodes, edges)

    radius, _ = calculate_static_blast_radius(
        seeds=["root"],
        graph=graph,
        max_depth=4,
        max_visited_nodes=3,
    )

    assert radius.cutoff is True
    assert radius.cutoff_reason == "node_budget_exceeded"
    assert radius.lower_bound is True
    assert radius.affected_component_count is not None
    assert radius.affected_component_count <= 4


def test_blast_radius_edge_budget_cutoff() -> None:
    # Many edges
    nodes = [DummyNode("root")] + [DummyNode(f"dep_{i}") for i in range(10)]
    edges = [DummyEdge(f"e_{i}", f"dep_{i}", "root") for i in range(10)]
    graph = DummyGraph(nodes, edges)

    radius, _ = calculate_static_blast_radius(
        seeds=["root"],
        graph=graph,
        max_depth=4,
        max_visited_edges=2,
    )

    assert radius.cutoff is True
    assert radius.cutoff_reason == "edge_budget_exceeded"
    assert radius.lower_bound is True


# ---------------------------------------------------------------------------
# Architectural Boundary Spread & Crossed Boundary Tests
# ---------------------------------------------------------------------------


def test_blast_radius_boundaries_crossed() -> None:
    # A (boundary="core") -> B (boundary="ui") -> C (boundary="db")
    # Edge e_ab: source A, target B. Source boundary = "core", Target boundary = "ui".
    # Edge e_bc: source B, target C. Source boundary = "ui", Target boundary = "db".
    nodes = [DummyNode("A"), DummyNode("B"), DummyNode("C")]
    edges = [
        DummyEdge("e_ab", "A", "B"),
        DummyEdge("e_bc", "B", "C"),
    ]
    graph = DummyGraph(nodes, edges)
    boundaries = {
        "A": "core",
        "B": "ui",
        "C": "db",
    }

    # When C changes, reverse dependents are B and A.
    # Visited edges in bounded subgraph:
    # e_bc (B -> C) source="B" (ui), target="C" (db) -> crossed pair ("ui", "db")
    # e_ab (A -> B) source="A" (core), target="B" (ui) -> crossed pair ("core", "ui")
    radius, summary = calculate_static_blast_radius(
        seeds=["C"],
        graph=graph,
        boundaries=boundaries,
        boundary_dimension="layer",
    )

    assert radius.boundary_spread_count == 1
    assert radius.crossed_boundary_count == 2
    assert "core -> ui" in radius.crossed_boundary_pairs
    assert "ui -> db" in radius.crossed_boundary_pairs
    assert summary.crossed_boundary_count == 2
    assert summary.boundary_spread_count == 1


def test_blast_radius_repeated_edges_same_boundary_pair() -> None:
    # A1 (core) -> B (ui), A2 (core) -> B (ui)
    # Both cross ("core", "ui"). Crossed boundary count should be 1, deduplicated!
    nodes = [DummyNode("A1"), DummyNode("A2"), DummyNode("B")]
    edges = [
        DummyEdge("e1", "A1", "B"),
        DummyEdge("e2", "A2", "B"),
    ]
    graph = DummyGraph(nodes, edges)
    boundaries = {"A1": "core", "A2": "core", "B": "ui"}

    radius, _ = calculate_static_blast_radius(
        seeds=["B"],
        graph=graph,
        boundaries=boundaries,
    )

    assert radius.crossed_boundary_count == 1
    assert radius.crossed_boundary_pairs == ["core -> ui"]
    # Both edge witnesses recorded under the pair key
    assert len(radius.edge_witnesses.get("core -> ui", [])) == 2


def test_blast_radius_missing_boundary_evidence_unknown() -> None:
    # Unmapped files > 0 or missing boundary mapping
    nodes = [DummyNode("A"), DummyNode("B")]
    edges = [DummyEdge("e1", "A", "B")]
    graph = DummyGraph(nodes, edges)

    # Node A is in boundary "core", but B is unmapped
    boundaries = {"A": "core"}

    radius, summary = calculate_static_blast_radius(
        seeds=["B"],
        graph=graph,
        boundaries=boundaries,
        unmapped_files=1,
    )

    # Missing boundary evidence cannot be claimed as exact 0
    assert summary.boundary_spread_status.value.lower() == "unknown"


# ---------------------------------------------------------------------------
# Test Association Tests (E08.2)
# ---------------------------------------------------------------------------


def test_blast_radius_test_associations_complete() -> None:
    nodes = [DummyNode("comp1"), DummyNode("comp2")]
    edges = [DummyEdge("e1", "comp2", "comp1")]
    graph = DummyGraph(nodes, edges)

    test_assoc = {
        "comp1": ["test_comp1_a", "test_comp1_b"],
        "comp2": ["test_comp2"],
    }

    radius, _ = calculate_static_blast_radius(
        seeds=["comp1"],
        graph=graph,
        test_associations=test_assoc,
        test_evidence_complete=True,
    )

    assert radius.affected_test_count == 3
    assert set(radius.affected_test_ids) == {"test_comp1_a", "test_comp1_b", "test_comp2"}
    assert radius.test_coverage_status == "pass"


def test_blast_radius_test_associations_exact_zero() -> None:
    nodes = [DummyNode("comp1")]
    edges: list[DummyEdge] = []
    graph = DummyGraph(nodes, edges)

    radius, _ = calculate_static_blast_radius(
        seeds=["comp1"],
        graph=graph,
        test_associations={},
        test_evidence_complete=True,
    )

    assert radius.affected_test_count == 0
    assert radius.affected_test_ids == []
    assert radius.test_coverage_status == "pass"


def test_blast_radius_test_associations_incomplete_unknown() -> None:
    nodes = [DummyNode("comp1")]
    edges: list[DummyEdge] = []
    graph = DummyGraph(nodes, edges)

    radius, _ = calculate_static_blast_radius(
        seeds=["comp1"],
        graph=graph,
        test_associations=None,
        test_evidence_complete=False,
    )

    assert radius.affected_test_count is None
    assert radius.test_coverage_status == "unknown"


def test_blast_radius_with_association_metric_model() -> None:
    record_a = AssociationRecord(
        association_id="rec_a",
        production_path="src/a.py",
        test_path="tests/test_a.py",
        method=AssociationMethod.IMPORT_REFERENCE,
        confidence=AssociationConfidence.HIGH,
        witness="import test_a",
        formula_version="v1",
    )
    record_b = AssociationRecord(
        association_id="rec_b",
        production_path="src/b.py",
        test_path="tests/test_b.py",
        method=AssociationMethod.NAMING_CONVENTION,
        confidence=AssociationConfidence.MEDIUM,
        witness="naming",
        formula_version="v1",
    )
    metric = AssociationMetric(
        status=MetricStatusName.VALUE,
        full_scope_status=CoverageScope.COMPLETE,
        reason="measured",
        formula_version="v1",
        associations=(record_a, record_b),
    )

    nodes = [DummyNode("src/a.py")]
    graph = DummyGraph(nodes, [])

    radius, _ = calculate_static_blast_radius(
        seeds=["src/a.py"],
        graph=graph,
        test_associations=metric,
        test_evidence_complete=True,
    )

    assert radius.affected_test_ids == ["tests/test_a.py"]
    assert radius.affected_test_count == 1
    assert radius.test_coverage_status == "pass"


# ---------------------------------------------------------------------------
# M29 Change Concerns Tests
# ---------------------------------------------------------------------------


def test_nearest_rank_p90_computation() -> None:
    # 10 values: 10, 20, 30, 40, 50, 60, 70, 80, 90, 100
    # nearest-rank p90: rank = ceil(0.9 * 10) = 9. 9th value is 90.
    values = [x for x in range(10, 110, 10)]
    p90 = nearest_rank_percentile(values, 0.9)
    assert p90.value == Decimal("90")


def test_m29_predicates() -> None:
    p90_churn = 50
    assert m29_high_churn(51, p90_churn) is True
    assert m29_high_churn(50, p90_churn) is False
    assert m29_high_churn(0, p90_churn) is False

    p90_cent = Decimal("0.8")
    assert m29_high_centrality(Decimal("0.85"), p90_cent) is True
    assert m29_high_centrality(Decimal("0.8"), p90_cent) is False

    assert m29_concern_class(high_churn=True, high_centrality=True) == "high_churn_and_centrality"
    assert m29_concern_class(high_churn=True, high_centrality=False) == "high_churn"
    assert m29_concern_class(high_churn=False, high_centrality=True) == "high_centrality"
    assert m29_concern_class(high_churn=False, high_centrality=False) == "ordinary"


def test_evaluate_change_concerns_ranking_and_deleted() -> None:
    changed_subjects = ["c_both", "c_churn", "c_cent", "c_ordinary", "c_deleted"]

    # Churn measures: 20 universe subjects with churn 10 to 200 (p90 = 200).
    churn_universe = {
        f"sub_{i}": i * 10 for i in range(1, 21)
    }
    churn_universe["c_both"] = 250
    churn_universe["c_churn"] = 250
    churn_universe["c_cent"] = 10
    churn_universe["c_ordinary"] = 5

    base_churn = {"c_deleted": 250}

    # Centrality universe: 20 subjects from 0.05 to 0.95 (p90 = 0.95).
    centrality_universe = {
        f"sub_{i}": Decimal(str(i * 5)) / Decimal("100") for i in range(1, 20)
    }
    centrality_universe["c_both"] = Decimal("0.98")
    centrality_universe["c_churn"] = Decimal("0.1")
    centrality_universe["c_cent"] = Decimal("0.98")
    centrality_universe["c_ordinary"] = Decimal("0.05")

    base_centrality = {"c_deleted": Decimal("0.05")}

    concerns = evaluate_change_concerns(
        changed_subjects=changed_subjects,
        churn_by_component=churn_universe,
        centrality_by_component=centrality_universe,
        base_churn_by_component=base_churn,
        base_centrality_by_component=base_centrality,
        deleted_subjects=["c_deleted"],
    )

    # Check ordering:
    # 1. both (c_both)
    # 2. churn-only (c_churn, c_deleted) - sorted by lines changed, then id
    # 3. centrality-only (c_cent)
    # 4. ordinary (c_ordinary)
    classes = [c.concern_class for c in concerns]
    ids = [c.subject_id for c in concerns]

    assert ids[0] == "c_both"
    assert classes[0] == "high_churn_and_centrality"

    assert "c_churn" in ids[1:3]
    assert "c_deleted" in ids[1:3]
    assert all(c.concern_class == "high_churn" for c in concerns[1:3])

    deleted_concern = next(c for c in concerns if c.subject_id == "c_deleted")
    assert deleted_concern.deleted is True

    assert ids[3] == "c_cent"
    assert classes[3] == "high_centrality"

    assert ids[4] == "c_ordinary"
    assert classes[4] == "ordinary"


def test_evaluate_change_concerns_unchanged_hotspot_excluded() -> None:
    # A component that has high churn and high centrality, but was NOT changed,
    # should NOT be present in change concerns!
    churn = {"hotspot": 1000, "mod": 5}
    centrality = {"hotspot": Decimal("0.99"), "mod": Decimal("0.1")}

    concerns = evaluate_change_concerns(
        changed_subjects=["mod"],
        churn_by_component=churn,
        centrality_by_component=centrality,
    )

    assert len(concerns) == 1
    assert concerns[0].subject_id == "mod"
    assert "hotspot" not in [c.subject_id for c in concerns]


def test_evaluate_change_concerns_missing_history_and_centrality() -> None:
    concerns = evaluate_change_concerns(
        changed_subjects=["mod"],
        churn_by_component={"mod": 100},
        centrality_by_component={"mod": Decimal("0.9")},
        has_history=False,
        has_centrality=False,
    )
    assert len(concerns) == 1
    assert concerns[0].partial_contributors is True
    assert "missing_history_window" in concerns[0].reasons
    assert "missing_centrality_evidence" in concerns[0].reasons


def test_graph_delta_with_file_mapping_and_metadata() -> None:
    class GraphWithMeta:
        def __init__(self, g_id: str, nodes: list[DummyNode]) -> None:
            self.metadata = type("Meta", (), {"graph_id": g_id})()
            self.nodes = nodes
            self.edges: list[DummyEdge] = []

    base = GraphWithMeta("base-graph-1", [DummyNode("comp_a")])
    cand = GraphWithMeta("cand-graph-1", [DummyNode("comp_a"), DummyNode("comp_b")])

    delta = calculate_graph_delta(
        base_graph=base,
        candidate_graph=cand,
        changed_files=["src/comp_b.py"],
        file_to_component={"src/comp_b.py": "comp_b"},
    )

    assert delta.graph_ids == {"base": "base-graph-1", "candidate": "cand-graph-1"}
    assert "comp_b" in delta.changed_seeds


def test_blast_radius_with_changed_files_mapping() -> None:
    nodes = [DummyNode("comp_a")]
    graph = DummyGraph(nodes, [])

    radius, summary = calculate_static_blast_radius(
        seeds=["comp_a"],
        graph=graph,
        changed_files=["src/comp_a.py"],
        unmapped_files=0,
    )

    assert summary.changed_file_count == 1
    assert summary.mapping_coverage == "1.000000"
    assert summary.mapping_coverage_status.value == "pass"


def test_series_pair_blast_radius_binds_m27_seeds_and_preserves_cutoff() -> None:
    s1 = DummyGraph([DummyNode("src/app.js")], [])
    s2 = DummyGraph([DummyNode("src/app.js")], [])
    s5 = DummyGraph(
        [DummyNode("src/app.js"), DummyNode("src/later.js")],
        [DummyEdge("e-later", "src/later.js", "src/app.js")],
    )
    adjacent = calculate_graph_delta(
        s1,
        s2,
        changed_files=["src/app.js"],
    )
    span = calculate_graph_delta(
        s1,
        s5,
        changed_files=["src/app.js", "src/later.js"],
    )
    assert "src/later.js" not in adjacent.added_nodes
    assert "src/later.js" not in adjacent.changed_seeds
    assert "src/later.js" in span.added_nodes
    cutoff, _ = calculate_static_blast_radius(
        seeds=["F"],
        graph=DummyGraph(
            [DummyNode(name) for name in "ABCDEF"],
            [
                DummyEdge("e1", "A", "B"),
                DummyEdge("e2", "B", "C"),
                DummyEdge("e3", "C", "D"),
                DummyEdge("e4", "D", "E"),
                DummyEdge("e5", "E", "F"),
            ],
        ),
        max_depth=2,
        changed_files=["src/app.js"],
    )
    assert cutoff.cutoff is True
    assert cutoff.lower_bound is True
    assert cutoff.cutoff_reason == "depth_bound_truncated"
    assert cutoff.affected_component_count is not None

