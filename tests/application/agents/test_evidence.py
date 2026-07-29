"""Evidence model tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.application.agents.evidence import (
    AgentEvidence,
    EvidenceSourceKind,
    dedupe_evidence,
    evidence_id_for,
)


def test_evidence_requires_stable_fields() -> None:
    item = AgentEvidence(
        evidence_id=evidence_id_for(EvidenceSourceKind.FINDING, "finding:rule:abc"),
        evidence_type="finding",
        source_id="finding:rule:abc",
        source_kind=EvidenceSourceKind.FINDING,
        title="Demo",
        summary="medium/architecture",
        related_ids=("run-1",),
        deterministic=True,
    )
    assert item.source_kind is EvidenceSourceKind.FINDING
    assert item.deterministic is True


def test_blank_evidence_rejected() -> None:
    with pytest.raises(ValidationError):
        AgentEvidence(
            evidence_id=" ",
            evidence_type="finding",
            source_id="x",
            source_kind=EvidenceSourceKind.FINDING,
            title="t",
            summary="s",
        )


def test_evidence_deduplication_preserves_order_by_kind() -> None:
    a = AgentEvidence(
        evidence_id="evidence:finding:a",
        evidence_type="finding",
        source_id="a",
        source_kind=EvidenceSourceKind.FINDING,
        title="A",
        summary="A",
    )
    b = AgentEvidence(
        evidence_id="evidence:finding:a",
        evidence_type="finding",
        source_id="a",
        source_kind=EvidenceSourceKind.FINDING,
        title="A duplicate",
        summary="A",
    )
    c = AgentEvidence(
        evidence_id="evidence:recommendation:r",
        evidence_type="recommendation",
        source_id="r",
        source_kind=EvidenceSourceKind.RECOMMENDATION,
        title="R",
        summary="R",
    )
    deduped = dedupe_evidence([c, a, b])
    assert len(deduped) == 2
    assert {item.evidence_id for item in deduped} == {
        "evidence:finding:a",
        "evidence:recommendation:r",
    }


def test_evidence_has_no_blob_or_credential_fields() -> None:
    fields = set(AgentEvidence.model_fields)
    assert "blob_path" not in fields
    assert "password" not in fields
    assert "aws_profile" not in fields
    assert "source_code" not in fields
