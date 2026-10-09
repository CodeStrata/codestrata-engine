"""Capability manifests for security M10/M11 (E06.1).

Engine-local until E01.2 publishes shared AnalyzerDescriptor catalog.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

CAPABILITY_MANIFEST_SCHEMA = "codestrata.security.capability.v1"
CAPABILITY_MANIFEST_VERSION = "e06.1.v1"
SECURITY_ENVELOPE_SCHEMA = "codestrata.security.envelope.v1"
SECURITY_COVERAGE_SCHEMA = "codestrata.security.coverage.v1"
CAP_M10 = "security.m10.secrets"
CAP_M11 = "security.m11.insecure_configuration"
FACT_KIND_SECRET = "security.secret_finding"
FACT_KIND_CONFIG = "security.configuration_finding"
FACT_KIND_COVERAGE = "security.coverage"


class CapabilityFamily(StrEnum):
    SECURITY = "security"


class CapabilityOutcome(StrEnum):
    SECURITY = "security"


class CapabilityDirection(StrEnum):
    LOWER_FAVORABLE = "lower_favorable"


class CapabilityNetwork(StrEnum):
    NONE = "none"


class EmptyScopeBehavior(StrEnum):
    NOT_APPLICABLE = "not_applicable"


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
    reads: tuple[str, ...] = ("repository_sensitive.facts",)
    emits: tuple[str, ...]
    applicability: str
    fact_schema: str = "codestrata.security.findings.v1"
    coverage_schema: str = SECURITY_COVERAGE_SCHEMA
    envelope_schema: str = SECURITY_ENVELOPE_SCHEMA
    budgets: CapabilityBudget
    network: CapabilityNetwork = CapabilityNetwork.NONE
    coverage_unit: str
    coverage_requirement: str
    empty_scope: EmptyScopeBehavior = EmptyScopeBehavior.NOT_APPLICABLE
    direction: CapabilityDirection = CapabilityDirection.LOWER_FAVORABLE
    comparison_unit: str = "count"
    epsilon: str = "0"
    failures: tuple[str, ...] = ()
    health_verdict: bool = False
    yaml_rule: bool = True
    git_history_scanned: bool = False
    limitations: tuple[str, ...] = ()


_BUDGET = CapabilityBudget(max_file_bytes=1_048_576)

SECURITY_CAPABILITY_MANIFESTS: tuple[CapabilityManifest, ...] = (
    CapabilityManifest(
        capability_id=CAP_M10,
        emits=(FACT_KIND_SECRET, FACT_KIND_COVERAGE),
        applicability="supported_source_config_literals",
        coverage_unit="rule_source_subject_occurrence",
        coverage_requirement=(
            "unique rule + source-subject + occurrence after placeholder classification"
        ),
        failures=(
            "unsupported_encoding",
            "unsupported_language",
            "binary_keystore",
        ),
        limitations=(
            "no_git_history_scan",
            "no_raw_secret_retention",
            "identity_independent_of_raw_bytes",
        ),
        budgets=_BUDGET,
    ),
    CapabilityManifest(
        capability_id=CAP_M11,
        emits=(FACT_KIND_CONFIG, FACT_KIND_COVERAGE),
        applicability="static_supported_tls_auth_cors_debug_config",
        coverage_unit="named_yaml_rule_finding",
        coverage_requirement=(
            "separate counts for tls/auth/cors/debug; production context evidenced"
        ),
        failures=(
            "unsupported_expression",
            "conditional_environment",
            "conflicting_configuration",
        ),
        limitations=(
            "unknown_environment_is_not_assumed_production",
            "no_runtime_exploitability_claim",
        ),
        budgets=_BUDGET,
    ),
)


def capability_manifests() -> tuple[CapabilityManifest, ...]:
    return SECURITY_CAPABILITY_MANIFESTS
