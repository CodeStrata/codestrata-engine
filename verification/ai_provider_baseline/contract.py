"""Contract constants for SV.11.1 AI Provider Compatibility Baseline.

CodeStrata v0.2.0 Epic 11, Slice 11.1 — Existing AI Architecture and
Compatibility Baseline. This module is **characterization only**: it records
the ground truth of the *existing* Engine AI provider architecture so Slice
11.2+ work has a frozen, evidence-backed starting point.

Hard constraints for this slice (do not violate in this package):

* No new common provider interface / provider platform / registry redesign.
* No OpenAI/Bedrock migration. No OpenRouter.
* No change to AI execution, selection, models, credentials, timeouts,
  retries, fail-soft, prompts, reports, Findings, or schemas.
* No real credentials, no provider network calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from codestrata.ai.providers.models import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT_SECONDS,
)
from codestrata.config.settings import DEFAULT_BEDROCK_MODEL_ID
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION

VERIFICATION_ID = "ai-provider-compatibility-baseline-verification"
VERIFICATION_VERSION = "1.0.0"

SCHEMA_NAME = "ai-provider-compatibility-baseline"
SCHEMA_VERSION = "1.0.0"

EPIC = "Epic 11: AI Provider Compatibility"
SLICE_ID = "11.1"
SLICE_TITLE = "Existing AI Architecture and Compatibility Baseline"

# Engine assess provider IDs — ground truth from
# codestrata.extensions.assess_ai._bootstrap_assess_providers(). "bedrock" is
# the default per codestrata.config.settings.AiSettings.provider.
ENGINE_PROVIDER_IDS: tuple[str, ...] = ("bedrock", "openai", "openrouter")
DEFAULT_ASSESS_PROVIDER = "bedrock"

# Analytics family mapping (record separately; the Engine provider ID remains
# "bedrock" — see codestrata.telemetry.analytics.ai_analytics_catalogs).
PROVIDER_FAMILY_MAP: dict[str, str] = {
    "bedrock": "aws_bedrock",
    "openai": "openai",
}

# Default model IDs. Bedrock default comes from config.settings; the OpenAI
# default is a literal fallback in providers/factory.py::resolve_assess_model_id
# and providers/doctor.py::_resolve_model_label (both hardcode "gpt-4o-mini").
DEFAULT_MODEL_IDS: dict[str, str] = {
    "bedrock": DEFAULT_BEDROCK_MODEL_ID,
    "openai": "gpt-4o-mini",
}

# codestrata.ai.providers.models: process-wide invocation defaults.
MODEL_INVOCATION_DEFAULTS: dict[str, float | int] = {
    "max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
    "temperature": DEFAULT_TEMPERATURE,
    "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
}

# codestrata.application.assessment.service.DEFAULT_ASSESS_MAX_OUTPUT_TOKENS —
# the Modernization Advisor assess path overrides the provider-neutral 8192
# default down to 5000 at the CLI/application layer.
ASSESS_ADVISOR_MAX_OUTPUT_TOKENS = 5000

ASSESSMENT_SCHEMA_VERSION = ASSESSMENT_JSON_SCHEMA_VERSION  # "1.2"

# AiEnrichmentService.run() calls provider.invoke() exactly once per assess
# run; codestrata.ai.providers.common.retry_call exists but is not imported
# or called by either production provider (bedrock.py / openai_provider.py).
INVOKE_CALLS_PER_ASSESS_RUN = 1

# BedrockSettings.timeout_seconds / max_retries and OpenAISettings.timeout_seconds
# / max_retries are declared in codestrata.config.settings but are NOT read by
# codestrata.extensions.assess_ai._bootstrap_assess_providers() when
# constructing BedrockAIModelProvider / OpenAIAIModelProvider for assess. This
# is a baseline finding / limitation for Slice 11.2+, not fixed here.
SETTINGS_TIMEOUT_MAX_RETRIES_WIRED_TO_ASSESS_FACTORY = False

# Optional extras (engine/pyproject.toml [project.optional-dependencies]).
OPTIONAL_EXTRAS: dict[str, tuple[str, ...]] = {
    "bedrock": ("boto3",),
    "openai": ("openai",),
}

# Existing partial abstraction surface (Phase 5.8 / 6.5) — inventoried, not
# expanded, by this slice.
EXISTING_COUPLING_SURFACE: tuple[str, ...] = (
    "codestrata.ai.providers.base.AIModelProvider",
    "codestrata.extensions.assess_ai.AssessAIProviderRegistry",
    "codestrata.ai.providers.registry.AIProviderRegistry",
)

# Relative-to-``src/codestrata`` modules inventoried for structural coupling.
# Adding a file to ai/providers/ beyond this set (other than tests/docs) is a
# signal that Slice 11.2 (or an out-of-scope provider platform) may have
# started; see boundaries.py::check_no_new_provider_platform_files.
INVENTORIED_MODULES: tuple[str, ...] = (
    "ai/providers/__init__.py",
    "ai/providers/base.py",
    "ai/providers/bedrock.py",
    "ai/providers/common.py",
    "ai/providers/doctor.py",
    "ai/providers/exceptions.py",
    "ai/providers/factory.py",
    "ai/providers/models.py",
    "ai/providers/openai_provider.py",
    "ai/providers/openrouter_provider.py",
    "ai/providers/parsing.py",
    "ai/providers/registry.py",
    "ai/aws_config.py",
    "ai/enrichment/service.py",
    "extensions/assess_ai.py",
)

ALLOWED_AI_PROVIDERS_DIRECTORY_FILES: frozenset[str] = frozenset(
    {
        "__init__.py",
        "base.py",
        "bedrock.py",
        "common.py",
        "doctor.py",
        "exceptions.py",
        "factory.py",
        "models.py",
        "openai_provider.py",
        "openrouter_provider.py",
        "parsing.py",
        "registry.py",
        "settings_policies.py",
    }
)

# Forbidden tokens for this slice — presence anywhere under ai/providers/ or
# extensions/assess_ai.py would indicate scope creep beyond Slice 11.1.
FORBIDDEN_PROVIDER_TOKENS: tuple[str, ...] = (
    "openrouter",
    "OpenRouter",
    "OPENROUTER",
)

EXPECTED_LIMITATIONS: tuple[str, ...] = (
    "no_live_provider_calls",
    "no_real_credentials",
    "settings_timeout_max_retries_not_wired_to_assess_factory",
)

OUTPUT_RELATIVE = "reports/verification/sv11-1"
REPORT_FILENAME = "ai-provider-compatibility-baseline.json"
REPORT_MD_FILENAME = "ai-provider-compatibility-baseline.md"

NEGATIVE_SCENARIO_COUNT_MIN = 20


@dataclass(frozen=True, slots=True)
class BaselineContract:
    """Pass/fail contract for SV.11.1 AI provider compatibility baseline."""

    verification_id: str = VERIFICATION_ID
    verification_version: str = VERIFICATION_VERSION
    schema_name: str = SCHEMA_NAME
    schema_version: str = SCHEMA_VERSION
    epic: str = EPIC
    slice_id: str = SLICE_ID
    providers: tuple[str, ...] = ENGINE_PROVIDER_IDS
    default_provider: str = DEFAULT_ASSESS_PROVIDER
    assessment_schema_version: str = ASSESSMENT_SCHEMA_VERSION
    invoke_calls_per_assess_run: int = INVOKE_CALLS_PER_ASSESS_RUN
    settings_timeout_max_retries_wired: bool = SETTINGS_TIMEOUT_MAX_RETRIES_WIRED_TO_ASSESS_FACTORY
    expected_limitations: tuple[str, ...] = EXPECTED_LIMITATIONS
    allowed_verdicts: tuple[str, ...] = ("pass", "pass_with_limitations")
    start_slice_11_2: bool = False
    migrate_openai_or_bedrock: bool = False
    add_openrouter: bool = False
    create_provider_platform: bool = False
    modify_ai_execution: bool = False
    modify_community_cloud_or_platform: bool = False
    commit_changes: bool = False
    notes: tuple[str, ...] = field(
        default_factory=lambda: (
            "SV.11.1 characterizes the existing AI provider architecture only. "
            "It freezes current behavior; it does not introduce a provider "
            "platform, migrate providers, or add OpenRouter.",
            "PASS_WITH_LIMITATIONS is expected without live credentials/network.",
        )
    )


def default_contract() -> BaselineContract:
    return BaselineContract()
