"""Architecture conclusion domain and pipeline tests."""

from __future__ import annotations

from codestrata.application.architecture.conclusions.clustering import cluster_findings
from codestrata.application.architecture.conclusions.factory import (
    create_architecture_conclusion_service,
)
from codestrata.application.architecture.conclusions.relationships import (
    build_finding_relationships,
)
from codestrata.domain.architecture.conclusions.identifiers import (
    POLICY_BOUNDARY_INTEGRITY,
    build_conclusion_id,
)
from codestrata.domain.findings import Finding
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.rules.architecture.ids import (
    RULE_DEPENDENCY_CYCLE,
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
    RULE_INVALID_DEPENDENCY_DIRECTION,
)


def _finding(
    rule_id: str,
    *subjects: str,
    severity: FindingSeverity = FindingSeverity.MEDIUM,
) -> Finding:
    return Finding.create(
        rule_id=rule_id,
        title=rule_id,
        description=f"{rule_id} observation",
        severity=severity,
        category=FindingCategory.ARCHITECTURE,
        subject_keys=subjects,
        metadata={
            "confidence": "high",
            "subject_keys": ",".join(subjects),
            "remediation": f"Fix {rule_id}",
            "business_impact": "unknown",
        },
    )


def test_conclusion_id_deterministic() -> None:
    left = build_conclusion_id(
        policy_id=POLICY_BOUNDARY_INTEGRITY,
        policy_version="1.0.0",
        repository_id="repo:demo",
        affected_scope=("codestrata.application", "codestrata.infrastructure"),
        source_finding_ids=("finding:a", "finding:b"),
    )
    right = build_conclusion_id(
        policy_id=POLICY_BOUNDARY_INTEGRITY,
        policy_version="1.0.0",
        repository_id="repo:demo",
        affected_scope=("codestrata.infrastructure", "codestrata.application"),
        source_finding_ids=("finding:b", "finding:a"),
    )
    assert left == right


def test_cycle_and_direction_relate_and_cluster() -> None:
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
            severity=FindingSeverity.MEDIUM,
        ),
    )
    relationships = build_finding_relationships(findings)
    assert any(
        item.reason_code == "cycle_and_direction_same_boundary" for item in relationships
    )
    clusters = cluster_findings(findings, relationships)
    assert len(clusters) >= 2
    boundary = [item for item in clusters if "boundary" in item.category]
    coupling = [item for item in clusters if "coupling" in item.category]
    assert boundary
    assert coupling


def test_service_option_a_two_conclusions() -> None:
    findings = (
        _finding(
            RULE_DEPENDENCY_CYCLE,
            "codestrata.application",
            "codestrata.infrastructure",
            "cycle",
            severity=FindingSeverity.HIGH,
        ),
        _finding(
            RULE_INVALID_DEPENDENCY_DIRECTION,
            "codestrata.application",
            "codestrata.infrastructure",
            "application",
            "infrastructure",
            severity=FindingSeverity.MEDIUM,
        ),
        _finding(
            RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
            "codestrata.application",
            "out:10",
            severity=FindingSeverity.MEDIUM,
        ),
    )
    service = create_architecture_conclusion_service()
    result = service.build(
        repository_id="repo:codestrata",
        findings=findings,
        classification_coverage=0.3,
        extraction_coverage=1.0,
    )
    assert result.enabled is True
    categories = {item.category for item in result.conclusions}
    assert "architecture.boundary-integrity" in categories
    assert "architecture.coupling" in categories
    # Underlying findings unchanged — conclusions only reference IDs.
    assert all(len(item.source_finding_ids) >= 1 for item in result.conclusions)
    assert all(item.business_impact == "unknown" for item in result.conclusions)
    assert result.recommendation_groups
    # Adding unrelated finding must not change existing conclusion IDs for same sources.
    first_ids = {item.conclusion_id for item in result.conclusions}
    extra = findings + (
        _finding(
            "architecture.framework-leakage",
            "other.unit",
            "jpa",
            "@Entity",
            "src/x.java",
        ),
    )
    second = service.build(
        repository_id="repo:codestrata",
        findings=extra,
        classification_coverage=0.3,
        extraction_coverage=1.0,
    )
    assert first_ids.issubset({item.conclusion_id for item in second.conclusions})


def test_registry_lists_policies() -> None:
    service = create_architecture_conclusion_service()
    rows = service.list_policies()
    ids = [row["policy_id"] for row in rows]
    assert ids == sorted(ids)
    assert "architecture.conclusion.boundary-integrity" in ids
