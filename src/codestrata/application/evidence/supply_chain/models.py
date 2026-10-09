"""Application-local supply-chain facts for M12/M13 (E06.2).

Domain Dependency Evidence stays declaration-only. Resolution, transitive
paths and vulnerability matches live here until a shared schema is published.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MetricStatusName(StrEnum):
    VALUE = "value"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class MatchingStatus(StrEnum):
    COMPLETE = "complete"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class FreshnessStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class DeclarationRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    declaration_id: str
    ecosystem: str
    package_name: str
    declared_range: str | None = None
    manifest_path: str
    lock_path: str | None = None
    scope_id: str
    environment: str = ""
    line: int | None = Field(default=None, ge=1)
    eligible: bool = True
    eligibility_reason: str = "supported_declaration"
    is_duplicate: bool = False
    is_conflict: bool = False
    is_mutable: bool = False
    is_unbounded: bool = False
    is_unresolved_expression: bool = False


class ResolutionOccurrence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    occurrence_id: str
    declaration_id: str | None = None
    ecosystem: str
    package_name: str
    resolved_version: str | None = None
    version_scheme: str
    lock_path: str
    direct: bool = True
    dependency_path: tuple[str, ...] = ()
    environment: str = ""
    exact: bool = False
    unsupported_scheme: bool = False


class ScopeCoverage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scope_id: str
    manifest_path: str
    environment: str = ""
    status: MetricStatusName
    numerator: int | None = None
    denominator: int | None = None
    serialized: str | None = None
    reason: str | None = None
    missing_resolution: bool = False
    fully_resolved_ids: tuple[str, ...] = ()
    eligible_ids: tuple[str, ...] = ()
    occurrence_count: int = Field(ge=0, default=0)
    transitive_count: int = Field(ge=0, default=0)


class HygieneCounts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mutable: int = Field(ge=0, default=0)
    unbounded: int = Field(ge=0, default=0)
    unresolved: int = Field(ge=0, default=0)
    duplicate: int = Field(ge=0, default=0)
    conflicting: int = Field(ge=0, default=0)


class LicenseDecision(StrEnum):
    ALLOWED = "allowed"
    DISALLOWED = "disallowed"
    UNKNOWN = "unknown"
    METADATA_ONLY = "metadata_only"


class LicenseExpressionStatus(StrEnum):
    SPDX = "spdx"
    MISSING = "missing"
    MALFORMED = "malformed"
    UNSUPPORTED = "unsupported"
    CONFLICT = "conflict"


class LicensePolicy(BaseModel):
    """Explicit allow/deny configuration. Empty lists mean no policy constraint."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = "1.0.0"
    allow: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()

    @property
    def present(self) -> bool:
        return bool(self.allow or self.deny)


class LicenseRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    license_id: str
    ecosystem: str
    package_name: str
    resolved_version: str
    lock_path: str
    raw_expression: str
    normalized_expression: str
    expression_status: LicenseExpressionStatus
    decision: LicenseDecision
    decision_rule: str
    license_source: str
    known_spdx_ids: tuple[str, ...] = ()
    unknown_reason: str | None = None
    legal_compliance_verdict: bool = False


class LicenseSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    known_spdx: int = Field(ge=0, default=0)
    unknown: int = Field(ge=0, default=0)
    allowed: int = Field(ge=0, default=0)
    disallowed: int = Field(ge=0, default=0)
    metadata_only: int = Field(ge=0, default=0)
    missing: int = Field(ge=0, default=0)
    malformed: int = Field(ge=0, default=0)
    conflicting: int = Field(ge=0, default=0)
    unsupported: int = Field(ge=0, default=0)
    policy_present: bool = False
    legal_compliance_verdict: bool = False


class FeedFreshness(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: FreshnessStatus
    reason: str
    provider_id: str = "osv.dev"
    snapshot_digest: str = ""
    published_at: str | None = None
    evaluation_time: str | None = None
    max_age_days: int = 7
    age_seconds: int | None = None
    cannot_prove_clean: bool = True


class VulnerabilityMatch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    alias_group: str
    advisory_id: str
    aliases: tuple[str, ...] = ()
    ecosystem: str
    package_name: str
    resolved_version: str
    affected_range: str
    feed_severity: str
    yaml_default_severity: str
    effective_severity: str
    severity_basis: str
    snapshot_digest: str
    published_at: str | None = None
    lock_path: str
    dependency_paths: tuple[tuple[str, ...], ...] = ()
    withdrawn: bool = False
    qualified: bool = False
    qualification_reason: str | None = None


class MatchingScope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: MatchingStatus
    reason: str
    match_count: int | None = None
    cannot_prove_clean: bool = True
    zero_is_not_secure: bool = True


class SupplyChainEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_id: str
    declarations: tuple[DeclarationRecord, ...] = ()
    occurrences: tuple[ResolutionOccurrence, ...] = ()
    scopes: tuple[ScopeCoverage, ...] = ()
    hygiene: HygieneCounts = Field(default_factory=HygieneCounts)
    freshness: FeedFreshness
    matching: MatchingScope
    matches: tuple[VulnerabilityMatch, ...] = ()
    licenses: tuple[LicenseRecord, ...] = ()
    license_policy: LicensePolicy | None = None
    license_summary: LicenseSummary = Field(default_factory=LicenseSummary)
    unknown_version_packages: tuple[str, ...] = ()
    executed_repository_code: bool = False
    live_lookup: bool = False
    limitations: tuple[str, ...] = ()
