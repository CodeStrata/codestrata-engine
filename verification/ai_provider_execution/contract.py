"""Contract constants for SV.11.4 Standardized Execution, Errors, Timeouts, and Retries.

CodeStrata v0.2.0 Epic 11, Slice 11.4. This package verifies the **new,
unwired** ``codestrata.ai.provider_contracts.execution_*`` (plus
``timeout_policy.py``/``retry_policy.py``/``retry_decision.py``/
``backoff.py``/``error_classification.py``/``executor.py``) domain modules:
their dependency boundary, their bounded value objects, their compatibility
with the Slice 11.1 baseline (CR-1..CR-6), retry/backoff/timeout policy
correctness, fail-soft executor behavior, privacy, and determinism. It does
not run, and does not require, any real provider network access or
credentials, and it never reads ``os.environ`` or a file on disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from verification.ai_provider_configuration.contract import (
    EXPECTED_MODULES as SLICE_11_3_MODULES,
)

VERIFICATION_ID = "ai-provider-execution-verification"
VERIFICATION_VERSION = "1.0.0"

SCHEMA_NAME = "ai-provider-execution-verification"
SCHEMA_VERSION = "1.0.0"

EPIC = "Epic 11: AI Provider Compatibility"
SLICE_ID = "11.4"
SLICE_TITLE = "Standardized Execution, Errors, Timeouts, and Retries"

PACKAGE_DOTTED_NAME = "codestrata.ai.provider_contracts"
PACKAGE_RELATIVE_PATH = "ai/provider_contracts"

# The 11 modules Slice 11.4 adds to the existing (Slice 11.2 + 11.3) package.
SLICE_11_4_NEW_MODULES: tuple[str, ...] = (
    "backoff.py",
    "error_classification.py",
    "execution_compatibility.py",
    "execution_diagnostics.py",
    "execution_models.py",
    "execution_policy.py",
    "execution_serialization.py",
    "executor.py",
    "retry_decision.py",
    "retry_policy.py",
    "timeout_policy.py",
)

# The full expected module set for the package after Slice 11.4 (Slice
# 11.2+11.3's set plus Slice 11.4's additions). Used to confirm nothing from
# any prior slice went missing and nothing unexpected was added.
EXPECTED_MODULES: tuple[str, ...] = tuple(
    sorted(set(SLICE_11_3_MODULES) | set(SLICE_11_4_NEW_MODULES))
)

FORBIDDEN_IMPORT_PREFIXES: tuple[str, ...] = (
    "openai",
    "boto3",
    "botocore",
    "httpx",
    "requests",
    "codestrata.platform",
    "codestrata.datalake",
    "codestrata.telemetry",
    "codestrata.analytics",
    "codestrata.cli",
    "codestrata.reporting",
)

# The Slice 11.4 execution modules must never import os/pathlib/subprocess/
# threading/asyncio/signal — the executor never enforces a wall-clock
# timeout itself (no threads, no signals, no asyncio; see executor.py's
# module docstring), and none of these modules reads the environment or a
# file itself.
FORBIDDEN_ENVIRONMENT_IMPORT_MODULES: tuple[str, ...] = (
    "os",
    "pathlib",
    "subprocess",
    "threading",
    "asyncio",
    "signal",
)

# Product-path files that must never import any provider_contracts module —
# identical to the Slice 11.3 list (Slice 11.4 does not widen the set of
# files that must remain free of provider_contracts imports), minus the
# OpenAI files that Slice 11.6 migrated and the Bedrock file that Slice 11.7
# migrated onto the contracts. SV.11.6/SV.11.7 assert the positive direction
# for ``ai/providers/openai_provider.py``, ``ai/providers/bedrock.py``, and
# ``ai/provider_adapters/``; orchestration and ``ai/aws_config.py`` stay
# contract-free here.
PRODUCT_PATH_FILES: tuple[str, ...] = (
    "application/assessment/service.py",
    "ai/enrichment/service.py",
    "ai/providers/__init__.py",
    "ai/providers/factory.py",
    "ai/providers/doctor.py",
    "ai/aws_config.py",
    "extensions/assess_ai.py",
    "config/settings.py",
    "config/profiles.py",
    "cli/assess.py",
)

FORBIDDEN_PROVIDER_TOKENS: tuple[str, ...] = ("openrouter", "OpenRouter", "OPENROUTER")

EXPECTED_LIMITATIONS: tuple[str, ...] = (
    "executor_not_wired",
    "providers_not_migrated",
    "timeout_enforcement_deferred_to_adapters",
    "runtime_settings_still_unwired",
)

REQUIRED_COMPATIBILITY_REQUIREMENT_IDS: tuple[str, ...] = (
    "CR-1",
    "CR-2",
    "CR-3",
    "CR-4",
    "CR-5",
    "CR-6",
)

# Ground-truth defaults this slice must never change (see
# engine/docs/ai-provider-execution.md and the real, unchanged
# codestrata.ai.providers.models.DEFAULT_TIMEOUT_SECONDS /
# codestrata.config.settings.BedrockSettings.max_retries /
# codestrata.config.settings.OpenAISettings.max_retries defaults).
DEFAULT_TIMEOUT_SECONDS = 60.0
SETTINGS_DEFAULT_MAX_RETRIES = 3
DEFAULT_MAXIMUM_ATTEMPTS = 1

OUTPUT_RELATIVE = "reports/verification/sv11-4"
REPORT_FILENAME = "ai-provider-execution-verification.json"
REPORT_MD_FILENAME = "ai-provider-execution-verification.md"

NEGATIVE_SCENARIO_COUNT_MIN = 20

ALLOWED_VERDICTS: tuple[str, ...] = ("pass", "pass_with_limitations")


@dataclass(frozen=True, slots=True)
class ExecutionVerificationContract:
    """Pass/fail contract for SV.11.4 Standardized Execution, Errors, Timeouts, and Retries."""

    verification_id: str = VERIFICATION_ID
    verification_version: str = VERIFICATION_VERSION
    schema_name: str = SCHEMA_NAME
    schema_version: str = SCHEMA_VERSION
    epic: str = EPIC
    slice_id: str = SLICE_ID
    allowed_verdicts: tuple[str, ...] = ALLOWED_VERDICTS
    expected_limitations: tuple[str, ...] = EXPECTED_LIMITATIONS
    required_compatibility_requirement_ids: tuple[str, ...] = REQUIRED_COMPATIBILITY_REQUIREMENT_IDS
    default_maximum_attempts: int = DEFAULT_MAXIMUM_ATTEMPTS
    start_slice_11_5: bool = False
    migrate_openai_or_bedrock: bool = False
    add_openrouter: bool = False
    wire_executor_into_assess_enrichment_providers_doctor_cli_or_factory: bool = False
    modify_defaults_selection_credentials_wire_formats_doctor_fail_soft_prompts_reports_schemas: (
        bool
    ) = False
    modify_telemetry_analytics_community_cloud_data_lake_vscode_cursor_infrastructure: bool = False
    commit_changes: bool = False
    notes: tuple[str, ...] = field(
        default_factory=lambda: (
            "SV.11.4 verifies the new execution_* / timeout_policy / retry_policy / "
            "retry_decision / backoff / error_classification / executor domain modules: "
            "bounded value objects, dependency boundary, Slice 11.1 CR-1..CR-6 compatibility, "
            "fail-soft executor behavior, privacy, and determinism.",
            "PASS_WITH_LIMITATIONS is expected: executor_not_wired, providers_not_migrated, "
            "timeout_enforcement_deferred_to_adapters, and runtime_settings_still_unwired are "
            "recorded, intentional limitations.",
        )
    )


def default_contract() -> ExecutionVerificationContract:
    return ExecutionVerificationContract()


__all__ = [
    "ALLOWED_VERDICTS",
    "DEFAULT_MAXIMUM_ATTEMPTS",
    "DEFAULT_TIMEOUT_SECONDS",
    "EPIC",
    "EXPECTED_LIMITATIONS",
    "EXPECTED_MODULES",
    "FORBIDDEN_ENVIRONMENT_IMPORT_MODULES",
    "FORBIDDEN_IMPORT_PREFIXES",
    "FORBIDDEN_PROVIDER_TOKENS",
    "NEGATIVE_SCENARIO_COUNT_MIN",
    "OUTPUT_RELATIVE",
    "PACKAGE_DOTTED_NAME",
    "PACKAGE_RELATIVE_PATH",
    "PRODUCT_PATH_FILES",
    "REPORT_FILENAME",
    "REPORT_MD_FILENAME",
    "REQUIRED_COMPATIBILITY_REQUIREMENT_IDS",
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "SETTINGS_DEFAULT_MAX_RETRIES",
    "SLICE_11_3_MODULES",
    "SLICE_11_4_NEW_MODULES",
    "SLICE_ID",
    "SLICE_TITLE",
    "VERIFICATION_ID",
    "VERIFICATION_VERSION",
    "ExecutionVerificationContract",
    "default_contract",
]
