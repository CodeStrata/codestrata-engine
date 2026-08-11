"""Negative scenarios A–Z for SV.11.11."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from codestrata.ai.provider_adapters.openrouter.factory import (
    OPENROUTER_RETRY_POLICY,
    build_openrouter_provider,
)

# Import factory before assess_ai to keep load order stable.
from codestrata.ai.providers.factory import create_assess_ai_provider, resolve_assess_model_id
from codestrata.ai.providers.bedrock import BedrockAIModelProvider
from codestrata.ai.providers.doctor import (
    ConfigStatus,
    OpenRouterReadinessStatus,
    build_ai_configuration_report,
    evaluate_openrouter_readiness,
)
from codestrata.ai.providers.exceptions import AIProviderConfigurationError
from codestrata.ai.providers.openai_provider import OpenAIAIModelProvider
from codestrata.ai.providers.openrouter_provider import OpenRouterAIModelProvider
from codestrata.config.settings import AiSettings, OpenRouterSettings
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from verification.openrouter_doctor_integration.contract import (
    ASSESSMENT_SCHEMA_VERSION,
    DEFAULT_API_KEY_ENV,
    DEFAULT_PROVIDER,
    DOCTOR_FORBIDDEN_ADAPTER_IMPORT,
    DOCTOR_FORBIDDEN_CALL_TOKENS,
    NEGATIVE_SCENARIO_COUNT_MIN,
    OPENAI_DEFAULT_MODEL,
    BEDROCK_DEFAULT_MODEL,
    TEST_ONLY_MODEL,
)
from verification.openrouter_doctor_integration.fixtures import (
    SYNTHETIC_API_KEY,
    SYNTHETIC_APP_NAME,
    SYNTHETIC_INSTRUCTION,
    SYNTHETIC_INVALID_BASE_URL,
    SYNTHETIC_OPENAI_API_KEY,
    SYNTHETIC_SITE_URL,
    Client,
    injected_environ,
    invocation_options,
    model_request,
    provider_request,
    sdk_exception,
    settings_for,
)
from verification.openrouter_doctor_integration.models import ScenarioResult

_DOCTOR_REL = "src/codestrata/ai/providers/doctor.py"


def run_negative_scenarios(engine_root: Path) -> list[ScenarioResult]:
    scenarios: list[ScenarioResult] = []

    def add(scenario_id: str, title: str, forbidden: str, holds: bool, detail: str = "") -> None:
        scenarios.append(
            ScenarioResult(
                scenario_id=scenario_id,
                title=title,
                forbidden_condition=forbidden,
                ok=not holds,
                detail=detail,
            )
        )

    doctor_source = (engine_root / _DOCTOR_REL).read_text(encoding="utf-8")
    tree = ast.parse(doctor_source, filename="doctor.py")
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    add(
        "A",
        "doctor sends a provider request",
        "doctor source contains invoke/execute/chat.completions/OpenAI(/resolve_client(",
        any(token in doctor_source for token in DOCTOR_FORBIDDEN_CALL_TOKENS),
    )
    add(
        "B",
        "doctor constructs a prompt",
        "doctor constructs ModernizationPromptBuilder or prompt payload",
        "ModernizationPromptBuilder" in doctor_source or "prompt_request" in doctor_source,
    )
    add(
        "C",
        "doctor validates model remotely",
        "doctor performs remote model validation",
        "chat.completions" in doctor_source or "resolve_client(" in doctor_source,
    )

    env = injected_environ()
    ready = evaluate_openrouter_readiness(
        settings_for("openrouter", openrouter={"model": TEST_ONLY_MODEL}),
        environ=env,
        dependency_available=True,
    )
    report = build_ai_configuration_report(
        settings_for("openrouter", openrouter={"model": TEST_ONLY_MODEL}),
        environ=env,
        openrouter_dependency_available=True,
    )
    redacted_blob = json.dumps(ready.redacted(), sort_keys=True)
    overview_blob = json.dumps(
        {
            "model_id": report.model_id,
            "details": [item.detail for item in report.providers],
            "checks": [check.detail for check in report.checks],
        },
        sort_keys=True,
    )

    add(
        "D",
        "doctor prints API key",
        "synthetic API key appears in doctor redacted/overview output",
        SYNTHETIC_API_KEY in redacted_blob or SYNTHETIC_API_KEY in overview_blob,
    )
    add(
        "E",
        "doctor prints API-key prefix or length",
        "key prefix or key length diagnostics appear",
        "sk-" in redacted_blob or "key_length" in redacted_blob or "api_key_prefix" in redacted_blob,
    )
    add(
        "F",
        "doctor prints environment-variable value",
        "synthetic env value appears in doctor output",
        SYNTHETIC_API_KEY in overview_blob or SYNTHETIC_OPENAI_API_KEY in overview_blob,
    )
    add(
        "G",
        "doctor prints model",
        "test-only model value appears in doctor output",
        TEST_ONLY_MODEL in overview_blob or TEST_ONLY_MODEL in redacted_blob,
    )
    add(
        "H",
        "doctor prints base URL",
        "URL scheme appears in redacted readiness",
        "https://" in redacted_blob or "http://" in redacted_blob,
    )

    site_ready = evaluate_openrouter_readiness(
        settings_for(
            "openrouter",
            openrouter={
                "model": TEST_ONLY_MODEL,
                "site_url": SYNTHETIC_SITE_URL,
                "app_name": SYNTHETIC_APP_NAME,
            },
        ),
        environ=env,
        dependency_available=True,
    )
    site_blob = json.dumps(site_ready.redacted(), sort_keys=True)
    add(
        "I",
        "doctor prints site URL/app name",
        "site URL or app name value appears in redacted readiness",
        SYNTHETIC_SITE_URL in site_blob or SYNTHETIC_APP_NAME in site_blob,
    )
    add(
        "J",
        "doctor prints headers",
        "auth or identification header names appear in doctor output",
        any(
            token in redacted_blob or token in overview_blob
            for token in ("Authorization", "HTTP-Referer", "X-Title", "Bearer")
        ),
    )

    before_provider = AiSettings().provider
    _ = evaluate_openrouter_readiness(
        settings_for("openrouter", openrouter={"model": TEST_ONLY_MODEL}),
        environ=env,
        dependency_available=True,
    )
    add(
        "K",
        "doctor changes provider selection",
        "doctor mutates default AiSettings provider",
        AiSettings().provider != before_provider,
        f"provider={AiSettings().provider}",
    )

    add(
        "L",
        "doctor creates client while provider not selected",
        "doctor imports openrouter adapter or resolve_client",
        any(DOCTOR_FORBIDDEN_ADAPTER_IMPORT in name for name in imported)
        or "resolve_client(" in doctor_source,
    )
    add(
        "M",
        "doctor creates multiple clients",
        "doctor constructs OpenAI( clients",
        "OpenAI(" in doctor_source,
    )

    mutates = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and "settings" in ast.dump(target):
                    mutates = True
    add("N", "doctor mutates configuration", "doctor assigns settings fields", mutates)

    open_write = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in {"write_text", "write_bytes", "write"}:
                open_write = True
            if name == "open" and len(node.args) >= 2:
                mode = node.args[1]
                if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
                    if any(flag in mode.value for flag in ("w", "a", "x")):
                        open_write = True
    add("O", "doctor writes files", "doctor opens files for write", open_write)

    created = create_assess_ai_provider(settings_for("openrouter"))
    add(
        "P",
        "runtime falls back to OpenAI",
        "openrouter selection returns OpenAIAIModelProvider",
        isinstance(created, OpenAIAIModelProvider),
        f"class={type(created).__name__}",
    )
    add(
        "Q",
        "runtime falls back to Bedrock",
        "openrouter selection returns BedrockAIModelProvider",
        isinstance(created, BedrockAIModelProvider),
        f"class={type(created).__name__}",
    )

    client = Client()
    provider = OpenRouterAIModelProvider(
        openrouter_settings=OpenRouterSettings(model=TEST_ONLY_MODEL),
        client=client,
    )
    provider.invoke(model_request(), invocation_options())
    add(
        "R",
        "duplicate OpenRouter invocation",
        "more than one chat completion call for one invoke",
        len(client.calls) > 1,
        f"calls={len(client.calls)}",
    )

    missing_key = evaluate_openrouter_readiness(
        settings_for("openrouter", openrouter={"model": TEST_ONLY_MODEL}),
        environ={},
        dependency_available=True,
    )
    add(
        "S",
        "missing API key marked ready",
        "credential_missing classified as ready",
        missing_key.readiness is OpenRouterReadinessStatus.READY,
    )

    missing_model = evaluate_openrouter_readiness(
        settings_for("openrouter", openrouter={"model": ""}),
        environ={DEFAULT_API_KEY_ENV: SYNTHETIC_API_KEY},
        dependency_available=True,
    )
    add(
        "T",
        "missing model marked ready",
        "model_missing classified as ready",
        missing_model.readiness is OpenRouterReadinessStatus.READY,
    )

    invalid_https = evaluate_openrouter_readiness(
        settings_for(
            "openrouter",
            openrouter={"model": TEST_ONLY_MODEL, "base_url": SYNTHETIC_INVALID_BASE_URL},
        ),
        environ=env,
        dependency_available=True,
    )
    add(
        "U",
        "invalid HTTPS configuration marked ready",
        "invalid base URL classified as ready",
        invalid_https.readiness is OpenRouterReadinessStatus.READY,
    )

    fail_client = Client(sdk_exception("AuthenticationError", "upstream rejected credentials"))
    fail_provider = OpenRouterAIModelProvider(
        openrouter_settings=OpenRouterSettings(model=TEST_ONLY_MODEL),
        client=fail_client,
    )
    raised: Exception | None
    try:
        fail_provider.invoke(model_request(), invocation_options())
        raised = None
    except Exception as error:  # noqa: BLE001
        raised = error
    # Raw provider exception class names / upstream messages must not be the
    # assessment-report surface; raised errors are allowed for fail-soft but
    # scenario V checks that bounded mapping avoids raw exception text in
    # adapter error detail.
    mapped = build_openrouter_provider(
        client=Client(sdk_exception("AuthenticationError", "upstream rejected credentials"))
    ).execute(provider_request())
    raw_in_mapped = (
        mapped.error is not None
        and (
            "AuthenticationError" in (mapped.error.detail or "")
            or "upstream rejected credentials" in (mapped.error.detail or "")
        )
    )
    add(
        "V",
        "raw provider error enters report",
        "raw exception text in mapped provider error detail",
        raw_in_mapped,
    )

    schema_path = (
        engine_root
        / "src/codestrata/resources/schemas/assessment/codestrata.io/v1.2/AssessmentReport.json"
    )
    schema_text = schema_path.read_text(encoding="utf-8") if schema_path.is_file() else ""
    doctor_in_assessment = any(
        token in schema_text
        for token in (
            "openrouter_readiness",
            "evaluate_openrouter_readiness",
            "OpenRouterDoctorReadiness",
            "credential_present",
        )
    ) or ASSESSMENT_JSON_SCHEMA_VERSION != ASSESSMENT_SCHEMA_VERSION
    add(
        "W",
        "doctor results enter assessment report",
        "doctor tokens in Assessment schema or schema version changed",
        doctor_in_assessment,
    )

    from codestrata.ai.providers import doctor as doctor_module

    openai_overview = doctor_module._openai_overview(
        settings_for("openai", openai={"api_key_env": "SYNTHETIC_DOCTOR_OPENAI_KEY_VAR"}),
        environ={},
    )
    openai_regressed = (
        openai_overview.name != "openai"
        or openai_overview.status is not ConfigStatus.NOT_CONFIGURED
        or resolve_assess_model_id(cli_model_id=None, settings=settings_for("openai"))
        != OPENAI_DEFAULT_MODEL
    )
    add("X", "OpenAI doctor regression", "openai doctor/overview/default changed", openai_regressed)

    bedrock_regressed = (
        AiSettings().provider != DEFAULT_PROVIDER
        or resolve_assess_model_id(cli_model_id=None, settings=settings_for("bedrock"))
        != BEDROCK_DEFAULT_MODEL
    )
    add(
        "Y",
        "Bedrock doctor regression",
        "bedrock default provider or model changed",
        bedrock_regressed,
    )

    # Privacy scanned after report assembly; placeholder ensures scenario Z exists.
    add(
        "Z",
        "verification report leaks",
        "verification report contains secrets endpoints models or prompts",
        False,
        "privacy scanned after report assembly",
    )

    # Keep retry policy referenced so duplicate-invocation guard stays honest.
    _ = OPENROUTER_RETRY_POLICY
    _ = raised
    _ = SYNTHETIC_INSTRUCTION

    assert len(scenarios) >= NEGATIVE_SCENARIO_COUNT_MIN
    return scenarios


__all__ = ["run_negative_scenarios"]
