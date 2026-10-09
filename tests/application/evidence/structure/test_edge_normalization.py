"""Normalize structural observations into operator graphs and M05/M06 metrics."""

from __future__ import annotations

from codestrata.application.evidence.structure import (
    FileImportObservation,
    StructuralNormalizationRequest,
    normalize_structural_edges,
)
from codestrata.domain.contracts.enums import MetricStatus
from codestrata.domain.repository_graph.enums import RepositoryNodeType
from codestrata.domain.repository_graph.structural import (
    StructuralConfidence,
    StructuralDropReason,
    StructuralEdgeObservation,
    StructuralView,
)


def _import(source: str, target: str, **overrides: object) -> StructuralEdgeObservation:
    payload: dict[str, object] = {
        "edge_type": "imports",
        "source_id": source,
        "target_id": target,
        "source_type": RepositoryNodeType.MODULE,
        "target_type": RepositoryNodeType.MODULE,
        "confidence": StructuralConfidence.HIGH,
        "view": StructuralView.BOTH,
        "unknown": False,
        "resolved": True,
        "evidence_path": "src/mod.py",
    }
    payload.update(overrides)
    return StructuralEdgeObservation.model_validate(payload)


def test_unresolved_and_partial_roots_keep_unknown_edges() -> None:
    evidence = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(
                _import("mod.a", "mod.b"),
                _import("mod.b", "mod.missing", unknown=True, resolved=False),
            ),
            module_ids=("mod.a", "mod.b"),
            missing_source_roots=("vendor/missing",),
        )
    )
    assert evidence.complete is False
    assert "partial_source_roots" in evidence.limitations
    unknown = [edge for edge in evidence.resolved_graph.edges if edge.unknown]
    assert len(unknown) == 1
    assert evidence.resolved_graph.complete is False
    assert evidence.cycles.computation.status is MetricStatus.UNKNOWN


def test_cross_repo_and_runtime_never_enter_the_graph() -> None:
    evidence = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(
                _import("mod.a", "mod.other-repo", cross_repository=True),
                _import("svc.a", "svc.b", runtime_topology=True),
            ),
            module_ids=("mod.a", "svc.a"),
        )
    )
    assert evidence.admitted == ()
    reasons = {item.reason for item in evidence.dropped}
    assert StructuralDropReason.CROSS_REPOSITORY in reasons
    assert StructuralDropReason.RUNTIME_TOPOLOGY in reasons


def test_reordered_observations_same_digest_and_ids() -> None:
    first = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(
                _import("mod.b", "mod.a"),
                _import("mod.a", "mod.b"),
            ),
            module_ids=("mod.a", "mod.b"),
        )
    )
    second = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(
                _import("mod.a", "mod.b"),
                _import("mod.b", "mod.a"),
            ),
            module_ids=("mod.b", "mod.a"),
        )
    )
    assert first.facts_digest == second.facts_digest
    assert [item.relationship_id for item in first.admitted] == [
        item.relationship_id for item in second.admitted
    ]
    assert first.cycles.count == second.cycles.count == 1


def test_file_import_ratio_excludes_unmapped_and_duplicates() -> None:
    evidence = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(),
            module_ids=("mod.a", "mod.b"),
            file_imports=(
                FileImportObservation(
                    source_file_id="file:a",
                    target_file_id="file:b",
                    source_component_id="mod.a",
                    target_component_id="mod.b",
                ),
                FileImportObservation(
                    source_file_id="file:a",
                    target_file_id="file:b",
                    source_component_id="mod.a",
                    target_component_id="mod.b",
                ),
                FileImportObservation(
                    source_file_id="file:a",
                    target_file_id="file:c",
                    source_component_id="mod.a",
                    target_component_id="",
                ),
                FileImportObservation(
                    source_file_id="file:a",
                    target_file_id="file:d",
                    source_component_id="mod.a",
                    target_component_id="mod.a",
                ),
            ),
        )
    )
    assert evidence.coupling.unmapped_excluded == 1
    assert evidence.coupling.external_edge_ratio.numerator == 1
    assert evidence.coupling.external_edge_ratio.denominator == 2


def test_declared_and_resolved_views_stay_independent_and_infer_modules() -> None:
    evidence = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(
                _import("mod.a", "mod.b", view=StructuralView.DECLARED),
                _import("mod.b", "mod.c", view=StructuralView.RESOLVED),
                StructuralEdgeObservation.model_validate(
                    {
                        "edge_type": "calls",
                        "source_id": "fn.a",
                        "target_id": "fn.b",
                        "source_type": RepositoryNodeType.CALLABLE,
                        "target_type": RepositoryNodeType.CALLABLE,
                        "confidence": StructuralConfidence.HIGH,
                        "view": StructuralView.RESOLVED,
                        "unknown": False,
                        "resolved": True,
                        "evidence_path": "src/a.py",
                    }
                ),
                _import(
                    "file.a",
                    "file.b",
                    source_type=RepositoryNodeType.FILE,
                    target_type=RepositoryNodeType.FILE,
                ),
            ),
        )
    )
    declared_pairs = {(edge.source, edge.target) for edge in evidence.declared_graph.edges}
    resolved_pairs = {(edge.source, edge.target) for edge in evidence.resolved_graph.edges}
    assert ("mod.a", "mod.b") in declared_pairs
    assert ("mod.b", "mod.c") not in declared_pairs
    assert ("mod.b", "mod.c") in resolved_pairs
    assert ("mod.a", "mod.b") not in resolved_pairs
    assert evidence.cycles.member_ids == ()
    assert "mod.a" in {item.module_id for item in evidence.coupling.modules}
