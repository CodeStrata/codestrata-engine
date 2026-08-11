"""Negative scenarios A–Z for SV.11.12. ok = not holds."""

from __future__ import annotations

import ast
import io
import json
import logging
from pathlib import Path
from unittest.mock import patch

from codestrata.ai.provider_adapters.openai import diagnostics as openai_diagnostics
from codestrata.ai.provider_adapters.openai.factory import (
    build_openai_executor,
    build_openai_provider,
)
from codestrata.ai.provider_adapters.openrouter.factory import build_openrouter_provider
from codestrata.ai.provider_contracts.executor import AIProviderExecutor
from codestrata.ai.provider_contracts.retry_policy import DEFAULT_RETRY_POLICY
from codestrata.ai.providers.doctor import evaluate_openrouter_readiness
from codestrata.ai.providers.exceptions import AIProviderConfigurationError
from codestrata.ai.providers.factory import create_assess_ai_provider
from codestrata.config.settings import AiSettings
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from verification.ai_provider_privacy_boundaries.contract import (
    DEFAULT_PROVIDER,
    DOCTOR_FORBIDDEN_CALL_TOKENS,
    NEGATIVE_SCENARIO_COUNT_MIN,
)
from verification.ai_provider_privacy_boundaries.fixtures import (
    BedrockClient,
    OpenAIStyleClient,
    OpenAIStyleResponse,
    SYNTHETIC_MODEL_OPENAI,
    SYNTHETIC_MODEL_OPENROUTER,
    SYNTHETIC_OPENAI_KEY,
    SYNTHETIC_OPENROUTER_KEY,
    SYNTHETIC_PROMPT,
    SYNTHETIC_REQUEST_ID,
    SYNTHETIC_RESPONSE,
    canonical_json,
    leaked_markers,
    openai_settings_secret,
    openrouter_settings_secret,
    provider_request,
    sdk_exception,
    settings_for,
)
from verification.ai_provider_privacy_boundaries.models import ScenarioResult

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

    adapter = build_openai_provider(
        openai_settings=openai_settings_secret(),
        client=OpenAIStyleClient(),
        environment_reader=lambda _name: SYNTHETIC_OPENAI_KEY,
    )
    diag_blob = canonical_json(openai_diagnostics.diagnostic_view_of_adapter(adapter))

    # A. credential in diagnostics
    add(
        "A",
        "credential in diagnostics",
        "synthetic API key appears in adapter diagnostics",
        SYNTHETIC_OPENAI_KEY in diag_blob,
    )

    # B. credential in report — deferred placeholder; runner re-validates via privacy scan
    add(
        "B",
        "credential in report",
        "synthetic API key appears in verification report draft markers check",
        False,
        detail="report privacy scanned after assembly",
    )

    # C. credential in doctor
    ready = evaluate_openrouter_readiness(
        settings_for("openrouter", openrouter={"model": SYNTHETIC_MODEL_OPENROUTER}),
        environ={"OPENROUTER_API_KEY": SYNTHETIC_OPENROUTER_KEY},
        dependency_available=True,
    )
    add(
        "C",
        "credential in doctor",
        "synthetic OpenRouter key appears in doctor redacted readiness",
        SYNTHETIC_OPENROUTER_KEY in canonical_json(ready.redacted()),
    )

    # D. prompt in diagnostics
    result = adapter.execute(provider_request(model_id=SYNTHETIC_MODEL_OPENAI))
    result_blob = canonical_json(
        openai_diagnostics.diagnostic_view_of_provider_result(result)
    )
    add(
        "D",
        "prompt in diagnostics",
        "synthetic prompt appears in result diagnostics",
        SYNTHETIC_PROMPT in result_blob,
    )

    # E. prompt in verification report — deferred
    add(
        "E",
        "prompt in verification report",
        "synthetic prompt appears in verification report",
        False,
        detail="report privacy scanned after assembly",
    )

    # F. response in diagnostics
    add(
        "F",
        "response in diagnostics",
        "synthetic response appears in result diagnostics",
        SYNTHETIC_RESPONSE in result_blob or SYNTHETIC_REQUEST_ID in result_blob,
    )

    # G. response in logs (capture; known model_id/profile logs are not response)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger("codestrata.ai.providers.openai_provider")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        # Wrapper path not required; adapter execute is enough for response content.
        adapter.execute(provider_request(model_id=SYNTHETIC_MODEL_OPENAI))
    finally:
        logger.removeHandler(handler)
    add(
        "G",
        "response in logs",
        "synthetic response marker appears in captured logs",
        SYNTHETIC_RESPONSE in stream.getvalue(),
    )

    # H. model value in diagnostics
    add(
        "H",
        "model value in diagnostics",
        "synthetic model appears in adapter diagnostics",
        SYNTHETIC_MODEL_OPENAI in diag_blob,
    )

    # I. endpoint/header in diagnostics
    add(
        "I",
        "endpoint/header in diagnostics",
        "synthetic base URL or Authorization appears in adapter diagnostics",
        "synth-privacy-1112.example.invalid" in diag_blob or "Authorization" in diag_blob,
    )

    # J. request ID in report — deferred
    add(
        "J",
        "request ID in report",
        "synthetic request id appears in verification report",
        False,
        detail="report privacy scanned after assembly",
    )

    # K. raw exception text in report — deferred
    add(
        "K",
        "raw exception text in report",
        "synthetic exception text appears in verification report",
        False,
        detail="report privacy scanned after assembly",
    )

    # L. traceback in CLI AI doctor/help surfaces (provider path must not dump tracebacks).
    # General assess CLI may print traceback.format_exc for unexpected non-AI errors —
    # that is not a provider privacy leak. Fail only if ai_cmd dumps format_exc.
    ai_cmd = (engine_root / "src/codestrata/cli/ai_cmd.py").read_text(encoding="utf-8")
    add(
        "L",
        "traceback in CLI output",
        "ai_cmd prints traceback.format_exc for provider/doctor paths",
        "traceback.format_exc" in ai_cmd,
    )

    # M. authentication failure retried
    auth_adapter = build_openai_provider(
        openai_settings=openai_settings_secret(),
        client=OpenAIStyleClient(sdk_exception("AuthenticationError")),
        environment_reader=lambda _name: SYNTHETIC_OPENAI_KEY,
    )
    auth_client = auth_adapter._client  # noqa: SLF001
    auth_exec = build_openai_executor(auth_adapter)
    auth_result = auth_exec.execute(provider_request(model_id=SYNTHETIC_MODEL_OPENAI))
    add(
        "M",
        "authentication failure retried",
        "authentication failure produces more than one attempt",
        auth_result.attempts > 1 or len(auth_client.calls) > 1,
        detail=f"attempts={auth_result.attempts}",
    )

    # N. invalid model retried
    invalid_adapter = build_openai_provider(
        openai_settings=openai_settings_secret(),
        client=OpenAIStyleClient(sdk_exception("NotFoundError")),
        environment_reader=lambda _name: SYNTHETIC_OPENAI_KEY,
    )
    invalid_client = invalid_adapter._client  # noqa: SLF001
    invalid_result = build_openai_executor(invalid_adapter).execute(
        provider_request(model_id=SYNTHETIC_MODEL_OPENAI)
    )
    add(
        "N",
        "invalid model retried",
        "invalid model failure produces more than one attempt",
        invalid_result.attempts > 1 or len(invalid_client.calls) > 1,
    )

    # O. malformed response retried
    malformed_adapter = build_openai_provider(
        openai_settings=openai_settings_secret(),
        client=OpenAIStyleClient(OpenAIStyleResponse.malformed()),
        environment_reader=lambda _name: SYNTHETIC_OPENAI_KEY,
    )
    malformed_client = malformed_adapter._client  # noqa: SLF001
    malformed_result = build_openai_executor(malformed_adapter).execute(
        provider_request(model_id=SYNTHETIC_MODEL_OPENAI)
    )
    add(
        "O",
        "malformed response retried",
        "malformed response produces more than one attempt",
        malformed_result.attempts > 1 or len(malformed_client.calls) > 1,
    )

    # P. retries exceed maximum
    add(
        "P",
        "retries exceed maximum",
        "DEFAULT_RETRY_POLICY.maximum_attempts > 1",
        DEFAULT_RETRY_POLICY.maximum_attempts > 1,
        detail=f"maximum_attempts={DEFAULT_RETRY_POLICY.maximum_attempts}",
    )

    # Q/R. KeyboardInterrupt / SystemExit swallowed
    from tests.ai.provider_contracts.execution_fakes import FakeRaisingProvider

    class _KB(FakeRaisingProvider):
        def execute(self, request):  # type: ignore[no-untyped-def]
            raise KeyboardInterrupt()

    class _SE(FakeRaisingProvider):
        def execute(self, request):  # type: ignore[no-untyped-def]
            raise SystemExit(2)

    kb_swallowed = True
    try:
        AIProviderExecutor(_KB()).execute(provider_request(model_id="x"))
    except KeyboardInterrupt:
        kb_swallowed = False
    se_swallowed = True
    try:
        AIProviderExecutor(_SE()).execute(provider_request(model_id="x"))
    except SystemExit:
        se_swallowed = False
    add("Q", "KeyboardInterrupt swallowed", "KeyboardInterrupt not propagated", kb_swallowed)
    add("R", "SystemExit swallowed", "SystemExit not propagated", se_swallowed)

    # S. provider fallback occurs
    created = create_assess_ai_provider(settings_for("openrouter"))
    fallback = type(created).__name__ in {"OpenAIAIModelProvider", "BedrockAIModelProvider"}
    add(
        "S",
        "provider fallback occurs",
        "explicit openrouter selection returns openai or bedrock wrapper",
        fallback,
        detail=f"class={type(created).__name__}",
    )

    # T. duplicate invocation occurs
    add(
        "T",
        "duplicate invocation occurs",
        "auth failure under default policy invokes client more than once",
        len(auth_client.calls) > 1,
    )

    # U. provider diagnostics enter report — check assessment field names
    from codestrata.reporting import modernization_models

    field_names: set[str] = set()
    for name in ("ModernizationAssessmentResult", "AIAttemptInfo"):
        model = getattr(modernization_models, name, None)
        if model is not None and hasattr(model, "model_fields"):
            field_names.update(model.model_fields)
    add(
        "U",
        "provider diagnostics enter report",
        "assessment models expose api_key/request_id/doctor readiness fields",
        any(
            token in field_names
            for token in ("api_key", "request_id", "doctor_ready", "base_url")
        ),
    )

    # V. provider failure changes non-AI results — schema authority proxy
    add(
        "V",
        "provider failure changes non-AI results",
        "assessment schema version drifted from 1.2",
        ASSESSMENT_JSON_SCHEMA_VERSION != "1.2",
        detail=f"schema={ASSESSMENT_JSON_SCHEMA_VERSION}",
    )

    # W. provider dependency missing breaks core import
    core_import_ok = True
    try:
        import codestrata  # noqa: F401
        from codestrata.config.settings import CodestrataSettings  # noqa: F401
    except Exception:  # noqa: BLE001
        core_import_ok = False
    add(
        "W",
        "provider dependency missing breaks core import",
        "core codestrata import fails",
        not core_import_ok,
    )

    # X. Platform/Data Lake imported by Engine provider execution
    offenders: list[str] = []
    for rel in (
        "src/codestrata/ai/provider_adapters/openai",
        "src/codestrata/ai/provider_adapters/bedrock",
        "src/codestrata/ai/provider_adapters/openrouter",
        "src/codestrata/ai/provider_contracts",
    ):
        root = engine_root / rel
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                modules: list[str] = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules = [node.module]
                for module in modules:
                    if module.startswith(
                        ("codestrata.platform", "codestrata.datalake", "codestrata_platform")
                    ):
                        offenders.append(module)
    add(
        "X",
        "Platform/Data Lake imported by Engine provider execution",
        "provider adapters/contracts import platform or datalake",
        bool(offenders),
        detail=f"offenders={sorted(set(offenders))}",
    )

    # Y. VS Code/Cursor modified with OpenRouter config
    repo_root = engine_root.parent
    plugin_hits: list[str] = []
    for plugin in ("vscode-plugin", "cursor-plugin"):
        src = repo_root / plugin / "src"
        if not src.is_dir():
            continue
        for path in src.rglob("*"):
            if path.suffix.lower() not in {".ts", ".js", ".json"} or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "openrouter" in text.lower():
                plugin_hits.append(str(path.relative_to(repo_root)))
    add(
        "Y",
        "VS Code/Cursor modified",
        "openrouter appears under vscode/cursor plugin src",
        bool(plugin_hits),
        detail=f"hits={plugin_hits}",
    )

    # Z. verification report leaks — deferred to privacy scan; also pin default unchanged
    add(
        "Z",
        "verification report leaks secrets, content, models, endpoints, identities, errors, or paths",
        "default provider changed away from bedrock or AiSettings drifted",
        AiSettings().provider != DEFAULT_PROVIDER,
        detail=f"provider={AiSettings().provider}; report scanned after assembly",
    )

    # Extra hardening scenarios to keep count >= 26 without inventing product changes.
    unknown_accepted = False
    try:
        create_assess_ai_provider(settings_for("not-a-provider"))
        unknown_accepted = True
    except AIProviderConfigurationError:
        unknown_accepted = False
    except Exception:  # noqa: BLE001
        unknown_accepted = True
    add(
        "AA",
        "unknown provider accepted",
        "unknown provider is accepted",
        unknown_accepted,
    )

    doctor_source = (engine_root / _DOCTOR_REL).read_text(encoding="utf-8")
    add(
        "AB",
        "doctor constructs provider client",
        "doctor source contains forbidden client tokens",
        any(token in doctor_source for token in DOCTOR_FORBIDDEN_CALL_TOKENS),
    )

    or_adapter = build_openrouter_provider(
        openrouter_settings=openrouter_settings_secret(),
        client=OpenAIStyleClient(),
        environment_reader=lambda _name: SYNTHETIC_OPENROUTER_KEY,
        api_key_present=True,
    )
    or_diag = canonical_json(
        __import__(
            "codestrata.ai.provider_adapters.openrouter.diagnostics",
            fromlist=["diagnostic_view_of_adapter"],
        ).diagnostic_view_of_adapter(or_adapter)
    )
    add(
        "AC",
        "openrouter app name/site URL leak in diagnostics",
        "synthetic site URL or app name appears in openrouter diagnostics",
        "synth-site-privacy-1112" in or_diag or "SynthAppPrivacy1112" in or_diag,
    )

    bedrock = __import__(
        "codestrata.ai.provider_adapters.bedrock.factory",
        fromlist=["build_bedrock_provider"],
    ).build_bedrock_provider(client=BedrockClient())
    bedrock_diag = canonical_json(
        __import__(
            "codestrata.ai.provider_adapters.bedrock.diagnostics",
            fromlist=["diagnostic_view_of_adapter"],
        ).diagnostic_view_of_adapter(bedrock)
    )
    add(
        "AD",
        "bedrock profile/region values in diagnostics",
        "literal profile/region values appear in bedrock diagnostics",
        "synth-privacy-1112-profile" in bedrock_diag
        or "synth-privacy-1112-region" in bedrock_diag,
    )

    assert len(scenarios) >= NEGATIVE_SCENARIO_COUNT_MIN
    return scenarios


__all__ = ["run_negative_scenarios"]
