"""Canonical maintainability envelope for M22/M23 (Engine-local until E03.3)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.application.evidence.maintainability.capability import (
    CAP_M22,
    CAP_M23,
    CAPABILITY_MANIFEST_VERSION,
    MAINTAINABILITY_ENVELOPE_SCHEMA,
    CapabilityManifest,
    capability_manifests,
)
from codestrata.application.evidence.maintainability.models import (
    ConcernRecord,
    CoverageScope,
    FindingRejection,
    HistoryWindow,
    MaintainabilityEvidence,
    MaintainabilityThresholds,
    MetricStatusName,
    StalenessRecord,
)
from codestrata.domain.contracts.hotspot import EngineeringHotspot

MAINTAINABILITY_ENVELOPE_VERSION = "1"
SUPPORTED_ENVELOPE_MAJORS = frozenset({1})


class EnvelopeError(ValueError):
    """Unsupported or corrupt maintainability envelope."""


class MaintainabilityCoverageRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    capability_id: str
    evaluated: int | None = None
    eligible: int | None = None
    unknown: int = Field(ge=0)
    error: int = Field(ge=0)
    coverage_reason: str
    coverage_ratio: str | None = None
    full_scope_status: str


class MaintainabilityEnvelopeBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = MAINTAINABILITY_ENVELOPE_SCHEMA
    schema_version: str = MAINTAINABILITY_ENVELOPE_VERSION
    projection_version: str = CAPABILITY_MANIFEST_VERSION
    repository_id: str
    catalog_digest: str
    yaml_runtime: str = "maintainability.bundled_yaml"
    input_state_digest: str
    history: HistoryWindow | None
    complete_hotspots: tuple[EngineeringHotspot, ...]
    partial_hotspots: tuple[EngineeringHotspot, ...]
    static_function_ids: tuple[str, ...]
    staleness: tuple[StalenessRecord, ...]
    concerns: tuple[ConcernRecord, ...]
    finding_rejections: tuple[FindingRejection, ...]
    thresholds: MaintainabilityThresholds
    coverage: tuple[MaintainabilityCoverageRecord, ...]
    capabilities: tuple[CapabilityManifest, ...]
    metadata_snapshot_digest: str = ""
    executed_repository_code: bool = False
    live_lookup: bool = False
    health_verdict: str = "none"
    opaque_score: None = None
    runtime_failure_probability: None = None
    cost_to_fix: None = None
    developer_blame: None = None
    limitations: tuple[str, ...] = ()

    @field_validator(
        "complete_hotspots",
        "partial_hotspots",
        "static_function_ids",
        "staleness",
        "concerns",
        "finding_rejections",
        "coverage",
        "capabilities",
        "limitations",
        mode="before",
    )
    @classmethod
    def as_tuple(cls, value: object) -> tuple[object, ...]:
        if value is None:
            return ()
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(value)
        raise EnvelopeError("sequence field must be a list")


class MaintainabilityOperationalMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str | None = None
    generated_at: str | None = None


class MaintainabilityEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = MAINTAINABILITY_ENVELOPE_SCHEMA
    schema_version: str = MAINTAINABILITY_ENVELOPE_VERSION
    body: MaintainabilityEnvelopeBody
    body_digest: str
    operational: MaintainabilityOperationalMetadata = Field(
        default_factory=MaintainabilityOperationalMetadata
    )


def _stable_dumps(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_body(body: MaintainabilityEnvelopeBody) -> str:
    return hashlib.sha256(_stable_dumps(body.model_dump(mode="json")).encode("utf-8")).hexdigest()


def _m22_coverage(
    complete: Sequence[EngineeringHotspot],
    partial: Sequence[EngineeringHotspot],
    history: HistoryWindow | None,
) -> MaintainabilityCoverageRecord:
    eligible = len(complete) + len(partial)
    if history is None or history.coverage in {
        CoverageScope.MISSING,
        CoverageScope.UNKNOWN,
    }:
        return MaintainabilityCoverageRecord(
            capability_id=CAP_M22,
            evaluated=len(complete) if complete else None,
            eligible=eligible if eligible else None,
            unknown=len(partial),
            error=0,
            coverage_reason="missing_or_unknown_history",
            full_scope_status=CoverageScope.UNKNOWN.value,
        )
    if not eligible:
        return MaintainabilityCoverageRecord(
            capability_id=CAP_M22,
            evaluated=0,
            eligible=0,
            unknown=0,
            error=0,
            coverage_reason="no_components",
            full_scope_status=CoverageScope.NOT_APPLICABLE.value,
        )
    if partial:
        return MaintainabilityCoverageRecord(
            capability_id=CAP_M22,
            evaluated=len(complete),
            eligible=eligible,
            unknown=len(partial),
            error=0,
            coverage_reason="partial_or_unknown_ranking_inputs",
            coverage_ratio=f"{len(complete) / eligible:.6f}",
            full_scope_status=CoverageScope.PARTIAL.value,
        )
    return MaintainabilityCoverageRecord(
        capability_id=CAP_M22,
        evaluated=len(complete),
        eligible=eligible,
        unknown=0,
        error=0,
        coverage_reason="complete_comparable",
        coverage_ratio="1.000000",
        full_scope_status=CoverageScope.COMPLETE.value,
    )


def _m23_coverage(staleness: Sequence[StalenessRecord]) -> MaintainabilityCoverageRecord:
    if not staleness:
        return MaintainabilityCoverageRecord(
            capability_id=CAP_M23,
            evaluated=0,
            eligible=0,
            unknown=0,
            error=0,
            coverage_reason="no_resolved_packages",
            full_scope_status=CoverageScope.NOT_APPLICABLE.value,
        )
    known = [item for item in staleness if item.status is MetricStatusName.VALUE]
    unknown = len(staleness) - len(known)
    if unknown:
        return MaintainabilityCoverageRecord(
            capability_id=CAP_M23,
            evaluated=len(known),
            eligible=len(staleness),
            unknown=unknown,
            error=0,
            coverage_reason="missing_or_invalid_timestamp",
            coverage_ratio=f"{len(known) / len(staleness):.6f}",
            full_scope_status=CoverageScope.PARTIAL.value,
        )
    return MaintainabilityCoverageRecord(
        capability_id=CAP_M23,
        evaluated=len(known),
        eligible=len(staleness),
        unknown=0,
        error=0,
        coverage_reason="pinned_dates",
        coverage_ratio="1.000000",
        full_scope_status=CoverageScope.COMPLETE.value,
    )


def seal_maintainability_envelope(
    *,
    evidence: MaintainabilityEvidence,
    catalog_digest: str,
    operational: MaintainabilityOperationalMetadata | None = None,
) -> MaintainabilityEnvelope:
    coverage = (
        _m22_coverage(
            evidence.complete_hotspots, evidence.partial_hotspots, evidence.history
        ),
        _m23_coverage(evidence.staleness),
    )
    body = MaintainabilityEnvelopeBody(
        repository_id=evidence.repository_id,
        catalog_digest=catalog_digest,
        input_state_digest=evidence.input_state_digest,
        history=evidence.history,
        complete_hotspots=evidence.complete_hotspots,
        partial_hotspots=evidence.partial_hotspots,
        static_function_ids=evidence.static_function_ids,
        staleness=evidence.staleness,
        concerns=evidence.concerns,
        finding_rejections=evidence.finding_rejections,
        thresholds=evidence.thresholds,
        coverage=coverage,
        capabilities=capability_manifests(),
        metadata_snapshot_digest=evidence.metadata_snapshot_digest,
        executed_repository_code=evidence.executed_repository_code,
        live_lookup=evidence.live_lookup,
        limitations=evidence.limitations,
    )
    return MaintainabilityEnvelope(
        body=body,
        body_digest=digest_body(body),
        operational=operational or MaintainabilityOperationalMetadata(),
    )


def parse_envelope_payload(payload: object) -> MaintainabilityEnvelope:
    if not isinstance(payload, Mapping):
        raise EnvelopeError("envelope must be an object")
    schema = str(payload.get("schema_name") or "")
    version = str(payload.get("schema_version") or "")
    if schema != MAINTAINABILITY_ENVELOPE_SCHEMA:
        raise EnvelopeError(f"unsupported envelope schema: {schema}")
    major_text = version.split(".", 1)[0]
    try:
        major = int(major_text)
    except ValueError as error:
        raise EnvelopeError(f"unsupported envelope version: {version}") from error
    if major not in SUPPORTED_ENVELOPE_MAJORS:
        raise EnvelopeError(f"unsupported envelope major version: {version}")
    try:
        envelope = MaintainabilityEnvelope.model_validate(payload)
    except EnvelopeError:
        raise
    except Exception as error:
        raise EnvelopeError("corrupt maintainability envelope") from error
    if digest_body(envelope.body) != envelope.body_digest:
        raise EnvelopeError("envelope body_digest does not match canonical body")
    if envelope.body.health_verdict != "none":
        raise EnvelopeError("maintainability envelope must not carry a health verdict")
    if envelope.body.opaque_score is not None:
        raise EnvelopeError("maintainability envelope must not carry an opaque score")
    if envelope.body.live_lookup or envelope.body.executed_repository_code:
        raise EnvelopeError("canonical evaluation must not live-lookup or execute repository code")
    return envelope


__all__ = [
    "EnvelopeError",
    "MAINTAINABILITY_ENVELOPE_SCHEMA",
    "MaintainabilityEnvelope",
    "MaintainabilityEnvelopeBody",
    "MaintainabilityOperationalMetadata",
    "digest_body",
    "parse_envelope_payload",
    "seal_maintainability_envelope",
]
