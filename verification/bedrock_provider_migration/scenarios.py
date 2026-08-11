"""Negative scenarios A-Z: conditions that must NOT hold after Slice 11.7.

Each scenario names a forbidden condition and passes when that condition is
absent. Together they are the "what would make this migration wrong" list.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from verification.bedrock_provider_migration.contract import (
    ASSESSMENT_SCHEMA_VERSION,
    BEDROCK_CONFIG_KEYS,
    BEDROCK_DEFAULT_MODEL_ID,
    DEFAULT_PROVIDER,
    EXPECTED_MAXIMUM_ATTEMPTS,
    EXPECTED_MODULES,
    EXPECTED_REGISTERED_PROVIDERS,
    EXPECTED_SDK_MAX_ATTEMPTS,
    FORBIDDEN_PROVIDER_TOKENS,
    STRUCTURED_JSON_INSTRUCTION,
    SUPPORTS_NATIVE_STRUCTURED_JSON,
    WRAPPER_REQUIRED_EXPORTS,
)
from verification.bedrock_provider_migration.models import ScenarioResult


def _module_imports(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def scenario_a_the_default_provider_changed() -> ScenarioResult:
    from codestrata.config.settings import CodestrataSettings

    actual = CodestrataSettings.model_validate({"repository": {"path": "."}}).ai.provider
    return ScenarioResult(
        scenario_id="A",
        title="The default provider silently changed",
        forbidden_condition="an unconfigured run no longer selects bedrock",
        ok=actual == DEFAULT_PROVIDER,
        detail=f"default_provider={actual}",
    )


def scenario_b_the_default_model_changed() -> ScenarioResult:
    from codestrata.config import DEFAULT_BEDROCK_MODEL_ID

    return ScenarioResult(
        scenario_id="B",
        title="The default Bedrock model changed",
        forbidden_condition="the default model is no longer amazon.nova-lite-v1:0",
        ok=DEFAULT_BEDROCK_MODEL_ID == BEDROCK_DEFAULT_MODEL_ID,
        detail=f"default_model_id={DEFAULT_BEDROCK_MODEL_ID}",
    )


def scenario_c_a_bedrock_config_key_changed() -> ScenarioResult:
    from codestrata.config.settings import BedrockSettings

    actual = tuple(sorted(BedrockSettings.model_fields))
    return ScenarioResult(
        scenario_id="C",
        title="A Bedrock configuration key was renamed, added, or removed",
        forbidden_condition="the [ai.bedrock] key set differs from the baseline",
        ok=actual == BEDROCK_CONFIG_KEYS,
        detail=f"config_keys={list(actual)}",
    )


def scenario_d_the_wrapper_lost_its_public_surface() -> ScenarioResult:
    from codestrata.ai.providers import bedrock as wrapper_module

    missing = sorted(
        name for name in WRAPPER_REQUIRED_EXPORTS if not hasattr(wrapper_module, name)
    )
    return ScenarioResult(
        scenario_id="D",
        title="The compatibility wrapper dropped a public helper",
        forbidden_condition="an existing import from codestrata.ai.providers.bedrock broke",
        ok=not missing,
        detail=f"missing_exports={missing}",
    )


def scenario_e_the_constructor_signature_changed() -> ScenarioResult:
    import inspect

    from codestrata.ai.providers.bedrock import BedrockAIModelProvider
    from verification.bedrock_provider_migration.contract import (
        WRAPPER_CONSTRUCTOR_PARAMETERS,
    )

    actual = tuple(inspect.signature(BedrockAIModelProvider.__init__).parameters)
    return ScenarioResult(
        scenario_id="E",
        title="The provider constructor signature changed",
        forbidden_condition="an existing construction call site would break",
        ok=actual == WRAPPER_CONSTRUCTOR_PARAMETERS,
        detail=f"parameters={list(actual)}",
    )


def scenario_f_construction_still_reaches_aws() -> ScenarioResult:
    from codestrata.ai.provider_adapters.bedrock import client as client_module
    from codestrata.ai.providers.bedrock import BedrockAIModelProvider

    calls: list[dict[str, Any]] = []

    class _Stub:
        AwsAuthenticationError = client_module.AwsAuthenticationError

        @staticmethod
        def create_bedrock_runtime_client(**kwargs: Any) -> Any:
            calls.append(kwargs)
            return object()

    real = client_module.aws_config
    client_module.aws_config = _Stub  # type: ignore[assignment]
    try:
        BedrockAIModelProvider()
    finally:
        client_module.aws_config = real  # type: ignore[assignment]
    return ScenarioResult(
        scenario_id="F",
        title="Client construction stayed eager",
        forbidden_condition="constructing a provider still reaches the AWS credential chain",
        ok=not calls,
        detail=f"client_factory_calls_during_construction={len(calls)}",
    )


def scenario_g_the_credential_boundary_widened(package_dir: Path) -> ScenarioResult:
    offenders = sorted(
        filename
        for filename in EXPECTED_MODULES
        if filename != "client.py"
        and any(
            name.split(".")[0] in {"boto3", "botocore"}
            for name in _module_imports(package_dir / filename)
        )
    )
    return ScenarioResult(
        scenario_id="G",
        title="A second module reached for the AWS SDK",
        forbidden_condition="a module other than client.py imports boto3 or botocore",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def scenario_h_the_credential_chain_was_reimplemented(package_dir: Path) -> ScenarioResult:
    offenders: list[str] = []
    for filename in EXPECTED_MODULES:
        path = package_dir / filename
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if any(
            token in text
            for token in ("boto3.Session(", "Session(profile_name", "get_credentials(")
        ):
            offenders.append(filename)
    return ScenarioResult(
        scenario_id="H",
        title="The AWS credential chain was reimplemented in the adapter",
        forbidden_condition="the adapter builds its own boto3 session or reads credentials",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def scenario_i_the_adapter_reads_the_environment(package_dir: Path) -> ScenarioResult:
    offenders = sorted(
        filename
        for filename in EXPECTED_MODULES
        if "os" in _module_imports(package_dir / filename)
    )
    return ScenarioResult(
        scenario_id="I",
        title="The adapter started reading environment variables",
        forbidden_condition="an adapter module imports os to read AWS configuration",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def scenario_j_the_converse_wire_shape_changed() -> ScenarioResult:
    from codestrata.ai.provider_adapters.bedrock.factory import build_bedrock_provider
    from verification.bedrock_provider_migration import fixtures
    from verification.bedrock_provider_migration.contract import (
        EXPECTED_CONVERSE_KWARG_NAMES,
    )

    client = fixtures.Client()
    build_bedrock_provider(client=client).execute(fixtures.provider_request())
    actual = tuple(sorted(client.calls[0]))
    return ScenarioResult(
        scenario_id="J",
        title="The Converse call shape changed",
        forbidden_condition="the kwargs sent to converse differ from the baseline",
        ok=actual == EXPECTED_CONVERSE_KWARG_NAMES,
        detail=f"kwarg_names={list(actual)}",
    )


def scenario_k_the_prompt_bytes_changed() -> ScenarioResult:
    from codestrata.ai.provider_adapters.bedrock.factory import build_bedrock_provider
    from verification.bedrock_provider_migration import fixtures

    client = fixtures.Client()
    build_bedrock_provider(client=client).execute(fixtures.provider_request())
    system_text = client.calls[0]["system"][0]["text"]
    return ScenarioResult(
        scenario_id="K",
        title="The prompt bytes changed",
        forbidden_condition="the structured-JSON instruction is missing or duplicated",
        ok=system_text.count(STRUCTURED_JSON_INSTRUCTION) == 1,
        detail=f"instruction_occurrences={system_text.count(STRUCTURED_JSON_INSTRUCTION)}",
    )


def scenario_l_a_native_json_mode_was_claimed() -> ScenarioResult:
    from codestrata.ai.provider_adapters.bedrock import capabilities

    return ScenarioResult(
        scenario_id="L",
        title="Bedrock claimed a native structured-JSON mode",
        forbidden_condition="the capability profile reports native structured JSON support",
        ok=capabilities.SUPPORTS_NATIVE_STRUCTURED_JSON is SUPPORTS_NATIVE_STRUCTURED_JSON,
        detail=f"supports_structured_json={capabilities.SUPPORTS_NATIVE_STRUCTURED_JSON}",
    )


def scenario_m_an_openai_concept_leaked() -> ScenarioResult:
    from codestrata.ai.provider_adapters.bedrock.factory import build_bedrock_provider
    from verification.bedrock_provider_migration import fixtures
    from verification.bedrock_provider_migration.contract import (
        FORBIDDEN_REQUEST_KWARG_NAMES,
    )

    client = fixtures.Client()
    build_bedrock_provider(client=client).execute(fixtures.provider_request())
    offenders = sorted(
        name for name in FORBIDDEN_REQUEST_KWARG_NAMES if name in client.calls[0]
    )
    return ScenarioResult(
        scenario_id="M",
        title="An OpenAI request concept leaked into the Converse call",
        forbidden_condition="an OpenAI-style kwarg such as response_format is sent to Bedrock",
        ok=not offenders,
        detail=f"offending_kwargs={offenders}",
    )


def scenario_n_codestrata_retries_were_activated() -> ScenarioResult:
    from codestrata.ai.provider_adapters.bedrock.factory import BEDROCK_RETRY_POLICY

    return ScenarioResult(
        scenario_id="N",
        title="CodeStrata retries were activated",
        forbidden_condition="the executor makes more than one attempt per assess run",
        ok=BEDROCK_RETRY_POLICY.maximum_attempts == EXPECTED_MAXIMUM_ATTEMPTS,
        detail=f"maximum_attempts={BEDROCK_RETRY_POLICY.maximum_attempts}",
    )


def scenario_o_sdk_retries_were_stacked(engine_root: Path) -> ScenarioResult:
    source = (engine_root / "src" / "codestrata" / "ai" / "aws_config.py").read_text(
        encoding="utf-8"
    )
    return ScenarioResult(
        scenario_id="O",
        title="CodeStrata retries were stacked on top of SDK retries",
        forbidden_condition="botocore is no longer pinned to a single retry attempt",
        ok=f'"max_attempts": {EXPECTED_SDK_MAX_ATTEMPTS}' in source,
        detail=f"expected_sdk_max_attempts={EXPECTED_SDK_MAX_ATTEMPTS}",
    )


def scenario_p_max_retries_was_wired() -> ScenarioResult:
    from codestrata.ai.provider_adapters.bedrock.configuration import resolve_max_retries
    from codestrata.ai.provider_adapters.bedrock.factory import BEDROCK_RETRY_POLICY
    from verification.bedrock_provider_migration.configuration import settings_with

    declared = resolve_max_retries(settings_with(max_retries=9))
    return ScenarioResult(
        scenario_id="P",
        title="The max_retries setting became load-bearing",
        forbidden_condition="a configured max_retries changes the number of attempts",
        ok=declared == 9 and BEDROCK_RETRY_POLICY.maximum_attempts == 1,
        detail=f"declared={declared} attempts={BEDROCK_RETRY_POLICY.maximum_attempts}",
    )


def scenario_q_execute_raises_for_an_expected_failure() -> ScenarioResult:
    from codestrata.ai.provider_adapters.bedrock.factory import build_bedrock_provider
    from verification.bedrock_provider_migration import fixtures

    raised: list[str] = []
    for outcome in (
        fixtures.client_error("ThrottlingException"),
        fixtures.sdk_exception("NoCredentialsError"),
        {},
        "not-a-mapping",
    ):
        try:
            build_bedrock_provider(client=fixtures.Client(outcome)).execute(
                fixtures.provider_request()
            )
        except Exception as error:  # noqa: BLE001 - escaping exceptions are the subject
            raised.append(type(error).__name__)
    return ScenarioResult(
        scenario_id="Q",
        title="execute() raised for an expected provider failure",
        forbidden_condition="an expected failure escapes as an exception instead of a result",
        ok=not raised,
        detail=f"escaped_exceptions={raised}",
    )


def scenario_r_the_legacy_exception_type_changed() -> ScenarioResult:
    from codestrata.ai.providers.bedrock import BedrockAIModelProvider
    from codestrata.ai.providers.exceptions import AIProviderTimeoutError
    from verification.bedrock_provider_migration import fixtures

    provider = BedrockAIModelProvider(
        client=fixtures.Client(fixtures.sdk_exception("ReadTimeoutError"))
    )
    try:
        provider.invoke(fixtures.model_request(), fixtures.invocation_options())
    except BaseException as error:  # noqa: BLE001 - the raised type is the subject
        raised: BaseException | None = error
    else:
        raised = None
    return ScenarioResult(
        scenario_id="R",
        title="A failure changed which legacy exception enrichment sees",
        forbidden_condition="a timeout no longer raises AIProviderTimeoutError",
        ok=isinstance(raised, AIProviderTimeoutError),
        detail=f"raised={type(raised).__name__}",
    )


def scenario_s_the_report_schema_changed() -> ScenarioResult:
    from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION

    return ScenarioResult(
        scenario_id="S",
        title="The assessment report schema changed",
        forbidden_condition="the assessment schema version is no longer 1.2",
        ok=ASSESSMENT_JSON_SCHEMA_VERSION == ASSESSMENT_SCHEMA_VERSION,
        detail=f"schema_version={ASSESSMENT_JSON_SCHEMA_VERSION}",
    )


def scenario_t_the_adapter_reached_the_reporting_layer(package_dir: Path) -> ScenarioResult:
    offenders = sorted(
        filename
        for filename in EXPECTED_MODULES
        if any(
            name.startswith(
                (
                    "codestrata.analytics",
                    "codestrata.datalake",
                    "codestrata.reporting",
                    "codestrata.telemetry",
                )
            )
            for name in _module_imports(package_dir / filename)
        )
    )
    return ScenarioResult(
        scenario_id="T",
        title="The adapter reached the reporting or telemetry layer",
        forbidden_condition="an adapter module imports reporting, analytics, or telemetry",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def scenario_u_a_request_id_reached_a_result() -> ScenarioResult:
    from codestrata.ai.provider_adapters.bedrock import diagnostics
    from codestrata.ai.provider_adapters.bedrock.factory import build_bedrock_provider
    from verification.bedrock_provider_migration import fixtures
    from verification.bedrock_provider_migration.determinism import canonical_json

    result = build_bedrock_provider(
        client=fixtures.Client(fixtures.converse_response())
    ).execute(fixtures.provider_request())
    rendered = canonical_json(diagnostics.diagnostic_view_of_provider_result(result))
    return ScenarioResult(
        scenario_id="U",
        title="A provider request ID reached a contract result",
        forbidden_condition="the request ID appears in a result diagnostic view",
        ok=fixtures.SYNTHETIC_REQUEST_ID not in rendered,
        detail="request IDs stay on the bridge-only invocation detail",
    )


def scenario_v_a_profile_or_region_reached_a_diagnostic_view() -> ScenarioResult:
    from codestrata.ai.provider_adapters.bedrock import diagnostics
    from codestrata.ai.provider_adapters.bedrock.factory import build_bedrock_provider
    from verification.bedrock_provider_migration import fixtures, privacy
    from verification.bedrock_provider_migration.determinism import canonical_json

    from codestrata.config.settings import CodestrataSettings

    settings = CodestrataSettings.model_validate(
        {
            "repository": {"path": "."},
            "aws": {
                "profile": privacy.SECRET_PROFILE_NAME,
                "region": privacy.SECRET_REGION_NAME,
            },
        }
    )
    adapter = build_bedrock_provider(settings=settings, client=fixtures.Client())
    rendered = canonical_json(diagnostics.diagnostic_view_of_adapter(adapter))
    leaked = privacy.leaked_substrings(rendered)
    return ScenarioResult(
        scenario_id="V",
        title="An AWS profile or region reached a diagnostic view",
        forbidden_condition="a diagnostic view renders the profile name or region string",
        ok=not leaked,
        detail=f"leaked={leaked}",
    )


def scenario_w_the_adapter_can_sleep_or_open_a_socket(package_dir: Path) -> ScenarioResult:
    offenders: list[str] = []
    for filename in EXPECTED_MODULES:
        names = _module_imports(package_dir / filename)
        if names & {"asyncio", "httpx", "requests", "socket", "subprocess", "threading", "urllib"}:
            offenders.append(filename)
        path = package_dir / filename
        if path.is_file() and "time.sleep(" in path.read_text(encoding="utf-8"):
            offenders.append(filename)
    return ScenarioResult(
        scenario_id="W",
        title="The adapter gained a wait or its own network client",
        forbidden_condition="an adapter module sleeps, threads, or opens a socket",
        ok=not offenders,
        detail=f"offenders={sorted(set(offenders))}",
    )


def scenario_x_openrouter_work_started(engine_root: Path) -> ScenarioResult:
    """Fail when OpenRouter appears outside allowed operational surfaces (incl. doctor readiness)."""

    ai_root = engine_root / "src" / "codestrata" / "ai"
    allowed = {
        "providers/openrouter_provider.py",
        "providers/factory.py",
        "providers/doctor.py",
    }
    offenders: list[str] = []
    for path in sorted(ai_root.rglob("*.py")):
        rel = path.relative_to(ai_root).as_posix()
        if (
            rel.startswith("provider_adapters/openrouter/")
            or rel.startswith("provider_contracts/")
            or rel in allowed
        ):
            continue
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in FORBIDDEN_PROVIDER_TOKENS):
            offenders.append(rel)
    return ScenarioResult(
        scenario_id="X",
        title="OpenRouter appeared outside allowed operational surfaces",
        forbidden_condition=(
            "an OpenRouter reference exists under ai/ outside "
            "adapter/contracts/wrapper/factory/doctor"
        ),
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def scenario_y_an_unexpected_provider_adapter_appeared(engine_root: Path) -> ScenarioResult:
    adapters_root = engine_root / "src" / "codestrata" / "ai" / "provider_adapters"
    packages = sorted(
        path.name
        for path in adapters_root.iterdir()
        if path.is_dir() and (path / "__init__.py").is_file()
    )
    allowed = set(EXPECTED_REGISTERED_PROVIDERS) | {"openrouter"}
    unexpected = sorted(set(packages) - allowed)
    return ScenarioResult(
        scenario_id="Y",
        title="An unexpected provider adapter appeared",
        forbidden_condition="an adapter package beyond bedrock, openai, and openrouter exists",
        ok=not unexpected,
        detail=f"unexpected_adapter_packages={unexpected}",
    )


def scenario_z_the_openai_adapter_regressed(engine_root: Path) -> ScenarioResult:
    from verification.bedrock_provider_migration.openai_regression import (
        check_the_openai_adapter_module_set_is_unchanged,
        check_the_openai_adapter_still_succeeds,
    )

    failures = [
        check.name
        for check in (
            check_the_openai_adapter_still_succeeds(),
            check_the_openai_adapter_module_set_is_unchanged(engine_root),
        )
        if not check.ok
    ]
    return ScenarioResult(
        scenario_id="Z",
        title="The Slice 11.6 OpenAI migration regressed",
        forbidden_condition="the OpenAI adapter stopped working or changed shape",
        ok=not failures,
        detail=f"failed_checks={failures}",
    )


def run_negative_scenarios(engine_root: Path, package_dir: Path) -> list[ScenarioResult]:
    return [
        scenario_a_the_default_provider_changed(),
        scenario_b_the_default_model_changed(),
        scenario_c_a_bedrock_config_key_changed(),
        scenario_d_the_wrapper_lost_its_public_surface(),
        scenario_e_the_constructor_signature_changed(),
        scenario_f_construction_still_reaches_aws(),
        scenario_g_the_credential_boundary_widened(package_dir),
        scenario_h_the_credential_chain_was_reimplemented(package_dir),
        scenario_i_the_adapter_reads_the_environment(package_dir),
        scenario_j_the_converse_wire_shape_changed(),
        scenario_k_the_prompt_bytes_changed(),
        scenario_l_a_native_json_mode_was_claimed(),
        scenario_m_an_openai_concept_leaked(),
        scenario_n_codestrata_retries_were_activated(),
        scenario_o_sdk_retries_were_stacked(engine_root),
        scenario_p_max_retries_was_wired(),
        scenario_q_execute_raises_for_an_expected_failure(),
        scenario_r_the_legacy_exception_type_changed(),
        scenario_s_the_report_schema_changed(),
        scenario_t_the_adapter_reached_the_reporting_layer(package_dir),
        scenario_u_a_request_id_reached_a_result(),
        scenario_v_a_profile_or_region_reached_a_diagnostic_view(),
        scenario_w_the_adapter_can_sleep_or_open_a_socket(package_dir),
        scenario_x_openrouter_work_started(engine_root),
        scenario_y_an_unexpected_provider_adapter_appeared(engine_root),
        scenario_z_the_openai_adapter_regressed(engine_root),
    ]


__all__ = [
    "run_negative_scenarios",
    "scenario_a_the_default_provider_changed",
    "scenario_b_the_default_model_changed",
    "scenario_c_a_bedrock_config_key_changed",
    "scenario_d_the_wrapper_lost_its_public_surface",
    "scenario_e_the_constructor_signature_changed",
    "scenario_f_construction_still_reaches_aws",
    "scenario_g_the_credential_boundary_widened",
    "scenario_h_the_credential_chain_was_reimplemented",
    "scenario_i_the_adapter_reads_the_environment",
    "scenario_j_the_converse_wire_shape_changed",
    "scenario_k_the_prompt_bytes_changed",
    "scenario_l_a_native_json_mode_was_claimed",
    "scenario_m_an_openai_concept_leaked",
    "scenario_n_codestrata_retries_were_activated",
    "scenario_o_sdk_retries_were_stacked",
    "scenario_p_max_retries_was_wired",
    "scenario_q_execute_raises_for_an_expected_failure",
    "scenario_r_the_legacy_exception_type_changed",
    "scenario_s_the_report_schema_changed",
    "scenario_t_the_adapter_reached_the_reporting_layer",
    "scenario_u_a_request_id_reached_a_result",
    "scenario_v_a_profile_or_region_reached_a_diagnostic_view",
    "scenario_w_the_adapter_can_sleep_or_open_a_socket",
    "scenario_x_openrouter_work_started",
    "scenario_y_an_unexpected_provider_adapter_appeared",
    "scenario_z_the_openai_adapter_regressed",
]
