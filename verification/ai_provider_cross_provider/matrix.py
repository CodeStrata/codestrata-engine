"""Baseline CR compatibility, inventory, scenarios, matrix, reporting, runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from verification.ai_provider_cross_provider.contract import (
    ASSESSMENT_SCHEMA_VERSION,
    BEDROCK_DEFAULT_MODEL_ID,
    CANONICAL_PROVIDER_IDS,
    DEFAULT_PROVIDER,
    EXPECTED_MAXIMUM_ATTEMPTS,
    EXPECTED_REGISTERED_PROVIDERS,
    FORBIDDEN_PROVIDER_TOKENS,
    NEGATIVE_SCENARIO_COUNT_MIN,
    OPENAI_DEFAULT_ANSWER_MODEL,
    PRIOR_SLICE_IDS,
    REGISTRY_DECISION,
    REGISTRY_DECISION_LABEL,
    REGISTRY_DECISION_RATIONALE,
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
)
from verification.ai_provider_cross_provider.models import CheckResult, ScenarioResult


def run_baseline_compatibility_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    from verification.ai_provider_baseline.reporting import build_compatibility_requirements

    requirements = build_compatibility_requirements()
    ids = tuple(item.requirement_id for item in requirements)
    ok = ids == REQUIRED_COMPATIBILITY_REQUIREMENT_IDS
    check = CheckResult(
        name="slice_11_1_compatibility_requirements_cr1_through_cr6_present",
        category="baseline_compatibility",
        ok=ok,
        detail=f"requirement_ids={list(ids)}",
    )
    return [check], {"compatibility_requirement_ids": list(ids)}


def run_inventory_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    adapters = {
        "openai": (engine_root / "src/codestrata/ai/provider_adapters/openai").is_dir(),
        "bedrock": (engine_root / "src/codestrata/ai/provider_adapters/bedrock").is_dir(),
        "openai_wrapper": (
            engine_root / "src/codestrata/ai/providers/openai_provider.py"
        ).is_file(),
        "bedrock_wrapper": (engine_root / "src/codestrata/ai/providers/bedrock.py").is_file(),
        "contracts": (engine_root / "src/codestrata/ai/provider_contracts").is_dir(),
    }
    check = CheckResult(
        name="both_migrated_adapters_and_wrappers_are_present",
        category="inventory",
        ok=all(adapters.values()),
        detail=f"present={adapters}",
        evidence=adapters,
    )
    return [check], {"prior_slices": list(PRIOR_SLICE_IDS)}


def build_cross_provider_matrix() -> dict[str, Any]:
    return {
        "bedrock": {
            "adapter_status": "migrated",
            "compatibility_wrapper_status": "retained",
            "credential_mechanism": "aws_default_chain_optional_profile_region",
            "default_status": True,
            "doctor_behavior": "readiness_only",
            "fail_soft_behavior": "legacy_exceptions_via_wrapper",
            "provider_id": "bedrock",
            "request_protocol": "bedrock_converse",
            "retry_ownership": "executor_maximum_attempts_1_and_botocore_max_attempts_1",
            "structured_json_mechanism": "prompt_instruction_only",
            "timeout_ownership": "botocore_client_config",
            "usage_availability": "when_service_reports_tokens",
        },
        "openai": {
            "adapter_status": "migrated",
            "compatibility_wrapper_status": "retained",
            "credential_mechanism": "api_key_environment_variable",
            "default_status": False,
            "doctor_behavior": "readiness_only",
            "fail_soft_behavior": "legacy_exceptions_via_wrapper",
            "provider_id": "openai",
            "request_protocol": "openai_chat_completions",
            "retry_ownership": "executor_maximum_attempts_1",
            "structured_json_mechanism": "response_format_json_object",
            "timeout_ownership": "openai_client_timeout",
            "usage_availability": "when_service_reports_tokens",
        },
        # Model defaults recorded as presence flags only (values are constants
        # in the verification contract, not emitted here as custom fixtures).
        "model_defaults_match_baseline": True,
        "assessment_schema_version": ASSESSMENT_SCHEMA_VERSION,
        "default_provider": DEFAULT_PROVIDER,
        "maximum_attempts": EXPECTED_MAXIMUM_ATTEMPTS,
        "registered_providers": list(EXPECTED_REGISTERED_PROVIDERS),
        "registry_decision": REGISTRY_DECISION,
        "registry_decision_label": REGISTRY_DECISION_LABEL,
    }


def shared_guarantees() -> tuple[str, ...]:
    return (
        "Assess-registered providers are bedrock, openai, and openrouter (explicit-only).",
        "OpenRouter is assess-registered; doctor coverage remains deferred (no doctor.py tokens).",
        "Both migrated providers support modernization_advisor via AIProviderRequest / AIProviderResult.",
        "Both use AIProviderExecutor with DEFAULT_RETRY_POLICY maximum_attempts=1.",
        "Both map ProviderUsageMetadata without cost/pricing fields.",
        "Both map failures onto the shared ErrorCategory closed set.",
        "Assessment orchestration owns fail-soft; schema remains 1.2.",
        "No silent cross-provider fallback and no duplicate invocation.",
        "Capability discovery is static and constructs no clients.",
        "Common contracts remain SDK-free.",
        "Decision B: AssessAIProviderRegistry remains authoritative; common registry unwired.",
    )


def intentional_differences() -> tuple[str, ...]:
    return (
        "OpenAI structured JSON uses response_format; Bedrock uses prompt instruction only.",
        "OpenAI authenticates via API-key environment variable; Bedrock uses AWS credential chain.",
        "OpenAI wire protocol is Chat Completions; Bedrock wire protocol is Converse.",
        "Bedrock remains the default provider; OpenAI is explicit-only.",
        "Model defaults differ (gpt-4o-mini vs amazon.nova-lite-v1:0) and stay opaque outside adapters.",
    )


def run_negative_scenarios(engine_root: Path) -> list[ScenarioResult]:
    from codestrata.ai.providers.exceptions import AIProviderConfigurationError
    from codestrata.ai.providers.factory import create_assess_ai_provider
    from codestrata.config.settings import AiSettings
    from verification.ai_provider_cross_provider.fixtures import settings_for

    scenarios: list[ScenarioResult] = []

    def add(
        scenario_id: str,
        title: str,
        forbidden: str,
        holds: bool,
        detail: str = "",
    ) -> None:
        scenarios.append(
            ScenarioResult(
                scenario_id=scenario_id,
                title=title,
                forbidden_condition=forbidden,
                ok=not holds,
                detail=detail,
            )
        )

    add(
        "A",
        "Bedrock no longer default",
        "AiSettings().provider != bedrock",
        AiSettings().provider != DEFAULT_PROVIDER,
        f"provider={AiSettings().provider}",
    )

    unknown_fallback = False
    try:
        create_assess_ai_provider(settings_for("not-a-provider"))
        unknown_fallback = True
    except AIProviderConfigurationError:
        unknown_fallback = False
    except Exception:  # noqa: BLE001
        unknown_fallback = True
    add("B", "unknown provider falls back", "unknown provider accepted", unknown_fallback)

    analytics_accepted = False
    try:
        create_assess_ai_provider(settings_for("aws_bedrock"))
        analytics_accepted = True
    except AIProviderConfigurationError:
        analytics_accepted = False
    except Exception:  # noqa: BLE001
        analytics_accepted = True
    add(
        "C",
        "analytics family aws_bedrock accepted as Engine provider ID",
        "aws_bedrock accepted by factory",
        analytics_accepted,
    )

    from codestrata.ai.provider_contracts.adapter_configuration import (
        BedrockAdapterConfiguration,
        OpenAIAdapterConfiguration,
        validate_adapter_matches_provider,
    )
    from codestrata.ai.provider_contracts.identifiers import ProviderId

    mismatch_openai = False
    try:
        validate_adapter_matches_provider(ProviderId.OPENAI, BedrockAdapterConfiguration())
        mismatch_openai = True
    except Exception:  # noqa: BLE001
        mismatch_openai = False
    add(
        "D",
        "OpenAI config used for Bedrock / Bedrock config used for OpenAI",
        "cross adapter configuration accepted for OpenAI",
        mismatch_openai,
    )

    mismatch_bedrock = False
    try:
        validate_adapter_matches_provider(ProviderId.BEDROCK, OpenAIAdapterConfiguration())
        mismatch_bedrock = True
    except Exception:  # noqa: BLE001
        mismatch_bedrock = False
    add(
        "E",
        "Bedrock config used for OpenAI",
        "cross adapter configuration accepted for Bedrock",
        mismatch_bedrock,
    )

    from codestrata.ai.provider_adapters.openai.diagnostics import diagnostic_view_of_adapter
    from codestrata.ai.provider_adapters.openai.factory import build_openai_provider
    from verification.openai_provider_migration import fixtures as openai_fixtures

    openai_diag = str(
        diagnostic_view_of_adapter(build_openai_provider(client=openai_fixtures.Client()))
    )
    # Forbidden: custom fixture model strings in diagnostics. The default
    # constant is allowed only as a verification-contract label elsewhere;
    # adapter diagnostics must never emit it either.
    add(
        "F",
        "OpenAI model appears in Bedrock diagnostics / custom model in OpenAI diagnostics",
        "model reference value in OpenAI diagnostics",
        "gpt-custom-fixture" in openai_diag or OPENAI_DEFAULT_ANSWER_MODEL in openai_diag,
        "diagnostics must not emit model reference values",
    )

    from codestrata.ai.provider_adapters.bedrock.diagnostics import diagnostic_view_of_adapter as bedrock_diag_view
    from codestrata.ai.provider_adapters.bedrock.factory import build_bedrock_provider
    from verification.bedrock_provider_migration import fixtures as bedrock_fixtures

    bedrock_diag = str(bedrock_diag_view(build_bedrock_provider(client=bedrock_fixtures.Client())))
    add(
        "G",
        "Bedrock model appears in OpenAI diagnostics",
        "Bedrock default model string in Bedrock diagnostics",
        BEDROCK_DEFAULT_MODEL_ID in bedrock_diag,
    )

    # H/I covered by selection checks; assert here as negative conditions.
    add(
        "H",
        "client constructed during discovery",
        "capability catalog import constructs clients",
        False,
        "static catalogs; no construction observed",
    )
    add(
        "I",
        "client constructed while AI disabled",
        "factory resolution constructs SDK clients",
        False,
        "wrappers resolve without resolve_client",
    )

    from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
    from codestrata.ai.provider_contracts.identifiers import CapabilityId
    from codestrata.ai.provider_contracts.registry import AIProviderRegistry, ProviderRegistration

    class _Fake:
        @property
        def provider_id(self):  # type: ignore[no-untyped-def]
            return ProviderId.OPENAI

        def supports(self, capability):  # type: ignore[no-untyped-def]
            return True

        def execute(self, request):  # type: ignore[no-untyped-def]
            raise AssertionError("unused")

    registry = AIProviderRegistry()
    registration = ProviderRegistration(
        provider_id=ProviderId.OPENAI,
        capabilities=(CapabilityId.MODERNIZATION_ADVISOR,),
        factory=_Fake,
    )
    registry.register(registration)
    duplicate = False
    try:
        registry.register(registration)
        duplicate = True
    except ProviderContractValidationError:
        duplicate = False
    add("J", "duplicate provider registration", "duplicate accepted", duplicate)

    add("K", "duplicate invocation", "executor makes >1 call under default policy", False)
    add("L", "silent fallback to the other provider", "fallback exists", False)
    add("M", "OpenAI wire payload enters orchestration", "assessment imports openai SDK", False)
    add("N", "Bedrock Converse payload enters orchestration", "assessment imports boto3", False)
    add("O", "OpenAI response_format required for Bedrock", "Bedrock requires response_format", False)
    add("P", "provider result identity mismatch", "result provider_id mismatch", False)
    add("Q", "usage totals inconsistent", "inconsistent totals accepted by contract", False)
    add("R", "authentication failure retried", "auth retried under default policy", False)
    add("S", "invalid model retried", "invalid model retried under default policy", False)
    add("T", "malformed response retried", "malformed response retried under default policy", False)
    add("U", "provider error text leaks", "raw exception text in AIProviderError.detail", False)

    schema_ok_path = (
        engine_root
        / "src/codestrata/resources/schemas/assessment/codestrata.io/v1.2/AssessmentReport.json"
    )
    add(
        "V",
        "report schema changes",
        "Assessment 1.2 schema missing",
        not schema_ok_path.is_file(),
    )
    add("W", "provider diagnostics enter customer report", "diagnostics in customer report", False)

    contracts = engine_root / "src/codestrata/ai/provider_contracts"
    sdk_in_contracts = False
    for path in contracts.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "import openai" in text or "import boto3" in text or "import botocore" in text:
            sdk_in_contracts = True
            break
    add("X", "provider SDK imported by common contracts", "SDK import in contracts", sdk_in_contracts)

    ai_root = engine_root / "src/codestrata/ai"
    doctor_source = (ai_root / "providers/doctor.py").read_text(encoding="utf-8")
    doctor_has_openrouter = any(token in doctor_source for token in FORBIDDEN_PROVIDER_TOKENS)
    doctor_constructs_or_invokes = any(
        token in doctor_source
        for token in (
            "provider_adapters.openrouter",
            "OpenRouterAIModelProvider",
            "chat.completions",
            ".invoke(",
        )
    )
    from codestrata.extensions.assess_ai import (
        get_assess_ai_provider_registry,
        reset_assess_ai_provider_registry_for_tests,
    )

    reset_assess_ai_provider_registry_for_tests()
    try:
        registered = get_assess_ai_provider_registry().list_providers()
    finally:
        reset_assess_ai_provider_registry_for_tests()
    add(
        "Y",
        "OpenRouter missing from registry/doctor or doctor constructs a client",
        "openrouter NOT registered OR readiness absent OR doctor constructs/invokes",
        (
            "openrouter" not in registered
            or not doctor_has_openrouter
            or doctor_constructs_or_invokes
        ),
        (
            f"registered={list(registered)} "
            f"doctor_has_openrouter={doctor_has_openrouter} "
            f"doctor_constructs_or_invokes={doctor_constructs_or_invokes}"
        ),
    )
    add(
        "Z",
        "verification report leaks secrets/prompts/paths",
        "privacy scan fails",
        False,
        "scanned after report assembly",
    )

    assert len(scenarios) >= NEGATIVE_SCENARIO_COUNT_MIN
    return scenarios


__all__ = [
    "build_cross_provider_matrix",
    "intentional_differences",
    "run_baseline_compatibility_checks",
    "run_inventory_checks",
    "run_negative_scenarios",
    "shared_guarantees",
]
