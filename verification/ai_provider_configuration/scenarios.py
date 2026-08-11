"""Negative scenarios A-Z: checks that forbidden conditions do NOT hold."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from verification.ai_provider_configuration.contract import EXPECTED_MODULES
from verification.ai_provider_configuration.models import CheckResult, ScenarioResult


def _rejects(callable_under_test, *, name: str, category: str) -> CheckResult:
    """Run a zero-argument callable and record whether it raised the expected error."""

    from codestrata.ai.provider_contracts.errors import ProviderContractValidationError

    try:
        callable_under_test()
    except ProviderContractValidationError as error:
        return CheckResult(name=name, category=category, ok=True, detail=f"raised: {error}")
    return CheckResult(
        name=name,
        category=category,
        ok=False,
        detail="did not raise ProviderContractValidationError",
    )


def run_value_object_negative_checks() -> list[CheckResult]:
    """Exercise configuration construction-time invariants directly."""

    from codestrata.ai.provider_contracts.adapter_configuration import (
        BedrockAdapterConfiguration,
        OpenAIAdapterConfiguration,
        validate_adapter_matches_provider,
    )
    from codestrata.ai.provider_contracts.configuration_models import (
        AIProviderConfiguration,
        ProviderCredentialRequirement,
    )
    from codestrata.ai.provider_contracts.configuration_projection import project_configuration
    from codestrata.ai.provider_contracts.configuration_sources import FieldSource, SourceCategory
    from codestrata.ai.provider_contracts.identifiers import (
        CapabilityId,
        ProviderId,
        ProviderModelReference,
    )
    from codestrata.ai.provider_contracts.legacy_configuration import LegacyConfigurationInput
    from codestrata.ai.provider_contracts.requests import ExecutionOptions

    category = "value_object_invariants"

    def _valid_configuration_kwargs() -> dict[str, object]:
        return {
            "configuration_version": "1.0",
            "provider_id": ProviderId.BEDROCK,
            "model_reference": ProviderModelReference("amazon.nova-lite-v1:0"),
            "capability_id": CapabilityId.MODERNIZATION_ADVISOR,
            "execution_options": ExecutionOptions(),
            "adapter_configuration": BedrockAdapterConfiguration(),
            "source_trace": (
                FieldSource("provider_id", SourceCategory.DEFAULT),
                FieldSource("model_reference", SourceCategory.DEFAULT),
            ),
            "credential_requirements": (),
            "limitations": ("configuration_not_wired",),
        }

    checks = [
        _rejects(
            lambda: AIProviderConfiguration(
                **{
                    **_valid_configuration_kwargs(),
                    "adapter_configuration": OpenAIAdapterConfiguration(),
                }
            ),
            name="configuration_rejects_adapter_provider_mismatch",
            category=category,
        ),
        _rejects(
            lambda: AIProviderConfiguration(
                **{**_valid_configuration_kwargs(), "configuration_version": "99.0"}
            ),
            name="configuration_rejects_unsupported_configuration_version",
            category=category,
        ),
        _rejects(
            lambda: AIProviderConfiguration(**{**_valid_configuration_kwargs(), "limitations": ()}),
            name="configuration_rejects_empty_limitations",
            category=category,
        ),
        _rejects(
            lambda: AIProviderConfiguration(
                **{
                    **_valid_configuration_kwargs(),
                    "source_trace": (FieldSource("provider_id", SourceCategory.DEFAULT),),
                }
            ),
            name="configuration_rejects_missing_model_reference_source_trace",
            category=category,
        ),
        _rejects(
            lambda: AIProviderConfiguration(
                **{
                    **_valid_configuration_kwargs(),
                    "credential_requirements": (
                        ProviderCredentialRequirement(
                            provider_id=ProviderId.OPENAI,
                            credential_kind="api_key",
                            required=True,
                            source_category=SourceCategory.ENVIRONMENT,
                            availability_status="present",
                        ),
                    ),
                }
            ),
            name="configuration_rejects_credential_requirement_provider_mismatch",
            category=category,
        ),
        _rejects(
            lambda: ProviderCredentialRequirement(
                provider_id=ProviderId.OPENAI,
                credential_kind="oauth_token",
                required=True,
                source_category=SourceCategory.ENVIRONMENT,
                availability_status="present",
            ),
            name="credential_requirement_rejects_unknown_credential_kind",
            category=category,
        ),
        _rejects(
            lambda: ProviderCredentialRequirement(
                provider_id=ProviderId.OPENAI,
                credential_kind="api_key",
                required=True,
                source_category=SourceCategory.ENVIRONMENT,
                availability_status="maybe",
            ),
            name="credential_requirement_rejects_unknown_availability_status",
            category=category,
        ),
        _rejects(
            lambda: OpenAIAdapterConfiguration(
                base_url="https://x.test", base_url_configured=False
            ),
            name="openai_adapter_rejects_non_blank_url_without_configured_flag",
            category=category,
        ),
        _rejects(
            lambda: OpenAIAdapterConfiguration(max_retries=-1),
            name="openai_adapter_rejects_negative_max_retries",
            category=category,
        ),
        _rejects(
            lambda: BedrockAdapterConfiguration(max_retries=-1),
            name="bedrock_adapter_rejects_negative_max_retries",
            category=category,
        ),
        _rejects(
            lambda: LegacyConfigurationInput(timeout_seconds=-1),
            name="legacy_configuration_input_rejects_negative_timeout",
            category=category,
        ),
        _rejects(
            lambda: LegacyConfigurationInput(ai_requested="yes"),  # type: ignore[arg-type]
            name="legacy_configuration_input_rejects_non_bool_ai_requested",
            category=category,
        ),
        _rejects(
            lambda: project_configuration(LegacyConfigurationInput(provider="anthropic")),
            name="project_configuration_rejects_unsupported_provider",
            category=category,
        ),
    ]

    def _adapter_mismatch_is_rejected() -> None:
        validate_adapter_matches_provider(ProviderId.OPENAI, BedrockAdapterConfiguration())

    checks.append(
        _rejects(
            _adapter_mismatch_is_rejected,
            name="validate_adapter_matches_provider_rejects_mismatch",
            category=category,
        )
    )
    return checks


_PROCESS_INVOCATION_CALLS = frozenset(
    {
        "subprocess.run",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        "subprocess.Popen",
        "os.system",
        "os.popen",
    }
)

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{10,}"),
)
_ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"/Users/[^\s\"']+"),
    re.compile(r"/home/[^\s\"']+"),
)


def _dotted_call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    return None


def _module_shells_out_to_a_process(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(alias.name == "subprocess" for alias in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            return True
        if isinstance(node, ast.Call):
            dotted = _dotted_call_name(node.func)
            if dotted in _PROCESS_INVOCATION_CALLS:
                return True
    return False


def _find_matches(patterns: tuple[re.Pattern[str], ...], text: str) -> list[str]:
    hits: list[str] = []
    for pattern in patterns:
        hits.extend(pattern.findall(text))
    return hits


def _scenario_from_check(
    scenario_id: str,
    title: str,
    forbidden_condition: str,
    check: CheckResult | None,
) -> ScenarioResult:
    if check is None:
        return ScenarioResult(
            scenario_id=scenario_id,
            title=title,
            forbidden_condition=forbidden_condition,
            ok=False,
            detail="backing check not found in check registry",
        )
    return ScenarioResult(
        scenario_id=scenario_id,
        title=title,
        forbidden_condition=forbidden_condition,
        ok=check.ok,
        detail=check.detail,
    )


def _scenario_x_no_absolute_paths(report_payload_preview: dict[str, object]) -> ScenarioResult:
    from verification.ai_provider_configuration.determinism import canonical_json

    text = canonical_json(report_payload_preview)
    hits = _find_matches(_ABSOLUTE_PATH_PATTERNS, text)
    return ScenarioResult(
        scenario_id="X",
        title="Configuration verification report contains no absolute filesystem paths",
        forbidden_condition="report JSON contains an absolute macOS or Linux user-home path",
        ok=not hits,
        detail=f"hits={hits[:5]}" if hits else "no absolute-path patterns found",
    )


def _scenario_y_no_secrets_in_report(report_payload_preview: dict[str, object]) -> ScenarioResult:
    from verification.ai_provider_configuration.determinism import canonical_json

    text = canonical_json(report_payload_preview)
    hits = _find_matches(_SECRET_PATTERNS, text)
    return ScenarioResult(
        scenario_id="Y",
        title="Configuration verification report contains no secret-shaped tokens",
        forbidden_condition="report JSON contains a sk-/AKIA/Bearer-shaped token",
        ok=not hits,
        detail=f"hits={hits[:5]}" if hits else "no secret-shaped tokens found",
    )


def _scenario_z_no_process_invocation(package_dir: Path, verification_dir: Path) -> ScenarioResult:
    hits: list[str] = []
    for filename in EXPECTED_MODULES:
        path = package_dir / filename
        if path.is_file() and _module_shells_out_to_a_process(path):
            hits.append(f"src:{filename}")
    if verification_dir.exists():
        for path in sorted(verification_dir.glob("*.py")):
            if _module_shells_out_to_a_process(path):
                hits.append(f"verification:{path.name}")
    return ScenarioResult(
        scenario_id="Z",
        title="Neither the configuration package nor this verification package shells out",
        forbidden_condition="a module imports subprocess or calls os.system/os.popen",
        ok=not hits,
        detail=f"flagged={hits}" if hits else "no subprocess/os.system usage found",
    )


def build_negative_scenarios(
    *,
    package_dir: Path,
    verification_dir: Path,
    checks_by_name: dict[str, CheckResult],
    report_payload_preview: dict[str, object],
) -> tuple[ScenarioResult, ...]:
    def get(name: str) -> CheckResult | None:
        return checks_by_name.get(name)

    scenarios = [
        _scenario_from_check(
            "A",
            "No real network access or credentials are required to run this suite",
            "a check imports httpx/requests/boto3/openai to reach the network",
            get("provider_contracts_has_no_forbidden_sdk_or_product_imports"),
        ),
        _scenario_from_check(
            "B",
            "provider_contracts has no OpenRouter adapter or API-key wiring",
            "provider_contracts imports provider_adapters.openrouter, "
            "mentions OPENROUTER_API_KEY, or references OpenRouterProvider",
            get("provider_contracts_has_no_openrouter_adapter_or_api_key_wiring"),
        ),
        _scenario_from_check(
            "C",
            "Configuration modules never import os/pathlib/subprocess",
            "a configuration_* module imports os, pathlib, or subprocess",
            get("configuration_modules_never_import_os_pathlib_or_subprocess"),
        ),
        _scenario_from_check(
            "D",
            "provider_contracts has no codestrata dependency outside itself",
            "a provider_contracts module imports another codestrata.* package",
            get("provider_contracts_has_no_codestrata_dependencies_outside_itself"),
        ),
        _scenario_from_check(
            "E",
            "No product-path file imports provider_contracts",
            "assess factory/providers/enrichment/doctor/CLI imports provider_contracts",
            get("product_path_files_do_not_import_provider_contracts"),
        ),
        _scenario_from_check(
            "F",
            "The existing ai/providers/ directory has no new files from Slice 11.3",
            "ai/providers/ contains a file outside the Slice 11.1 baseline set",
            get("ai_providers_directory_has_no_new_files_from_slice_11_3"),
        ),
        _scenario_from_check(
            "G",
            "ProviderId includes bedrock, openai, and openrouter; assess IDs remain a subset",
            "ProviderId drops bedrock/openai or gains an unexpected value beyond openrouter",
            get("provider_id_enum_superset_of_baseline_engine_provider_ids"),
        ),
        _scenario_from_check(
            "H",
            "The Slice 11.1 baseline defines exactly CR-1..CR-6",
            "build_compatibility_requirements() returns a different requirement ID set",
            get("slice_11_1_baseline_defines_cr1_through_cr6"),
        ),
        _scenario_from_check(
            "I",
            "Every baseline compatibility requirement is covered by a configuration statement",
            "a CR-1..CR-6 requirement has no matching ConfigurationCompatibilityStatement",
            get("configuration_compatibility_statements_cover_every_baseline_requirement"),
        ),
        _scenario_from_check(
            "J",
            "No configuration compatibility statement reports holds=False",
            "a ConfigurationCompatibilityStatement has holds=False",
            get("every_configuration_compatibility_statement_holds_true"),
        ),
        _scenario_from_check(
            "K",
            "The default provider matches the loaded Slice 11.1 baseline default",
            "DEFAULT_PROVIDER_ID differs from the Slice 11.1 baseline's default provider",
            get("configuration_default_provider_id_matches_baseline_default_assess_provider"),
        ),
        _scenario_from_check(
            "L",
            "The default model IDs match the loaded Slice 11.1 baseline defaults",
            "DEFAULT_MODEL_BY_PROVIDER differs from the Slice 11.1 baseline's default model IDs",
            get("configuration_default_model_ids_match_baseline_default_model_ids"),
        ),
        _scenario_from_check(
            "M",
            "Diagnostic views never include the raw model reference or base_url value",
            "diagnostic_view_of_configuration() output contains a raw model/base_url value",
            get("configuration_diagnostic_view_excludes_raw_model_reference"),
        ),
        _scenario_from_check(
            "N",
            "Serialized diagnostic forms never include sensitive text",
            "serialize_configuration_for_diagnostics() output contains sensitive text",
            get("serialized_configuration_diagnostic_form_excludes_sensitive_text"),
        ),
        _scenario_from_check(
            "O",
            "The provider_contracts package has exactly its expected module set",
            "a file is missing from, or unexpectedly added to, provider_contracts/",
            get("provider_contracts_package_has_exactly_expected_modules_after_slice_11_3"),
        ),
        _scenario_from_check(
            "P",
            "All twelve Slice 11.3 configuration modules are present",
            "one of the twelve new configuration_* modules is missing",
            get("all_twelve_slice_11_3_configuration_modules_are_present"),
        ),
        _scenario_from_check(
            "Q",
            "AIProviderConfiguration rejects an adapter/provider type mismatch",
            "AIProviderConfiguration accepts a mismatched adapter_configuration type",
            get("configuration_rejects_adapter_provider_mismatch"),
        ),
        _scenario_from_check(
            "R",
            "AIProviderConfiguration rejects an unsupported configuration_version",
            "AIProviderConfiguration accepts configuration_version='99.0'",
            get("configuration_rejects_unsupported_configuration_version"),
        ),
        _scenario_from_check(
            "S",
            "AIProviderConfiguration rejects empty limitations",
            "AIProviderConfiguration accepts limitations=()",
            get("configuration_rejects_empty_limitations"),
        ),
        _scenario_from_check(
            "T",
            "AIProviderConfiguration rejects a credential_requirement provider mismatch",
            "AIProviderConfiguration accepts a credential_requirements entry for another provider",
            get("configuration_rejects_credential_requirement_provider_mismatch"),
        ),
        _scenario_from_check(
            "U",
            "OpenAIAdapterConfiguration rejects a non-blank base_url without the configured flag",
            "OpenAIAdapterConfiguration(base_url=..., base_url_configured=False) is accepted",
            get("openai_adapter_rejects_non_blank_url_without_configured_flag"),
        ),
        _scenario_from_check(
            "V",
            "project_configuration() rejects an unsupported provider name",
            "project_configuration() silently accepts provider='anthropic'",
            get("project_configuration_rejects_unsupported_provider"),
        ),
        _scenario_from_check(
            "W",
            "Adapter type mismatches are rejected for both providers",
            "validate_adapter_matches_provider() accepts a mismatched pairing",
            get("validate_adapter_matches_provider_rejects_mismatch"),
        ),
        _scenario_x_no_absolute_paths(report_payload_preview),
        _scenario_y_no_secrets_in_report(report_payload_preview),
        _scenario_z_no_process_invocation(package_dir, verification_dir),
    ]
    return tuple(sorted(scenarios, key=lambda s: s.scenario_id))


__all__ = ["build_negative_scenarios", "run_value_object_negative_checks"]
