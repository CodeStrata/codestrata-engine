"""Policy constants for Provider Usage Metadata and Capability Discovery (Epic 11, Slice 11.5).

Mirrors the shape of ``policy.py`` (Slice 11.2), ``configuration_policy.py``
(Slice 11.3), and ``execution_policy.py`` (Slice 11.4): a small module of
identifiers and bounded allowed-value sets, re-using
``ALLOWED_PROVIDER_IDS``/``ALLOWED_CAPABILITY_IDS`` from the sibling
``policy.py`` rather than re-declaring them. See
``engine/docs/ai-provider-capabilities.md`` for the full design rationale.

Like every policy module in this package, this module deliberately does not
spell out the forbidden third-party router-provider name as a literal string
constant (see ``policy.py``'s module docstring for why).
"""

from __future__ import annotations

from codestrata.ai.provider_contracts.policy import ALLOWED_CAPABILITY_IDS, ALLOWED_PROVIDER_IDS

POLICY_ID = "community-ai-provider-capability-policy:1.0"
CONTRACT_ID = "community-ai-provider-capability:1.0"
CONTRACT_VERSION = "1.0"

EPIC = "Epic 11: AI Provider Compatibility"
SLICE_ID = "11.5"
SLICE_TITLE = "Provider Usage Metadata and Capability Discovery"

# Re-exported for callers that only need capability-side policy imports;
# always identical to policy.ALLOWED_PROVIDER_IDS / policy.ALLOWED_CAPABILITY_IDS.
CAPABILITY_ALLOWED_PROVIDER_IDS: tuple[str, ...] = ALLOWED_PROVIDER_IDS
CAPABILITY_ALLOWED_CAPABILITY_IDS: tuple[str, ...] = ALLOWED_CAPABILITY_IDS

# The bounded, closed set of boolean feature-flag names a
# ProviderCapabilityProfile may declare. Used by capability_validation.py to
# confirm every flag on a profile is a real, declared bool field.
ALLOWED_CAPABILITY_FEATURE_FLAGS: tuple[str, ...] = (
    "supports_structured_json",
    "supports_streaming",
    "supports_timeout_policy",
    "supports_retry_policy",
    "reports_usage_metadata",
    "reports_token_accounting",
)

# The bounded, closed set of limitation strings a ProviderCapabilityProfile
# may declare. "prompt_instruction_only" documents that a provider's
# structured-JSON support (if any) is prompt-instruction-based rather than a
# native provider JSON mode. "not_wired_to_runtime" documents that
# supports_timeout_policy/supports_retry_policy describe adapter-capability
# only — no adapter honors either policy today. "streaming_not_implemented"
# documents that supports_streaming=False reflects "no streaming code exists
# yet", not a provider SDK limitation. The OpenRouter-specific values
# (Slice 11.9) record that the adapter exists but is runtime-unregistered
# and that configuration/auth are deferred.
ALLOWED_CAPABILITY_LIMITATIONS: tuple[str, ...] = (
    "prompt_instruction_only",
    "not_wired_to_runtime",
    "streaming_not_implemented",
    "runtime_unregistered",
    "configuration_deferred",
    "authentication_deferred",
    "model_support_for_structured_json_varies",
)

# Slice 11.1 compatibility requirement IDs this module must remain
# compatible with (loaded for real, from the baseline package, only by the
# verification suite — see
# verification.ai_provider_capabilities.compatibility).
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
    "do_not_start_slice_11_6",
    "do_not_migrate_openai_or_bedrock",
    "do_not_wire_capability_discovery_or_usage_metadata_into_assess_enrichment_doctor_or_factory",
    "do_not_add_a_third_party_llm_routing_provider",
    "do_not_modify_runtime_provider_behavior",
    "do_not_modify_telemetry_analytics_community_cloud_data_lake_vscode_cursor_infrastructure",
    "do_not_commit_changes",
)

__all__ = [
    "ALLOWED_CAPABILITY_FEATURE_FLAGS",
    "ALLOWED_CAPABILITY_LIMITATIONS",
    "CAPABILITY_ALLOWED_CAPABILITY_IDS",
    "CAPABILITY_ALLOWED_PROVIDER_IDS",
    "CONTRACT_ID",
    "CONTRACT_VERSION",
    "EPIC",
    "HARD_CONSTRAINTS",
    "POLICY_ID",
    "REQUIRED_COMPATIBILITY_REQUIREMENT_IDS",
    "SLICE_ID",
    "SLICE_TITLE",
]
