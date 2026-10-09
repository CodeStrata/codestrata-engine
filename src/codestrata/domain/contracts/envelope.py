"""Canonical assessment envelope: deterministic body vs operational metadata."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from codestrata.domain.contracts.enums import CoverageState, FreshnessState
from codestrata.domain.contracts.facts import EvidenceRecord, FactRecord, FindingRecord, GraphRecord
from codestrata.domain.contracts.hotspot import (
    ChangeSummary,
    EngineeringHotspot,
    OwnershipConcentration,
)
from codestrata.domain.contracts.serialization import (
    digest_canonical,
    dumps_canonical,
    require_supported_major,
    walk_forbidden_identity,
)
from codestrata.domain.graph.validation import as_tuple, require_nonblank

ENVELOPE_SCHEMA = "codestrata.canonical-envelope.v1"
ENVELOPE_VERSION = "1.0.0"


class EnvelopeError(ValueError):
    """Unsupported, unknown-field or corrupt canonical envelope."""


class CapabilityCoverage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.capability-coverage.v1"
    schema_version: str = "1.0.0"
    capability_id: str
    capability_version: str
    scope: str
    applicability: str
    execution_state: CoverageState
    evaluated_count: int | None = Field(default=None, ge=0)
    eligible_count: int | None = Field(default=None, ge=0)
    unknown_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    excluded_count: int = Field(default=0, ge=0)
    coverage_ratio: str | None = None
    coverage_reason: str | None = None
    evidence_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    @field_validator("capability_id", "capability_version", "scope", "applicability", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="coverage field")

    @model_validator(mode="after")
    def unknown_denominator_not_percent(self) -> CapabilityCoverage:
        if self.eligible_count is None:
            if self.coverage_ratio is not None:
                raise ValueError("unknown denominator never serializes 0% or 100%")
            if self.coverage_reason is None:
                raise ValueError("unknown denominator needs a coverage_reason")
        return self


class CapabilityFreshness(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    capability_id: str
    state: FreshnessState
    reason_code: str
    explanation: str
    evaluation_time: str | None = None
    source_digest: str | None = None
    source_publication_time: str | None = None
    max_age_days: int | None = Field(default=None, ge=0)
    feed_provider: str | None = None
    feed_digest: str | None = None
    git_head: str | None = None
    git_window: str | None = None

    @field_validator("capability_id", "reason_code", "explanation", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="freshness field")


class ComparisonRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    has_baseline: bool
    movement: str
    reason_code: str
    explanation: str


class EnvelopeBody(BaseModel):
    """Deterministic comparison body. Run time and signatures stay out."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = ENVELOPE_SCHEMA
    schema_version: str = ENVELOPE_VERSION
    repository_subject_id: str
    source_revision: str
    working_state_digest: str
    evaluation_time: str | None = None
    descriptor_ids: tuple[str, ...]
    outcome_driver_manifest_digest: str
    facts: tuple[FactRecord, ...]
    evidence: tuple[EvidenceRecord, ...]
    graph: GraphRecord
    findings: tuple[FindingRecord, ...]
    hotspots: tuple[EngineeringHotspot, ...]
    ownership: tuple[OwnershipConcentration, ...]
    change_summary: ChangeSummary | None = None
    coverage: tuple[CapabilityCoverage, ...]
    freshness: tuple[CapabilityFreshness, ...]
    comparison: ComparisonRecord
    limitations: tuple[str, ...] = ()
    health_score: None = None

    @field_validator(
        "repository_subject_id",
        "source_revision",
        "working_state_digest",
        "outcome_driver_manifest_digest",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="envelope body field")

    @field_validator("descriptor_ids", "limitations", mode="before")
    @classmethod
    def normalize_seq(cls, value: object) -> tuple[str, ...]:
        return tuple(require_nonblank(str(item), label="body list") for item in as_tuple(value))

    @model_validator(mode="after")
    def freeze_no_score_and_identity(self) -> EnvelopeBody:
        if self.health_score is not None:
            raise ValueError("canonical body must not carry a health score")
        payload = self.model_dump(mode="json")
        walk_forbidden_identity(payload)
        require_supported_major(self.schema_version)
        finding_ids = {item.finding_id for item in self.findings}
        evidence_ids = {item.evidence_id for item in self.evidence}
        for finding in self.findings:
            missing = set(finding.evidence_ids) - evidence_ids
            if missing:
                raise ValueError(
                    f"finding {finding.finding_id} references missing evidence {sorted(missing)}"
                )
        for hotspot in self.hotspots:
            missing_e = set(hotspot.evidence_ids) - evidence_ids
            if missing_e:
                raise ValueError(f"hotspot {hotspot.record_id} references missing evidence")
            missing_f = set(hotspot.active_finding_ids) - finding_ids
            if missing_f:
                raise ValueError(f"hotspot {hotspot.record_id} references missing findings")
        return self


class EnvelopeOperational(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str | None = None
    generated_at: str | None = None
    duration_ms: float | None = Field(default=None, ge=0.0)
    signature: str | None = None


class CanonicalEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = ENVELOPE_SCHEMA
    schema_version: str = ENVELOPE_VERSION
    body: EnvelopeBody
    body_digest: str
    operational: EnvelopeOperational = Field(default_factory=EnvelopeOperational)

    @model_validator(mode="after")
    def digest_matches(self) -> CanonicalEnvelope:
        require_supported_major(self.schema_version)
        expected = digest_canonical(self.body.model_dump(mode="json"))
        if self.body_digest != expected:
            raise ValueError("body_digest does not match canonical body")
        return self


def seal_envelope(
    body: EnvelopeBody,
    operational: EnvelopeOperational | None = None,
) -> CanonicalEnvelope:
    return CanonicalEnvelope(
        body=body,
        body_digest=digest_canonical(body.model_dump(mode="json")),
        operational=operational or EnvelopeOperational(),
    )


def parse_envelope(payload: object) -> CanonicalEnvelope:
    if not isinstance(payload, dict):
        raise EnvelopeError("envelope must be an object")
    try:
        require_supported_major(str(payload.get("schema_version", "")))
        envelope = CanonicalEnvelope.model_validate(payload)
    except (ValidationError, ValueError) as error:
        raise EnvelopeError(str(error)) from error
    return envelope


def dumps_envelope(envelope: CanonicalEnvelope) -> str:
    return dumps_canonical(envelope.model_dump(mode="json"))
