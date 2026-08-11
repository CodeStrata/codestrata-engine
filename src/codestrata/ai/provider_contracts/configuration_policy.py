"""Policy constants for Standardized Provider and Model Configuration (Epic 11, Slice 11.3).

Mirrors the shape of ``policy.py`` (Slice 11.2): a small, mostly-import-free
module of identifiers and bounded allowed-value sets. The one intentional
exception is ``ALLOWED_PROVIDER_IDS``, re-imported from the sibling
``policy.py`` rather than re-declared, so the two slices can never silently
drift apart on "what is a valid Engine provider ID." See
``engine/docs/ai-provider-configuration.md`` for the full design rationale.
"""

from __future__ import annotations

from codestrata.ai.provider_contracts.policy import ALLOWED_PROVIDER_IDS

# Identity of the policy and contract this module implements. Any future
# schema-breaking change to the configuration types below must bump these
# and publish a migration note in the docs.
POLICY_ID = "community-ai-provider-configuration-policy:1.0"
CONTRACT_ID = "community-ai-provider-configuration:1.0"
CONTRACT_VERSION = "1.0"

EPIC = "Epic 11: AI Provider Compatibility"
SLICE_ID = "11.3"
SLICE_TITLE = "Standardized Provider and Model Configuration"

# Re-exported for callers that only need configuration-side policy imports;
# always identical to policy.ALLOWED_PROVIDER_IDS (asserted in identifiers.py
# for the enum, and by verification for this constant).
CONFIGURATION_ALLOWED_PROVIDER_IDS: tuple[str, ...] = ALLOWED_PROVIDER_IDS

# Where a resolved configuration value can come from. Matches the actual
# `codestrata assess` precedence chain: CLI flag > environment variable >
# codestrata.toml file value > hardcoded default. Not every field has a
# value at every level (e.g. there is no `--provider` CLI flag today; see
# configuration_precedence.py for field-specific notes).
ALLOWED_SOURCE_CATEGORIES: tuple[str, ...] = (
    "cli",
    "environment",
    "configuration_file",
    "default",
)

# Kinds of credential a provider adapter needs, described abstractly —
# never as an actual secret value. "api_key" -> OpenAI's environment-variable
# API key; "aws_default_chain" -> Bedrock's boto3 default credential
# provider chain; "aws_profile" -> an optional named AWS profile override.
ALLOWED_CREDENTIAL_KINDS: tuple[str, ...] = (
    "api_key",
    "aws_default_chain",
    "aws_profile",
)

# Whether a credential appears to be available, without ever inspecting or
# recording its value. "unknown" covers cases (e.g. the AWS default
# credential provider chain) where availability cannot be determined without
# a real network call, which this package never makes.
ALLOWED_CREDENTIAL_AVAILABILITY_STATUSES: tuple[str, ...] = (
    "present",
    "absent",
    "unknown",
)

# Default provider and default model IDs. These MUST always equal the real
# production defaults (codestrata.config.settings.AiSettings.provider /
# DEFAULT_BEDROCK_MODEL_ID, and the "gpt-4o-mini" literal in
# codestrata.ai.providers.factory.resolve_assess_model_id). Slice 11.3 does
# not change these; it only represents them as configuration domain values.
# Verification cross-checks these literals against the loaded Slice 11.1
# baseline (verification.ai_provider_baseline.contract.DEFAULT_MODEL_IDS /
# DEFAULT_ASSESS_PROVIDER).
DEFAULT_PROVIDER_ID: str = "bedrock"
DEFAULT_MODEL_BY_PROVIDER: dict[str, str] = {
    "bedrock": "amazon.nova-lite-v1:0",
    "openai": "gpt-4o-mini",
}

# Slice 11.1 compatibility requirement IDs this module must remain
# compatible with (loaded for real, from the baseline package, only by the
# verification suite — see
# verification.ai_provider_configuration.baseline_compatibility).
REQUIRED_COMPATIBILITY_REQUIREMENT_IDS: tuple[str, ...] = (
    "CR-1",
    "CR-2",
    "CR-3",
    "CR-4",
    "CR-5",
    "CR-6",
)

# Hard constraints this slice must never violate (documentation + test fixture).
HARD_CONSTRAINTS: tuple[str, ...] = (
    "do_not_start_slice_11_4",
    "do_not_migrate_openai_or_bedrock",
    "do_not_wire_configuration_to_ai_provider_protocol",
    "do_not_change_provider_selection_defaults_or_model_resolution_defaults",
    "do_not_change_precedence_rename_or_remove_config_keys",
    "do_not_wire_timeout_or_retry_settings",
    "do_not_change_doctor_cli_or_execution_behavior",
    "do_not_add_a_third_party_llm_routing_provider",
    "do_not_modify_telemetry_analytics_community_cloud_data_lake_vscode_cursor_infrastructure",
    "do_not_commit_changes",
    "do_not_wire_configuration_into_assessment_product_path",
)

# NOTE: like policy.py (Slice 11.2), this module deliberately does not spell
# out the forbidden third-party router-provider name as a literal string
# constant — Slice 11.1's boundary checker
# (verification/ai_provider_baseline/boundaries.py) scans the entire `ai/`
# tree for that literal. ALLOWED_PROVIDER_IDS / CONFIGURATION_ALLOWED_PROVIDER_IDS
# above are the actual enforcement mechanism.


__all__ = [
    "ALLOWED_CREDENTIAL_AVAILABILITY_STATUSES",
    "ALLOWED_CREDENTIAL_KINDS",
    "ALLOWED_SOURCE_CATEGORIES",
    "CONFIGURATION_ALLOWED_PROVIDER_IDS",
    "CONTRACT_ID",
    "CONTRACT_VERSION",
    "DEFAULT_MODEL_BY_PROVIDER",
    "DEFAULT_PROVIDER_ID",
    "EPIC",
    "HARD_CONSTRAINTS",
    "POLICY_ID",
    "REQUIRED_COMPATIBILITY_REQUIREMENT_IDS",
    "SLICE_ID",
    "SLICE_TITLE",
]
