"""Canonical testing envelope for M19/M20/M21 (Engine-local until E03.3)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.application.evidence.testing.capability import (
    CAP_M19,
    CAP_M20,
    CAP_M21,
    CAPABILITY_MANIFEST_VERSION,
    TESTING_ENVELOPE_SCHEMA,
    CapabilityManifest,
    capability_manifests,
)
from codestrata.application.evidence.testing.models import (
    AssociationMetric,
    CiGapMetric,
    SkipMetric,
    TestingEvidence,
    TestingThresholds,
)

TESTING_ENVELOPE_VERSION = "1"
SUPPORTED_ENVELOPE_MAJORS = frozenset({1})


class EnvelopeError(ValueError):
    """Unsupported or corrupt testing envelope."""


class TestingCoverageRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    __test__ = False

    capability_id: str
    evaluated: int | None = None
    eligible: int | None = None
    unknown: int = Field(ge=0)
    error: int = Field(ge=0)
    coverage_reason: str
    coverage_ratio: str | None = None
    full_scope_status: str


class TestingEnvelopeBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    __test__ = False

    schema_name: str = TESTING_ENVELOPE_SCHEMA
    schema_version: str = TESTING_ENVELOPE_VERSION
    projection_version: str = CAPABILITY_MANIFEST_VERSION
    repository_id: str
    catalog_digest: str
    yaml_runtime: str = "testing.association.bundled_yaml"
    association: AssociationMetric
    skipped: SkipMetric
    ci_gap: CiGapMetric
    thresholds: TestingThresholds
    coverage: tuple[TestingCoverageRecord, ...]
    capabilities: tuple[CapabilityManifest, ...]
    executed_repository_code: bool = False
    live_lookup: bool = False
    health_verdict: str = "none"
    runtime_coverage: None = None
    coverage_percent: None = None
    limitations: tuple[str, ...] = ()

    @field_validator("coverage", "capabilities", "limitations", mode="before")
    @classmethod
    def as_tuple(cls, value: object) -> tuple[object, ...]:
        if value is None:
            return ()
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(value)
        raise EnvelopeError("sequence field must be a list")


class TestingOperationalMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    __test__ = False

    run_id: str | None = None
    generated_at: str | None = None


class TestingEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    __test__ = False

    schema_name: str = TESTING_ENVELOPE_SCHEMA
    schema_version: str = TESTING_ENVELOPE_VERSION
    body: TestingEnvelopeBody
    body_digest: str
    operational: TestingOperationalMetadata = Field(
        default_factory=TestingOperationalMetadata
    )


def _stable_dumps(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_body(body: TestingEnvelopeBody) -> str:
    return hashlib.sha256(_stable_dumps(body.model_dump(mode="json")).encode("utf-8")).hexdigest()


def _m19_coverage(metric: AssociationMetric) -> TestingCoverageRecord:
    unknown = len(metric.unsupported_frameworks) + metric.generated_tests
    return TestingCoverageRecord(
        capability_id=CAP_M19,
        evaluated=metric.associated,
        eligible=metric.eligible,
        unknown=unknown,
        error=0,
        coverage_reason=metric.reason,
        coverage_ratio=metric.serialized,
        full_scope_status=metric.full_scope_status.value,
    )


def _m20_coverage(metric: SkipMetric) -> TestingCoverageRecord:
    eligible = None
    if metric.explicit_disabled is not None:
        eligible = (
            metric.explicit_disabled
            + metric.conditional
            + metric.unknown_eligibility
            + metric.enabled
            + metric.unsupported_decorator
        )
    return TestingCoverageRecord(
        capability_id=CAP_M20,
        evaluated=metric.explicit_disabled,
        eligible=eligible,
        unknown=metric.unknown_eligibility,
        error=0,
        coverage_reason=metric.reason,
        coverage_ratio=None,
        full_scope_status=metric.full_scope_status.value,
    )


def _m21_coverage(metric: CiGapMetric) -> TestingCoverageRecord:
    eligible = len(metric.declared) if metric.declared else metric.proven_absent
    return TestingCoverageRecord(
        capability_id=CAP_M21,
        evaluated=metric.proven_absent,
        eligible=eligible,
        unknown=metric.unknown,
        error=0,
        coverage_reason=metric.reason,
        coverage_ratio=None,
        full_scope_status=metric.full_scope_status.value,
    )


def seal_testing_envelope(
    *,
    evidence: TestingEvidence,
    catalog_digest: str,
    operational: TestingOperationalMetadata | None = None,
) -> TestingEnvelope:
    notes = list(evidence.limitations)
    notes.extend(
        (
            "static_association_not_runtime_coverage",
            "missing_coverage_report_is_not_zero_percent",
            "conditional_job_uncertainty_visible",
            "testing_envelope_is_engine_local",
        )
    )
    coverage = (
        _m19_coverage(evidence.association),
        _m20_coverage(evidence.skipped),
        _m21_coverage(evidence.ci_gap),
    )
    body = TestingEnvelopeBody(
        repository_id=evidence.repository_id,
        catalog_digest=catalog_digest,
        association=evidence.association,
        skipped=evidence.skipped,
        ci_gap=evidence.ci_gap,
        thresholds=evidence.thresholds,
        coverage=coverage,
        capabilities=capability_manifests(),
        executed_repository_code=evidence.executed_repository_code,
        live_lookup=evidence.live_lookup,
        runtime_coverage=None,
        coverage_percent=None,
        limitations=tuple(sorted(set(notes))),
    )
    return TestingEnvelope(
        body=body,
        body_digest=digest_body(body),
        operational=operational or TestingOperationalMetadata(),
    )


def parse_envelope_payload(payload: object) -> TestingEnvelope:
    if not isinstance(payload, Mapping):
        raise EnvelopeError("envelope must be an object")
    schema = str(payload.get("schema_name") or "")
    version = str(payload.get("schema_version") or "")
    if schema != TESTING_ENVELOPE_SCHEMA:
        raise EnvelopeError(f"unsupported envelope schema: {schema}")
    major_text = version.split(".", 1)[0]
    try:
        major = int(major_text)
    except ValueError as error:
        raise EnvelopeError(f"unsupported envelope version: {version}") from error
    if major not in SUPPORTED_ENVELOPE_MAJORS:
        raise EnvelopeError(f"unsupported envelope major version: {version}")
    try:
        envelope = TestingEnvelope.model_validate(payload)
    except EnvelopeError:
        raise
    except Exception as error:
        raise EnvelopeError("corrupt testing envelope") from error
    if digest_body(envelope.body) != envelope.body_digest:
        raise EnvelopeError("envelope body_digest does not match canonical body")
    if envelope.body.health_verdict != "none":
        raise EnvelopeError("testing envelope must not carry a health verdict")
    if envelope.body.runtime_coverage is not None or envelope.body.coverage_percent is not None:
        raise EnvelopeError("testing envelope must not claim runtime coverage")
    if envelope.body.live_lookup or envelope.body.executed_repository_code:
        raise EnvelopeError("canonical evaluation must not live-lookup or execute repository code")
    if envelope.body.association.runtime_coverage is not None:
        raise EnvelopeError("association metric must not claim runtime coverage")
    if envelope.body.ci_gap.coverage_percent is not None:
        raise EnvelopeError("missing coverage report is not 0% code coverage")
    return envelope


__all__ = [
    "EnvelopeError",
    "TESTING_ENVELOPE_SCHEMA",
    "TestingEnvelope",
    "TestingEnvelopeBody",
    "TestingOperationalMetadata",
    "digest_body",
    "parse_envelope_payload",
    "seal_testing_envelope",
]
