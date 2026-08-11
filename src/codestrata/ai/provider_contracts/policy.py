"""Policy constants for the Common AI Provider Contracts (Epic 11, Slice 11.2).

This module has **zero imports** from the rest of ``codestrata`` on purpose:
the policy identifiers, allowed value sets, and forbidden tokens defined here
are the root of a fully self-contained, SDK-free domain package. See
``engine/docs/ai-provider-contracts.md`` for the full design rationale.
"""

from __future__ import annotations

# Identity of the policy and contract this package implements. Any future
# schema-breaking change to the contract types below must bump these and
# publish a migration note in the docs.
POLICY_ID = "community-ai-provider-contract-policy:1.0"
CONTRACT_ID = "community-ai-provider-contract:1.0"
CONTRACT_VERSION = "1.0"

EPIC = "Epic 11: AI Provider Compatibility"
SLICE_ID = "11.2"
SLICE_TITLE = "Common AI Provider Contracts"

# Engine provider IDs (matches verification.ai_provider_baseline.contract.
# ENGINE_PROVIDER_IDS — duplicated here as literals, not imported, so this
# package has no dependency on the verification tree). "aws_bedrock" is an
# analytics-only provider_family label and is intentionally not a value here.
# Engine provider IDs known to the provider-platform contracts. Assess runtime
# registration may be a strict subset (today: bedrock + openai). The third
# value is the OpenRouter adapter ID (Slice 11.9); it is not the assess default
# and is not registered in AssessAIProviderRegistry in that slice.
ALLOWED_PROVIDER_IDS: tuple[str, ...] = ("bedrock", "openai", "openrouter")

# A single capability is in scope for Slice 11.2. "Modernization Advisor" is
# the product-facing display name; the stable identifier matches the
# analytics capability catalog (APPROVED_AI_CAPABILITIES).
ALLOWED_CAPABILITY_IDS: tuple[str, ...] = ("modernization_advisor",)

# What shape of content a caller expects back. "structured_json" describes
# the caller's expectation only — whether an adapter uses a provider's native
# JSON-mode is an adapter implementation detail, not part of this contract.
ALLOWED_RESPONSE_EXPECTATIONS: tuple[str, ...] = ("text", "structured_json")

# Coarse execution outcomes for a single AIProvider.execute() call. Deliberately
# smaller and adapter-neutral compared to codestrata.reporting.modernization_models.
# AIExecutionStatus; see execution.py for the documented (not-imported) mapping.
ALLOWED_EXECUTION_STATUSES: tuple[str, ...] = ("success", "unavailable", "failed", "skipped")

# Bounded error categories. No other category may be used; no raw exception
# text or provider SDK exception classes may ever appear in an AIProviderError.
ALLOWED_ERROR_CATEGORIES: tuple[str, ...] = (
    "missing_configuration",
    "dependency_unavailable",
    "authentication_failed",
    "authorization_failed",
    "invalid_model",
    "timeout",
    "rate_limited",
    "provider_unavailable",
    "invalid_request",
    "invalid_response",
    "parsing_failed",
    "internal_failure",
)

# Slice 11.1 compatibility requirement IDs this package must remain
# compatible with (loaded for real, from the baseline package, only by the
# verification suite — see verification/ai_provider_contracts/baseline_compatibility.py).
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
    "do_not_start_slice_11_3",
    "do_not_migrate_openai_or_bedrock",
    "do_not_add_a_third_party_llm_routing_provider",
    "do_not_change_provider_selection_defaults_config_model_resolution",
    "do_not_change_timeouts_retries_auth_errors_doctor_or_ai_execution",
    "do_not_modify_telemetry_analytics_community_cloud_data_lake_vscode_cursor_infrastructure",
    "do_not_wire_contracts_into_assessment_product_path",
)


__all__ = [
    "ALLOWED_CAPABILITY_IDS",
    "ALLOWED_ERROR_CATEGORIES",
    "ALLOWED_EXECUTION_STATUSES",
    "ALLOWED_PROVIDER_IDS",
    "ALLOWED_RESPONSE_EXPECTATIONS",
    "CONTRACT_ID",
    "CONTRACT_VERSION",
    "EPIC",
    "HARD_CONSTRAINTS",
    "POLICY_ID",
    "REQUIRED_COMPATIBILITY_REQUIREMENT_IDS",
    "SLICE_ID",
    "SLICE_TITLE",
]
