"""Tests for Finding additive EvidenceRef fields (Slice 2.2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.domain.findings import (
    Finding,
    FindingCategory,
    FindingEvidence,
    FindingSeverity,
    build_finding_id,
)
from codestrata.domain.traceability import (
    EvidenceCompleteness,
    EvidenceLocation,
    EvidenceRef,
    SnippetRedactionLevel,
    RedactedSnippet,
)


def _base_kwargs(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "rule_id": "security.credential-literal",
        "title": "Literal credential",
        "description": "Found credential",
        "severity": FindingSeverity.HIGH,
        "category": FindingCategory.SECURITY,
        "subject_keys": ("path:.env", "ev:abc"),
    }
    payload.update(overrides)
    return payload


def test_empty_evidence_refs_backward_compatible() -> None:
    finding = Finding.create(**_base_kwargs())  # type: ignore[arg-type]
    assert finding.evidence_refs == ()
    assert finding.primary_evidence_id is None
    assert finding.evidence_completeness is EvidenceCompleteness.LEGACY


def test_immutable_evidence_refs_accepted() -> None:
    ref = EvidenceRef(
        evidence_id="ev:abc",
        location=EvidenceLocation(path="config/.env"),
    )
    finding = Finding.create(**_base_kwargs(evidence_refs=(ref,), primary_evidence_id="ev:abc"))  # type: ignore[arg-type]
    assert finding.evidence_refs[0].evidence_id == "ev:abc"


def test_primary_must_exist_in_evidence_refs() -> None:
    ref = EvidenceRef(evidence_id="ev:abc")
    with pytest.raises(ValidationError, match="primary_evidence_id"):
        Finding.create(
            **_base_kwargs(
                evidence_refs=(ref,),
                primary_evidence_id="ev:missing",
            )
        )  # type: ignore[arg-type]


def test_synthesized_ids_sorted_unique() -> None:
    refs = (
        EvidenceRef(evidence_id="ev:b"),
        EvidenceRef(evidence_id="ev:a"),
    )
    finding = Finding.create(
        **_base_kwargs(
            evidence_refs=refs,
            primary_evidence_id="ev:a",
            synthesized_from_evidence_ids=("ev:b", "ev:a", "ev:b"),
            evidence_completeness=EvidenceCompleteness.COMPLETE,
        )
    )  # type: ignore[arg-type]
    assert finding.synthesized_from_evidence_ids == ("ev:a", "ev:b")


def test_finding_id_unchanged_with_traceability_populated() -> None:
    subjects = ("path:src/a.py", "ev:1")
    without = Finding.create(**_base_kwargs(subject_keys=subjects))  # type: ignore[arg-type]
    ref = EvidenceRef(
        evidence_id="ev:1",
        location=EvidenceLocation(path="src/a.py"),
        snippet=RedactedSnippet(
            text="password=***",
            redaction_level=SnippetRedactionLevel.PARTIALLY_REDACTED,
        ),
    )
    with_refs = Finding.create(
        **_base_kwargs(
            subject_keys=subjects,
            evidence_refs=(ref,),
            primary_evidence_id="ev:1",
            evidence_completeness=EvidenceCompleteness.COMPLETE,
            limitations=("note",),
            evidence=(
                FindingEvidence(
                    evidence_type="configuration_key",
                    source_id="ev:1",
                    path="src/a.py",
                    excerpt="credential",
                ),
            ),
        )
    )  # type: ignore[arg-type]
    assert without.id == with_refs.id
    assert without.id == build_finding_id(
        rule_id="security.credential-literal",
        subject_keys=subjects,
    )
