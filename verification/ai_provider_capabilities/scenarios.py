"""Negative scenarios A-Z: checks that forbidden conditions do NOT hold."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from verification.ai_provider_capabilities.contract import EXPECTED_MODULES
from verification.ai_provider_capabilities.models import CheckResult, ScenarioResult

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


def _scenario_no_absolute_paths(
    scenario_id: str, report_payload_preview: dict[str, object]
) -> ScenarioResult:
    from verification.ai_provider_capabilities.determinism import canonical_json

    text = canonical_json(report_payload_preview)
    hits = _find_matches(_ABSOLUTE_PATH_PATTERNS, text)
    return ScenarioResult(
        scenario_id=scenario_id,
        title="Capability verification report contains no absolute filesystem paths",
        forbidden_condition="report JSON contains an absolute macOS or Linux user-home path",
        ok=not hits,
        detail=f"hits={hits[:5]}" if hits else "no absolute-path patterns found",
    )


def _scenario_no_secrets_in_report(
    scenario_id: str, report_payload_preview: dict[str, object]
) -> ScenarioResult:
    from verification.ai_provider_capabilities.determinism import canonical_json

    text = canonical_json(report_payload_preview)
    hits = _find_matches(_SECRET_PATTERNS, text)
    return ScenarioResult(
        scenario_id=scenario_id,
        title="Capability verification report contains no secret-shaped tokens",
        forbidden_condition="report JSON contains a sk-/AKIA/Bearer-shaped token",
        ok=not hits,
        detail=f"hits={hits[:5]}" if hits else "no secret-shaped tokens found",
    )


def _scenario_no_process_invocation(
    scenario_id: str, package_dir: Path, verification_dir: Path
) -> ScenarioResult:
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
        scenario_id=scenario_id,
        title="Neither the capability/usage modules nor this verification package shells out",
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
            "provider_contracts has no codestrata dependency outside itself",
            "a capability_*/usage_* module imports another codestrata.* package",
            get("provider_contracts_has_no_codestrata_dependencies_outside_itself"),
        ),
        _scenario_from_check(
            "D",
            "No product-path file imports provider_contracts",
            "assessment/service.py, enrichment/service.py, bedrock.py, "
            "doctor.py, aws_config.py, settings.py, profiles.py, or assess.py imports "
            "provider_contracts",
            get("product_path_files_do_not_import_provider_contracts"),
        ),
        _scenario_from_check(
            "E",
            "The existing ai/providers/ directory has no new files from Slice 11.5",
            "ai/providers/ contains a file outside the Slice 11.1 baseline set",
            get("ai_providers_directory_has_no_new_files_from_slice_11_5"),
        ),
        _scenario_from_check(
            "F",
            "The 12 new capability_*/usage_* modules never import os/pathlib/subprocess/"
            "threading/asyncio/signal",
            "a capability_*/usage_* module imports a forbidden runtime module",
            get(
                "capability_and_usage_modules_never_import_os_pathlib_subprocess_"
                "threading_asyncio_or_signal"
            ),
        ),
        _scenario_from_check(
            "G",
            "The provider_contracts package has exactly its expected module set after Slice 11.5",
            "a file is missing from, or unexpectedly added to, provider_contracts/",
            get("provider_contracts_package_has_exactly_expected_modules_after_slice_11_5"),
        ),
        _scenario_from_check(
            "H",
            "All twelve Slice 11.5 capability/usage modules are present",
            "a Slice 11.5 capability_*/usage_* module is missing",
            get("all_twelve_slice_11_5_capability_and_usage_modules_are_present"),
        ),
        _scenario_from_check(
            "I",
            "The Slice 11.1 baseline defines exactly CR-1..CR-6",
            "build_compatibility_requirements() returns a different requirement ID set",
            get("slice_11_1_baseline_defines_cr1_through_cr6"),
        ),
        _scenario_from_check(
            "J",
            "Every baseline compatibility requirement is covered by a capability statement",
            "a CR-1..CR-6 requirement has no matching CapabilityCompatibilityStatement",
            get("capability_compatibility_statements_cover_every_baseline_requirement"),
        ),
        _scenario_from_check(
            "K",
            "No capability compatibility statement reports holds=False",
            "a CapabilityCompatibilityStatement has holds=False",
            get("every_capability_compatibility_statement_holds_true"),
        ),
        _scenario_from_check(
            "L",
            "Prior slice compatibility notes cover exactly 11.2, 11.3, and 11.4",
            "a prior-slice compatibility note is missing or an extra slice ID appears",
            get("prior_slice_compatibility_notes_cover_slices_11_2_11_3_and_11_4"),
        ),
        _scenario_from_check(
            "M",
            "No prior-slice compatibility note reports holds=False",
            "a PriorSliceCompatibilityNote has holds=False",
            get("every_prior_slice_compatibility_note_holds_true"),
        ),
        _scenario_from_check(
            "N",
            "ProviderId includes bedrock, openai, and openrouter; assess IDs remain a subset",
            "ProviderId drops bedrock/openai or gains an unexpected value beyond openrouter",
            get("provider_id_enum_superset_of_baseline_engine_provider_ids"),
        ),
        _scenario_from_check(
            "O",
            "Both catalog profiles declare the modernization_advisor capability",
            "the bedrock or openai catalog profile omits modernization_advisor",
            get("both_catalog_profiles_declare_modernization_advisor"),
        ),
        _scenario_from_check(
            "P",
            "Structured JSON support reflects the intentional OpenAI/Bedrock difference",
            "openai_supports_structured_json is False, or bedrock is True without the "
            "prompt_instruction_only limitation",
            get("structured_json_support_reflects_intentional_openai_bedrock_difference"),
        ),
        _scenario_from_check(
            "Q",
            "Neither catalog profile declares streaming support",
            "bedrock or openai declares supports_streaming=True",
            get("neither_catalog_profile_declares_streaming_support"),
        ),
        _scenario_from_check(
            "R",
            "Timeout/retry policy support flags carry the not_wired_to_runtime limitation",
            "a catalog profile declares supports_timeout_policy/supports_retry_policy=True "
            "without the not_wired_to_runtime limitation",
            get("timeout_and_retry_policy_support_flags_carry_not_wired_to_runtime_limitation"),
        ),
        _scenario_from_check(
            "S",
            "ProviderCapabilityProfile construction rejects a non-CapabilityId entry",
            "ProviderCapabilityProfile accepts a plain string in supported_capability_ids",
            get("profile_construction_rejects_a_non_capability_id_entry"),
        ),
        _scenario_from_check(
            "T",
            "ProviderCapabilityProfile construction rejects an unknown limitation string",
            "ProviderCapabilityProfile accepts a limitation outside the allowed set",
            get("profile_construction_rejects_an_unknown_limitation"),
        ),
        _scenario_from_check(
            "U",
            "ProviderCapabilityProfile construction rejects supports_streaming=True",
            "ProviderCapabilityProfile accepts supports_streaming=True for this slice's baseline",
            get("profile_construction_rejects_supports_streaming_true"),
        ),
        _scenario_from_check(
            "V",
            "validate_completion_status_is_known rejects an unknown completion status string",
            "validate_completion_status_is_known accepts a status outside the allowed set",
            get("validate_completion_status_is_known_rejects_an_unknown_string"),
        ),
        _scenario_from_check(
            "W",
            "Capability profile diagnostics/serialization contain no credential-shaped tokens",
            "diagnostic_view_of_capability_profile()/serialize_capability_profile_for_"
            "diagnostics() output contains a sk-/AKIA/Bearer-shaped token",
            get("capability_diagnostic_view_contains_no_credential_shaped_tokens"),
        ),
        _scenario_from_check(
            "X",
            "Usage serialization never contains a forbidden (cost/prompt/response/etc.) field name",
            "a serialized capability or usage view contains a forbidden field name from "
            "usage_policy.FORBIDDEN_USAGE_FIELD_NAMES",
            get("serialized_capability_and_usage_forms_exclude_forbidden_field_names"),
        ),
        _scenario_from_check(
            "Y",
            "Importing capability/usage modules never changes the assess provider registry",
            "importing a capability_*/usage_* module changes get_assess_ai_provider_registry()"
            ".list_providers()",
            get("importing_capability_modules_does_not_change_assess_registry"),
        ),
        _scenario_from_check(
            "Z",
            "Importing capability/usage modules never changes AiSettings defaults",
            "importing a capability_*/usage_* module changes AiSettings().provider or "
            "openai.answer_model",
            get("ai_settings_defaults_are_unchanged_after_importing_capability_modules"),
        ),
        _scenario_no_absolute_paths("AA", report_payload_preview),
        _scenario_no_secrets_in_report("AB", report_payload_preview),
        _scenario_no_process_invocation("AC", package_dir, verification_dir),
    ]
    return tuple(sorted(scenarios, key=lambda s: (len(s.scenario_id), s.scenario_id)))


__all__ = ["build_negative_scenarios"]
