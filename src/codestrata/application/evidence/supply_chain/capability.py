"""Capability manifests for M12/M13/M14 supply-chain evidence (E06.3)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

CAPABILITY_MANIFEST_SCHEMA = "codestrata.supply_chain.capability.v1"
CAPABILITY_MANIFEST_VERSION = "e06.3.v1"
SUPPLY_CHAIN_ENVELOPE_SCHEMA = "codestrata.supply_chain.envelope.v1"
SUPPLY_CHAIN_COVERAGE_SCHEMA = "codestrata.supply_chain.coverage.v1"
CAP_M12 = "security.m12.resolution_hygiene"
CAP_M13 = "security.m13.known_vulnerability"
CAP_M14 = "security.m14.license_metadata"
FACT_KIND_DECLARATION = "supply_chain.declaration"
FACT_KIND_OCCURRENCE = "supply_chain.occurrence"
FACT_KIND_MATCH = "supply_chain.vulnerability_match"
FACT_KIND_LICENSE = "supply_chain.license"
FACT_KIND_COVERAGE = "supply_chain.coverage"


class CapabilityFamily(StrEnum):
    SECURITY = "security"


class CapabilityOutcome(StrEnum):
    SECURITY = "security"


class CapabilityNetwork(StrEnum):
    NONE = "none"


class EmptyScopeBehavior(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class CapabilityBudget(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_file_bytes: int = Field(ge=1)
    network: CapabilityNetwork = CapabilityNetwork.NONE


class CapabilityManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = CAPABILITY_MANIFEST_SCHEMA
    schema_version: str = CAPABILITY_MANIFEST_VERSION
    capability_id: str
    family: CapabilityFamily = CapabilityFamily.SECURITY
    outcome: CapabilityOutcome = CapabilityOutcome.SECURITY
    role: str = "flagship"
    version: str = CAPABILITY_MANIFEST_VERSION
    reads: tuple[str, ...]
    emits: tuple[str, ...]
    applicability: str
    fact_schema: str = "codestrata.supply_chain.facts.v1"
    coverage_schema: str = SUPPLY_CHAIN_COVERAGE_SCHEMA
    envelope_schema: str = SUPPLY_CHAIN_ENVELOPE_SCHEMA
    budgets: CapabilityBudget
    network: CapabilityNetwork = CapabilityNetwork.NONE
    coverage_unit: str
    coverage_requirement: str
    empty_scope: EmptyScopeBehavior = EmptyScopeBehavior.NOT_APPLICABLE
    direction: str
    comparison_unit: str
    epsilon: str = "0"
    failures: tuple[str, ...] = ()
    health_verdict: bool = False
    yaml_rule: bool = False
    live_lookup: bool = False
    limitations: tuple[str, ...] = ()


_BUDGET = CapabilityBudget(max_file_bytes=1_048_576)

SUPPLY_CHAIN_CAPABILITY_MANIFESTS: tuple[CapabilityManifest, ...] = (
    CapabilityManifest(
        capability_id=CAP_M12,
        reads=("manifest_declarations", "lock_resolution"),
        emits=(FACT_KIND_DECLARATION, FACT_KIND_OCCURRENCE, FACT_KIND_COVERAGE),
        applicability="manifest declarations and available lock resolution",
        coverage_unit="eligible_declaration_id",
        coverage_requirement=(
            "fully resolved eligible declaration IDs / eligible declaration IDs "
            "in the same manifest/workspace/environment scope"
        ),
        empty_scope=EmptyScopeBehavior.NOT_APPLICABLE,
        direction="higher_ratio_favorable",
        comparison_unit="ratio",
        epsilon="0.01",
        failures=(
            "unknown_ecosystem",
            "missing_lock",
            "lock_mismatch",
            "unsupported_version_scheme",
            "partial_context",
        ),
        limitations=(
            "never_install_packages",
            "occurrences_do_not_inflate_declaration_coverage",
            "unknown_denominator_never_0_or_100",
        ),
        budgets=_BUDGET,
    ),
    CapabilityManifest(
        capability_id=CAP_M13,
        reads=("resolved_package_versions", "pinned_osv_snapshot"),
        emits=(FACT_KIND_MATCH, FACT_KIND_COVERAGE),
        applicability="resolved versions plus fresh pinned OSV snapshot",
        coverage_unit="advisory_alias_group_plus_ecosystem_package_version",
        coverage_requirement="fresh supported feed required; else UNKNOWN not clean",
        empty_scope=EmptyScopeBehavior.UNKNOWN,
        direction="lower_count_favorable",
        comparison_unit="count",
        yaml_rule=True,
        failures=(
            "feed_missing",
            "feed_stale",
            "feed_unsupported",
            "no_exact_version",
            "withdrawn_advisory",
        ),
        limitations=(
            "no_silent_online_fallback",
            "zero_matches_is_not_secure",
            "alias_group_does_not_multiply_finding_count",
            "withdrawn_records_do_not_count",
        ),
        budgets=_BUDGET,
    ),
    CapabilityManifest(
        capability_id=CAP_M14,
        reads=("resolved_package_license_metadata", "explicit_allow_deny_policy"),
        emits=(FACT_KIND_LICENSE, FACT_KIND_COVERAGE),
        applicability="resolved package license metadata and configured allow/deny",
        coverage_unit="package_license_expression",
        coverage_requirement=(
            "known SPDX-compatible expressions evaluated against explicit policy; "
            "unknowns counted separately"
        ),
        empty_scope=EmptyScopeBehavior.NOT_APPLICABLE,
        direction="lower_count_favorable",
        comparison_unit="count",
        yaml_rule=True,
        failures=(
            "missing_metadata",
            "conflicting_metadata",
            "malformed_expression",
            "unsupported_expression",
            "absent_policy",
        ),
        limitations=(
            "not_legal_compliance",
            "absent_policy_is_metadata_only",
            "unknown_never_guessed_allow_or_deny",
        ),
        budgets=_BUDGET,
    ),
)


def capability_manifests() -> tuple[CapabilityManifest, ...]:
    return SUPPLY_CHAIN_CAPABILITY_MANIFESTS
