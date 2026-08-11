"""Slice 4.7 — Dependency precision expectation model, metrics, and fixture."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from codestrata.application.rules.dependency.helpers import (
    is_exact_version,
    is_mutable_version,
)
from codestrata.application.rules.dependency.rules import (
    ConflictingExactVersionsRule,
    DuplicateDeclarationRule,
    MutableVersionRule,
    UnboundedRequirementRule,
    UnresolvedVersionRule,
)
from codestrata.domain.dependency.ids import HYGIENE_RULE_IDS
from codestrata.domain.evidence.dependency.enums import (
    DependencyDeclarationKind,
    DependencyEcosystem,
    DependencyEvidenceAvailability,
    DependencyManifestType,
    DependencyParseStatus,
    DependencyVersionResolutionStatus,
)
from codestrata.domain.evidence.dependency.models import (
    AggregatedDependencyEvidence,
    DependencyDeclarationEvidence,
    DependencyEvidenceCoverage,
    DependencyManifestEvidence,
    DependencySourceLocation,
)
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin, SourceClassification
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
)
from codestrata.domain.rules.enums import RuleResultStatus
from validation.actual import run_real_assessment
from validation.dependency import (
    DependencyExpectation,
    DependencyFindingActual,
    DependencyFindingExpectation,
    DependencyForbiddenManifestExpectation,
    DependencyManifestActual,
    DependencyManifestExpectation,
    aggregate_dependency_results,
    extract_dependency_findings,
    extract_dependency_manifests,
    validate_dependency_precision,
)
from validation.inventory import FactClassification, compute_precision_recall
from validation.models import ExpectedResults, ValidationVerdict
from validation.paths import VALIDATION_ROOT
from validation.registry import load_all_repositories, resolve_expected_results
from validation.runner import run_validation_suite
from validation.summary import build_validation_summary


def _prov(path: str = "pom.xml") -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id="dependency.maven.manifest",
        provider_version="1.0.0",
        source_analyzer="test",
        extraction_method="fixture",
        origin=EvidenceOrigin.MANIFEST,
        source_path=path,
    )


def _decl(
    *,
    evidence_id: str,
    identity: str,
    path: str = "pom.xml",
    raw_version: str | None = "1.0.0",
    resolved: str | None = None,
    resolution_status: DependencyVersionResolutionStatus = (
        DependencyVersionResolutionStatus.RESOLVED
    ),
    ecosystem: DependencyEcosystem = DependencyEcosystem.MAVEN,
    kind: DependencyDeclarationKind = DependencyDeclarationKind.RUNTIME,
    profile: str | None = None,
) -> DependencyDeclarationEvidence:
    return DependencyDeclarationEvidence(
        evidence_id=evidence_id,
        ecosystem=ecosystem,
        manifest_type=(
            DependencyManifestType.REQUIREMENTS_TXT
            if ecosystem is DependencyEcosystem.PYTHON
            else DependencyManifestType.POM_XML
        ),
        declaration_kind=kind,
        normalized_identity=identity,
        original_identity=identity,
        raw_version=raw_version,
        resolved_version_local=resolved if resolved is not None else raw_version,
        version_availability=(
            DependencyEvidenceAvailability.AVAILABLE
            if raw_version
            else DependencyEvidenceAvailability.UNAVAILABLE
        ),
        version_resolution_status=resolution_status,
        profile=profile,
        source=DependencySourceLocation(path=path, line_start=1, line_end=1),
        classification=SourceClassification.SOURCE,
        provenance=_prov(path),
    )


def test_contradictory_dependency_expectations_rejected() -> None:
    with pytest.raises(ValidationError, match="contradictory"):
        DependencyExpectation(
            expected_rule_ids=("dependency.mutable-version",),
            forbidden_rule_ids=("dependency.mutable-version",),
        )
    with pytest.raises(ValidationError, match="contradictory"):
        ExpectedResults(
            dependency=DependencyExpectation(
                required_findings=(
                    DependencyFindingExpectation(rule_id="dependency.unresolved-version"),
                ),
                forbidden_rule_ids=("dependency.unresolved-version",),
            )
        )
    with pytest.raises(ValidationError, match="contradictory"):
        DependencyExpectation(
            required_manifests=(
                DependencyManifestExpectation(path="pom.xml", ecosystem="maven"),
            ),
            forbidden_manifests=(
                DependencyForbiddenManifestExpectation(path_pattern=r"pom\.xml$"),
            ),
        )


def test_classify_tp_fp_fn_and_metrics() -> None:
    expectation = DependencyExpectation(
        required_manifests=(
            DependencyManifestExpectation(path="pyproject.toml", ecosystem="python"),
        ),
        required_findings=(
            DependencyFindingExpectation(
                rule_id="dependency.unbounded-requirement",
                dependency_name="unbounded-pkg",
            ),
        ),
        forbidden_rule_ids=("dependency.mutable-version",),
        forbidden_conclusions=("secure supply chain",),
    )
    actual_findings = (
        DependencyFindingActual(
            rule_id="dependency.unbounded-requirement",
            path="requirements.txt",
            dependency_name="unbounded-pkg",
            declared_version="",
            ecosystem="python",
            evidence_ids=("e1",),
        ),
        DependencyFindingActual(
            rule_id="dependency.mutable-version",
            path="pom.xml",
            dependency_name="com.example:snap",
            declared_version="1.0.0-SNAPSHOT",
            ecosystem="maven",
            evidence_ids=("e2",),
        ),
    )
    manifests = (
        DependencyManifestActual(
            path="pyproject.toml",
            ecosystem="python",
            manifest_type="pyproject.toml",
            parse_status="succeeded",
            declaration_count=1,
        ),
    )
    result = validate_dependency_precision(
        repository_id="fixture",
        expectation=expectation,
        actual_findings=actual_findings,
        actual_manifests=manifests,
        artifact_texts={"report.json": "safe disclaimer only"},
    )
    by_name = {item.name: item.classification for item in result.classifications}
    assert by_name["manifest:pyproject.toml"] is FactClassification.TRUE_POSITIVE
    assert by_name["dependency.unbounded-requirement"] is FactClassification.TRUE_POSITIVE
    assert by_name["dependency.mutable-version"] is FactClassification.FALSE_POSITIVE
    assert result.precision == pytest.approx(2 / 3)
    assert result.recall == pytest.approx(1.0)


def test_precision_recall_zero_denominator_unavailable() -> None:
    precision, recall, reason = compute_precision_recall(
        true_positives=0, false_positives=0, false_negatives=0
    )
    assert precision is None and recall is None and reason is not None


def test_aggregate_deterministic_order() -> None:
    expectation = DependencyExpectation(
        required_manifests=(DependencyManifestExpectation(path="pom.xml"),)
    )
    manifests = (DependencyManifestActual(path="pom.xml", ecosystem="maven"),)
    a = validate_dependency_precision(
        repository_id="repo-a",
        expectation=expectation,
        actual_findings=(),
        actual_manifests=manifests,
    )
    b = validate_dependency_precision(
        repository_id="repo-b",
        expectation=expectation,
        actual_findings=(),
        actual_manifests=manifests,
    )
    aggregate = aggregate_dependency_results((b, a))
    assert [item.repository_id for item in aggregate.per_repository] == ["repo-b", "repo-a"]
    assert aggregate.precision == 1.0


def test_all_repositories_have_dependency_expectations() -> None:
    for definition in load_all_repositories():
        if not definition.enabled:
            continue
        expected = resolve_expected_results(definition)
        assert expected.dependency is not None, definition.repository_id
        assert expected.dependency.evidence_notes, definition.repository_id


def test_version_classification_boundaries() -> None:
    assert is_mutable_version("1.0.0-SNAPSHOT")
    assert is_mutable_version("latest")
    assert not is_mutable_version(">=3.0.0")
    assert not is_mutable_version("^4.21.0")
    assert is_exact_version("1.2.3")
    assert not is_exact_version(">=1.0,<2.0")


def test_profile_and_scope_negatives_for_conflict() -> None:
    decls = (
        _decl(evidence_id="a", identity="com.example:scoped-lib", raw_version="1.0.0"),
        _decl(
            evidence_id="b",
            identity="com.example:scoped-lib",
            raw_version="2.0.0",
            kind=DependencyDeclarationKind.TEST,
        ),
        _decl(
            evidence_id="c",
            identity="com.example:scoped-lib",
            raw_version="9.9.9",
            profile="extra",
        ),
    )
    evidence = AggregatedDependencyEvidence(
        repository_id="repo",
        status=DependencyParseStatus.SUCCEEDED,
        manifests=(
            DependencyManifestEvidence(
                evidence_id="m1",
                path="pom.xml",
                ecosystem=DependencyEcosystem.MAVEN,
                manifest_type=DependencyManifestType.POM_XML,
                parse_status=DependencyParseStatus.SUCCEEDED,
                provenance=_prov(),
            ),
        ),
        declarations=decls,
        coverage=DependencyEvidenceCoverage(
            manifests_discovered=1,
            manifests_supported=1,
            manifests_parsed=1,
            declarations_collected=3,
        ),
        evidence_fingerprint="fp",
    )
    context = RuleExecutionContext(
        repository=RepositoryFactView(repository_id="repo"),
        languages=LanguageInventoryView(languages=("java",)),
        dependency_evidence=evidence,
    )
    result = ConflictingExactVersionsRule().evaluate(context)
    assert result.status is RuleResultStatus.NOT_MATCHED


def test_true_conflict_and_duplicate_detected() -> None:
    conflict = (
        _decl(evidence_id="c1", identity="com.example:conflict-lib", raw_version="1.0.0"),
        _decl(evidence_id="c2", identity="com.example:conflict-lib", raw_version="2.0.0"),
    )
    duplicate = (
        _decl(evidence_id="d1", identity="com.example:dup-lib", raw_version="1.2.3"),
        _decl(evidence_id="d2", identity="com.example:dup-lib", raw_version="1.2.3"),
    )
    evidence = AggregatedDependencyEvidence(
        repository_id="repo",
        status=DependencyParseStatus.SUCCEEDED,
        manifests=(
            DependencyManifestEvidence(
                evidence_id="m1",
                path="pom.xml",
                ecosystem=DependencyEcosystem.MAVEN,
                manifest_type=DependencyManifestType.POM_XML,
                parse_status=DependencyParseStatus.SUCCEEDED,
                provenance=_prov(),
            ),
        ),
        declarations=conflict + duplicate,
        coverage=DependencyEvidenceCoverage(declarations_collected=4),
        evidence_fingerprint="fp",
    )
    context = RuleExecutionContext(
        repository=RepositoryFactView(repository_id="repo"),
        languages=LanguageInventoryView(languages=("java",)),
        dependency_evidence=evidence,
    )
    assert ConflictingExactVersionsRule().evaluate(context).status is RuleResultStatus.MATCHED
    assert DuplicateDeclarationRule().evaluate(context).status is RuleResultStatus.MATCHED


def test_unresolved_and_mutable_and_unbounded_rules() -> None:
    unresolved = _decl(
        evidence_id="u1",
        identity="com.example:missing",
        raw_version="${missing.version}",
        resolved=None,
        resolution_status=DependencyVersionResolutionStatus.PROVEN_UNRESOLVED,
    )
    mutable = _decl(
        evidence_id="m1",
        identity="com.example:snap",
        raw_version="1.0.0-SNAPSHOT",
    )
    unbounded = _decl(
        evidence_id="b1",
        identity="unbounded-pkg",
        path="requirements.txt",
        ecosystem=DependencyEcosystem.PYTHON,
        raw_version=None,
        resolved=None,
        resolution_status=DependencyVersionResolutionStatus.NOT_APPLICABLE,
    )
    evidence = AggregatedDependencyEvidence(
        repository_id="repo",
        status=DependencyParseStatus.SUCCEEDED,
        manifests=(),
        declarations=(unresolved, mutable, unbounded),
        coverage=DependencyEvidenceCoverage(declarations_collected=3),
        evidence_fingerprint="fp",
    )
    context = RuleExecutionContext(
        repository=RepositoryFactView(repository_id="repo"),
        languages=LanguageInventoryView(languages=("java", "python")),
        dependency_evidence=evidence,
    )
    assert UnresolvedVersionRule().evaluate(context).status is RuleResultStatus.MATCHED
    assert MutableVersionRule().evaluate(context).status is RuleResultStatus.MATCHED
    assert UnboundedRequirementRule().evaluate(context).status is RuleResultStatus.MATCHED


def test_controlled_dependency_fixture_precision(tmp_path: Path) -> None:
    fixture = (VALIDATION_ROOT / "fixtures" / "dependency-signals").resolve()
    config = VALIDATION_ROOT / "configs" / "local-dependency-signals.toml"
    actual, _ = run_real_assessment(
        repository_path=fixture,
        output_directory=tmp_path / "out",
        config_path=config,
    )
    rule_ids = {item.rule_id for item in actual.dependency_findings}
    for rule_id in HYGIENE_RULE_IDS:
        assert rule_id in rule_ids, rule_id

    assert any(item.path == "pom.xml" for item in actual.dependency_manifests)
    assert any(item.path == "requirements.txt" for item in actual.dependency_manifests)

    expectation = DependencyExpectation(
        required_manifests=(
            DependencyManifestExpectation(
                path="pom.xml",
                ecosystem="maven",
                manifest_type="pom.xml",
            ),
            DependencyManifestExpectation(
                path="requirements.txt",
                ecosystem="python",
                manifest_type="requirements.txt",
                parse_status="succeeded",
            ),
        ),
        required_findings=(
            DependencyFindingExpectation(
                rule_id="dependency.unresolved-version",
                path="pom.xml",
                dependency_pattern="missing-prop-lib",
                declared_version="${missing.version}",
            ),
            DependencyFindingExpectation(
                rule_id="dependency.mutable-version",
                path="pom.xml",
                dependency_pattern="snapshot-lib",
                declared_version="1.0.0-SNAPSHOT",
            ),
            DependencyFindingExpectation(
                rule_id="dependency.unbounded-requirement",
                path="requirements.txt",
                dependency_name="unbounded-pkg",
            ),
            DependencyFindingExpectation(
                rule_id="dependency.conflicting-exact-versions",
                path="pom.xml",
                dependency_pattern="conflict-lib",
            ),
            DependencyFindingExpectation(
                rule_id="dependency.duplicate-declaration",
                path="pom.xml",
                dependency_pattern="dup-lib",
            ),
        ),
        forbidden_findings=(
            DependencyFindingExpectation(
                rule_id="dependency.unresolved-version",
                dependency_pattern="known-lib",
                rationale="locally resolved property must not be unresolved",
            ),
            DependencyFindingExpectation(
                rule_id="dependency.mutable-version",
                dependency_pattern="flask",
                rationale="Python ranges are not mutable",
            ),
            DependencyFindingExpectation(
                rule_id="dependency.unbounded-requirement",
                dependency_name="flask",
                rationale="ranged requirement is constrained",
            ),
            DependencyFindingExpectation(
                rule_id="dependency.conflicting-exact-versions",
                dependency_pattern="scoped-lib",
                rationale="scope/profile negatives must not conflict",
            ),
        ),
        maximum_false_positive_count=0,
        evidence_notes="Controlled dependency-signals fixture",
    )
    result = validate_dependency_precision(
        repository_id="dependency-signals",
        expectation=expectation,
        actual_findings=actual.dependency_findings,
        actual_manifests=actual.dependency_manifests,
    )
    assert result.false_positives == 0, result.diagnostics
    assert result.false_negatives == 0, result.diagnostics
    assert result.path_failures == ()
    assert result.passed

    for item in actual.dependency_findings:
        assert item.finding_id
        assert item.evidence_ids
        assert item.path is None or not item.path.startswith("/")
        assert item.dependency_name


def test_dependency_fixture_repeat_run_determinism(tmp_path: Path) -> None:
    fixture = (VALIDATION_ROOT / "fixtures" / "dependency-signals").resolve()
    config = VALIDATION_ROOT / "configs" / "local-dependency-signals.toml"
    first, _ = run_real_assessment(
        repository_path=fixture, output_directory=tmp_path / "a", config_path=config
    )
    second, _ = run_real_assessment(
        repository_path=fixture, output_directory=tmp_path / "b", config_path=config
    )
    assert sorted(item.finding_id or "" for item in first.dependency_findings) == sorted(
        item.finding_id or "" for item in second.dependency_findings
    )


def test_extract_manifests_from_sidecar(tmp_path: Path) -> None:
    sidecar = {
        "manifest_inventory": {
            "entries": [
                {
                    "path": "pyproject.toml",
                    "ecosystem": "python",
                    "manifest_type": "pyproject.toml",
                    "parse_status": "succeeded",
                    "declaration_count": 2,
                    "evidence_id": "ev:1",
                }
            ]
        }
    }
    path = tmp_path / "dependency-assessment.json"
    path.write_text(json.dumps(sidecar), encoding="utf-8")
    manifests = extract_dependency_manifests(
        {},
        artifact_paths={"dependency-assessment.json": str(path)},
    )
    assert len(manifests) == 1
    assert manifests[0].path == "pyproject.toml"
    assert manifests[0].ecosystem == "python"


def test_negative_control_repositories_dependency(tmp_path_factory) -> None:
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
    output_root = tmp_path_factory.mktemp("dep-neg")
    results = run_validation_suite(
        definitions,
        output_root=output_root,
        records_root=output_root / "_records",
        keep_results=True,
        local_only=True,
        include_remote=False,
    )
    summary = build_validation_summary(results)
    assert summary.failed == 0, [(r.repository_id, r.mismatches) for r in results if r.verdict != ValidationVerdict.PASS]
    assert summary.errors == 0

    dep_results = []
    for definition, run in zip(definitions, results, strict=True):
        assert run.verdict == ValidationVerdict.PASS, (
            definition.repository_id,
            run.mismatches,
        )
        expected = resolve_expected_results(definition)
        assert expected.dependency is not None
        report = next(Path(run.artifact_dir).rglob("report.json"))
        document = json.loads(report.read_text(encoding="utf-8"))
        assessment_path = report.parent / "dependency-assessment.json"
        artifact_paths = {"report.json": str(report)}
        if assessment_path.is_file():
            artifact_paths["dependency-assessment.json"] = str(assessment_path)
        findings = extract_dependency_findings(document["assessment"]["findings"])
        manifests = extract_dependency_manifests(document, artifact_paths=artifact_paths)
        for forbidden in expected.dependency.forbidden_rule_ids:
            assert forbidden not in {item.rule_id for item in findings}
        # Collect limitation texts including summary fields.
        limitations = []
        dep_section = document["assessment"].get("dependency") or {}
        for item in dep_section.get("limitations") or []:
            if isinstance(item, dict) and item.get("summary"):
                limitations.append(str(item["summary"]))
        result = validate_dependency_precision(
            repository_id=definition.repository_id,
            expectation=expected.dependency,
            actual_findings=findings,
            actual_manifests=manifests,
            artifact_texts={"report.json": report.read_text(encoding="utf-8")},
            limitation_texts=limitations,
        )
        assert result.false_positives == 0, result.diagnostics
        assert result.passed, result.diagnostics
        dep_results.append(result)
    aggregate = aggregate_dependency_results(dep_results)
    assert aggregate.false_positives == 0
