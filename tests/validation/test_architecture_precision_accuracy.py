"""Slice 4.5 — Architecture precision expectation model, metrics, and fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from codestrata.application.rules.architecture.view_builder import (
    build_architecture_analysis_view,
    find_directed_cycles,
)
from validation.actual import load_emitted_assessment, run_real_assessment
from validation.architecture import (
    ArchitectureCycleExpectation,
    ArchitectureEdgeExpectation,
    ArchitectureExpectation,
    ArchitectureFindingActual,
    ArchitectureFindingExpectation,
    ArchitectureGraphActual,
    aggregate_architecture_results,
    canonicalize_cycle,
    extract_architecture_findings,
    validate_architecture_precision,
)
from validation.inventory import FactClassification, compute_precision_recall
from validation.models import ExpectedResults, ValidationVerdict
from validation.paths import VALIDATION_ROOT
from validation.registry import load_all_repositories, resolve_expected_results
from validation.runner import run_validation_suite
from validation.summary import build_validation_summary


def test_contradictory_architecture_expectations_rejected() -> None:
    with pytest.raises(ValidationError, match="contradictory"):
        ArchitectureExpectation(
            expected_rule_ids=("architecture.dependency-cycle",),
            forbidden_rule_ids=("architecture.dependency-cycle",),
        )
    with pytest.raises(ValidationError, match="contradictory"):
        ArchitectureExpectation(
            required_edges=(ArchitectureEdgeExpectation(source="a", target="b"),),
            forbidden_edges=(ArchitectureEdgeExpectation(source="a", target="b"),),
        )
    with pytest.raises(ValidationError, match="contradictory"):
        ExpectedResults(
            architecture=ArchitectureExpectation(
                required_findings=(
                    ArchitectureFindingExpectation(rule_id="architecture.framework-leakage"),
                ),
                forbidden_rule_ids=("architecture.framework-leakage",),
            )
        )


def test_cycle_rotation_invariance() -> None:
    assert canonicalize_cycle(("a", "b", "c", "a")) == canonicalize_cycle(("b", "c", "a", "b"))
    assert canonicalize_cycle(("c", "a", "b")) == canonicalize_cycle(("a", "b", "c"))


def test_classify_tp_fp_fn_ambiguous_and_metrics() -> None:
    expectation = ArchitectureExpectation(
        required_findings=(
            ArchitectureFindingExpectation(
                rule_id="architecture.framework-leakage",
                path_pattern="model/",
            ),
            ArchitectureFindingExpectation(
                rule_id="architecture.dependency-cycle",
            ),
        ),
        forbidden_rule_ids=("architecture.layer-boundary-violation",),
        allowed_findings=(
            ArchitectureFindingExpectation(rule_id="ARCH001"),
        ),
        forbidden_unsupported_claims=("microservices",),
    )
    actual = (
        ArchitectureFindingActual(
            rule_id="architecture.framework-leakage",
            path="src/main/java/org/example/model/Person.java",
            evidence_ids=("e1",),
        ),
        ArchitectureFindingActual(
            rule_id="architecture.layer-boundary-violation",
            path="src/controller/Ui.java",
            evidence_ids=("e2",),
        ),
        ArchitectureFindingActual(
            rule_id="ARCH001",
            path=".",
            evidence_ids=("e3",),
        ),
    )
    result = validate_architecture_precision(
        repository_id="fixture",
        expectation=expectation,
        actual_findings=actual,
        artifact_texts={"report.json": "safe disclaimer only"},
    )
    by_rule = {item.rule_id: item.classification for item in result.classifications}
    assert by_rule["architecture.framework-leakage"] is FactClassification.TRUE_POSITIVE
    assert by_rule["architecture.dependency-cycle"] is FactClassification.FALSE_NEGATIVE
    assert by_rule["architecture.layer-boundary-violation"] is FactClassification.FALSE_POSITIVE
    assert by_rule["ARCH001"] is FactClassification.AMBIGUOUS
    assert result.precision == pytest.approx(0.5)
    assert result.recall == pytest.approx(0.5)
    assert result.passed is False


def test_precision_recall_zero_denominator_unavailable() -> None:
    precision, recall, reason = compute_precision_recall(
        true_positives=0,
        false_positives=0,
        false_negatives=0,
    )
    assert precision is None
    assert recall is None
    assert reason is not None


def test_aggregate_architecture_metrics_deterministic_order() -> None:
    expectation = ArchitectureExpectation(
        required_findings=(
            ArchitectureFindingExpectation(rule_id="architecture.framework-leakage"),
        ),
        maximum_false_positive_count=0,
    )
    actual = (
        ArchitectureFindingActual(
            rule_id="architecture.framework-leakage",
            path="model/Person.java",
            evidence_ids=("e1",),
        ),
    )
    a = validate_architecture_precision(
        repository_id="repo-a",
        expectation=expectation,
        actual_findings=actual,
    )
    b = validate_architecture_precision(
        repository_id="repo-b",
        expectation=expectation,
        actual_findings=actual,
    )
    aggregate = aggregate_architecture_results((b, a))
    assert [item.repository_id for item in aggregate.per_repository] == ["repo-b", "repo-a"]
    assert aggregate.precision == 1.0
    assert aggregate.recall == 1.0


def test_all_repositories_have_architecture_expectations() -> None:
    for definition in load_all_repositories():
        if not definition.enabled:
            continue
        expected = resolve_expected_results(definition)
        assert expected.architecture is not None, definition.repository_id
        assert expected.architecture.evidence_notes, definition.repository_id


def test_controlled_architecture_fixture_precision(tmp_path: Path) -> None:
    fixture = (VALIDATION_ROOT / "fixtures" / "architecture-signals").resolve()
    config = VALIDATION_ROOT / "configs" / "local-architecture-signals.toml"
    texts = {
        str(path.relative_to(fixture)).replace("\\", "/"): path.read_text(encoding="utf-8")
        for path in fixture.rglob("*.java")
    }
    view = build_architecture_analysis_view(
        relative_paths=sorted(texts),
        file_texts=texts,
    )
    cycles = find_directed_cycles(view.adjacency())
    assert cycles
    assert all(not _is_test_path(path) for edge in view.included_edges() for path in edge.evidence_paths)

    actual, _ = run_real_assessment(
        repository_path=fixture,
        output_directory=tmp_path / "out",
        config_path=config,
    )
    rule_ids = {item.rule_id for item in actual.architecture_findings}
    assert "architecture.dependency-cycle" in rule_ids
    assert "architecture.layer-boundary-violation" in rule_ids
    assert not any(
        item.path and "src/test/" in item.path.replace("\\", "/")
        and item.rule_id.startswith("architecture.")
        and item.rule_id
        in {
            "architecture.dependency-cycle",
            "architecture.layer-boundary-violation",
            "architecture.invalid-dependency-direction",
        }
        and "TestOnlyImport" in (item.path or "")
        for item in actual.architecture_findings
    )

    expectation = ArchitectureExpectation(
        required_findings=(
            ArchitectureFindingExpectation(
                rule_id="architecture.dependency-cycle",
                expected_count=1,
                rationale="Intentional domain↔application cycle",
            ),
            ArchitectureFindingExpectation(
                rule_id="architecture.layer-boundary-violation",
                path_pattern="controller/",
                expected_count=1,
                rationale="Intentional presentation→persistence skip",
            ),
        ),
        allowed_findings=(
            ArchitectureFindingExpectation(
                rule_id="architecture.invalid-dependency-direction",
                rationale="Cycle and boundary edges also violate direction; allowed overlap",
            ),
            ArchitectureFindingExpectation(
                rule_id="architecture.component-concentration",
                rationale="Small fixture may concentrate edges; ambiguous",
            ),
            ArchitectureFindingExpectation(rule_id="ARCH001", rationale="legacy"),
            ArchitectureFindingExpectation(rule_id="ARCH002", rationale="legacy"),
            ArchitectureFindingExpectation(rule_id="ARCH003", rationale="legacy"),
            ArchitectureFindingExpectation(rule_id="ARCH005", rationale="legacy"),
            ArchitectureFindingExpectation(rule_id="ARCH007", rationale="legacy"),
        ),
        forbidden_rule_ids=("architecture.framework-leakage",),
        expected_cycles=(
            ArchitectureCycleExpectation(
                nodes=("com.example.application", "com.example.domain"),
                rationale="Canonical cycle from fixture",
            ),
        ),
        maximum_false_positive_count=0,
        evidence_notes="Controlled architecture-signals fixture",
    )
    # Score findings only (graph cycles come from view, not report sample).
    result = validate_architecture_precision(
        repository_id="architecture-signals",
        expectation=expectation.model_copy(update={"expected_cycles": ()}),
        actual_findings=actual.architecture_findings,
        graph=ArchitectureGraphActual(
            nodes=tuple(unit.unit_id for unit in view.units),
            edges=tuple(
                f"{edge.source_unit_id}->{edge.target_unit_id}"
                for edge in view.included_edges()
            ),
            cycles=tuple(canonicalize_cycle(cycle) for cycle in cycles),
        ),
    )
    assert result.false_positives == 0, result.diagnostics
    assert result.false_negatives == 0, result.diagnostics
    assert result.passed

    for item in actual.architecture_findings:
        if item.rule_id.startswith("architecture."):
            assert item.finding_id
            assert item.path is None or not item.path.startswith("/")
            assert item.evidence_ids


def test_negative_control_repositories_architecture_precision(tmp_path_factory) -> None:
    definitions = [
        item
        for item in load_all_repositories()
        if item.repository_id
        in {
            "local-sample-js",
            "local-sample-python",
            "local-cloud-signals",
            "local-security-hygiene",
            "local-ai-readiness",
        }
    ]
    output_root = tmp_path_factory.mktemp("architecture-neg")
    results = run_validation_suite(
        definitions,
        output_root=output_root,
        records_root=output_root / "_records",
        keep_results=True,
        local_only=True,
        include_remote=False,
    )
    summary = build_validation_summary(results)
    assert summary.failed == 0
    assert summary.errors == 0

    architecture_results = []
    for definition, run in zip(definitions, results, strict=True):
        assert run.verdict == ValidationVerdict.PASS
        expected = resolve_expected_results(definition)
        assert expected.architecture is not None
        report, document = load_emitted_assessment(run.artifact_dir)
        findings = extract_architecture_findings(
            (document.get("assessment") or {}).get("findings") or []
        )
        for forbidden in expected.architecture.forbidden_rule_ids:
            assert forbidden not in {item.rule_id for item in findings}
        result = validate_architecture_precision(
            repository_id=definition.repository_id,
            expectation=expected.architecture,
            actual_findings=findings,
            artifact_texts={report.name: json.dumps(document)},
        )
        assert result.false_positives == 0, result.diagnostics
        assert result.passed
        architecture_results.append(result)

    aggregate = aggregate_architecture_results(architecture_results)
    assert aggregate.false_positives == 0


def test_architecture_fixture_repeat_run_determinism(tmp_path: Path) -> None:
    fixture = (VALIDATION_ROOT / "fixtures" / "architecture-signals").resolve()
    config = VALIDATION_ROOT / "configs" / "local-architecture-signals.toml"
    first, _ = run_real_assessment(
        repository_path=fixture,
        output_directory=tmp_path / "a",
        config_path=config,
    )
    second, _ = run_real_assessment(
        repository_path=fixture,
        output_directory=tmp_path / "b",
        config_path=config,
    )
    assert sorted(item.finding_id or "" for item in first.architecture_findings) == sorted(
        item.finding_id or "" for item in second.architecture_findings
    )


def _is_test_path(path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    return any(marker in lowered for marker in ("/test/", "/tests/", "/src/test/"))
