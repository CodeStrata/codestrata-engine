"""Tests for Phase 3 finding domain models."""

from __future__ import annotations

from codestrata.domain.findings import (
    Finding,
    FindingCategory,
    FindingEvidence,
    FindingSeverity,
    FindingSource,
    build_finding_id,
)


def test_finding_id_is_deterministic() -> None:
    first = build_finding_id(
        rule_id="codestrata-rule-missing-readme",
        subject_keys=("repo", "readme"),
    )
    second = build_finding_id(
        rule_id="codestrata-rule-missing-readme",
        subject_keys=("readme", "repo"),
    )
    assert first == second
    assert first.startswith("finding:codestrata-rule-missing-readme:")


def test_finding_create_round_trip() -> None:
    finding = Finding.create(
        rule_id="codestrata-rule-missing-license",
        title="Missing LICENSE",
        description="No license file.",
        severity=FindingSeverity.MEDIUM,
        category=FindingCategory.GOVERNANCE,
        evidence=(
            FindingEvidence(
                evidence_type="repository_manifest",
                source_id="demo",
                excerpt="missing",
            ),
        ),
        subject_keys=("demo", "license"),
    )
    assert finding.source is FindingSource.RULE
    restored = Finding.model_validate(finding.model_dump(mode="json"))
    assert restored == finding
