"""Independent M06–M09 fixtures for boundary, concentration and reach."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from codestrata.domain.contracts.formulas import m09_centrality
from codestrata.domain.repository_graph.metrics import (
    BoundaryEdge,
    BoundaryPattern,
    ModuleEdge,
    ReachQuery,
    SourceLineFile,
    boundary_pattern_match,
    count_nonblank_noncomment_lines,
    m06_module_coupling,
    m07_boundary_violations,
    m08_component_concentration,
    m09_reach,
    m09_structural_centrality,
)
from codestrata.domain.rules.operators.graph import _glob_match

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "e07.2" / "expected-outcomes.json"
EXPECTED = json.loads(FIXTURE.read_text(encoding="utf-8"))

BUNDLED = BoundaryPattern(
    constraint_id="forbid:api->internal",
    source_pattern="api",
    target_pattern="internal",
    allowed_directions=("api>api", "api>public"),
)


def _edge(source: str, target: str, *, unknown: bool = False) -> ModuleEdge:
    return ModuleEdge(source=source, target=target, edge_type="imports", unknown=unknown)


def _boundary(
    source: str,
    target: str,
    *,
    unknown: bool = False,
    path: str | None = None,
) -> BoundaryEdge:
    return BoundaryEdge(
        source=source,
        target=target,
        unknown=unknown,
        evidence_path=path,
    )


def _source(path: str, component: str, lines: int, **overrides: object) -> SourceLineFile:
    payload: dict[str, object] = {
        "relative_path": path,
        "component_id": component,
        "source_text": "\n".join(["value"] * lines + ["", "# note"]),
    }
    payload.update(overrides)
    return SourceLineFile.model_validate(payload)


def test_pattern_match_tracks_boundary_operator() -> None:
    samples = (
        ("api", "api"),
        ("api", "public"),
        ("api/*", "api/a"),
        ("api/*", "api/a/b"),
        ("api/**", "api/a/b"),
        ("internal", "internal"),
    )
    for pattern, value in samples:
        assert boundary_pattern_match(pattern, value) is _glob_match(pattern, value)


def test_m06_ratio_uses_file_import_edges_by_component() -> None:
    expected = EXPECTED["m06"]["file_component_ratio"]
    metric = m06_module_coupling(
        ("mod.a", "mod.b"),
        (_edge("mod.a", "mod.b"),),
        file_import_edges=(
            ("file:a1", "file:a2", "comp.a", "comp.a"),
            ("file:a1", "file:b1", "comp.a", "comp.b"),
        ),
        complete=True,
    )
    ratio = metric.external_edge_ratio
    assert ratio.numerator == expected["numerator"]
    assert ratio.denominator == expected["denominator"]
    assert ratio.serialized == expected["serialized"]
    assert metric.max_fan_out.value == expected["max_fan_out"]
    same_component = 1
    assert ratio.denominator == ratio.numerator + same_component


def test_m07_api_internal_counts_unique_path_and_ignores_parallel() -> None:
    expected = EXPECTED["m07"]
    violating = m07_boundary_violations(
        (
            _boundary("api", "internal", path="src/api/mod.py"),
            _boundary("api", "internal", path="src/api/mod.py"),
        ),
        pattern=BUNDLED,
        complete=True,
    )
    assert violating.count == expected["parallel"]["count"]
    assert violating.violations[0].identity == expected["api_internal"]["identity"]
    assert violating.violations[0].evidence_path == expected["api_internal"]["path"]


def test_m07_api_public_passes_and_persistence_is_not_invented() -> None:
    expected = EXPECTED["m07"]
    public = m07_boundary_violations(
        (_boundary("api", "public", path="src/api/mod.py"),),
        pattern=BUNDLED,
        complete=True,
    )
    persistence = m07_boundary_violations(
        (_boundary("api", "persistence", path="src/api/mod.py"),),
        pattern=BUNDLED,
        complete=True,
    )
    assert public.count == expected["api_public"]["count"]
    assert public.computation.status.value == expected["api_public"]["status"]
    assert persistence.count == expected["persistence"]["count"]
    assert persistence.computation.status.value == expected["persistence"]["status"]


def test_m07_unresolved_relevant_edge_is_unknown_and_missing_pattern_is_na() -> None:
    expected = EXPECTED["m07"]
    unresolved = m07_boundary_violations(
        (_boundary("api", "internal", unknown=True),),
        pattern=BUNDLED,
        complete=True,
    )
    absent = m07_boundary_violations(
        (_boundary("api", "internal", path="src/api/mod.py"),),
        pattern=None,
        complete=True,
    )
    assert unresolved.computation.status.value == expected["unresolved"]["status"]
    assert unresolved.count == 0
    assert absent.computation.status.value == expected["no_pattern"]["status"]
    assert absent.computation.reason == "no_declared_pattern"


def test_line_count_skips_blank_and_full_line_comments() -> None:
    text = "\n".join(["value", "", "# note", "// note", "  value"])
    assert count_nonblank_noncomment_lines(text, ("#", "//")) == 2


def test_m08_share_boundaries_single_component_and_exclusions() -> None:
    expected = EXPECTED["m08"]
    at_60 = m08_component_concentration(
        (
            _source("src/component-a.py", "component.a", 60),
            _source("src/component-b.py", "component.b", 40),
        )
    )
    at_61 = m08_component_concentration(
        (
            _source("src/component-a.py", "component.a", 61),
            _source("src/component-b.py", "component.b", 39),
        )
    )
    single = m08_component_concentration((_source("src/only.py", "component.a", 100),))
    generated = m08_component_concentration(
        (
            _source("src/component-a.py", "component.a", 61),
            _source("src/component-b.py", "component.b", 39),
            _source("gen/out.py", "component.a", 1000, generated=True),
        )
    )
    assert at_60.max_share.status.value == expected["share_60"]["status"]
    assert at_60.max_share.numerator == expected["share_60"]["numerator"]
    assert at_60.max_share.denominator == expected["share_60"]["denominator"]
    assert at_60.max_share.serialized == expected["share_60"]["serialized"]
    assert at_60.full_repo_valid is True
    assert at_61.max_share.serialized == expected["share_61"]["serialized"]
    assert at_61.max_share.extra["witness_path"] == expected["share_61"]["witness_path"]
    assert single.max_share.status.value == expected["single"]["status"]
    assert generated.max_share.denominator == expected["generated"]["denominator"]
    assert generated.generated_excluded == expected["generated"]["generated_excluded"]
    assert generated.max_share.serialized == expected["generated"]["serialized"]


def test_m08_unmapped_and_unreadable_keep_observed_partial_share() -> None:
    expected = EXPECTED["m08"]
    unmapped = m08_component_concentration(
        (
            _source("src/component-a.py", "component.a", 30),
            _source("src/component-b.py", "component.b", 30),
            _source("src/loose.py", "", 40),
        )
    )
    unreadable = m08_component_concentration(
        (
            _source("src/component-a.py", "component.a", 60),
            _source("src/component-b.py", "component.b", 40),
            _source("src/locked.py", "component.c", 500, readable=False),
        )
    )
    assert unmapped.max_share.status.value == expected["unmapped"]["status"]
    assert unmapped.max_share.serialized == expected["unmapped"]["serialized"]
    assert unmapped.max_share.numerator == expected["unmapped"]["numerator"]
    assert unmapped.max_share.denominator == expected["unmapped"]["denominator"]
    assert unmapped.full_repo_valid is False
    assert unreadable.max_share.status.value == expected["unreadable"]["status"]
    assert unreadable.max_share.serialized == expected["unreadable"]["serialized"]
    assert unreadable.unreadable_files == 1


def test_m09_centrality_excludes_seed_and_collapses_parallel_edges() -> None:
    expected = EXPECTED["m09"]
    singleton = m09_structural_centrality("a", ("a",), (), dependency_view="resolved")
    self_loop = m09_structural_centrality(
        "a",
        ("a",),
        (_edge("a", "a"),),
        dependency_view="resolved",
    )
    two_node = m09_structural_centrality(
        "a",
        ("a", "b"),
        (_edge("a", "a"), _edge("b", "a")),
        dependency_view="resolved",
    )
    parallel = m09_structural_centrality(
        "a",
        ("a", "b"),
        (_edge("b", "a"), _edge("b", "a")),
        dependency_view="resolved",
    )
    partial = m09_structural_centrality(
        "a",
        ("a", "b"),
        (_edge("b", "a"),),
        dependency_view="resolved",
        partial_universe=True,
    )
    outside = m09_structural_centrality("c", ("a", "b"), (), dependency_view="resolved")
    formula = m09_centrality("a", ("a", "b"), ("a", "b", "b"))
    assert singleton.computation.serialized == expected["singleton"]["serialized"]
    assert singleton.computation.denominator == expected["singleton"]["denominator"]
    assert self_loop.computation.numerator == expected["self_loop"]["numerator"]
    assert two_node.computation.numerator == expected["two_node"]["numerator"]
    assert two_node.computation.serialized == expected["two_node"]["serialized"]
    assert two_node.computation.numerator == formula.numerator
    assert parallel.computation.numerator == expected["parallel"]["numerator"]
    assert partial.computation.status.value == expected["partial_universe"]["status"]
    assert partial.computation.numerator == expected["partial_universe"]["lower_bound"]
    assert partial.computation.reason == expected["partial_universe"]["reason"]
    assert outside.computation.reason == "node_outside_universe"


def test_m09_reach_dedupes_cycles_and_discloses_cutoff() -> None:
    expected = EXPECTED["m09"]
    diamond = m09_reach(
        (
            _edge("a", "b"),
            _edge("a", "c"),
            _edge("b", "d"),
            _edge("c", "d"),
            _edge("c", "d"),
        ),
        ReachQuery(
            seed="a",
            universe=("a", "b", "c", "d"),
            dependency_view="resolved",
            traversal="transitive",
            max_depth=3,
        ),
    )
    cycle = m09_reach(
        (_edge("a", "b"), _edge("b", "a"), _edge("a", "a")),
        ReachQuery(
            seed="a",
            universe=("a", "b"),
            dependency_view="resolved",
            traversal="transitive",
            max_depth=5,
        ),
    )
    disconnected = m09_reach(
        (_edge("a", "b"),),
        ReachQuery(
            seed="a",
            universe=("a", "b", "c"),
            dependency_view="resolved",
            traversal="transitive",
            max_depth=4,
        ),
    )
    cutoff = m09_reach(
        (_edge("a", "b"), _edge("b", "c")),
        ReachQuery(
            seed="a",
            universe=("a", "b", "c"),
            dependency_view="resolved",
            traversal="direct",
            max_depth=1,
        ),
    )
    assert list(diamond.reached) == expected["diamond"]["reached"]
    assert diamond.computation.serialized == expected["diamond"]["serialized"]
    assert diamond.cutoff is expected["diamond"]["cutoff"]
    assert "a" not in diamond.reached
    assert list(cycle.reached) == expected["cycle"]["reached"]
    assert cycle.cutoff is expected["cycle"]["cutoff"]
    assert "a" not in cycle.reached
    assert list(disconnected.reached) == expected["disconnected"]["reached"]
    assert expected["disconnected"]["absent"] not in disconnected.reached
    assert list(cutoff.reached) == expected["cutoff"]["reached"]
    assert cutoff.cutoff is expected["cutoff"]["cutoff"]
    assert cutoff.computation.status.value == expected["cutoff"]["status"]
    assert cutoff.computation.reason == expected["cutoff"]["reason"]
    assert cutoff.computation.numerator == expected["cutoff"]["lower_bound"]
    assert cutoff.computation.extra["truncated"] is True


def test_m09_view_and_traversal_are_independent() -> None:
    expected = EXPECTED["m09"]
    declared = m09_reach(
        (_edge("a", "b"),),
        ReachQuery(
            seed="a",
            universe=("a", "b", "c"),
            dependency_view="declared",
            traversal="direct",
            max_depth=1,
        ),
    )
    resolved = m09_reach(
        (_edge("a", "c"),),
        ReachQuery(
            seed="a",
            universe=("a", "b", "c"),
            dependency_view="resolved",
            traversal="transitive",
            max_depth=2,
        ),
    )
    incoming = m09_reach(
        (_edge("b", "a"),),
        ReachQuery(
            seed="a",
            universe=("a", "b"),
            dependency_view="resolved",
            traversal="direct",
            max_depth=1,
            direction="incoming",
        ),
    )
    assert declared.dependency_view == expected["declared_direct"]["dependency_view"]
    assert declared.traversal == expected["declared_direct"]["traversal"]
    assert list(declared.reached) == expected["declared_direct"]["reached"]
    assert resolved.dependency_view == expected["resolved_transitive"]["dependency_view"]
    assert resolved.traversal == expected["resolved_transitive"]["traversal"]
    assert list(resolved.reached) == expected["resolved_transitive"]["reached"]
    assert declared.traversal != resolved.traversal
    assert declared.dependency_view != resolved.dependency_view
    assert list(incoming.reached) == ["b"]


def test_direct_reach_rejects_depth_above_one() -> None:
    with pytest.raises(ValidationError):
        ReachQuery(
            seed="a",
            universe=("a",),
            dependency_view="declared",
            traversal="direct",
            max_depth=2,
        )
