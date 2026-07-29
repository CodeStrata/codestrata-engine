"""Test Hygiene SharedRule tests (Phase 4.6.3)."""

from __future__ import annotations

import random
from pathlib import Path

from codestrata.application.rules.finding_mapper import RuleFindingMapper
from codestrata.application.rules.registry import RuleRegistry
from codestrata.application.rules.testing.helpers import (
    TEST001_SEVERITY_LOW_MIN,
    TEST001_SEVERITY_MEDIUM_MIN,
    TEST002_MIN_CONSIDERED,
    TEST002_MIN_RATIO,
    TEST002_MIN_UNCONFIRMED,
    is_considered_candidate,
    severity_for_marker_count,
)
from codestrata.application.rules.testing.pack import TestingRulePack
from codestrata.application.rules.testing.pack import testing_rules as load_testing_rules
from codestrata.application.rules.testing.registration import register_testing_pack
from codestrata.application.rules.testing.rules import (
    CoverageWithoutCiInvocationRule,
    DeclaredWithoutObservationRule,
    DisabledOrSkippedMarkersRule,
    UnconfirmedCandidatesRule,
)
from codestrata.application.testing.assessment.artifacts import (
    write_testing_assessment_artifact,
)
from codestrata.application.testing.assessment.assembler import TestAssessmentAssembler
from codestrata.config import load_settings
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_testing.enums import (
    CoverageFactType,
    EvidenceConfirmationLevel,
    FrameworkEvidenceBasis,
    RepositoryTestingParseStatus,
    TestFileRole,
    TestFrameworkFamily,
    TestMarkerType,
)
from codestrata.domain.evidence.repository_testing.models import (
    AggregatedRepositoryTestingEvidence,
    CiTestInvocationFactEvidence,
    CoverageFactEvidence,
    FrameworkFactEvidence,
    MarkerFactEvidence,
    RepositoryTestingEvidenceCoverage,
    TestFileCandidateEvidence,
)
from codestrata.domain.findings.enums import FindingCategory
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
)
from codestrata.domain.rules.enums import RuleCategory, RuleResultStatus, RuleSeverity
from codestrata.domain.testing.ids import (
    DEFERRED_RULE_IDS,
    HYGIENE_RULE_IDS,
    PACK_ID,
    RULE_COVERAGE_WITHOUT_CI_INVOCATION,
    RULE_DECLARED_WITHOUT_OBSERVATION,
    RULE_DISABLED_OR_SKIPPED,
    RULE_OBSERVED_WITHOUT_DECLARATION,
    RULE_UNCONFIRMED_CANDIDATES,
    TESTING_RULE_IDS,
)
from codestrata.services.artifact_serialization import dumps_stable_json


def _prov() -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id="test",
        provider_version="1.0.0",
        source_analyzer="test",
        extraction_method="test",
    )


def _marker(
    *,
    path: str,
    marker_type: TestMarkerType = TestMarkerType.DISABLED,
    marker_text: str = "@Disabled",
    evidence_id: str | None = None,
    line_start: int | None = 1,
) -> MarkerFactEvidence:
    return MarkerFactEvidence(
        evidence_id=evidence_id or f"marker:{path}:{marker_type.value}",
        path=path,
        marker_type=marker_type,
        marker_text=marker_text,
        line_start=line_start,
        provenance=_prov(),
    )


def _candidate(
    *,
    path: str,
    role: TestFileRole = TestFileRole.UNIT_TEST,
    confirmation: EvidenceConfirmationLevel = (
        EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    ),
    language_hint: str | None = "python",
    evidence_id: str | None = None,
) -> TestFileCandidateEvidence:
    return TestFileCandidateEvidence(
        evidence_id=evidence_id or f"cand:{path}",
        path=path,
        role=role,
        confirmation_level=confirmation,
        language_hint=language_hint,
        provenance=_prov(),
    )


def _framework(
    *,
    framework: TestFrameworkFamily,
    basis: FrameworkEvidenceBasis,
    path: str = "package.json",
    evidence_id: str | None = None,
) -> FrameworkFactEvidence:
    return FrameworkFactEvidence(
        evidence_id=evidence_id or f"fw:{framework.value}:{basis.value}",
        framework=framework,
        basis=basis,
        path=path,
        provenance=_prov(),
    )


def _coverage_fact(
    *,
    path: str = "pyproject.toml",
    fact_type: CoverageFactType = CoverageFactType.COVERAGE_CONFIGURATION,
    tool: TestFrameworkFamily | None = TestFrameworkFamily.COVERAGE_PY,
) -> CoverageFactEvidence:
    return CoverageFactEvidence(
        evidence_id=f"cov:{path}:{fact_type.value}",
        path=path,
        fact_type=fact_type,
        tool=tool,
        provenance=_prov(),
    )


def _ci_invocation(
    *,
    path: str = ".github/workflows/ci.yml",
    command: str = "pytest",
) -> CiTestInvocationFactEvidence:
    return CiTestInvocationFactEvidence(
        evidence_id=f"ci:{path}:{command}",
        path=path,
        job_or_step="test",
        tool="pytest",
        command_projection=command,
        provenance=_prov(),
    )


def _bundle(
    *,
    markers: tuple[MarkerFactEvidence, ...] = (),
    candidates: tuple[TestFileCandidateEvidence, ...] = (),
    frameworks: tuple[FrameworkFactEvidence, ...] = (),
    coverage_facts: tuple[CoverageFactEvidence, ...] = (),
    ci_invocations: tuple[CiTestInvocationFactEvidence, ...] = (),
    languages: tuple[str, ...] = ("python",),
    candidate_files_inspected: int | None = None,
    ci_files_inspected: int = 0,
    coverage_configurations: int | None = None,
    status: RepositoryTestingParseStatus = RepositoryTestingParseStatus.SUCCEEDED,
) -> AggregatedRepositoryTestingEvidence:
    inspected = (
        candidate_files_inspected
        if candidate_files_inspected is not None
        else (len(candidates) if candidates else (1 if frameworks or markers else 0))
    )
    cov_count = (
        coverage_configurations
        if coverage_configurations is not None
        else len(coverage_facts)
    )
    return AggregatedRepositoryTestingEvidence(
        repository_id="fixture",
        status=status,
        file_candidates=candidates,
        framework_facts=frameworks,
        marker_facts=markers,
        coverage_facts=coverage_facts,
        ci_test_invocation_facts=ci_invocations,
        coverage=RepositoryTestingEvidenceCoverage(
            candidate_files_inspected=inspected,
            ci_files_inspected=ci_files_inspected,
            coverage_configurations=cov_count,
            languages_represented=languages,
            marker_facts=len(markers),
        ),
        evidence_fingerprint="deadbeef",
    )


def _context(
    evidence: AggregatedRepositoryTestingEvidence | None,
    *,
    languages: tuple[str, ...] = ("python",),
) -> RuleExecutionContext:
    return RuleExecutionContext(
        repository=RepositoryFactView(repository_id="fixture"),
        languages=LanguageInventoryView(languages=languages),
        repository_testing_evidence=evidence,
    )


def test_pack_registration_and_catalog() -> None:
    registry = RuleRegistry()
    pack = register_testing_pack(registry)
    assert pack.pack_id == PACK_ID
    assert len(load_testing_rules()) == 4
    assert len(load_testing_rules()) == len(HYGIENE_RULE_IDS)
    assert TESTING_RULE_IDS == HYGIENE_RULE_IDS
    assert registry.size == len(HYGIENE_RULE_IDS)
    rule_ids = [str(rule.metadata.rule_id) for rule in load_testing_rules()]
    assert len(rule_ids) == len(set(rule_ids))
    assert RULE_DISABLED_OR_SKIPPED in rule_ids
    assert RULE_UNCONFIRMED_CANDIDATES in rule_ids
    assert RULE_DECLARED_WITHOUT_OBSERVATION in rule_ids
    assert RULE_COVERAGE_WITHOUT_CI_INVOCATION in rule_ids
    assert RULE_OBSERVED_WITHOUT_DECLARATION not in rule_ids
    assert RULE_OBSERVED_WITHOUT_DECLARATION in DEFERRED_RULE_IDS
    assert RULE_OBSERVED_WITHOUT_DECLARATION not in HYGIENE_RULE_IDS

    mapper = RuleFindingMapper()
    evidence = _bundle(
        markers=(_marker(path="tests/a.py", marker_type=TestMarkerType.SKIPPED),)
    )
    context = _context(evidence)
    matches = []
    for rule in load_testing_rules():
        if rule.evaluate_applicability(context).applicable:
            matches.extend(rule.evaluate(context).matches)
    findings = mapper.map_matches(
        tuple(matches),
        category_by_rule={rid: RuleCategory.TESTING for rid in HYGIENE_RULE_IDS},
    )
    assert findings
    assert all(item.category is FindingCategory.TESTING for item in findings)


def test_test001_disabled_skipped_markers() -> None:
    rule = DisabledOrSkippedMarkersRule()
    empty = rule.evaluate(_context(_bundle()))
    assert empty.status is RuleResultStatus.NOT_MATCHED
    assert empty.matches == ()

    single = (
        _marker(path="tests/a.py", marker_type=TestMarkerType.DISABLED),
    )
    result = rule.evaluate(_context(_bundle(markers=single)))
    assert result.status is RuleResultStatus.MATCHED
    assert len(result.matches) == 1
    assert result.matches[0].severity is RuleSeverity.INFORMATIONAL

    low_markers = tuple(
        _marker(
            path=f"tests/t{i}.py",
            marker_type=TestMarkerType.SKIPPED,
            evidence_id=f"m{i}",
        )
        for i in range(TEST001_SEVERITY_LOW_MIN)
    )
    low = rule.evaluate(_context(_bundle(markers=low_markers)))
    assert low.matches[0].severity is RuleSeverity.LOW
    assert severity_for_marker_count(TEST001_SEVERITY_LOW_MIN) is RuleSeverity.LOW

    medium_markers = tuple(
        _marker(
            path=f"tests/m{i}.py",
            marker_type=TestMarkerType.IGNORED,
            evidence_id=f"med{i}",
        )
        for i in range(TEST001_SEVERITY_MEDIUM_MIN)
    )
    medium = rule.evaluate(_context(_bundle(markers=medium_markers)))
    assert medium.matches[0].severity is RuleSeverity.MEDIUM

    hotspot_markers = (
        _marker(path="tests/hot.py", marker_type=TestMarkerType.DISABLED, evidence_id="h1"),
        _marker(path="tests/hot.py", marker_type=TestMarkerType.SKIPPED, evidence_id="h2"),
        _marker(path="tests/cold.py", marker_type=TestMarkerType.DISABLED, evidence_id="h3"),
    )
    hotspot = rule.evaluate(_context(_bundle(markers=hotspot_markers)))
    summary = hotspot.matches[0].summary
    assert "tests/hot.py" in summary
    assert "Concentrated paths" in summary
    fact_attrs = next(
        dict(item.attributes)
        for item in hotspot.matches[0].evidence
        if "hotspot_paths" in item.attributes
    )
    assert "tests/hot.py" in fact_attrs["hotspot_paths"]


def test_test002_unconfirmed_candidates() -> None:
    rule = UnconfirmedCandidatesRule()

    # Material unconfirmed → finding.
    considered = [
        _candidate(
            path=f"tests/u{i}.py",
            confirmation=EvidenceConfirmationLevel.DISCOVERED_CANDIDATE,
        )
        for i in range(TEST002_MIN_UNCONFIRMED)
    ] + [
        _candidate(
            path=f"tests/c{i}.py",
            confirmation=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        )
        for i in range(TEST002_MIN_CONSIDERED - TEST002_MIN_UNCONFIRMED)
    ]
    assert len(considered) >= TEST002_MIN_CONSIDERED
    unconfirmed = [item for item in considered if is_considered_candidate(item)]
    unconfirmed_only = [
        item
        for item in considered
        if item.confirmation_level
        is not EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
    ]
    ratio = len(unconfirmed_only) / len(unconfirmed)
    assert ratio >= TEST002_MIN_RATIO
    material = rule.evaluate(_context(_bundle(candidates=tuple(considered))))
    assert material.status is RuleResultStatus.MATCHED
    assert len(material.matches) == 1

    # Small repo suppress.
    small = [
        _candidate(path=f"tests/s{i}.py")
        for i in range(TEST002_MIN_CONSIDERED - 1)
    ]
    assert (
        rule.evaluate(_context(_bundle(candidates=tuple(small)))).status
        is RuleResultStatus.NOT_MATCHED
    )

    # Low ratio suppress (enough considered, few unconfirmed).
    low_ratio = [
        _candidate(
            path=f"tests/l{i}.py",
            confirmation=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        )
        for i in range(TEST002_MIN_CONSIDERED)
    ] + [
        _candidate(
            path=f"tests/x{i}.py",
            confirmation=EvidenceConfirmationLevel.DISCOVERED_CANDIDATE,
        )
        for i in range(2)
    ]
    low = rule.evaluate(_context(_bundle(candidates=tuple(low_ratio))))
    assert low.status is RuleResultStatus.NOT_MATCHED

    # Fixtures excluded from considered — pad with fixtures so raw count is high
    # but considered stays below threshold.
    fixtures = [
        _candidate(
            path=f"tests/fixtures/f{i}.json",
            role=TestFileRole.TEST_FIXTURE,
            confirmation=EvidenceConfirmationLevel.DISCOVERED_CANDIDATE,
        )
        for i in range(30)
    ] + [
        _candidate(
            path=f"tests/real{i}.py",
            confirmation=EvidenceConfirmationLevel.DISCOVERED_CANDIDATE,
        )
        for i in range(5)
    ]
    excluded = rule.evaluate(_context(_bundle(candidates=tuple(fixtures))))
    assert excluded.status is RuleResultStatus.NOT_MATCHED


def test_test003_declared_without_observation() -> None:
    rule = DeclaredWithoutObservationRule()

    # Declared jest without observation + JS language → finding.
    jest_only = _bundle(
        frameworks=(
            _framework(
                framework=TestFrameworkFamily.JEST,
                basis=FrameworkEvidenceBasis.DECLARED,
                path="package.json",
            ),
        ),
        candidates=(
            _candidate(
                path="src/app.test.js",
                language_hint="javascript",
                confirmation=EvidenceConfirmationLevel.DISCOVERED_CANDIDATE,
            ),
        ),
        languages=("javascript",),
        candidate_files_inspected=1,
    )
    jest_result = rule.evaluate(_context(jest_only, languages=("javascript",)))
    assert jest_result.status is RuleResultStatus.MATCHED
    assert "jest" in jest_result.matches[0].summary.lower()

    # Matching pytest declared + observed → no finding.
    pytest_matched = _bundle(
        frameworks=(
            _framework(
                framework=TestFrameworkFamily.PYTEST,
                basis=FrameworkEvidenceBasis.DECLARED,
                path="pyproject.toml",
            ),
            _framework(
                framework=TestFrameworkFamily.PYTEST,
                basis=FrameworkEvidenceBasis.STRUCTURALLY_OBSERVED,
                path="tests/test_a.py",
            ),
        ),
        candidates=(
            _candidate(
                path="tests/test_a.py",
                confirmation=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
            ),
        ),
        languages=("python",),
        candidate_files_inspected=1,
    )
    assert rule.evaluate(_context(pytest_matched)).status is RuleResultStatus.NOT_MATCHED

    # Incomplete inspection suppress.
    incomplete = _bundle(
        frameworks=(
            _framework(
                framework=TestFrameworkFamily.JEST,
                basis=FrameworkEvidenceBasis.DECLARED,
            ),
        ),
        languages=("javascript",),
        candidate_files_inspected=0,
    )
    assert rule.evaluate(
        _context(incomplete, languages=("javascript",))
    ).status is RuleResultStatus.NOT_MATCHED


def test_test004_deferred_not_registered() -> None:
    active_ids = [str(rule.metadata.rule_id) for rule in load_testing_rules()]
    assert RULE_OBSERVED_WITHOUT_DECLARATION not in active_ids
    assert RULE_OBSERVED_WITHOUT_DECLARATION not in HYGIENE_RULE_IDS
    assert RULE_OBSERVED_WITHOUT_DECLARATION in DEFERRED_RULE_IDS
    pack = TestingRulePack()
    assert RULE_OBSERVED_WITHOUT_DECLARATION in pack.deferred_rule_ids
    assert RULE_OBSERVED_WITHOUT_DECLARATION not in pack.included_rule_ids


def test_test005_coverage_without_ci_invocation() -> None:
    rule = CoverageWithoutCiInvocationRule()

    # Coverage + CI inspected + no invocation → finding.
    gap = _bundle(
        coverage_facts=(_coverage_fact(),),
        ci_files_inspected=1,
        ci_invocations=(),
        candidates=(_candidate(path="tests/test_a.py"),),
    )
    gap_result = rule.evaluate(_context(gap))
    assert gap_result.status is RuleResultStatus.MATCHED
    assert gap_result.matches[0].severity is RuleSeverity.INFORMATIONAL

    # With invocation → no finding.
    with_ci = _bundle(
        coverage_facts=(_coverage_fact(),),
        ci_files_inspected=1,
        ci_invocations=(_ci_invocation(),),
        candidates=(_candidate(path="tests/test_a.py"),),
    )
    assert rule.evaluate(_context(with_ci)).status is RuleResultStatus.NOT_MATCHED

    # No CI inspected → no finding.
    no_ci = _bundle(
        coverage_facts=(_coverage_fact(),),
        ci_files_inspected=0,
        candidates=(_candidate(path="tests/test_a.py"),),
    )
    assert rule.evaluate(_context(no_ci)).status is RuleResultStatus.NOT_MATCHED


def test_determinism_shuffle_and_assessment_bytes(tmp_path: Path) -> None:
    markers = [
        _marker(
            path=f"tests/d{i}.py",
            marker_type=TestMarkerType.DISABLED,
            marker_text="@Disabled",
            evidence_id=f"det{i}",
        )
        for i in range(5)
    ]
    shuffled = list(markers)
    random.Random(42).shuffle(shuffled)
    left = DisabledOrSkippedMarkersRule().evaluate(
        _context(_bundle(markers=tuple(markers)))
    )
    right = DisabledOrSkippedMarkersRule().evaluate(
        _context(_bundle(markers=tuple(shuffled)))
    )
    assert left.matches[0].subject_keys == right.matches[0].subject_keys

    mapper = RuleFindingMapper()
    findings_left = mapper.map_matches(
        left.matches,
        category_by_rule={RULE_DISABLED_OR_SKIPPED: RuleCategory.TESTING},
    )
    findings_right = mapper.map_matches(
        right.matches,
        category_by_rule={RULE_DISABLED_OR_SKIPPED: RuleCategory.TESTING},
    )
    assert findings_left[0].id == findings_right[0].id

    evidence = _bundle(markers=tuple(markers))
    assembler = TestAssessmentAssembler()
    section = assembler.assemble(
        repository_id="fixture",
        findings=findings_left,
        evidence=evidence,
        pack_enabled=True,
        rules_executed=4,
        rules_matched=1,
        evidence_pipeline="repository_testing",
        evidence_fingerprint="deadbeef",
    )
    write = write_testing_assessment_artifact(section, tmp_path)
    again = write_testing_assessment_artifact(section, tmp_path)
    assert write.path.read_bytes() == again.path.read_bytes()


def test_privacy_no_absolute_paths_or_source_body() -> None:
    markers = (
        _marker(
            path="tests/secret_path.py",
            marker_type=TestMarkerType.SKIPPED,
            marker_text="pytest.skip",
        ),
    )
    # Absolute path must never appear even if someone put it in marker text.
    evidence = _bundle(
        markers=markers,
        candidates=(
            _candidate(path="tests/secret_path.py"),
        ),
    )
    context = _context(evidence)
    matches = []
    for rule in load_testing_rules():
        if rule.evaluate_applicability(context).applicable:
            matches.extend(rule.evaluate(context).matches)
    mapper = RuleFindingMapper()
    findings = mapper.map_matches(
        tuple(matches),
        category_by_rule={rid: RuleCategory.TESTING for rid in HYGIENE_RULE_IDS},
    )
    text = dumps_stable_json(
        {
            "ids": [item.id for item in findings],
            "desc": [item.description for item in findings],
            "meta": [dict(item.metadata) for item in findings],
            "ev": [
                {"path": e.path, "excerpt": e.excerpt}
                for item in findings
                for e in item.evidence
            ],
        }
    )
    assert "/Users/" not in text
    assert "def test_" not in text
    assert "BEGIN PRIVATE" not in text
    assert "source body" not in text.lower()


def test_gates_independent(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        [evidence.repository_testing]
        enabled = true
        [rules]
        enabled = false
        [rules.testing]
        enabled = false
        [assessment.sections.testing]
        enabled = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.evidence.repository_testing.enabled is True
    assert settings.rules.testing.enabled is False
    assert settings.assessment.sections.testing.enabled is False
    assert settings.rules.security.enabled is False
    assert settings.assessment.sections.security.enabled is False
