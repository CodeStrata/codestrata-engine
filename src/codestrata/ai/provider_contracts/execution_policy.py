"""Policy constants for Standardized Execution, Errors, Timeouts, and Retries (Epic 11, Slice 11.4).

Mirrors the shape of ``policy.py`` (Slice 11.2) and ``configuration_policy.py``
(Slice 11.3): a small, mostly-import-free module of identifiers and bounded
allowed-value sets, re-using ``ALLOWED_PROVIDER_IDS``/``ALLOWED_ERROR_CATEGORIES``
from the sibling ``policy.py`` rather than re-declaring them. See
``engine/docs/ai-provider-execution.md`` for the full design rationale.

This module deliberately restates two real, unrelated settings defaults as
plain literals (``DEFAULT_TIMEOUT_SECONDS``, ``SETTINGS_DEFAULT_MAX_RETRIES``)
rather than importing ``codestrata.ai.providers.models`` /
``codestrata.config.settings`` — this package has zero ``codestrata``
dependencies outside itself (see ``dependency_boundary`` tests). The
verification suite is responsible for cross-checking these literals against
the real values.
"""

from __future__ import annotations

from codestrata.ai.provider_contracts.policy import ALLOWED_ERROR_CATEGORIES, ALLOWED_PROVIDER_IDS

POLICY_ID = "community-ai-provider-execution-policy:1.0"
CONTRACT_ID = "community-ai-provider-execution:1.0"
CONTRACT_VERSION = "1.0"

EPIC = "Epic 11: AI Provider Compatibility"
SLICE_ID = "11.4"
SLICE_TITLE = "Standardized Execution, Errors, Timeouts, and Retries"

# Re-exported for callers that only need execution-side policy imports;
# always identical to policy.ALLOWED_PROVIDER_IDS.
EXECUTION_ALLOWED_PROVIDER_IDS: tuple[str, ...] = ALLOWED_PROVIDER_IDS

# Where a timeout applies. "provider_request" bounds a single
# AIProvider.execute() call; "total_execution" would bound the entire retry
# loop across all attempts. This is a policy value only — see executor.py's
# module docstring for why AIProviderExecutor never enforces either scope
# itself (no threads/signals/asyncio); real enforcement is deferred to a
# future adapter.
ALLOWED_TIMEOUT_SCOPES: tuple[str, ...] = ("provider_request", "total_execution")

# Bounded backoff strategies between retry attempts. No jitter-only strategy:
# jitter is a boolean modifier of "fixed"/"exponential", not its own strategy.
ALLOWED_BACKOFF_STRATEGIES: tuple[str, ...] = ("none", "fixed", "exponential")

# Restates codestrata.ai.providers.models.DEFAULT_TIMEOUT_SECONDS (60.0) as a
# literal. Verification cross-checks this against the real value.
DEFAULT_TIMEOUT_SECONDS: float = 60.0
MAX_TIMEOUT_SECONDS: float = 3600.0

# Restates BedrockSettings.max_retries / OpenAISettings.max_retries's default
# value (3) as a literal, used only to build SETTINGS_REPRESENTABLE_RETRY_POLICY
# (retry_policy.py) — a pure *representation* of what that settings default
# would mean as maximum_attempts, never wired to anything. Verification
# cross-checks this literal against the real settings defaults.
SETTINGS_DEFAULT_MAX_RETRIES: int = 3

# CR-1 (exact-one-invoke): the default retry policy makes exactly one attempt.
DEFAULT_MAXIMUM_ATTEMPTS: int = 1
MAX_MAXIMUM_ATTEMPTS: int = 10

# The bounded, closed partition of ErrorCategory into retryable / non-retryable
# under the *default* retry policy (a caller-supplied AIProviderRetryPolicy may
# use a different partition — see retry_policy.py). Rationale: transient,
# infrastructure-shaped failures (a timed-out call, rate limiting, a
# temporarily unavailable provider) are worth retrying; failures caused by the
# request/configuration itself (bad auth, bad model, invalid input/output,
# parsing failures, missing configuration, an unavailable dependency) or an
# unexpected internal failure will not be fixed by retrying, so they are not.
DEFAULT_RETRYABLE_ERROR_CATEGORIES: tuple[str, ...] = (
    "timeout",
    "rate_limited",
    "provider_unavailable",
)
DEFAULT_NON_RETRYABLE_ERROR_CATEGORIES: tuple[str, ...] = (
    "missing_configuration",
    "dependency_unavailable",
    "authentication_failed",
    "authorization_failed",
    "invalid_model",
    "invalid_request",
    "invalid_response",
    "parsing_failed",
    "internal_failure",
)

assert set(DEFAULT_RETRYABLE_ERROR_CATEGORIES) | set(
    DEFAULT_NON_RETRYABLE_ERROR_CATEGORIES
) == set(ALLOWED_ERROR_CATEGORIES), (
    "the default retryable/non-retryable partition must cover every ErrorCategory exactly once"
)
assert set(DEFAULT_RETRYABLE_ERROR_CATEGORIES).isdisjoint(DEFAULT_NON_RETRYABLE_ERROR_CATEGORIES)

# Slice 11.1 compatibility requirement IDs this module must remain
# compatible with (loaded for real, from the baseline package, only by the
# verification suite — see
# verification.ai_provider_execution.baseline_compatibility).
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
    "do_not_start_slice_11_5",
    "do_not_migrate_openai_or_bedrock",
    "do_not_wire_executor_into_assess_enrichment_providers_doctor_cli_or_factory",
    "do_not_change_defaults_selection_credentials_wire_formats_doctor_fail_soft_prompts_reports_or_schemas",
    "do_not_add_a_third_party_llm_routing_provider",
    "do_not_modify_telemetry_analytics_community_cloud_data_lake_vscode_cursor_infrastructure",
    "do_not_commit_changes",
)

# NOTE: like policy.py (Slice 11.2) and configuration_policy.py (Slice 11.3),
# this module deliberately does not spell out the forbidden third-party
# router-provider name as a literal string constant.

__all__ = [
    "ALLOWED_BACKOFF_STRATEGIES",
    "ALLOWED_TIMEOUT_SCOPES",
    "CONTRACT_ID",
    "CONTRACT_VERSION",
    "DEFAULT_MAXIMUM_ATTEMPTS",
    "DEFAULT_NON_RETRYABLE_ERROR_CATEGORIES",
    "DEFAULT_RETRYABLE_ERROR_CATEGORIES",
    "DEFAULT_TIMEOUT_SECONDS",
    "EPIC",
    "EXECUTION_ALLOWED_PROVIDER_IDS",
    "HARD_CONSTRAINTS",
    "MAX_MAXIMUM_ATTEMPTS",
    "MAX_TIMEOUT_SECONDS",
    "POLICY_ID",
    "REQUIRED_COMPATIBILITY_REQUIREMENT_IDS",
    "SETTINGS_DEFAULT_MAX_RETRIES",
    "SLICE_ID",
    "SLICE_TITLE",
]
