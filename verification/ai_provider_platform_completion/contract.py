"""Contract constants for SV.11.13 AI Provider Platform Completion Verification.

CodeStrata v0.2.0 Epic 11, Slice 11.13 is the authoritative completion gate for
all 13 Epic 11 slices. Verification and documentation-consistency only. No
provider behavior or default changes. Decision B retained. Bedrock remains the
default provider. Epic 12 is not started. No commit/tag/publish/deploy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

VERIFICATION_ID = "ai-provider-platform-completion-verification"
VERIFICATION_VERSION = "1.0.0"
SCHEMA_NAME = "ai-provider-platform-completion-verification"
SCHEMA_VERSION = "1.0.0"

EPIC = 11
EPIC_LABEL = "Epic 11: AI Provider Compatibility"
SLICE_ID = "11.13"
SLICE_TITLE = "Epic Boundary and Completion Verification"
RELEASE = "0.2.0"

COMPLETED_SLICES = 13
TOTAL_SLICES = 13
START_EPIC_12 = False

PROVIDERS: tuple[str, ...] = ("bedrock", "openai", "openrouter")
DEFAULT_PROVIDER = "bedrock"
ASSESS_REGISTERED_PROVIDERS: tuple[str, ...] = ("bedrock", "openai", "openrouter")

REGISTRY_DECISION = "B"
REGISTRY_DECISION_LABEL = "compatibility_registry_retained"

ASSESSMENT_SCHEMA_VERSION = "1.2"
EXPECTED_MAXIMUM_ATTEMPTS = 1

NEGATIVE_SCENARIO_COUNT_MIN = 26

BEDROCK_DEFAULT_MODEL = "amazon.nova-lite-v1:0"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"

OUTPUT_RELATIVE = "reports/verification/sv11-13"
REPORT_FILENAME = "ai-provider-platform-completion-verification.json"
REPORT_MD_FILENAME = "ai-provider-platform-completion-verification.md"

ALLOWED_VERDICTS: tuple[str, ...] = ("pass", "pass_with_limitations")

EXPECTED_LIMITATIONS: tuple[str, ...] = (
    "no_live_provider_calls",
    "no_real_credentials",
    "no_remote_model_validation",
    "no_remote_credential_validation",
    "compatibility_registry_retained",
    "operational_retry_conservative",
    "wall_clock_timeout_client_owned",
    "no_full_external_extension_host_or_cloud_validation",
    "worktree_uncommitted",
)

PRODUCT_CONTRACT_IDS: tuple[str, ...] = (
    "community-ai-provider-contract:1.0",
    "community-ai-provider-configuration:1.0",
    "community-ai-provider-execution:1.0",
    "community-ai-provider-capability:1.0",
    "community-ai-provider-usage:1.0",
)

PRODUCT_POLICY_IDS: tuple[str, ...] = (
    "community-ai-provider-contract-policy:1.0",
    "community-ai-provider-configuration-policy:1.0",
    "community-ai-provider-execution-policy:1.0",
    "community-ai-provider-capability-policy:1.0",
    "community-ai-provider-usage-policy:1.0",
)

COMPATIBILITY_REQUIREMENT_IDS: tuple[str, ...] = (
    "CR-1",
    "CR-2",
    "CR-3",
    "CR-4",
    "CR-5",
    "CR-6",
)

FORBIDDEN_STALE_CLAIMS: tuple[str, ...] = (
    "Slice 11.13 is not started",
    "Slice 11.12 is not started",
    "OpenRouter not started",
    "OpenRouter remains Slice 11.9 and is not started",
    "openrouter_not_started",
    "OpenRouter is not implemented",
)

CURRENT_POSTURE_DOC_RELATIVE: tuple[str, ...] = (
    "ARCHITECTURE.md",
    "engine/docs/ai-provider-platform.md",
    "engine/docs/ai-provider-openrouter-doctor.md",
    "engine/docs/ai-provider-bedrock.md",
    "engine/docs/ai-provider-capabilities.md",
    "engine/docs/ai-provider-openai.md",
    "engine/docs/ai-provider-security-boundaries.md",
    "engine/verification/README.md",
    "engine/README.md",
    "engine/docs/README.md",
    "engine/docs/telemetry-ai-analytics.md",
    "engine/verification/ai_provider_baseline/README.md",
    "engine/verification/ai_provider_contracts/README.md",
    "engine/verification/ai_provider_configuration/README.md",
    "engine/verification/ai_provider_execution/README.md",
    "engine/verification/ai_provider_capabilities/README.md",
    "engine/verification/openai_provider_migration/README.md",
)

CLI_FORBIDDEN_FLAG_TOKENS: tuple[str, ...] = (
    "--openrouter-api-key",
    "--api-key",
    "--send-test",
)

DOCTOR_FORBIDDEN_CALL_TOKENS: tuple[str, ...] = (
    "OpenAI(",
    "resolve_client(",
)

PRIVACY_FORBIDDEN_FRAGMENTS: tuple[str, ...] = (
    "sk-synth-",
    "AKIASYNTH",
    "Authorization: Bearer",
    "/Users/synthetic",
    "Traceback (most recent call last)",
    "SYNTHETIC_COMPLETION_PROMPT",
    "SYNTHETIC_COMPLETION_RESPONSE",
)

RELEASE_POSTURE: dict[str, bool] = {
    "epic_11_complete": True,
    "commit": False,
    "tag": False,
    "publish": False,
    "deploy": False,
    "live_provider_validation": False,
    "real_credential_validation": False,
    "start_epic_12": False,
    "worktree_may_contain_uncommitted_epic11_changes": True,
}

REQUIRED_MANIFEST_DOCS: tuple[str, ...] = (
    "docs/ai-provider-security-boundaries.md",
    "docs/ai-provider-openrouter.md",
    "docs/ai-provider-openrouter-configuration.md",
    "docs/ai-provider-openrouter-doctor.md",
)

ADAPTER_PACKAGES: tuple[str, ...] = (
    "src/codestrata/ai/provider_adapters/openai",
    "src/codestrata/ai/provider_adapters/bedrock",
    "src/codestrata/ai/provider_adapters/openrouter",
)

WRAPPER_MODULES: tuple[str, ...] = (
    "src/codestrata/ai/providers/openai_provider.py",
    "src/codestrata/ai/providers/bedrock.py",
    "src/codestrata/ai/providers/openrouter_provider.py",
)


@dataclass(frozen=True, slots=True)
class AIProviderPlatformCompletionVerificationContract:
    verification_id: str = VERIFICATION_ID
    verification_version: str = VERIFICATION_VERSION
    schema_name: str = SCHEMA_NAME
    schema_version: str = SCHEMA_VERSION
    epic: int = EPIC
    release: str = RELEASE
    slice_id: str = SLICE_ID
    completed_slices: int = COMPLETED_SLICES
    total_slices: int = TOTAL_SLICES
    start_epic_12: bool = START_EPIC_12
    allowed_verdicts: tuple[str, ...] = ALLOWED_VERDICTS
    expected_limitations: tuple[str, ...] = EXPECTED_LIMITATIONS
    registry_decision: str = REGISTRY_DECISION
    notes: tuple[str, ...] = field(
        default_factory=lambda: (
            "SV.11.13 proves Epic 11 completion across all 13 slices.",
            "PASS_WITH_LIMITATIONS expected: no live provider calls; no real "
            "credentials; Decision B retained; worktree may be uncommitted.",
            "Epic 12 is not started.",
        )
    )


def default_contract() -> AIProviderPlatformCompletionVerificationContract:
    return AIProviderPlatformCompletionVerificationContract()


__all__ = [
    "ADAPTER_PACKAGES",
    "ALLOWED_VERDICTS",
    "ASSESSMENT_SCHEMA_VERSION",
    "ASSESS_REGISTERED_PROVIDERS",
    "BEDROCK_DEFAULT_MODEL",
    "CLI_FORBIDDEN_FLAG_TOKENS",
    "COMPATIBILITY_REQUIREMENT_IDS",
    "COMPLETED_SLICES",
    "CURRENT_POSTURE_DOC_RELATIVE",
    "DEFAULT_PROVIDER",
    "DOCTOR_FORBIDDEN_CALL_TOKENS",
    "EPIC",
    "EPIC_LABEL",
    "EXPECTED_LIMITATIONS",
    "EXPECTED_MAXIMUM_ATTEMPTS",
    "FORBIDDEN_STALE_CLAIMS",
    "NEGATIVE_SCENARIO_COUNT_MIN",
    "OPENAI_DEFAULT_MODEL",
    "OUTPUT_RELATIVE",
    "PRIVACY_FORBIDDEN_FRAGMENTS",
    "PRODUCT_CONTRACT_IDS",
    "PRODUCT_POLICY_IDS",
    "PROVIDERS",
    "REGISTRY_DECISION",
    "REGISTRY_DECISION_LABEL",
    "RELEASE",
    "RELEASE_POSTURE",
    "REPORT_FILENAME",
    "REPORT_MD_FILENAME",
    "REQUIRED_MANIFEST_DOCS",
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "SLICE_ID",
    "SLICE_TITLE",
    "START_EPIC_12",
    "TOTAL_SLICES",
    "VERIFICATION_ID",
    "VERIFICATION_VERSION",
    "WRAPPER_MODULES",
    "AIProviderPlatformCompletionVerificationContract",
    "default_contract",
]
