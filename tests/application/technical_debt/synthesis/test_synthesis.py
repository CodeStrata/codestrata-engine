"""Technical Debt assessment synthesis tests (Phase 4.3.5)."""

from __future__ import annotations

from codestrata.application.technical_debt.assessment.assembler import (
    TechnicalDebtAssessmentAssembler,
)
from codestrata.application.technical_debt.assessment.inventory import (
    build_finding_references,
    build_hotspot_inventory,
)
from codestrata.application.technical_debt.synthesis.service import synthesize_technical_debt
from codestrata.domain.findings import Finding
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.technical_debt.assessment.enums import (
    TechnicalDebtAssessmentStatus,
    TechnicalDebtSourceRole,
)
from codestrata.domain.technical_debt.assessment.models import TechnicalDebtHotspotInventory
from codestrata.domain.technical_debt.ids import (
    RULE_EXCESSIVE_BRANCHING,
    RULE_LARGE_CALLABLE,
)
from codestrata.domain.technical_debt.synthesis.enums import (
    TechnicalDebtConclusionAudience,
    TechnicalDebtConclusionKind,
    TechnicalDebtSynthesisStatus,
)
from codestrata.domain.technical_debt.synthesis.identifiers import (
    PACKAGE_CONCENTRATION_MIN_SHARE,
)


def _finding(
    *,
    rule_id: str,
    path: str,
    symbol: str,
    package: str | None = None,
    severity: FindingSeverity = FindingSeverity.MEDIUM,
    classification: str = "source",
    metric: str = "physical_line_count",
    value: str = "80",
    threshold: str = "50",
) -> Finding:
    return Finding.create(
        rule_id=rule_id,
        title=rule_id,
        description=f"{metric}={value} threshold {threshold}",
        severity=severity,
        category=FindingCategory.TECHNICAL_DEBT,
        subject_keys=(path, symbol),
        metadata={
            "classification": classification,
            "language": "python" if path.endswith(".py") else "java",
            "metric": metric,
            "value": value,
            "threshold": threshold,
            "severity_basis": f"value>{threshold}",
            "confidence": "high",
            "taxonomy_id": "technical-debt.complexity",
            "assessment_dimensions": "technical-debt",
            "subject_keys": f"{path},{symbol}",
            "path": path,
            "package": package or "/".join(path.split("/")[:-1]),
        },
    )


def test_synthesis_production_themes_and_traceability() -> None:
    findings = (
        _finding(
            rule_id=RULE_LARGE_CALLABLE,
            path="src/codestrata/app.py",
            symbol="run#0@1",
            severity=FindingSeverity.HIGH,
            value="120",
        ),
        _finding(
            rule_id=RULE_EXCESSIVE_BRANCHING,
            path="src/codestrata/app.py",
            symbol="run#0@1",
            metric="branch_point_count",
            value="12",
            threshold="10",
        ),
        _finding(
            rule_id=RULE_LARGE_CALLABLE,
            path="tests/test_app.py",
            symbol="test_big#0@1",
            classification="test",
            value="70",
        ),
    )
    section = TechnicalDebtAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=findings,
        pack_enabled=True,
        complexity_evidence_enabled=True,
        files_considered=2,
        files_analyzed=2,
        configuration_payload="stable",
    )
    assert section.synthesis.status is TechnicalDebtSynthesisStatus.SUCCEEDED
    assert any(
        item.kind is TechnicalDebtConclusionKind.COMPLEXITY_PRESENT
        for item in section.conclusions
    )
    assert any(
        item.kind is TechnicalDebtConclusionKind.THEME_COMPLEXITY
        and item.source_role is TechnicalDebtSourceRole.PRODUCTION
        for item in section.conclusions
    )
    test_conclusions = [
        item
        for item in section.conclusions
        if item.kind is TechnicalDebtConclusionKind.TEST_MAINTAINABILITY
    ]
    assert len(test_conclusions) == 1
    assert test_conclusions[0].audience is TechnicalDebtConclusionAudience.TEST_OBSERVATION
    # Test observation must not be labeled production_health.
    assert all(
        item.audience is not TechnicalDebtConclusionAudience.PRODUCTION_HEALTH
        or item.source_role is TechnicalDebtSourceRole.PRODUCTION
        for item in section.conclusions
        if item.kind is not TechnicalDebtConclusionKind.PARTIAL_COVERAGE
    )
    assert section.recommendations
    assert all(rec.conclusion_ids for rec in section.recommendations)
    assert any(
        edge.relation.value == "recommendation_to_conclusion"
        for edge in section.traceability.edges
    )
    assert any(
        edge.relation.value == "conclusion_to_finding"
        for edge in section.traceability.edges
    )


def test_test_findings_do_not_drive_production_present_alone() -> None:
    findings = (
        _finding(
            rule_id=RULE_LARGE_CALLABLE,
            path="tests/test_app.py",
            symbol="test_big#0@1",
            classification="test",
            value="70",
        ),
    )
    section = TechnicalDebtAssessmentAssembler().assemble(
        repository_id="repo:test-only",
        findings=findings,
        pack_enabled=True,
        complexity_evidence_enabled=True,
        files_considered=1,
        files_analyzed=1,
    )
    kinds = {item.kind for item in section.conclusions}
    assert TechnicalDebtConclusionKind.NO_PRODUCTION_FINDINGS in kinds
    assert TechnicalDebtConclusionKind.TEST_MAINTAINABILITY in kinds
    assert TechnicalDebtConclusionKind.COMPLEXITY_PRESENT not in kinds
    assert section.finding_ids == ()


def test_concentration_boundary() -> None:
    # 20 findings in one package => 100% share exceeds 15%.
    findings = tuple(
        _finding(
            rule_id=RULE_LARGE_CALLABLE,
            path=f"src/pkg/file{index}.py",
            symbol=f"fn{index}#0@1",
            package="src/pkg",
            value="60",
        )
        for index in range(20)
    )
    refs = build_finding_references(findings)
    hotspots = build_hotspot_inventory(refs)
    result = synthesize_technical_debt(
        repository_id="repo:conc",
        pack_enabled=True,
        section_status=TechnicalDebtAssessmentStatus.SUCCEEDED,
        finding_summaries=refs,
        hotspot_inventory=hotspots,
    )
    package_facts = [
        fact for fact in result.concentration_facts if fact.kind == "package_share"
    ]
    assert package_facts
    assert package_facts[0].share >= PACKAGE_CONCENTRATION_MIN_SHARE
    assert package_facts[0].exceeds_threshold is True
    assert any(
        item.kind is TechnicalDebtConclusionKind.PACKAGE_CONCENTRATION
        for item in result.conclusions
    )


def test_disabled_and_empty_synthesis() -> None:
    disabled = TechnicalDebtAssessmentAssembler().assemble_disabled(repository_id="repo:x")
    assert disabled.status is TechnicalDebtAssessmentStatus.DISABLED

    empty = TechnicalDebtAssessmentAssembler().assemble(
        repository_id="repo:empty",
        findings=(),
        pack_enabled=True,
        complexity_evidence_enabled=True,
        files_considered=3,
        files_analyzed=3,
    )
    assert any(
        item.kind is TechnicalDebtConclusionKind.NO_PRODUCTION_FINDINGS
        for item in empty.conclusions
    )
    assert empty.synthesis.status in {
        TechnicalDebtSynthesisStatus.EMPTY,
        TechnicalDebtSynthesisStatus.SUCCEEDED,
    }


def test_determinism() -> None:
    findings = (
        _finding(
            rule_id=RULE_LARGE_CALLABLE,
            path="src/a.py",
            symbol="a#0@1",
            value="90",
        ),
        _finding(
            rule_id=RULE_EXCESSIVE_BRANCHING,
            path="src/a.py",
            symbol="a#0@1",
            metric="branch_point_count",
            value="15",
            threshold="10",
        ),
    )
    first = TechnicalDebtAssessmentAssembler().assemble(
        repository_id="repo:det",
        findings=findings,
        pack_enabled=True,
        complexity_evidence_enabled=True,
        files_considered=1,
        files_analyzed=1,
        configuration_payload="stable",
    )
    second = TechnicalDebtAssessmentAssembler().assemble(
        repository_id="repo:det",
        findings=tuple(reversed(findings)),
        pack_enabled=True,
        complexity_evidence_enabled=True,
        files_considered=1,
        files_analyzed=1,
        configuration_payload="stable",
    )
    assert first.conclusion_ids == second.conclusion_ids
    assert first.recommendation_ids == second.recommendation_ids
    assert first.theme_ids == second.theme_ids
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_include_synthesis_false() -> None:
    refs = build_finding_references(
        (
            _finding(
                rule_id=RULE_LARGE_CALLABLE,
                path="src/a.py",
                symbol="a#0@1",
            ),
        )
    )
    result = synthesize_technical_debt(
        repository_id="repo:off",
        pack_enabled=True,
        section_status=TechnicalDebtAssessmentStatus.SUCCEEDED,
        finding_summaries=refs,
        hotspot_inventory=TechnicalDebtHotspotInventory(),
        include_synthesis=False,
    )
    assert result.status is TechnicalDebtSynthesisStatus.NOT_REQUESTED
    assert result.conclusions == ()
