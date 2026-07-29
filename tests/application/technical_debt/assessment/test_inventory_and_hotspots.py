"""Phase 4.3.4A inventory, hotspot, and status-semantics tests."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.evidence.language.adapters import classify_source_path
from codestrata.application.technical_debt.assessment.assembler import (
    TechnicalDebtAssessmentAssembler,
)
from codestrata.application.technical_debt.assessment.inventory import (
    build_finding_inventory,
    build_finding_references,
    build_hotspot_inventory,
    map_source_role,
    material_production_parse_failures,
)
from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.domain.findings import Finding
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.technical_debt.assessment.enums import (
    TechnicalDebtAssessmentStatus,
    TechnicalDebtSourceRole,
)
from codestrata.domain.technical_debt.ids import (
    RULE_EXCESSIVE_BRANCHING,
    RULE_LARGE_CALLABLE,
)


def _finding(
    *,
    rule_id: str,
    path: str,
    symbol: str,
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
        },
    )


def test_petclinic_path_roles() -> None:
    main = "src/main/java/org/springframework/samples/petclinic/owner/OwnerController.java"
    test = "src/test/java/org/springframework/samples/petclinic/system/I18nPropertiesSyncTest.java"
    assert classify_source_path(main) is SourceClassification.SOURCE
    assert classify_source_path(test) is SourceClassification.TEST
    assert map_source_role("source", path=main) is TechnicalDebtSourceRole.PRODUCTION
    assert map_source_role("test", path=test) is TechnicalDebtSourceRole.TEST


def test_inventory_separates_production_and_test() -> None:
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
    refs = build_finding_references(findings)
    inventory = build_finding_inventory(refs)
    hotspots = build_hotspot_inventory(refs)
    assert inventory.production.finding_count == 2
    assert inventory.test.finding_count == 1
    assert inventory.overlapping_source_unit_count == 1
    assert len(hotspots.production) == 1
    hotspot = hotspots.production[0]
    assert hotspot.finding_count == 2
    assert set(hotspot.rule_ids) == {RULE_LARGE_CALLABLE, RULE_EXCESSIVE_BRANCHING}
    assert hotspot.highest_severity == "high"
    assert hotspot.source_role is TechnicalDebtSourceRole.PRODUCTION

    section = TechnicalDebtAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=findings,
        pack_enabled=True,
        complexity_evidence_enabled=True,
        files_considered=2,
        files_analyzed=2,
    )
    assert section.finding_ids == inventory.production.finding_ids
    assert len(section.all_finding_ids) == 3
    assert section.execution_summary.production_finding_count == 2
    assert section.execution_summary.test_finding_count == 1
    assert section.execution_summary.total_finding_count == 3
    assert section.execution_summary.visible_finding_count == 2
    assert section.hotspot_inventory.production[0].hotspot_id == hotspot.hotspot_id


def test_fixture_parse_failure_does_not_partially_succeed() -> None:
    diagnostics = (
        "python_syntax_error:tests/application/evidence/language/complexity/"
        "fixtures/python/unsupported_syntax.py:'(' was never closed",
    )
    assert material_production_parse_failures(diagnostics) == 0
    section = TechnicalDebtAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=(),
        pack_enabled=True,
        complexity_evidence_enabled=True,
        files_considered=10,
        files_analyzed=10,
        files_failed=1,
        diagnostics=diagnostics,
    )
    assert section.status is TechnicalDebtAssessmentStatus.SUCCEEDED
    assert section.execution_summary.provider_failures == 0
    assert section.execution_summary.files_parse_failed == 1
    assert any("non_material_parse_failures" in item for item in section.diagnostics)


def test_production_parse_failure_is_partial() -> None:
    diagnostics = ("python_syntax_error:src/codestrata/broken.py:invalid syntax",)
    assert material_production_parse_failures(diagnostics) == 1
    section = TechnicalDebtAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=(),
        pack_enabled=True,
        complexity_evidence_enabled=True,
        files_considered=2,
        files_analyzed=2,
        files_failed=1,
        diagnostics=diagnostics,
    )
    assert section.status is TechnicalDebtAssessmentStatus.PARTIALLY_SUCCEEDED
    assert section.execution_summary.provider_failures == 1


def test_hotspot_ordering_deterministic() -> None:
    findings = (
        _finding(
            rule_id=RULE_LARGE_CALLABLE,
            path="src/b.py",
            symbol="b#0@1",
            severity=FindingSeverity.MEDIUM,
            value="60",
        ),
        _finding(
            rule_id=RULE_LARGE_CALLABLE,
            path="src/a.py",
            symbol="a#0@1",
            severity=FindingSeverity.HIGH,
            value="120",
        ),
        _finding(
            rule_id=RULE_EXCESSIVE_BRANCHING,
            path="src/a.py",
            symbol="a#0@1",
            severity=FindingSeverity.MEDIUM,
            metric="branch_point_count",
            value="11",
            threshold="10",
        ),
    )
    first = build_hotspot_inventory(build_finding_references(findings))
    second = build_hotspot_inventory(build_finding_references(tuple(reversed(findings))))
    assert [item.hotspot_id for item in first.production] == [
        item.hotspot_id for item in second.production
    ]
    assert first.production[0].path == "src/a.py"
    assert first.production[0].highest_severity == "high"


def test_generated_paths_are_unknown_not_production() -> None:
    assert (
        map_source_role("generated", path="src/generated/Foo.java")
        is TechnicalDebtSourceRole.UNKNOWN
    )
    assert (
        map_source_role(None, path="target/generated/sources/Foo.java")
        is TechnicalDebtSourceRole.UNKNOWN
    )


def test_section_round_trip_includes_inventory(tmp_path: Path) -> None:
    from codestrata.application.technical_debt.assessment.artifacts import (
        write_technical_debt_assessment_artifact,
    )
    from codestrata.domain.technical_debt.assessment.models import TechnicalDebtAssessmentSection
    from codestrata.services.artifact_serialization import loads_stable_json

    findings = (
        _finding(
            rule_id=RULE_LARGE_CALLABLE,
            path="src/main/java/Demo.java",
            symbol="Demo#0@1",
            classification="source",
        ),
        _finding(
            rule_id=RULE_LARGE_CALLABLE,
            path="src/test/java/DemoTest.java",
            symbol="DemoTest#0@1",
            classification="test",
        ),
    )
    section = TechnicalDebtAssessmentAssembler().assemble(
        repository_id="repo:petclinic",
        findings=findings,
        pack_enabled=True,
        complexity_evidence_enabled=True,
        files_considered=2,
        files_analyzed=2,
        configuration_payload="stable",
    )
    written = write_technical_debt_assessment_artifact(section, tmp_path)
    restored = TechnicalDebtAssessmentSection.model_validate(
        loads_stable_json(written.path.read_text(encoding="utf-8"))
    )
    assert restored == section
    assert written.finding_count == 1
    assert restored.finding_inventory.production.finding_count == 1
    assert restored.finding_inventory.test.finding_count == 1
