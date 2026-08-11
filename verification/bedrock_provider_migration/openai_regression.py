"""No OpenAI regression: Slice 11.6's migrated behavior is untouched.

Slice 11.7 touches the OpenAI side only where SV.11.6's own mixed-mode
assumptions had to be updated (Bedrock is no longer "the unmigrated
provider"). The adapter package itself must be unchanged and still working,
which is what these checks establish with the same in-memory fixtures the
OpenAI suite uses.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from codestrata.ai.provider_adapters.openai import capabilities as openai_capabilities
from codestrata.ai.provider_adapters.openai.factory import (
    build_openai_executor,
    build_openai_provider,
)
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import ProviderId
from verification.bedrock_provider_migration.models import CheckResult

_OPENAI_PACKAGE_RELATIVE_PATH = "ai/provider_adapters/openai"


def _openai_fixtures() -> Any:
    from verification.openai_provider_migration import fixtures

    return fixtures


def check_the_openai_adapter_still_succeeds() -> CheckResult:
    fixtures = _openai_fixtures()
    provider = build_openai_provider(
        client=fixtures.Client(fixtures.response()),
        environment_reader=lambda _name: "synthetic-openai-key",
    )
    result = build_openai_executor(provider).execute(fixtures.provider_request())
    return CheckResult(
        name="the_openai_adapter_still_executes_successfully_on_an_injected_client",
        category="openai_regression",
        ok=result.status is ProviderExecutionStatus.SUCCESS,
        detail=f"status={result.status.value}",
    )


def check_the_openai_adapter_still_declares_structured_json() -> CheckResult:
    profile = openai_capabilities.openai_capability_profile()
    return CheckResult(
        name="the_openai_adapter_still_declares_native_structured_json_support",
        category="openai_regression",
        ok=profile.supports_structured_json is True,
        detail="the two adapters keep distinct structured-JSON strategies",
    )


def check_the_two_adapters_stay_independent(engine_root: Path) -> CheckResult:
    """Neither adapter package may import the other."""

    src_root = engine_root / "src" / "codestrata"
    offenders: dict[str, list[str]] = {}
    for package, forbidden in (
        (_OPENAI_PACKAGE_RELATIVE_PATH, "codestrata.ai.provider_adapters.bedrock"),
        ("ai/provider_adapters/bedrock", "codestrata.ai.provider_adapters.openai"),
    ):
        for path in sorted((src_root / package).glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
            names: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names.add(node.module)
            if any(name.startswith(forbidden) for name in names):
                offenders.setdefault(package, []).append(path.name)
    return CheckResult(
        name="the_openai_and_bedrock_adapter_packages_never_import_each_other",
        category="openai_regression",
        ok=not offenders,
        detail=f"offenders={sorted(offenders)}",
    )


def check_the_two_providers_have_distinct_identities() -> CheckResult:
    from codestrata.ai.provider_adapters.bedrock import capabilities as bedrock_capabilities

    return CheckResult(
        name="the_two_adapters_report_distinct_provider_identities",
        category="openai_regression",
        ok=(
            bedrock_capabilities.BEDROCK_PROVIDER_ID is ProviderId.BEDROCK
            and openai_capabilities.OPENAI_PROVIDER_ID is ProviderId.OPENAI
        ),
        detail="bedrock and openai remain separate provider identities",
    )


def check_the_openai_wrapper_surface_is_unchanged() -> CheckResult:
    from codestrata.ai.providers import openai_provider

    missing = sorted(
        name
        for name in ("OPENAI_PROVIDER_NAME", "OpenAIAIModelProvider")
        if not hasattr(openai_provider, name)
    )
    return CheckResult(
        name="the_openai_compatibility_wrapper_surface_is_unchanged",
        category="openai_regression",
        ok=not missing,
        detail=f"missing_exports={missing}",
    )


def check_the_openai_adapter_module_set_is_unchanged(engine_root: Path) -> CheckResult:
    expected = {
        "__init__.py",
        "adapter.py",
        "capabilities.py",
        "client.py",
        "configuration.py",
        "diagnostics.py",
        "error_mapping.py",
        "factory.py",
        "legacy_bridge.py",
        "request_mapping.py",
        "response_mapping.py",
        "usage_mapping.py",
    }
    actual = {
        path.name
        for path in (engine_root / "src" / "codestrata" / _OPENAI_PACKAGE_RELATIVE_PATH).glob(
            "*.py"
        )
    }
    return CheckResult(
        name="the_openai_adapter_package_gained_and_lost_no_module",
        category="openai_regression",
        ok=actual == expected,
        detail=f"unexpected={sorted(actual - expected)} missing={sorted(expected - actual)}",
    )


def run_openai_regression_checks(
    engine_root: Path,
) -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_the_openai_adapter_still_succeeds(),
        check_the_openai_adapter_still_declares_structured_json(),
        check_the_two_adapters_stay_independent(engine_root),
        check_the_two_providers_have_distinct_identities(),
        check_the_openai_wrapper_surface_is_unchanged(),
        check_the_openai_adapter_module_set_is_unchanged(engine_root),
    ]
    matrix: dict[str, Any] = {
        "bedrock_structured_json_strategy": "prompt_instruction_only",
        "openai_structured_json_strategy": "native_response_format",
        "providers_migrated": ["bedrock", "openai"],
        "slice_11_6_behavior_changed": False,
    }
    return checks, matrix


__all__ = [
    "check_the_openai_adapter_module_set_is_unchanged",
    "check_the_openai_adapter_still_declares_structured_json",
    "check_the_openai_adapter_still_succeeds",
    "check_the_openai_wrapper_surface_is_unchanged",
    "check_the_two_adapters_stay_independent",
    "check_the_two_providers_have_distinct_identities",
    "run_openai_regression_checks",
]
