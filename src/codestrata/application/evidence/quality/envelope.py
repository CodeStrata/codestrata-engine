"""Canonical quality envelope for M16/M17/M18 (Engine-local until E03.3)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.application.evidence.quality.capability import (
    CAP_M16,
    CAP_M17,
    CAP_M18,
    CAPABILITY_MANIFEST_VERSION,
    QUALITY_ENVELOPE_SCHEMA,
    CapabilityManifest,
    capability_manifests,
)
from codestrata.application.evidence.quality.models import (
    CloneMetric,
    CoverageScope,
    FileSizeRecord,
    FunctionDistribution,
    FunctionRecord,
    FunctionStatus,
    MetricStatusName,
    QualityEvidence,
    QualityThresholds,
)

QUALITY_ENVELOPE_VERSION = "1"
SUPPORTED_ENVELOPE_MAJORS = frozenset({1})


class EnvelopeError(ValueError):
    """Unsupported or corrupt quality envelope."""


class QualityCoverageRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    capability_id: str
    evaluated: int | None = None
    eligible: int | None = None
    unknown: int = Field(ge=0)
    error: int = Field(ge=0)
    coverage_reason: str
    coverage_ratio: str | None = None
    full_scope_status: str


class QualityEnvelopeBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = QUALITY_ENVELOPE_SCHEMA
    schema_version: str = QUALITY_ENVELOPE_VERSION
    projection_version: str = CAPABILITY_MANIFEST_VERSION
    repository_id: str
    catalog_digest: str
    yaml_runtime: str = "quality.structural.bundled_yaml"
    functions: tuple[FunctionRecord, ...]
    files: tuple[FileSizeRecord, ...]
    distribution: FunctionDistribution
    clone: CloneMetric
    thresholds: QualityThresholds
    coverage: tuple[QualityCoverageRecord, ...]
    capabilities: tuple[CapabilityManifest, ...]
    executed_repository_code: bool = False
    live_lookup: bool = False
    health_verdict: str = "none"
    maintainability_index: None = None
    limitations: tuple[str, ...] = ()

    @field_validator(
        "functions",
        "files",
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


class QualityOperationalMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str | None = None
    generated_at: str | None = None


class QualityEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = QUALITY_ENVELOPE_SCHEMA
    schema_version: str = QUALITY_ENVELOPE_VERSION
    body: QualityEnvelopeBody
    body_digest: str
    operational: QualityOperationalMetadata = Field(default_factory=QualityOperationalMetadata)


def _stable_dumps(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_body(body: QualityEnvelopeBody) -> str:
    return hashlib.sha256(_stable_dumps(body.model_dump(mode="json")).encode("utf-8")).hexdigest()


def _m16_coverage(
    functions: Sequence[FunctionRecord], files: Sequence[FileSizeRecord]
) -> QualityCoverageRecord:
    unknown_files = sum(1 for item in files if item.parse_status is MetricStatusName.UNKNOWN)
    measured = sum(1 for item in functions if item.status is FunctionStatus.MEASURED)
    unknown_fn = sum(1 for item in functions if item.status is FunctionStatus.UNKNOWN)
    attempted = measured + unknown_fn
    if attempted == 0 and unknown_files:
        return QualityCoverageRecord(
            capability_id=CAP_M16,
            evaluated=None,
            eligible=None,
            unknown=unknown_files,
            error=0,
            coverage_reason="unparsed_functions",
            full_scope_status=CoverageScope.UNKNOWN.value,
        )
    if attempted == 0:
        return QualityCoverageRecord(
            capability_id=CAP_M16,
            evaluated=0,
            eligible=0,
            unknown=0,
            error=0,
            coverage_reason="zero_functions",
            coverage_ratio=None,
            full_scope_status=CoverageScope.NOT_APPLICABLE.value,
        )
    ratio = f"{measured / attempted:.6f}"
    complete = unknown_fn == 0 and unknown_files == 0
    status = CoverageScope.COMPLETE if complete else CoverageScope.PARTIAL
    return QualityCoverageRecord(
        capability_id=CAP_M16,
        evaluated=measured,
        eligible=attempted,
        unknown=unknown_fn,
        error=0,
        coverage_reason="established_function",
        coverage_ratio=ratio,
        full_scope_status=status.value,
    )


def _m17_coverage(
    functions: Sequence[FunctionRecord], files: Sequence[FileSizeRecord]
) -> QualityCoverageRecord:
    unknown_files = sum(1 for item in files if item.parse_status is MetricStatusName.UNKNOWN)
    measured = [
        item
        for item in functions
        if item.status is FunctionStatus.MEASURED and item.max_nesting_depth is not None
    ]
    unknown_fn = sum(1 for item in functions if item.status is FunctionStatus.UNKNOWN)
    if not functions and not unknown_files:
        return QualityCoverageRecord(
            capability_id=CAP_M17,
            evaluated=0,
            eligible=0,
            unknown=0,
            error=0,
            coverage_reason="absent_functions",
            full_scope_status=CoverageScope.NOT_APPLICABLE.value,
        )
    if unknown_files or unknown_fn:
        eligible = len(measured) + unknown_fn
        return QualityCoverageRecord(
            capability_id=CAP_M17,
            evaluated=len(measured) if measured else None,
            eligible=eligible if eligible else None,
            unknown=unknown_fn + unknown_files,
            error=0,
            coverage_reason="unknown_parse_invalidates_negative",
            coverage_ratio=(f"{len(measured) / eligible:.6f}" if eligible else None),
            full_scope_status=(
                CoverageScope.PARTIAL.value if measured else CoverageScope.UNKNOWN.value
            ),
        )
    return QualityCoverageRecord(
        capability_id=CAP_M17,
        evaluated=len(measured),
        eligible=len(functions),
        unknown=0,
        error=0,
        coverage_reason="established_function",
        coverage_ratio=f"{1:.6f}",
        full_scope_status=CoverageScope.COMPLETE.value,
    )


def _m18_coverage(clone: CloneMetric) -> QualityCoverageRecord:
    return QualityCoverageRecord(
        capability_id=CAP_M18,
        evaluated=clone.numerator,
        eligible=clone.denominator,
        unknown=1 if clone.full_scope_status is CoverageScope.UNKNOWN else 0,
        error=0,
        coverage_reason=clone.reason,
        coverage_ratio=clone.serialized,
        full_scope_status=clone.full_scope_status.value,
    )


def seal_quality_envelope(
    *,
    evidence: QualityEvidence,
    catalog_digest: str,
    operational: QualityOperationalMetadata | None = None,
) -> QualityEnvelope:
    notes = list(evidence.limitations)
    notes.extend(
        (
            "no_maintainability_index",
            "language_specific_branch_map",
            "heuristic_thresholds",
            "indicative_clone_not_proof",
            "quality_envelope_is_engine_local",
        )
    )
    coverage = (
        _m16_coverage(evidence.functions, evidence.files),
        _m17_coverage(evidence.functions, evidence.files),
        _m18_coverage(evidence.clone),
    )
    body = QualityEnvelopeBody(
        repository_id=evidence.repository_id,
        catalog_digest=catalog_digest,
        functions=evidence.functions,
        files=evidence.files,
        distribution=evidence.distribution,
        clone=evidence.clone,
        thresholds=evidence.thresholds,
        coverage=coverage,
        capabilities=capability_manifests(),
        executed_repository_code=evidence.executed_repository_code,
        live_lookup=evidence.live_lookup,
        limitations=tuple(sorted(set(notes))),
    )
    return QualityEnvelope(
        body=body,
        body_digest=digest_body(body),
        operational=operational or QualityOperationalMetadata(),
    )


def parse_envelope_payload(payload: object) -> QualityEnvelope:
    if not isinstance(payload, Mapping):
        raise EnvelopeError("envelope must be an object")
    schema = str(payload.get("schema_name") or "")
    version = str(payload.get("schema_version") or "")
    if schema != QUALITY_ENVELOPE_SCHEMA:
        raise EnvelopeError(f"unsupported envelope schema: {schema}")
    major_text = version.split(".", 1)[0]
    try:
        major = int(major_text)
    except ValueError as error:
        raise EnvelopeError(f"unsupported envelope version: {version}") from error
    if major not in SUPPORTED_ENVELOPE_MAJORS:
        raise EnvelopeError(f"unsupported envelope major version: {version}")
    try:
        envelope = QualityEnvelope.model_validate(payload)
    except EnvelopeError:
        raise
    except Exception as error:
        raise EnvelopeError("corrupt quality envelope") from error
    if digest_body(envelope.body) != envelope.body_digest:
        raise EnvelopeError("envelope body_digest does not match canonical body")
    if envelope.body.health_verdict != "none":
        raise EnvelopeError("quality envelope must not carry a health verdict")
    if envelope.body.maintainability_index is not None:
        raise EnvelopeError("quality envelope must not carry a maintainability index")
    if envelope.body.live_lookup or envelope.body.executed_repository_code:
        raise EnvelopeError("canonical evaluation must not live-lookup or execute repository code")
    return envelope


__all__ = [
    "EnvelopeError",
    "QUALITY_ENVELOPE_SCHEMA",
    "QualityEnvelope",
    "QualityEnvelopeBody",
    "QualityOperationalMetadata",
    "digest_body",
    "parse_envelope_payload",
    "seal_quality_envelope",
]
