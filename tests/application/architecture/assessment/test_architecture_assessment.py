"""Architecture assessment section assembly tests (Phase 4.2.4)."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.application.architecture.assessment.artifacts import (
    write_architecture_assessment_artifact,
)
from codestrata.application.architecture.assessment.assembler import (
    ArchitectureAssessmentAssembler,
)
from codestrata.application.architecture.conclusions.factory import (
    create_architecture_conclusion_service,
)
from codestrata.domain.architecture.assessment.enums import (
    ArchitectureAssessmentStatus,
    CoverageAreaStatus,
)
from codestrata.domain.architecture.assessment.identifiers import (
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
)
from codestrata.domain.architecture.assessment.models import ArchitectureAssessmentSection
from codestrata.domain.findings import Finding
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.rules.architecture.ids import (
    RULE_DEPENDENCY_CYCLE,
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
    RULE_INVALID_DEPENDENCY_DIRECTION,
)
from codestrata.services.artifact_serialization import dumps_stable_json, loads_stable_json


def _finding(rule_id: str, *subjects: str) -> Finding:
    return Finding.create(
        rule_id=rule_id,
        title=rule_id,
        description=f"{rule_id} observation",
        severity=FindingSeverity.MEDIUM,
        category=FindingCategory.ARCHITECTURE,
        subject_keys=subjects,
        metadata={
            "confidence": "high",
            "subject_keys": ",".join(subjects),
            "remediation": f"Fix {rule_id}",
            "business_impact": "unknown",
        },
    )


def test_section_id_and_version_stable() -> None:
    section = ArchitectureAssessmentAssembler().assemble_disabled(
        repository_id="repo:demo"
    )
    assert section.section_id == SECTION_ID
    assert section.section_version == SECTION_SCHEMA_VERSION
    assert section.status is ArchitectureAssessmentStatus.DISABLED


def test_assemble_findings_and_conclusions_option_a(tmp_path: Path) -> None:
    findings = (
        _finding(
            RULE_DEPENDENCY_CYCLE,
            "codestrata.application",
            "codestrata.infrastructure",
            "cycle",
        ),
        _finding(
            RULE_INVALID_DEPENDENCY_DIRECTION,
            "codestrata.application",
            "codestrata.infrastructure",
            "application",
            "infrastructure",
        ),
        _finding(
            RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
            "codestrata.application",
            "out:10",
        ),
    )
    conclusions = create_architecture_conclusion_service().build(
        repository_id="repo:demo",
        findings=findings,
        extraction_coverage=1.0,
        classification_coverage=0.5,
        graph_fingerprint="fp-demo",
    )
    section = ArchitectureAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=findings,
        conclusion_result=conclusions,
        pack_enabled=True,
        conclusions_enabled=True,
        extraction_coverage=1.0,
        classification_coverage=0.5,
        graph_fingerprint="fp-demo",
    )
    assert section.status is ArchitectureAssessmentStatus.SUCCEEDED
    assert len(section.finding_ids) == 3
    assert len(section.conclusions) == 2
    assert len(section.recommendation_groups) == 2
    assert section.strengths == ()
    assert section.business_impact == "unknown"
    assert any(
        item.category.value == "static-analysis-only" for item in section.limitations
    )
    assert section.traceability.edge_count > 0
    extraction = next(
        area for area in section.coverage.areas if area.area_id == "extraction_coverage"
    )
    assert extraction.status is CoverageAreaStatus.MEASURED
    assert extraction.ratio == 1.0

    write = write_architecture_assessment_artifact(section, tmp_path)
    loaded = loads_stable_json(write.path.read_text(encoding="utf-8"))
    assert loaded["section_id"] == SECTION_ID
    assert loaded["finding_ids"] == list(section.finding_ids)
    # Round-trip through pydantic.
    restored = ArchitectureAssessmentSection.model_validate(loaded)
    assert restored.finding_ids == section.finding_ids
    assert restored.conclusion_ids == section.conclusion_ids


def test_findings_only_when_conclusions_disabled() -> None:
    findings = (
        _finding(
            RULE_DEPENDENCY_CYCLE,
            "codestrata.application",
            "codestrata.infrastructure",
            "cycle",
        ),
    )
    section = ArchitectureAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=findings,
        conclusion_result=None,
        pack_enabled=True,
        conclusions_enabled=False,
        extraction_coverage=0.9,
        classification_coverage=0.4,
    )
    assert section.status is ArchitectureAssessmentStatus.SUCCEEDED
    assert len(section.finding_ids) == 1
    assert section.conclusions == ()
    assert section.recommendation_groups == ()
    assert any(
        "conclusions" in item.summary.lower() for item in section.limitations
    )


def test_deterministic_serialization() -> None:
    section = ArchitectureAssessmentAssembler().assemble_disabled(
        repository_id="repo:demo"
    )
    left = dumps_stable_json(section.model_dump(mode="json"))
    right = dumps_stable_json(section.model_dump(mode="json"))
    assert left == right
    assert json.loads(left)["status"] == "disabled"


def test_severity_preserved_on_finding_references() -> None:
    finding = _finding(RULE_DEPENDENCY_CYCLE, "codestrata.application", "cycle")
    section = ArchitectureAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=(finding,),
        pack_enabled=True,
        conclusions_enabled=False,
        extraction_coverage=1.0,
        classification_coverage=0.5,
    )
    assert section.finding_summaries[0].severity == finding.severity.value
    assert section.finding_summaries[0].finding_id == finding.id
