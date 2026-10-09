"""Canonical supply-chain envelope for M12/M13 (Engine-local until E03.3)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.application.evidence.supply_chain.capability import (
    CAP_M12,
    CAP_M13,
    CAP_M14,
    CAPABILITY_MANIFEST_VERSION,
    SUPPLY_CHAIN_ENVELOPE_SCHEMA,
    CapabilityManifest,
    capability_manifests,
)
from codestrata.application.evidence.supply_chain.models import (
    FeedFreshness,
    HygieneCounts,
    LicensePolicy,
    LicenseRecord,
    LicenseSummary,
    MatchingScope,
    ScopeCoverage,
    SupplyChainEvidence,
    VulnerabilityMatch,
)

SUPPLY_CHAIN_ENVELOPE_VERSION = "1"
SUPPORTED_ENVELOPE_MAJORS = frozenset({1})


class EnvelopeError(ValueError):
    """Unsupported or corrupt supply-chain envelope."""


class SupplyChainCoverageRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    capability_id: str
    evaluated: int | None = None
    eligible: int | None = None
    unknown: int = Field(ge=0)
    error: int = Field(ge=0)
    coverage_reason: str
    coverage_ratio: str | None = None
    matching_status: str | None = None
    match_count: int | None = None


class SupplyChainEnvelopeBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = SUPPLY_CHAIN_ENVELOPE_SCHEMA
    schema_version: str = SUPPLY_CHAIN_ENVELOPE_VERSION
    projection_version: str = CAPABILITY_MANIFEST_VERSION
    repository_id: str
    catalog_digest: str
    yaml_runtime: str = "security.known_vulnerability.bundled_yaml"
    feed_provider: str = "osv.dev"
    feed: FeedFreshness
    matching: MatchingScope
    scopes: tuple[ScopeCoverage, ...]
    hygiene: HygieneCounts
    matches: tuple[VulnerabilityMatch, ...]
    licenses: tuple[LicenseRecord, ...] = ()
    license_policy: LicensePolicy | None = None
    license_summary: LicenseSummary = Field(default_factory=LicenseSummary)
    coverage: tuple[SupplyChainCoverageRecord, ...]
    capabilities: tuple[CapabilityManifest, ...]
    executed_repository_code: bool = False
    live_lookup: bool = False
    health_verdict: str = "none"
    limitations: tuple[str, ...] = ()

    @field_validator(
        "scopes",
        "matches",
        "licenses",
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


class SupplyChainOperationalMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str | None = None
    generated_at: str | None = None


class SupplyChainEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = SUPPLY_CHAIN_ENVELOPE_SCHEMA
    schema_version: str = SUPPLY_CHAIN_ENVELOPE_VERSION
    body: SupplyChainEnvelopeBody
    body_digest: str
    operational: SupplyChainOperationalMetadata = Field(
        default_factory=SupplyChainOperationalMetadata
    )


def _stable_dumps(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_body(body: SupplyChainEnvelopeBody) -> str:
    return hashlib.sha256(_stable_dumps(body.model_dump(mode="json")).encode("utf-8")).hexdigest()


def _m12_coverage(scopes: Sequence[ScopeCoverage]) -> SupplyChainCoverageRecord:
    unknown = sum(1 for item in scopes if item.status.value == "unknown")
    if any(item.status.value == "unknown" for item in scopes) and all(
        item.status.value == "unknown" for item in scopes
    ):
        return SupplyChainCoverageRecord(
            capability_id=CAP_M12,
            evaluated=None,
            eligible=None,
            unknown=unknown,
            error=0,
            coverage_reason="unknown_denominator",
        )
    eligible_ids: list[str] = []
    resolved_ids: list[str] = []
    for item in scopes:
        if item.status.value == "not_applicable":
            continue
        eligible_ids.extend(item.eligible_ids)
        resolved_ids.extend(item.fully_resolved_ids)
    unique_eligible = list(dict.fromkeys(eligible_ids))
    unique_resolved = [item for item in dict.fromkeys(resolved_ids) if item in unique_eligible]
    if not unique_eligible:
        return SupplyChainCoverageRecord(
            capability_id=CAP_M12,
            evaluated=0,
            eligible=0,
            unknown=0,
            error=0,
            coverage_reason="zero_eligible",
        )
    ratio = f"{len(unique_resolved) / len(unique_eligible):.6f}"
    return SupplyChainCoverageRecord(
        capability_id=CAP_M12,
        evaluated=len(unique_resolved),
        eligible=len(unique_eligible),
        unknown=unknown,
        error=0,
        coverage_reason="eligible_declaration_id",
        coverage_ratio=ratio,
    )


def _m13_coverage(
    matching: MatchingScope, matches: Sequence[VulnerabilityMatch]
) -> SupplyChainCoverageRecord:
    return SupplyChainCoverageRecord(
        capability_id=CAP_M13,
        evaluated=len(matches) if matching.match_count is not None else None,
        eligible=matching.match_count,
        unknown=0 if matching.status.value == "complete" else 1,
        error=0,
        coverage_reason=matching.reason,
        matching_status=matching.status.value,
        match_count=matching.match_count,
    )


def _m14_coverage(
    licenses: Sequence[LicenseRecord], summary: LicenseSummary
) -> SupplyChainCoverageRecord:
    known = summary.known_spdx
    unknown = summary.unknown
    if not licenses:
        return SupplyChainCoverageRecord(
            capability_id=CAP_M14,
            evaluated=0,
            eligible=0,
            unknown=0,
            error=0,
            coverage_reason="zero_license_records",
        )
    return SupplyChainCoverageRecord(
        capability_id=CAP_M14,
        evaluated=known,
        eligible=len(licenses),
        unknown=unknown,
        error=0,
        coverage_reason="package_license_expression",
        coverage_ratio=None if not licenses else f"{known / len(licenses):.6f}",
        match_count=summary.disallowed,
    )


def seal_supply_chain_envelope(
    *,
    evidence: SupplyChainEvidence,
    catalog_digest: str,
    operational: SupplyChainOperationalMetadata | None = None,
) -> SupplyChainEnvelope:
    notes = list(evidence.limitations)
    notes.extend(
        (
            "never_install_packages",
            "no_silent_online_fallback",
            "zero_matches_is_not_secure",
            "supply_chain_envelope_is_engine_local",
            "license_not_legal_compliance",
        )
    )
    if evidence.matching.cannot_prove_clean:
        notes.append("matching_cannot_prove_clean")
    coverage = (
        _m12_coverage(evidence.scopes),
        _m13_coverage(evidence.matching, evidence.matches),
        _m14_coverage(evidence.licenses, evidence.license_summary),
    )
    body = SupplyChainEnvelopeBody(
        repository_id=evidence.repository_id,
        catalog_digest=catalog_digest,
        feed=evidence.freshness,
        matching=evidence.matching,
        scopes=evidence.scopes,
        hygiene=evidence.hygiene,
        matches=evidence.matches,
        licenses=evidence.licenses,
        license_policy=evidence.license_policy,
        license_summary=evidence.license_summary,
        coverage=coverage,
        capabilities=capability_manifests(),
        executed_repository_code=evidence.executed_repository_code,
        live_lookup=evidence.live_lookup,
        limitations=tuple(sorted(set(notes))),
    )
    return SupplyChainEnvelope(
        body=body,
        body_digest=digest_body(body),
        operational=operational or SupplyChainOperationalMetadata(),
    )


def parse_envelope_payload(payload: object) -> SupplyChainEnvelope:
    if not isinstance(payload, Mapping):
        raise EnvelopeError("envelope must be an object")
    schema = str(payload.get("schema_name") or "")
    version = str(payload.get("schema_version") or "")
    if schema != SUPPLY_CHAIN_ENVELOPE_SCHEMA:
        raise EnvelopeError(f"unsupported envelope schema: {schema}")
    major_text = version.split(".", 1)[0]
    try:
        major = int(major_text)
    except ValueError as error:
        raise EnvelopeError(f"unsupported envelope version: {version}") from error
    if major not in SUPPORTED_ENVELOPE_MAJORS:
        raise EnvelopeError(f"unsupported envelope major version: {version}")
    try:
        envelope = SupplyChainEnvelope.model_validate(payload)
    except EnvelopeError:
        raise
    except Exception as error:
        raise EnvelopeError("corrupt supply-chain envelope") from error
    if digest_body(envelope.body) != envelope.body_digest:
        raise EnvelopeError("envelope body_digest does not match canonical body")
    if envelope.body.health_verdict != "none":
        raise EnvelopeError("supply-chain envelope must not carry a health verdict")
    if envelope.body.live_lookup or envelope.body.executed_repository_code:
        raise EnvelopeError("canonical evaluation must not live-lookup or install")
    if (
        envelope.body.matching.status.value != "complete"
        and envelope.body.matching.match_count == 0
    ):
        raise EnvelopeError("unknown matching scope must not report zero CVEs")
    return envelope
