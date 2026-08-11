"""Tests for EvidenceRef ordering, dedupe, and serialization."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.domain.traceability import (
    EvidenceKind,
    EvidenceLocation,
    EvidenceMeasurement,
    EvidenceProductionMode,
    EvidenceRef,
    MeasurementValueType,
    RedactedSnippet,
    SnippetRedactionLevel,
    TraceabilityValidationError,
    dedupe_evidence_refs,
    evidence_ref_from_stable_dict,
    evidence_ref_to_stable_dict,
    order_evidence_refs,
)


def _minimal(evidence_id: str = "ev:abc") -> EvidenceRef:
    return EvidenceRef(evidence_id=evidence_id)


def test_minimal_valid_envelope() -> None:
    ref = _minimal()
    assert ref.production_mode is EvidenceProductionMode.DIRECT
    assert ref.parent_evidence_ids == ()


def test_complete_valid_envelope() -> None:
    ref = EvidenceRef(
        evidence_id="ev:complete",
        kind=EvidenceKind.MEASUREMENT,
        production_mode=EvidenceProductionMode.DIRECT,
        pack_id="technical_debt",
        provider_id="language.java.core",
        provider_version="1.0.0",
        rule_id="technical_debt.complexity.high",
        rule_version="1.0.0",
        location=EvidenceLocation(path="src/A.java", line_start=1, line_end=2),
        snippet=RedactedSnippet(
            text="int x = 0;",
            redaction_level=SnippetRedactionLevel.SAFE_NONSENSITIVE,
        ),
        measurement=EvidenceMeasurement.available(
            metric_id="complexity.cyclomatic",
            metric_name="cyclomatic",
            measured_value=12,
            value_type=MeasurementValueType.INTEGER,
            threshold=10,
            threshold_operator="gt",
            comparison_result="fails",
        ),
        parent_evidence_ids=("ev:parent-b", "ev:parent-a"),
        domain_type="CallableComplexityEvidence",
        domain_ref="ev:complete",
        confidence="high",
        limitations=("heuristic",),
        source_artifact="complexity-evidence.json",
    )
    assert ref.parent_evidence_ids == ("ev:parent-a", "ev:parent-b")


def test_self_parent_rejection() -> None:
    with pytest.raises(ValidationError, match="itself"):
        EvidenceRef(evidence_id="ev:1", parent_evidence_ids=("ev:1",))


def test_duplicate_parent_normalization() -> None:
    ref = EvidenceRef(
        evidence_id="ev:1",
        parent_evidence_ids=("ev:b", "ev:a", "ev:b"),
    )
    assert ref.parent_evidence_ids == ("ev:a", "ev:b")


def test_deterministic_ordering() -> None:
    items = (
        EvidenceRef(
            evidence_id="ev:b",
            production_mode=EvidenceProductionMode.DIRECT,
            location=EvidenceLocation(path="z.py"),
        ),
        EvidenceRef(
            evidence_id="ev:a",
            production_mode=EvidenceProductionMode.LEGACY,
        ),
        EvidenceRef(
            evidence_id="ev:a",
            production_mode=EvidenceProductionMode.DIRECT,
            location=EvidenceLocation(path="a.py"),
        ),
    )
    ordered = order_evidence_refs(items)
    # production_mode rank first, then evidence_id, then path.
    assert [item.evidence_id for item in ordered] == ["ev:a", "ev:b", "ev:a"]
    assert ordered[0].production_mode is EvidenceProductionMode.DIRECT
    assert ordered[1].production_mode is EvidenceProductionMode.DIRECT
    assert ordered[2].production_mode is EvidenceProductionMode.LEGACY


def test_deterministic_deduplication_prefers_richer() -> None:
    thin = EvidenceRef(evidence_id="ev:1", kind=EvidenceKind.OTHER)
    rich = EvidenceRef(
        evidence_id="ev:1",
        kind=EvidenceKind.OTHER,
        location=EvidenceLocation(path="src/a.py"),
        snippet=RedactedSnippet(
            text="ok",
            redaction_level=SnippetRedactionLevel.SAFE_NONSENSITIVE,
        ),
        parent_evidence_ids=("ev:p1",),
        pack_id="security",
    )
    other = EvidenceRef(
        evidence_id="ev:2",
        production_mode=EvidenceProductionMode.SYNTHESIZED,
    )
    result = dedupe_evidence_refs((thin, other, rich))
    assert [item.evidence_id for item in result] == ["ev:1", "ev:2"]
    kept = result[0]
    assert kept.location is not None
    assert kept.snippet is not None
    assert kept.pack_id == "security"
    assert kept.parent_evidence_ids == ("ev:p1",)


def test_dedupe_merges_nonconflicting_parents_and_limitations() -> None:
    left = EvidenceRef(
        evidence_id="ev:1",
        location=EvidenceLocation(path="a.py"),
        parent_evidence_ids=("ev:p1",),
        limitations=("a",),
    )
    right = EvidenceRef(
        evidence_id="ev:1",
        parent_evidence_ids=("ev:p2",),
        limitations=("b",),
        confidence="medium",
    )
    result = dedupe_evidence_refs((left, right))
    assert len(result) == 1
    assert result[0].parent_evidence_ids == ("ev:p1", "ev:p2")
    assert result[0].limitations == ("a", "b")
    assert result[0].confidence == "medium"
    assert result[0].location is not None


def test_dedupe_merges_same_evidence_id_different_rule_id() -> None:
    left = EvidenceRef(
        evidence_id="ev:1",
        rule_id="security.credential-literal",
        location=EvidenceLocation(path="config/app.properties"),
    )
    right = EvidenceRef(
        evidence_id="ev:1",
        rule_id="security.placeholder-credential",
        confidence="medium",
    )
    result = dedupe_evidence_refs((left, right))
    assert len(result) == 1
    assert result[0].rule_id == "security.credential-literal"
    assert result[0].confidence == "medium"
    assert result[0].location is not None


def test_contradictory_duplicate_rejection() -> None:
    left = EvidenceRef(
        evidence_id="ev:1",
        pack_id="security",
        location=EvidenceLocation(path="a.py"),
    )
    right = EvidenceRef(
        evidence_id="ev:1",
        pack_id="dependency",
        snippet=RedactedSnippet(
            text="x",
            redaction_level=SnippetRedactionLevel.SAFE_NONSENSITIVE,
        ),
    )
    with pytest.raises(TraceabilityValidationError, match="contradictory"):
        dedupe_evidence_refs((left, right))


def test_stable_serialization_round_trip() -> None:
    ref = EvidenceRef(
        evidence_id="ev:round",
        kind=EvidenceKind.FILE_LOCATION,
        location=EvidenceLocation(path="src/x.py", line_start=3, line_end=3),
        snippet=RedactedSnippet(
            text="return 1",
            redaction_level=SnippetRedactionLevel.SAFE_NONSENSITIVE,
        ),
        parent_evidence_ids=("ev:p",),
    )
    payload = evidence_ref_to_stable_dict(ref)
    assert list(payload.keys()) == sorted(payload.keys())
    assert "provider_id" not in payload
    restored = evidence_ref_from_stable_dict(payload)
    assert restored == ref


def test_rejects_blank_evidence_id() -> None:
    with pytest.raises(ValidationError):
        EvidenceRef(evidence_id="  ")
