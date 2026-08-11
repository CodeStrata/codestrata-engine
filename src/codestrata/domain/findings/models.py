"""Immutable Phase 3 finding models produced by the Rule Engine."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.findings.enums import FindingCategory, FindingSeverity, FindingSource
from codestrata.domain.findings.finding_confidence import FindingConfidence
from codestrata.domain.findings.ids import build_finding_id
from codestrata.domain.findings.severity import FindingSeverityAssessment
from codestrata.domain.graph.ids import NodeId
from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.traceability import EvidenceCompleteness, EvidenceRef, TraceabilityValidationError
from codestrata.domain.traceability.validators import normalize_limitations, sorted_unique_ids


class FindingEvidence(BaseModel):
    """Explainable evidence supporting a graph-rule finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_type: str
    source_id: str
    path: str | None = None
    excerpt: str | None = None
    node_id: NodeId | None = None

    @field_validator("evidence_type", "source_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="finding evidence field")

    @field_validator("path", "excerpt", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional finding evidence field")


class Finding(BaseModel):
    """One deterministic Assessment-Graph rule finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    rule_id: str
    title: str
    description: str
    severity: FindingSeverity
    category: FindingCategory
    source: FindingSource = FindingSource.RULE
    evidence: tuple[FindingEvidence, ...] = ()
    affected_assessment_node_ids: tuple[NodeId, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Additive Epic 2 Slice 2.2 — EvidenceRef traceability (not part of finding ID).
    evidence_refs: tuple[EvidenceRef, ...] = ()
    primary_evidence_id: str | None = None
    synthesized_from_evidence_ids: tuple[str, ...] = ()
    evidence_completeness: EvidenceCompleteness = EvidenceCompleteness.LEGACY
    limitations: tuple[str, ...] = ()
    # Epic 5 Slice 5.3 — Finding Confidence (not severity; not Match Evidence Confidence).
    finding_confidence: FindingConfidence = Field(
        default_factory=lambda: FindingConfidence.unavailable(
            limitations=("Legacy Finding payload omitted finding_confidence.",),
        )
    )
    # Epic 5 Slice 5.12 — cross-rule correlation references (not Finding ID material).
    correlation_ids: tuple[str, ...] = ()
    correlated_finding_ids: tuple[str, ...] = ()
    # Epic 5 Slice 5.13 — severity calibration (not Finding ID material).
    base_severity: FindingSeverity | None = None
    severity_assessment: FindingSeverityAssessment | None = None

    @field_validator("id", "rule_id", "title", "description", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="finding field")

    @field_validator(
        "evidence",
        "affected_assessment_node_ids",
        "evidence_refs",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @field_validator(
        "synthesized_from_evidence_ids",
        "correlation_ids",
        "correlated_finding_ids",
        mode="before",
    )
    @classmethod
    def normalize_synthesized(cls, value: object) -> tuple[str, ...]:
        return sorted_unique_ids(value, label="finding id ref")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limits(cls, value: object) -> tuple[str, ...]:
        return normalize_limitations(value)

    @field_validator("primary_evidence_id", mode="before")
    @classmethod
    def normalize_primary(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="primary_evidence_id")

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("metadata must be a mapping")
        return dict(value)

    @field_validator("finding_confidence", mode="before")
    @classmethod
    def normalize_finding_confidence(cls, value: object) -> object:
        if value is None:
            return FindingConfidence.unavailable(
                limitations=("Legacy Finding payload omitted finding_confidence.",),
            )
        if isinstance(value, FindingConfidence):
            return value
        if isinstance(value, Mapping):
            return FindingConfidence.model_validate(dict(value))
        return value

    @field_validator("severity_assessment", mode="before")
    @classmethod
    def normalize_severity_assessment(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, FindingSeverityAssessment):
            return value
        if isinstance(value, Mapping):
            return FindingSeverityAssessment.model_validate(dict(value))
        return value

    @model_validator(mode="after")
    def validate_traceability(self) -> Finding:
        ref_ids = {item.evidence_id for item in self.evidence_refs}
        if self.primary_evidence_id is not None and self.primary_evidence_id not in ref_ids:
            raise TraceabilityValidationError(
                "primary_evidence_id must reference an evidence_refs entry"
            )
        if not self.evidence_refs and self.synthesized_from_evidence_ids:
            raise TraceabilityValidationError(
                "synthesized_from_evidence_ids requires evidence_refs"
            )
        for parent_id in self.synthesized_from_evidence_ids:
            if parent_id not in ref_ids:
                raise TraceabilityValidationError(
                    "synthesized_from_evidence_ids must reference evidence_refs "
                    f"(unknown id: {parent_id})"
                )
        if self.id in self.correlated_finding_ids:
            raise TraceabilityValidationError(
                "correlated_finding_ids must not include self-reference"
            )
        return self

    @classmethod
    def create(
        cls,
        *,
        rule_id: str,
        title: str,
        description: str,
        severity: FindingSeverity,
        category: FindingCategory,
        evidence: Sequence[FindingEvidence] = (),
        affected_assessment_node_ids: Sequence[NodeId] = (),
        metadata: Mapping[str, Any] | None = None,
        subject_keys: Sequence[str] = (),
        evidence_refs: Sequence[EvidenceRef] = (),
        primary_evidence_id: str | None = None,
        synthesized_from_evidence_ids: Sequence[str] = (),
        evidence_completeness: EvidenceCompleteness = EvidenceCompleteness.LEGACY,
        limitations: Sequence[str] = (),
        finding_confidence: FindingConfidence | None = None,
        base_severity: FindingSeverity | None = None,
        severity_assessment: FindingSeverityAssessment | None = None,
    ) -> Finding:
        """Construct a finding with a deterministic identity.

        Traceability and severity-assessment fields are additive and are never
        included in finding ID material (``rule_id`` + ``subject_keys`` only).
        """

        node_ids = tuple(affected_assessment_node_ids)
        subjects = tuple(subject_keys) or tuple(node.root for node in node_ids)
        return cls(
            id=build_finding_id(rule_id=rule_id, subject_keys=subjects),
            rule_id=rule_id,
            title=title,
            description=description,
            severity=severity,
            category=category,
            source=FindingSource.RULE,
            evidence=tuple(evidence),
            affected_assessment_node_ids=node_ids,
            metadata=dict(metadata or {}),
            evidence_refs=tuple(evidence_refs),
            primary_evidence_id=primary_evidence_id,
            synthesized_from_evidence_ids=tuple(synthesized_from_evidence_ids),
            evidence_completeness=evidence_completeness,
            limitations=tuple(limitations),
            finding_confidence=finding_confidence
            or FindingConfidence.unavailable(
                limitations=("Finding confidence was not derived for this Finding.",),
            ),
            base_severity=base_severity,
            severity_assessment=severity_assessment,
        )

class RuleEvaluationResult(BaseModel):
    """Aggregated deterministic output of one Rule Engine execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    findings: tuple[Finding, ...] = ()
    rules_evaluated: tuple[str, ...] = ()
    rules_skipped: tuple[str, ...] = ()
    finding_count: int = Field(ge=0)

    @field_validator("findings", "rules_evaluated", "rules_skipped", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @classmethod
    def from_findings(
        cls,
        *,
        findings: Sequence[Finding],
        rules_evaluated: Sequence[str],
        rules_skipped: Sequence[str] = (),
    ) -> RuleEvaluationResult:
        ordered = tuple(sorted(findings, key=lambda item: (item.rule_id, item.id, item.title)))
        evaluated = tuple(
            sorted({require_nonblank(item, label="rule_id") for item in rules_evaluated})
        )
        skipped = tuple(sorted({require_nonblank(item, label="rule_id") for item in rules_skipped}))
        return cls(
            findings=ordered,
            rules_evaluated=evaluated,
            rules_skipped=skipped,
            finding_count=len(ordered),
        )
