"""Negative scenarios A-Z: conditions that must NOT hold after the migration.

Each scenario states a forbidden condition and passes when that condition is
absent. They are the inverse of the positive checks: where a check asserts "the
adapter classifies an authentication error correctly", a scenario asserts "no
code path lets a credential reach a diagnostic view".
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from codestrata.ai.provider_adapters.openai import (
    diagnostics,
    error_mapping,
    legacy_bridge,
    request_mapping,
)
from codestrata.ai.provider_adapters.openai.factory import (
    OPENAI_RETRY_POLICY,
    build_openai_executor,
    build_openai_provider,
)
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.providers.exceptions import AIProviderConfigurationError
from codestrata.ai.providers.openai_provider import OpenAIAIModelProvider, _chat_messages
from codestrata.config import CodestrataSettings
from codestrata.config.settings import OpenAISettings
from verification.openai_provider_migration import fixtures, privacy
from verification.openai_provider_migration.contract import (
    ASSESSMENT_SCHEMA_VERSION,
    BEDROCK_MODULE_RELATIVE_PATH,
    DEFAULT_PROVIDER,
    EXPECTED_MODULES,
    FORBIDDEN_PROVIDER_TOKENS,
    OPENAI_CONFIG_KEYS,
    OPENAI_DEFAULT_ANSWER_MODEL,
    STRUCTURED_JSON_INSTRUCTION,
)
from verification.openai_provider_migration.determinism import canonical_json
from verification.openai_provider_migration.models import ScenarioResult


def _scenario(
    scenario_id: str, title: str, forbidden: str, *, holds: bool, detail: str
) -> ScenarioResult:
    """Build a scenario result. ``holds=True`` means the forbidden condition occurred."""

    return ScenarioResult(
        scenario_id=scenario_id,
        title=title,
        forbidden_condition=forbidden,
        ok=not holds,
        detail=detail,
    )


def _module_paths(package_dir: Path) -> list[Path]:
    return [package_dir / name for name in EXPECTED_MODULES if (package_dir / name).is_file()]


def _imports_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def scenario_a_default_provider_changed() -> ScenarioResult:
    settings = CodestrataSettings.model_validate({"repository": {"path": "."}})
    changed = settings.ai.provider != DEFAULT_PROVIDER
    return _scenario(
        "A",
        "The default assess provider changed",
        "an unconfigured run selects anything other than bedrock",
        holds=changed,
        detail=f"default_provider={settings.ai.provider}",
    )


def scenario_b_openai_config_keys_changed() -> ScenarioResult:
    actual = tuple(sorted(OpenAISettings.model_fields))
    changed = actual != tuple(sorted(OPENAI_CONFIG_KEYS))
    return _scenario(
        "B",
        "The OpenAI configuration keys changed",
        "a key was added to, removed from, or renamed in [ai.openai]",
        holds=changed,
        detail=f"config_keys={list(actual)}",
    )


def scenario_c_default_answer_model_changed() -> ScenarioResult:
    actual = OpenAISettings().answer_model
    return _scenario(
        "C",
        "The default OpenAI answer model changed",
        "the default answer_model is no longer gpt-4o-mini",
        holds=actual != OPENAI_DEFAULT_ANSWER_MODEL,
        detail=f"answer_model={actual}",
    )


def scenario_d_prompt_content_changed() -> ScenarioResult:
    prompt_request = fixtures.prompt_request()
    migrated = request_mapping.build_chat_messages(
        legacy_bridge.fold_prompt_request(prompt_request),
        response_expectation=fixtures.provider_request().response_expectation,
    )
    return _scenario(
        "D",
        "The prompt content changed",
        "the migrated message array differs from the pre-migration helper's",
        holds=migrated != _chat_messages(prompt_request),
        detail="compared against ai/providers/openai_provider._chat_messages",
    )


def scenario_e_json_instruction_duplicated() -> ScenarioResult:
    messages = request_mapping.build_chat_messages(
        legacy_bridge.fold_prompt_request(fixtures.prompt_request(system=None, developer=None)),
        response_expectation=fixtures.provider_request().response_expectation,
    )
    occurrences = messages[0]["content"].count(STRUCTURED_JSON_INSTRUCTION)
    return _scenario(
        "E",
        "The structured-JSON instruction was appended twice",
        "a folded instruction text carries the JSON trailer more than once",
        holds=occurrences != 1,
        detail=f"json_instruction_occurrences={occurrences}",
    )


def scenario_f_retry_activated() -> ScenarioResult:
    attempts = OPENAI_RETRY_POLICY.maximum_attempts
    return _scenario(
        "F",
        "Operational retry was activated",
        "the pinned retry policy permits more than one attempt",
        holds=attempts != 1,
        detail=f"maximum_attempts={attempts}",
    )


def scenario_g_more_than_one_provider_call() -> ScenarioResult:
    client = fixtures.Client(fixtures.sdk_exception("RateLimitError"))
    executor = build_openai_executor(build_openai_provider(client=client))
    executor.execute(fixtures.provider_request())
    return _scenario(
        "G",
        "A retryable failure produced more than one provider call",
        "one invocation issues more than one Chat Completions call",
        holds=len(client.calls) != 1,
        detail=f"sdk_calls={len(client.calls)}",
    )


def scenario_h_executor_sleeps() -> ScenarioResult:
    delays: list[float] = []
    executor = build_openai_executor(
        build_openai_provider(client=fixtures.Client(fixtures.sdk_exception("APITimeoutError"))),
        sleeper=delays.append,
    )
    executor.execute(fixtures.provider_request())
    return _scenario(
        "H",
        "The executor introduced a wall-clock wait",
        "a backoff delay is requested during a single-attempt run",
        holds=bool(delays),
        detail=f"sleep_calls={len(delays)}",
    )


def scenario_i_execute_raises_for_an_expected_failure() -> ScenarioResult:
    raised: list[str] = []
    adapter = build_openai_provider(
        openai_settings=OpenAISettings(api_key_env="SYNTHETIC_SCENARIO_KEY_VAR"),
        environment_reader=fixtures.no_environment,
    )
    for outcome_name in ("missing_key", "sdk_failure", "empty_response"):
        try:
            if outcome_name == "missing_key":
                adapter.execute(fixtures.provider_request())
            else:
                probe = build_openai_provider(
                    client=fixtures.Client(
                        fixtures.sdk_exception("BadRequestError")
                        if outcome_name == "sdk_failure"
                        else fixtures.response("")
                    )
                )
                probe.execute(fixtures.provider_request())
        except Exception as error:  # noqa: BLE001 - the scenario is that nothing raises
            raised.append(f"{outcome_name}:{type(error).__name__}")
    return _scenario(
        "I",
        "AIProvider.execute raised for an expected failure",
        "an expected provider failure escapes execute() as an exception",
        holds=bool(raised),
        detail=f"raised={raised}",
    )


def scenario_j_a_secret_reaches_a_diagnostic_view() -> ScenarioResult:
    adapter = build_openai_provider(
        openai_settings=OpenAISettings(
            api_key_env=privacy.SECRET_KEY_ENV_NAME, base_url=privacy.SECRET_BASE_URL
        ),
        client=fixtures.Client(fixtures.response(privacy.SECRET_RESPONSE_TEXT)),
        environment_reader=lambda _name: privacy.SECRET_API_KEY,
    )
    rendered = canonical_json(diagnostics.diagnostic_view_of_adapter(adapter))
    leaked = privacy.leaked_substrings(rendered)
    return _scenario(
        "J",
        "A credential or base URL reached a diagnostic view",
        "a diagnostic view carries an API key or a base URL value",
        holds=bool(leaked),
        detail=f"leaked={leaked}",
    )


def scenario_k_raw_exception_text_reaches_a_bounded_error() -> ScenarioResult:
    mapped = error_mapping.classify_sdk_exception(
        fixtures.sdk_exception("BadRequestError", privacy.SECRET_EXCEPTION_TEXT)
    )
    leaked = privacy.leaked_substrings(f"{mapped.error.detail} {mapped.error.code}")
    return _scenario(
        "K",
        "Raw exception text reached a bounded error",
        "an AIProviderError detail echoes SDK exception text",
        holds=bool(leaked),
        detail=f"leaked={leaked}",
    )


def scenario_l_response_text_reaches_a_result_view() -> ScenarioResult:
    adapter = build_openai_provider(
        client=fixtures.Client(fixtures.response(privacy.SECRET_RESPONSE_TEXT))
    )
    result = adapter.execute(fixtures.provider_request())
    rendered = canonical_json(diagnostics.diagnostic_view_of_provider_result(result))
    leaked = privacy.leaked_substrings(rendered)
    return _scenario(
        "L",
        "Response text reached a result diagnostic view",
        "a result view carries provider response text",
        holds=bool(leaked),
        detail=f"leaked={leaked}",
    )


def scenario_m_a_legacy_exception_type_changed() -> ScenarioResult:
    from verification.openai_provider_migration.contract import LEGACY_EXCEPTION_MATRIX

    wrong: list[str] = []
    for class_name, expected_name in LEGACY_EXCEPTION_MATRIX.items():
        provider = OpenAIAIModelProvider(client=fixtures.Client(fixtures.sdk_exception(class_name)))
        try:
            provider.invoke(fixtures.model_request(), fixtures.invocation_options())
        except Exception as error:  # noqa: BLE001 - the raised type is the subject
            if type(error).__name__ != expected_name:
                wrong.append(class_name)
        else:
            wrong.append(class_name)
    return _scenario(
        "M",
        "A legacy exception type changed",
        "the wrapper raises a different exception type than before the migration",
        holds=bool(wrong),
        detail=f"changed={sorted(wrong)}",
    )


def scenario_n_a_missing_key_message_leaks_a_value() -> ScenarioResult:
    error = legacy_bridge.legacy_error_for(
        error_mapping.build_error(error_mapping.CODE_MISSING_API_KEY),
        api_key_env_name=privacy.SECRET_KEY_ENV_NAME,
    )
    message = str(error)
    holds = privacy.SECRET_API_KEY in message or privacy.SECRET_KEY_ENV_NAME not in message
    return _scenario(
        "N",
        "The missing-key message leaked a value or dropped the variable name",
        "the message omits the variable name or includes the credential",
        holds=holds,
        detail="the message names the variable and nothing else",
    )


def scenario_o_bedrock_reached_into_the_openai_adapter(engine_root: Path) -> ScenarioResult:
    """Slice 11.7 wired Bedrock to *its own* adapter; borrowing OpenAI's is the failure.

    Until Slice 11.7 this scenario asserted that ``bedrock.py`` referenced no
    contract, adapter, or executor at all. Bedrock is migrated now, so the
    falsifiable claim that remains for SV.11.6 is that this slice's OpenAI
    work never became Bedrock's dependency.
    """

    source = (engine_root / "src" / "codestrata" / BEDROCK_MODULE_RELATIVE_PATH).read_text(
        encoding="utf-8"
    )
    offenders = sorted(
        token
        for token in ("provider_adapters.openai", "openai_provider", "OpenAIProvider")
        if token in source
    )
    return _scenario(
        "O",
        "Bedrock reached into the OpenAI adapter",
        "bedrock.py references the OpenAI adapter package or its wrapper",
        holds=bool(offenders),
        detail=f"offending_tokens={offenders}",
    )


def scenario_p_openrouter_appeared(engine_root: Path) -> ScenarioResult:
    ai_root = engine_root / "src" / "codestrata" / "ai"
    allowed = {
        "providers/openrouter_provider.py",
        "providers/factory.py",
        "providers/doctor.py",
    }
    offenders = sorted(
        path.relative_to(ai_root).as_posix()
        for path in ai_root.rglob("*.py")
        if not (
            path.relative_to(ai_root).as_posix().startswith("provider_adapters/openrouter/")
            or path.relative_to(ai_root).as_posix().startswith("provider_contracts/")
            or path.relative_to(ai_root).as_posix() in allowed
        )
        and any(token in path.read_text(encoding="utf-8") for token in FORBIDDEN_PROVIDER_TOKENS)
    )
    return _scenario(
        "P",
        "OpenRouter appeared outside allowed operational surfaces",
        "an openrouter token appears under ai/ outside adapter/contracts/wrapper/factory/doctor",
        holds=bool(offenders),
        detail=f"offenders={offenders}",
    )


def scenario_q_an_unexpected_provider_adapter_appeared(engine_root: Path) -> ScenarioResult:
    """Known adapter packages are bedrock, openai, and openrouter (unwired)."""

    adapters_root = engine_root / "src" / "codestrata" / "ai" / "provider_adapters"
    packages = sorted(
        path.name
        for path in adapters_root.iterdir()
        if path.is_dir() and (path / "__init__.py").is_file()
    )
    allowed = {"bedrock", "openai", "openrouter"}
    unexpected = sorted(set(packages) - allowed)
    return _scenario(
        "Q",
        "An unexpected provider adapter package appeared",
        "provider_adapters contains a package other than bedrock, openai, and openrouter",
        holds=bool(unexpected),
        detail=f"adapter_packages={packages} unexpected={unexpected}",
    )


def scenario_r_the_sdk_leaked_outside_the_client(package_dir: Path) -> ScenarioResult:
    offenders = sorted(
        path.name
        for path in _module_paths(package_dir)
        if path.name != "client.py"
        and any(name == "openai" or name.startswith("openai.") for name in _imports_in(path))
    )
    return _scenario(
        "R",
        "The OpenAI SDK leaked outside the credential boundary",
        "a module other than client.py imports the openai SDK",
        holds=bool(offenders),
        detail=f"offenders={offenders}",
    )


def scenario_s_the_environment_was_read_outside_the_client(package_dir: Path) -> ScenarioResult:
    offenders: list[str] = []
    for path in _module_paths(package_dir):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        reads = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
            and node.attr in {"environ", "getenv"}
        }
        if reads and path.name != "client.py":
            offenders.append(path.name)
    return _scenario(
        "S",
        "The environment was read outside the credential boundary",
        "a module other than client.py reads os.environ or os.getenv",
        holds=bool(offenders),
        detail=f"offenders={sorted(offenders)}",
    )


def scenario_t_the_adapter_reached_a_forbidden_layer(package_dir: Path) -> ScenarioResult:
    forbidden_prefixes = (
        "codestrata.analytics",
        "codestrata.application",
        "codestrata.cli",
        "codestrata.datalake",
        "codestrata.extensions",
        "codestrata.platform",
        "codestrata.reporting",
        "codestrata.telemetry",
    )
    offenders = sorted(
        path.name
        for path in _module_paths(package_dir)
        if any(name.startswith(forbidden_prefixes) for name in _imports_in(path))
    )
    return _scenario(
        "T",
        "The adapter reached a forbidden layer",
        "an adapter module imports the CLI, reporting, telemetry, or platform layer",
        holds=bool(offenders),
        detail=f"offenders={offenders}",
    )


def scenario_u_the_assess_layer_imported_the_sdk(engine_root: Path) -> ScenarioResult:
    src_root = engine_root / "src" / "codestrata"
    watched = (
        "application/assessment/service.py",
        "ai/enrichment/service.py",
        "extensions/assess_ai.py",
        "cli/assess.py",
    )
    offenders: list[str] = []
    for relative in watched:
        path = src_root / relative
        if not path.is_file():
            continue
        if any(name == "openai" or name.startswith("openai.") for name in _imports_in(path)):
            offenders.append(relative)
    return _scenario(
        "U",
        "The assess layer imported the OpenAI SDK",
        "assessment, enrichment, the registry, or the CLI imports the SDK directly",
        holds=bool(offenders),
        detail=f"offenders={offenders}",
    )


def scenario_v_the_contracts_gained_an_sdk_dependency(engine_root: Path) -> ScenarioResult:
    contracts_dir = engine_root / "src" / "codestrata" / "ai" / "provider_contracts"
    offenders: list[str] = []
    for path in sorted(contracts_dir.glob("*.py")):
        names = _imports_in(path)
        if any(name.split(".")[0] in {"openai", "boto3", "botocore", "httpx"} for name in names):
            offenders.append(path.name)
        elif any(name.startswith("codestrata.ai.provider_adapters") for name in names):
            offenders.append(path.name)
    return _scenario(
        "V",
        "The contracts gained an SDK or adapter dependency",
        "a provider_contracts module imports an SDK or an adapter",
        holds=bool(offenders),
        detail=f"offenders={sorted(offenders)}",
    )


def scenario_w_the_wrapper_public_surface_changed() -> ScenarioResult:
    import inspect

    from codestrata.ai.providers import openai_provider

    expected_parameters = ["self", "settings", "openai_settings", "timeout_seconds", "client"]
    actual_parameters = list(inspect.signature(OpenAIAIModelProvider.__init__).parameters)
    surface_changed = (
        actual_parameters != expected_parameters
        or openai_provider.OPENAI_PROVIDER_NAME != "openai"
        or sorted(openai_provider.__all__) != ["OPENAI_PROVIDER_NAME", "OpenAIAIModelProvider"]
    )
    return _scenario(
        "W",
        "The wrapper's public surface changed",
        "the class name, provider name, exports, or constructor signature changed",
        holds=surface_changed,
        detail=f"constructor_parameters={actual_parameters}",
    )


def scenario_x_a_client_was_constructed_eagerly() -> ScenarioResult:
    reads: list[str] = []
    adapter = build_openai_provider(
        openai_settings=OpenAISettings(api_key_env="SYNTHETIC_SCENARIO_KEY_VAR"),
        environment_reader=lambda name: (reads.append(name), None)[1],
    )
    supported = adapter.supports(fixtures.provider_request().capability)
    return _scenario(
        "X",
        "A client was constructed eagerly",
        "construction or capability discovery reads a credential",
        holds=bool(reads) or not supported,
        detail=f"environment_reads={len(reads)}",
    )


def scenario_y_the_assessment_schema_changed() -> ScenarioResult:
    from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION

    return _scenario(
        "Y",
        "The assessment report schema changed",
        "the assessment JSON schema version is no longer 1.2",
        holds=ASSESSMENT_JSON_SCHEMA_VERSION != ASSESSMENT_SCHEMA_VERSION,
        detail=f"schema_version={ASSESSMENT_JSON_SCHEMA_VERSION}",
    )


def scenario_z_a_blank_model_reached_the_wire() -> ScenarioResult:
    client = fixtures.Client(fixtures.response())
    provider = OpenAIAIModelProvider(client=client)
    rejected = False
    try:
        provider.invoke(fixtures.model_request(), fixtures.invocation_options(model_id="  "))
    except AIProviderConfigurationError:
        rejected = True
    except Exception:  # noqa: BLE001 - any other type is itself a failure
        rejected = False
    return _scenario(
        "Z",
        "A blank model ID reached the wire",
        "an empty model ID is forwarded instead of rejected",
        holds=not rejected or bool(client.calls),
        detail=f"sdk_calls={len(client.calls)}",
    )


def scenario_aa_a_success_result_lost_its_usage() -> ScenarioResult:
    adapter = build_openai_provider(client=fixtures.Client(fixtures.response()))
    result = adapter.execute(fixtures.provider_request())
    missing = result.status is ProviderExecutionStatus.SUCCESS and result.usage is None
    return _scenario(
        "AA",
        "A successful result lost its usage record",
        "a success result carries no usage metadata",
        holds=missing,
        detail=f"status={result.status.value} has_usage={result.usage is not None}",
    )


def scenario_ab_token_totals_were_invented() -> ScenarioResult:
    adapter = build_openai_provider(
        client=fixtures.Client(fixtures.response(usage=None))  # type: ignore[call-arg]
    )
    result = adapter.execute(fixtures.provider_request())
    usage = result.usage
    invented = usage is not None and (
        usage.input_tokens is not None or usage.total_tokens is not None
    )
    return _scenario(
        "AB",
        "Token totals were invented",
        "usage reports token counts the provider never sent",
        holds=invented,
        detail="a response without usage yields no token counts",
    )


def build_negative_scenarios(engine_root: Path, package_dir: Path) -> tuple[ScenarioResult, ...]:
    return (
        scenario_a_default_provider_changed(),
        scenario_b_openai_config_keys_changed(),
        scenario_c_default_answer_model_changed(),
        scenario_d_prompt_content_changed(),
        scenario_e_json_instruction_duplicated(),
        scenario_f_retry_activated(),
        scenario_g_more_than_one_provider_call(),
        scenario_h_executor_sleeps(),
        scenario_i_execute_raises_for_an_expected_failure(),
        scenario_j_a_secret_reaches_a_diagnostic_view(),
        scenario_k_raw_exception_text_reaches_a_bounded_error(),
        scenario_l_response_text_reaches_a_result_view(),
        scenario_m_a_legacy_exception_type_changed(),
        scenario_n_a_missing_key_message_leaks_a_value(),
        scenario_o_bedrock_reached_into_the_openai_adapter(engine_root),
        scenario_p_openrouter_appeared(engine_root),
        scenario_q_an_unexpected_provider_adapter_appeared(engine_root),
        scenario_r_the_sdk_leaked_outside_the_client(package_dir),
        scenario_s_the_environment_was_read_outside_the_client(package_dir),
        scenario_t_the_adapter_reached_a_forbidden_layer(package_dir),
        scenario_u_the_assess_layer_imported_the_sdk(engine_root),
        scenario_v_the_contracts_gained_an_sdk_dependency(engine_root),
        scenario_w_the_wrapper_public_surface_changed(),
        scenario_x_a_client_was_constructed_eagerly(),
        scenario_y_the_assessment_schema_changed(),
        scenario_z_a_blank_model_reached_the_wire(),
        scenario_aa_a_success_result_lost_its_usage(),
        scenario_ab_token_totals_were_invented(),
    )


def scenario_matrix(scenarios: tuple[ScenarioResult, ...]) -> dict[str, Any]:
    return {
        "scenario_count": len(scenarios),
        "scenario_ids": [scenario.scenario_id for scenario in scenarios],
    }


__all__ = [
    "build_negative_scenarios",
    "scenario_matrix",
]
