"""Canonical security envelope for M10/M11 (Engine-local until E03.3)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.application.evidence.security.capability import (
    CAPABILITY_MANIFEST_VERSION,
    SECURITY_ENVELOPE_SCHEMA,
    CapabilityManifest,
    capability_manifests,
)
from codestrata.application.evidence.security.metrics import (
    SecurityFindingRecord,
    SecurityMetricCounts,
    count_metrics,
    unique_findings,
)
from codestrata.domain.rules.results import RuleMatch

SECURITY_ENVELOPE_VERSION = "1"
SUPPORTED_ENVELOPE_MAJORS = frozenset({1})


class EnvelopeError(ValueError):
    """Unsupported or corrupt security envelope."""


class SecurityCoverageRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    capability_id: str
    evaluated: int = Field(ge=0)
    eligible: int = Field(ge=0)
    unknown: int = Field(ge=0)
    error: int = Field(ge=0)
    coverage_reason: str
    git_history_scanned: bool = False


class SecurityEnvelopeBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = SECURITY_ENVELOPE_SCHEMA
    schema_version: str = SECURITY_ENVELOPE_VERSION
    projection_version: str = CAPABILITY_MANIFEST_VERSION
    repository_id: str
    catalog_digest: str
    yaml_runtime: str = "security.core.bundled_yaml"
    findings: tuple[SecurityFindingRecord, ...]
    counts: SecurityMetricCounts
    coverage: tuple[SecurityCoverageRecord, ...]
    capabilities: tuple[CapabilityManifest, ...]
    executed_repository_code: bool = False
    git_history_scanned: bool = False
    health_verdict: str = "none"
    limitations: tuple[str, ...] = ()

    @field_validator("findings", "coverage", "capabilities", "limitations", mode="before")
    @classmethod
    def as_tuple(cls, value: object) -> tuple[object, ...]:
        if value is None:
            return ()
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(value)
        raise EnvelopeError("sequence field must be a list")


class SecurityOperationalMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str | None = None
    generated_at: str | None = None


class SecurityEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = SECURITY_ENVELOPE_SCHEMA
    schema_version: str = SECURITY_ENVELOPE_VERSION
    body: SecurityEnvelopeBody
    body_digest: str
    operational: SecurityOperationalMetadata = Field(default_factory=SecurityOperationalMetadata)


def _stable_dumps(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_body(body: SecurityEnvelopeBody) -> str:
    return hashlib.sha256(_stable_dumps(body.model_dump(mode="json")).encode("utf-8")).hexdigest()


def seal_security_envelope(
    *,
    repository_id: str,
    catalog_digest: str,
    matches: Sequence[RuleMatch],
    unknown_scope: int = 0,
    error_scope: int = 0,
    limitations: Sequence[str] = (),
    operational: SecurityOperationalMetadata | None = None,
) -> SecurityEnvelope:
    findings = unique_findings(matches)
    counts = count_metrics(findings)
    manifests = capability_manifests()
    m10 = sum(
        1
        for item in findings
        if item.rule_id.startswith("security.")
        and item.rule_id
        in {
            "security.private-key-material",
            "security.credential-literal",
            "security.placeholder-credential",
        }
    )
    m11 = len(findings) - m10
    coverage = (
        SecurityCoverageRecord(
            capability_id="security.m10.secrets",
            evaluated=m10,
            eligible=m10,
            unknown=unknown_scope,
            error=error_scope,
            coverage_reason="unique_rule_subject_occurrence",
            git_history_scanned=False,
        ),
        SecurityCoverageRecord(
            capability_id="security.m11.insecure_configuration",
            evaluated=m11,
            eligible=m11,
            unknown=counts.m11_debug_unknown_context,
            error=error_scope,
            coverage_reason="named_yaml_rule_counts",
            git_history_scanned=False,
        ),
    )
    notes = list(limitations)
    notes.extend(
        (
            "no_git_history_scan",
            "no_raw_secret_retention",
            "yaml_default_severity_not_post_processed",
            "security_envelope_is_engine_local",
        )
    )
    body = SecurityEnvelopeBody(
        repository_id=repository_id,
        catalog_digest=catalog_digest,
        findings=findings,
        counts=counts,
        coverage=coverage,
        capabilities=manifests,
        limitations=tuple(sorted(set(notes))),
    )
    return SecurityEnvelope(
        body=body,
        body_digest=digest_body(body),
        operational=operational or SecurityOperationalMetadata(),
    )


def parse_envelope_payload(payload: object) -> SecurityEnvelope:
    if not isinstance(payload, Mapping):
        raise EnvelopeError("envelope must be an object")
    schema = str(payload.get("schema_name") or "")
    version = str(payload.get("schema_version") or "")
    if schema != SECURITY_ENVELOPE_SCHEMA:
        raise EnvelopeError(f"unsupported envelope schema: {schema}")
    major_text = version.split(".", 1)[0]
    try:
        major = int(major_text)
    except ValueError as error:
        raise EnvelopeError(f"unsupported envelope version: {version}") from error
    if major not in SUPPORTED_ENVELOPE_MAJORS:
        raise EnvelopeError(f"unsupported envelope major version: {version}")
    try:
        envelope = SecurityEnvelope.model_validate(payload)
    except EnvelopeError:
        raise
    except Exception as error:
        raise EnvelopeError("corrupt security envelope") from error
    expected = digest_body(envelope.body)
    if envelope.body_digest != expected:
        raise EnvelopeError("envelope body_digest does not match canonical body")
    if envelope.body.health_verdict != "none":
        raise EnvelopeError("security envelope must not carry a health verdict")
    if envelope.body.git_history_scanned:
        raise EnvelopeError("M10 must not scan Git history by default")
    return envelope
