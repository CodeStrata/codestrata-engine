"""Negative scenarios A-Z: checks that forbidden conditions do NOT hold."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from verification.ai_provider_contracts.contract import EXPECTED_MODULES
from verification.ai_provider_contracts.models import CheckResult, ScenarioResult


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
    """Exercise construction-time invariants directly (not via a live provider call)."""

    from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
    from codestrata.ai.provider_contracts.errors import AIProviderError, ErrorCategory
    from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
    from codestrata.ai.provider_contracts.identifiers import (
        CapabilityId,
        ProviderId,
        ProviderModelReference,
    )
    from codestrata.ai.provider_contracts.registry import (
        AIProviderRegistry,
        ProviderRegistration,
    )
    from codestrata.ai.provider_contracts.requests import AIProviderRequest, ResponseExpectation
    from codestrata.ai.provider_contracts.responses import (
        AIProviderResult,
        AIProviderResultContent,
    )
    from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata

    category = "value_object_invariants"

    def _valid_request_kwargs() -> dict[str, object]:
        return {
            "capability": CapabilityId.MODERNIZATION_ADVISOR,
            "payload": ModernizationAdvisorInput(instruction_text="a", context_payload_text="b"),
            "response_expectation": ResponseExpectation.TEXT,
            "model_reference": ProviderModelReference("m"),
        }

    checks = [
        _rejects(
            lambda: AIProviderRequest(**{**_valid_request_kwargs(), "payload": object()}),
            name="request_rejects_capability_payload_mismatch",
            category=category,
        ),
        _rejects(
            lambda: AIProviderRequest(**_valid_request_kwargs(), contract_version="99.0"),
            name="request_rejects_unsupported_contract_version",
            category=category,
        ),
        _rejects(
            lambda: ProviderUsageMetadata(input_tokens=1, output_tokens=2, total_tokens=999),
            name="usage_rejects_inconsistent_token_total",
            category=category,
        ),
        _rejects(
            lambda: AIProviderError(
                category=ErrorCategory.INTERNAL_FAILURE,
                code="x",
                detail="Traceback (most recent call last): boom",
            ),
            name="error_rejects_traceback_shaped_detail",
            category=category,
        ),
        _rejects(
            lambda: AIProviderResult(
                provider_id=ProviderId.OPENAI,
                capability=CapabilityId.MODERNIZATION_ADVISOR,
                status=ProviderExecutionStatus.SUCCESS,
                content=AIProviderResultContent(text="ok"),
                error=AIProviderError(category=ErrorCategory.TIMEOUT, code="t"),
            ),
            name="success_result_rejects_attached_error",
            category=category,
        ),
        _rejects(
            lambda: AIProviderResult(
                provider_id=ProviderId.BEDROCK,
                capability=CapabilityId.MODERNIZATION_ADVISOR,
                status=ProviderExecutionStatus.FAILED,
            ),
            name="failed_result_requires_attached_error",
            category=category,
        ),
    ]

    def _duplicate_registration() -> None:
        registry = AIProviderRegistry()
        registration = ProviderRegistration(
            provider_id=ProviderId.OPENAI,
            capabilities=(CapabilityId.MODERNIZATION_ADVISOR,),
            factory=lambda: None,
        )
        registry.register(registration)
        registry.register(registration)

    def _resolve_unknown() -> None:
        AIProviderRegistry().resolve(ProviderId.BEDROCK)

    checks.append(
        _rejects(
            _duplicate_registration,
            name="registry_rejects_duplicate_registration",
            category=category,
        )
    )
    checks.append(
        _rejects(
            _resolve_unknown,
            name="registry_resolve_raises_for_unknown_provider",
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
    from verification.ai_provider_contracts.determinism import canonical_json

    text = canonical_json(report_payload_preview)
    hits = _find_matches(_ABSOLUTE_PATH_PATTERNS, text)
    return ScenarioResult(
        scenario_id="X",
        title="Contract verification report contains no absolute filesystem paths",
        forbidden_condition="report JSON contains an absolute macOS or Linux user-home path",
        ok=not hits,
        detail=f"hits={hits[:5]}" if hits else "no absolute-path patterns found",
    )


def _scenario_y_no_secrets_in_report(report_payload_preview: dict[str, object]) -> ScenarioResult:
    from verification.ai_provider_contracts.determinism import canonical_json

    text = canonical_json(report_payload_preview)
    hits = _find_matches(_SECRET_PATTERNS, text)
    return ScenarioResult(
        scenario_id="Y",
        title="Contract verification report contains no secret-shaped tokens",
        forbidden_condition="report JSON contains a sk-/AKIA/Bearer-shaped token",
        ok=not hits,
        detail=f"hits={hits[:5]}" if hits else "no secret-shaped tokens found",
    )


def _scenario_w_registry_rejects_duplicates_and_unknown_ids(
    checks_by_name: dict[str, CheckResult],
) -> ScenarioResult:
    duplicate_check = checks_by_name.get("registry_rejects_duplicate_registration")
    unknown_check = checks_by_name.get("registry_resolve_raises_for_unknown_provider")
    ok = bool(duplicate_check and duplicate_check.ok and unknown_check and unknown_check.ok)
    detail_parts = [
        f"duplicate_rejected={duplicate_check.ok if duplicate_check else 'missing'}",
        f"unknown_id_raises={unknown_check.ok if unknown_check else 'missing'}",
    ]
    return ScenarioResult(
        scenario_id="W",
        title=(
            "AIProviderRegistry rejects duplicate registration and raises for an "
            "unknown provider ID"
        ),
        forbidden_condition=(
            "AIProviderRegistry.register() silently accepts a duplicate provider_id, or "
            "AIProviderRegistry.resolve() returns something for an unregistered provider_id"
        ),
        ok=ok,
        detail=", ".join(detail_parts),
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
        title="Neither the contract package nor this verification package shells out",
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
            "provider_contracts imports no forbidden SDK/product modules",
            "provider_contracts imports openai/boto3/botocore/httpx/requests/"
            "platform/datalake/telemetry/analytics/cli/reporting",
            get("provider_contracts_has_no_forbidden_sdk_or_product_imports"),
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
            "assessment/service.py, enrichment/service.py, bedrock.py, "
            "or providers/__init__.py imports provider_contracts",
            get("product_path_files_do_not_import_provider_contracts"),
        ),
        _scenario_from_check(
            "F",
            "The existing ai/providers/ directory has no new files from Slice 11.2",
            "ai/providers/ contains a file outside the Slice 11.1 baseline set",
            get("ai_providers_directory_has_no_new_files_from_slice_11_2"),
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
            "Every baseline compatibility requirement is covered by a contract statement",
            "a CR-1..CR-6 requirement has no matching ContractCompatibilityStatement",
            get("contract_compatibility_statements_cover_every_baseline_requirement"),
        ),
        _scenario_from_check(
            "J",
            "No contract compatibility statement reports holds=False",
            "a ContractCompatibilityStatement has holds=False",
            get("every_contract_compatibility_statement_holds_true"),
        ),
        _scenario_from_check(
            "K",
            "Request diagnostics never include prompt text or the raw model reference",
            "diagnostic_view_of_request() output contains instruction/context text "
            "or an unredacted model reference",
            get("request_diagnostic_view_excludes_prompt_and_raw_model_reference"),
        ),
        _scenario_from_check(
            "L",
            "Result diagnostics never include response text",
            "diagnostic_view_of_result() output contains response content text",
            get("result_diagnostic_view_excludes_response_text"),
        ),
        _scenario_from_check(
            "M",
            "Serialized diagnostic forms never include sensitive text",
            "serialize_request_for_diagnostics()/serialize_result_for_diagnostics() "
            "output contains prompt/response/path text",
            get("serialized_diagnostic_forms_exclude_sensitive_text"),
        ),
        _scenario_from_check(
            "N",
            "Bounded error details never contain credential-shaped tokens",
            "AIProviderError.detail contains a sk-/AKIA/Bearer-shaped token",
            get("error_detail_never_contains_credential_shaped_tokens"),
        ),
        _scenario_from_check(
            "O",
            "The provider_contracts package has exactly its expected module set",
            "a file is missing from, or unexpectedly added to, provider_contracts/",
            get("provider_contracts_package_has_exactly_expected_modules"),
        ),
        _scenario_from_check(
            "P",
            "The provider_contracts package exists at the documented sibling location",
            "codestrata.ai.provider_contracts is missing from src/codestrata/ai/",
            get("provider_contracts_package_exists_at_documented_sibling_location"),
        ),
        _scenario_from_check(
            "Q",
            "AIProviderRequest rejects a payload/capability mismatch",
            "AIProviderRequest accepts a payload type not declared for its capability",
            get("request_rejects_capability_payload_mismatch"),
        ),
        _scenario_from_check(
            "R",
            "AIProviderRequest rejects an unsupported contract_version",
            "AIProviderRequest accepts contract_version='99.0'",
            get("request_rejects_unsupported_contract_version"),
        ),
        _scenario_from_check(
            "S",
            "ProviderUsageMetadata rejects an inconsistent token total",
            "ProviderUsageMetadata(input_tokens, output_tokens, total_tokens) accepts a "
            "total that does not equal input + output",
            get("usage_rejects_inconsistent_token_total"),
        ),
        _scenario_from_check(
            "T",
            "AIProviderError rejects raw-exception-shaped detail text",
            "AIProviderError accepts a detail containing 'Traceback (most recent call last)'",
            get("error_rejects_traceback_shaped_detail"),
        ),
        _scenario_from_check(
            "U",
            "A SUCCESS result can never carry an attached error",
            "AIProviderResult(status=SUCCESS, error=...) is accepted",
            get("success_result_rejects_attached_error"),
        ),
        _scenario_from_check(
            "V",
            "A FAILED/UNAVAILABLE result always requires an attached error",
            "AIProviderResult(status=FAILED) is accepted without an error",
            get("failed_result_requires_attached_error"),
        ),
        _scenario_w_registry_rejects_duplicates_and_unknown_ids(checks_by_name),
        _scenario_x_no_absolute_paths(report_payload_preview),
        _scenario_y_no_secrets_in_report(report_payload_preview),
        _scenario_z_no_process_invocation(package_dir, verification_dir),
    ]
    return tuple(sorted(scenarios, key=lambda s: s.scenario_id))


__all__ = ["build_negative_scenarios"]
