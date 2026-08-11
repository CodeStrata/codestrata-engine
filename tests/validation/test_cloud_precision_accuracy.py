"""Slice 4.8 — Cloud Readiness precision expectation model, metrics, and fixture."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from codestrata.application.rules.cloud.helpers import (
    deployment_fact_is_confirmed,
    known_deployment_systems,
)
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_cloud.enums import (
    CloudDeploymentSystem,
    EvidenceConfirmationLevel,
)
from codestrata.domain.evidence.repository_cloud.models import (
    AggregatedRepositoryCloudEvidence,
    CloudDeploymentFactEvidence,
    RepositoryCloudEvidenceCoverage,
)
from codestrata.domain.evidence.repository_cloud.enums import RepositoryCloudParseStatus
from validation.actual import run_real_assessment
from validation.cloud import (
    CloudExpectation,
    CloudFamilyExpectation,
    CloudFindingActual,
    CloudFindingExpectation,
    CloudSignalActual,
    CloudSignalExpectation,
    aggregate_cloud_results,
    extract_cloud_findings,
    extract_cloud_signals,
    validate_cloud_precision,
)
from validation.inventory import FactClassification, compute_precision_recall
from validation.models import ExpectedResults, ValidationVerdict
from validation.paths import VALIDATION_ROOT
from validation.registry import load_all_repositories, resolve_expected_results
from validation.runner import run_validation_suite
from validation.summary import build_validation_summary


def _prov() -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id="test",
        provider_version="1.0.0",
        source_analyzer="test",
        extraction_method="fixture",
    )


def test_contradictory_cloud_expectations_rejected() -> None:
    with pytest.raises(ValidationError, match="contradictory"):
        CloudExpectation(
            expected_rule_ids=("cloud.cloud-010",),
            forbidden_rule_ids=("cloud.cloud-010",),
        )
    with pytest.raises(ValidationError, match="contradictory"):
        CloudExpectation(
            required_signal_families=(CloudFamilyExpectation(family_id="container"),),
            forbidden_signal_families=(CloudFamilyExpectation(family_id="container"),),
        )
    with pytest.raises(ValidationError, match="contradictory"):
        ExpectedResults(
            cloud=CloudExpectation(
                required_findings=(
                    CloudFindingExpectation(rule_id="cloud.cloud-011"),
                ),
                forbidden_rule_ids=("cloud.cloud-011",),
            )
        )


def test_classify_tp_fp_fn_and_metrics() -> None:
    expectation = CloudExpectation(
        required_signal_families=(
            CloudFamilyExpectation(family_id="container"),
        ),
        required_findings=(
            CloudFindingExpectation(rule_id="cloud.cloud-010"),
        ),
        forbidden_rule_ids=("cloud.cloud-030",),
        forbidden_conclusions=("cloud ready",),
    )
    actual_findings = (
        CloudFindingActual(
            rule_id="cloud.cloud-010",
            path="Dockerfile",
            evidence_ids=("e1",),
        ),
        CloudFindingActual(
            rule_id="cloud.cloud-030",
            path="handler.py",
            evidence_ids=("e2",),
        ),
    )
    signals = (
        CloudSignalActual(
            family_id="container",
            signal_kind="docker",
            path="Dockerfile",
            confirmation_level="structurally_confirmed",
        ),
    )
    result = validate_cloud_precision(
        repository_id="fixture",
        expectation=expectation,
        actual_findings=actual_findings,
        actual_signals=signals,
        artifact_texts={"report.json": "Live infrastructure was not assessed."},
    )
    by_name = {item.name: item.classification for item in result.classifications}
    assert by_name["family:container"] is FactClassification.TRUE_POSITIVE
    assert by_name["cloud.cloud-010"] is FactClassification.TRUE_POSITIVE
    assert by_name["cloud.cloud-030"] is FactClassification.FALSE_POSITIVE
    assert result.precision == pytest.approx(2 / 3)
    assert result.recall == pytest.approx(1.0)


def test_precision_recall_zero_denominator_unavailable() -> None:
    precision, recall, reason = compute_precision_recall(
        true_positives=0, false_positives=0, false_negatives=0
    )
    assert precision is None and recall is None and reason is not None


def test_aggregate_deterministic_order() -> None:
    expectation = CloudExpectation(
        required_signal_families=(CloudFamilyExpectation(family_id="container"),)
    )
    signals = (
        CloudSignalActual(
            family_id="container",
            signal_kind="docker",
            path="Dockerfile",
            confirmation_level="structurally_confirmed",
        ),
    )
    a = validate_cloud_precision(
        repository_id="repo-a",
        expectation=expectation,
        actual_findings=(),
        actual_signals=signals,
    )
    b = validate_cloud_precision(
        repository_id="repo-b",
        expectation=expectation,
        actual_findings=(),
        actual_signals=signals,
    )
    aggregate = aggregate_cloud_results((b, a))
    assert [item.repository_id for item in aggregate.per_repository] == ["repo-b", "repo-a"]
    assert aggregate.precision == 1.0


def test_all_repositories_have_cloud_expectations() -> None:
    for definition in load_all_repositories():
        if not definition.enabled:
            continue
        expected = resolve_expected_results(definition)
        assert expected.cloud is not None, definition.repository_id
        assert expected.cloud.evidence_notes, definition.repository_id


def test_build_only_workflow_not_confirmed_deployment() -> None:
    inspected = CloudDeploymentFactEvidence(
        evidence_id="dep:build",
        system=CloudDeploymentSystem.GITHUB_ACTIONS,
        path=".github/workflows/build.yml",
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED,
        provenance=_prov(),
    )
    confirmed = CloudDeploymentFactEvidence(
        evidence_id="dep:deploy",
        system=CloudDeploymentSystem.GITHUB_ACTIONS,
        path=".github/workflows/deploy.yml",
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )
    assert not deployment_fact_is_confirmed(inspected)
    assert deployment_fact_is_confirmed(confirmed)
    evidence = AggregatedRepositoryCloudEvidence(
        repository_id="repo",
        status=RepositoryCloudParseStatus.SUCCEEDED,
        deployment_facts=(inspected, confirmed),
        coverage=RepositoryCloudEvidenceCoverage(),
        evidence_fingerprint="fp",
    )
    systems = known_deployment_systems(evidence)
    assert systems == (CloudDeploymentSystem.GITHUB_ACTIONS,)


def test_controlled_cloud_signals_fixture_precision(tmp_path: Path) -> None:
    fixture = (VALIDATION_ROOT / "fixtures" / "cloud-signals").resolve()
    actual, _ = run_real_assessment(
        repository_path=fixture,
        output_directory=tmp_path / "out",
    )
    rule_ids = {item.rule_id for item in actual.cloud_findings}
    for rule_id in (
        "cloud.cloud-010",
        "cloud.cloud-011",
        "cloud.cloud-040",
        "cloud.cloud-060",
        "cloud.cloud-061",
    ):
        assert rule_id in rule_ids, rule_id
    assert "cloud.cloud-030" not in rule_ids
    assert "cloud.cloud-050" not in rule_ids

    families = {item.family_id for item in actual.cloud_signals}
    assert "container" in families
    assert "orchestration" in families
    assert any(
        item.family_id == "deployment" and item.confirmation_level == "structurally_confirmed"
        for item in actual.cloud_signals
    )
    assert not any(
        item.path and "generic-app.yaml" in item.path and item.family_id == "orchestration"
        for item in actual.cloud_signals
    )
    assert not any(
        item.path and "ordinary-handler" in item.path and item.family_id == "serverless"
        for item in actual.cloud_signals
    )
    assert not any(
        item.path
        and "build-only.yml" in item.path
        and item.family_id == "deployment"
        and item.confirmation_level == "structurally_confirmed"
        for item in actual.cloud_signals
    )

    expected = resolve_expected_results(
        next(
            item
            for item in load_all_repositories()
            if item.repository_id == "local-cloud-signals"
        )
    )
    assert expected.cloud is not None
    result = validate_cloud_precision(
        repository_id="local-cloud-signals",
        expectation=expected.cloud,
        actual_findings=actual.cloud_findings,
        actual_signals=actual.cloud_signals,
        actual_recommendations=actual.cloud_recommendations,
        artifact_texts={
            "report.json": json.dumps(actual.report_document),
        },
        limitation_texts=actual.limitations,
    )
    assert result.false_positives == 0, result.diagnostics
    assert result.false_negatives == 0, result.diagnostics
    assert result.passed, result.diagnostics

    for item in actual.cloud_findings:
        assert item.finding_id
        assert item.path is None or not item.path.startswith("/")


def test_cloud_signals_repeat_run_determinism(tmp_path: Path) -> None:
    fixture = (VALIDATION_ROOT / "fixtures" / "cloud-signals").resolve()
    first, _ = run_real_assessment(
        repository_path=fixture, output_directory=tmp_path / "a"
    )
    second, _ = run_real_assessment(
        repository_path=fixture, output_directory=tmp_path / "b"
    )
    assert sorted(item.finding_id or "" for item in first.cloud_findings) == sorted(
        item.finding_id or "" for item in second.cloud_findings
    )


def test_negative_control_repositories_cloud(tmp_path_factory) -> None:
    definitions = [
        item
        for item in load_all_repositories()
        if item.repository_id
        in {
            "local-sample-js",
            "local-sample-python",
            "local-security-hygiene",
            "local-ai-readiness",
        }
    ]
    output_root = tmp_path_factory.mktemp("cloud-neg")
    results = run_validation_suite(
        definitions,
        output_root=output_root,
        records_root=output_root / "_records",
        keep_results=True,
        local_only=True,
        include_remote=False,
    )
    summary = build_validation_summary(results)
    assert summary.failed == 0, [
        (r.repository_id, r.mismatches) for r in results if r.verdict != ValidationVerdict.PASS
    ]
    assert summary.errors == 0

    cloud_results = []
    for definition, run in zip(definitions, results, strict=True):
        assert run.verdict == ValidationVerdict.PASS, (
            definition.repository_id,
            run.mismatches,
        )
        expected = resolve_expected_results(definition)
        assert expected.cloud is not None
        report = next(Path(run.artifact_dir).rglob("report.json"))
        document = json.loads(report.read_text(encoding="utf-8"))
        artifact_paths = {"report.json": str(report)}
        evidence = report.parent / "repository-cloud-evidence.json"
        if evidence.is_file():
            artifact_paths["repository-cloud-evidence.json"] = str(evidence)
        findings = extract_cloud_findings(document["assessment"]["findings"])
        signals = extract_cloud_signals(document, artifact_paths=artifact_paths)
        for forbidden in expected.cloud.forbidden_rule_ids:
            assert forbidden not in {item.rule_id for item in findings}
        result = validate_cloud_precision(
            repository_id=definition.repository_id,
            expectation=expected.cloud,
            actual_findings=findings,
            actual_signals=signals,
            artifact_texts={"report.json": report.read_text(encoding="utf-8")},
            limitation_texts=(),
        )
        assert result.false_positives == 0, result.diagnostics
        assert result.passed, result.diagnostics
        cloud_results.append(result)
    aggregate = aggregate_cloud_results(cloud_results)
    assert aggregate.false_positives == 0


def test_generic_yaml_signal_expectation_matching() -> None:
    expectation = CloudExpectation(
        forbidden_signals=(
            CloudSignalExpectation(
                family_id="orchestration",
                path_pattern="generic-app\\.yaml",
            ),
        )
    )
    signals = (
        CloudSignalActual(
            family_id="orchestration",
            signal_kind="kubernetes",
            path="config/generic-app.yaml",
            confirmation_level="structurally_confirmed",
        ),
    )
    result = validate_cloud_precision(
        repository_id="bad",
        expectation=expectation,
        actual_findings=(),
        actual_signals=signals,
    )
    assert result.false_positives == 1
