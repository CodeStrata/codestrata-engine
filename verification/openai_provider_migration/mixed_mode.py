"""Mixed mode: one registry serving both providers through one legacy seam.

Slice 11.6 introduced this category to prove that a migrated OpenAI and a
then-legacy Bedrock could coexist behind a single
``AssessAIProviderRegistry`` and a single ``AIModelProvider`` interface.
Slice 11.7 migrated Bedrock, so the "one of them is legacy" half of that
claim is now historical. The checks below keep the half that still matters
and that SV.11.6 is responsible for: **one registry, one seam, one default,
and no leakage of this slice's OpenAI work into the Bedrock module.** Whether
Bedrock's own migration is correct is SV.11.7's subject, not this suite's.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

from codestrata.ai.providers import bedrock as bedrock_module
from codestrata.ai.providers import openai_provider as openai_provider_module
from codestrata.ai.providers.factory import create_assess_ai_provider
from codestrata.config import CodestrataSettings
from verification.openai_provider_migration.contract import (
    BEDROCK_FORBIDDEN_TOKENS,
    BEDROCK_MODULE_RELATIVE_PATH,
    BEDROCK_REQUIRED_TOKENS,
    DEFAULT_PROVIDER,
    EXPECTED_REGISTERED_PROVIDERS,
    FORBIDDEN_PROVIDER_TOKENS,
)
from verification.openai_provider_migration.models import CheckResult

# The Bedrock module surface as it stood before this slice. Recorded by name so
# a removal or rename shows up as a mixed-mode regression.
_BEDROCK_EXPECTED_EXPORTS: tuple[str, ...] = (
    "BedrockAIModelProvider",
    "build_converse_request",
    "extract_converse_response",
    "split_prompt_for_converse",
)


def bedrock_provider_class() -> type:
    """Resolve the Bedrock class from the live module, not an import-time alias.

    A test elsewhere in the suite reloads ``ai/providers/bedrock.py`` to prove
    no AWS client is built at import time, which replaces the class object.
    Reading it through the module keeps these checks order-independent.
    """

    return bedrock_module.BedrockAIModelProvider


def openai_provider_class() -> type:
    return openai_provider_module.OpenAIAIModelProvider


def _is_instance_of(provider: Any, expected: type) -> bool:
    """Compare by qualified class name so a module reload cannot break identity."""

    actual = type(provider)
    return (actual.__module__, actual.__name__) == (expected.__module__, expected.__name__)


def _provider_for(provider_name: str) -> Any:
    settings = CodestrataSettings.model_validate(
        {"repository": {"path": "."}, "ai": {"provider": provider_name}}
    )
    return create_assess_ai_provider(settings)


def _bedrock_source(engine_root: Path) -> str:
    return (engine_root / "src" / "codestrata" / BEDROCK_MODULE_RELATIVE_PATH).read_text(
        encoding="utf-8"
    )


def check_both_providers_resolve_from_one_registry() -> CheckResult:
    openai_provider = _provider_for("openai")
    bedrock_provider = _provider_for("bedrock")
    ok = _is_instance_of(openai_provider, openai_provider_class()) and _is_instance_of(
        bedrock_provider, bedrock_provider_class()
    )
    return CheckResult(
        name="the_same_registry_resolves_both_the_openai_and_bedrock_providers",
        category="mixed_mode",
        ok=ok,
        detail=f"registered_providers={list(EXPECTED_REGISTERED_PROVIDERS)}",
    )


def check_bedrock_is_still_the_default() -> CheckResult:
    settings = CodestrataSettings.model_validate({"repository": {"path": "."}})
    provider = create_assess_ai_provider(settings)
    ok = settings.ai.provider == DEFAULT_PROVIDER and _is_instance_of(
        provider, bedrock_provider_class()
    )
    return CheckResult(
        name="an_unconfigured_run_still_selects_the_bedrock_provider",
        category="mixed_mode",
        ok=ok,
        detail=f"default_provider={settings.ai.provider}",
    )


def check_bedrock_still_exposes_its_public_surface(engine_root: Path) -> CheckResult:
    """The Bedrock module's importable surface survived both migrations."""

    source = _bedrock_source(engine_root)
    missing = sorted(token for token in BEDROCK_REQUIRED_TOKENS if token not in source)
    return CheckResult(
        name="bedrock_still_exposes_its_pre_migration_public_surface",
        category="mixed_mode",
        ok=not missing,
        detail=f"missing_surface_anchors={missing}",
        evidence={"required_tokens": list(BEDROCK_REQUIRED_TOKENS)},
    )


def check_bedrock_gained_no_openai_or_openrouter_reference(engine_root: Path) -> CheckResult:
    """Slice 11.6's OpenAI work never leaked into Bedrock, and OpenRouter is absent."""

    source = _bedrock_source(engine_root)
    offenders = sorted(token for token in BEDROCK_FORBIDDEN_TOKENS if token in source)
    return CheckResult(
        name="bedrock_gained_no_openai_adapter_or_openrouter_reference",
        category="mixed_mode",
        ok=not offenders,
        detail=f"unexpected_tokens={offenders}",
        evidence={"forbidden_tokens": list(BEDROCK_FORBIDDEN_TOKENS)},
    )


def check_bedrock_routes_through_its_own_adapter(engine_root: Path) -> CheckResult:
    """Bedrock reaches the contracts through its own adapter, never OpenAI's."""

    tree = ast.parse(_bedrock_source(engine_root), filename="bedrock.py")
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    from_openai_adapter = sorted(
        name
        for name in imported
        if name.startswith("codestrata.ai.provider_adapters.openai")
        or name.startswith("codestrata.ai.providers.openai_provider")
    )
    uses_own_adapter = any(
        name.startswith("codestrata.ai.provider_adapters.bedrock") for name in imported
    )
    return CheckResult(
        name="bedrock_routes_through_its_own_adapter_and_never_the_openai_one",
        category="mixed_mode",
        ok=not from_openai_adapter and uses_own_adapter,
        detail=(
            f"openai_imports={from_openai_adapter} "
            f"uses_bedrock_adapter={uses_own_adapter}"
        ),
    )


def check_the_bedrock_module_surface_is_unchanged() -> CheckResult:
    missing = sorted(
        name for name in _BEDROCK_EXPECTED_EXPORTS if not hasattr(bedrock_module, name)
    )
    return CheckResult(
        name="the_bedrock_module_still_exports_its_pre_migration_surface",
        category="mixed_mode",
        ok=not missing,
        detail=f"missing_exports={missing}",
        evidence={"expected_exports": list(_BEDROCK_EXPECTED_EXPORTS)},
    )


def check_the_bedrock_constructor_signature_is_unchanged() -> CheckResult:
    expected = ["self", "client", "region_name", "profile_name", "settings", "timeout_seconds"]
    actual = list(inspect.signature(bedrock_provider_class().__init__).parameters)
    return CheckResult(
        name="the_bedrock_provider_constructor_signature_is_unchanged",
        category="mixed_mode",
        ok=actual == expected,
        detail=f"parameters={actual}",
    )


def check_the_two_providers_share_the_legacy_interface() -> CheckResult:
    from codestrata.ai.providers.base import AIModelProvider

    ok = issubclass(openai_provider_class(), AIModelProvider) and issubclass(
        bedrock_provider_class(), AIModelProvider
    )
    return CheckResult(
        name="both_providers_still_present_the_same_legacy_ai_model_provider_interface",
        category="mixed_mode",
        ok=ok,
        detail="the mixed-mode seam is the legacy interface, not the contracts",
    )


def check_no_openrouter_reference_exists_under_the_ai_package(engine_root: Path) -> CheckResult:
    """OpenRouter may exist under adapter, contracts, wrapper, factory, and doctor readiness."""

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
    return CheckResult(
        name="no_module_under_the_ai_package_references_openrouter",
        category="mixed_mode",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def check_the_openai_adapter_package_exists_alongside_its_peers(
    engine_root: Path,
) -> CheckResult:
    """``provider_adapters`` hosts openai, bedrock, and optionally openrouter (unwired)."""

    adapters_root = engine_root / "src" / "codestrata" / "ai" / "provider_adapters"
    packages = sorted(
        path.name
        for path in adapters_root.iterdir()
        if path.is_dir() and (path / "__init__.py").is_file()
    )
    allowed = {"bedrock", "openai", "openrouter"}
    ok = set(packages) <= allowed and {"bedrock", "openai"}.issubset(packages)
    return CheckResult(
        name="the_openai_adapter_package_is_present_and_no_unexpected_provider_joined_it",
        category="mixed_mode",
        ok=ok,
        detail=f"adapter_packages={packages}",
    )


def run_mixed_mode_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_both_providers_resolve_from_one_registry(),
        check_bedrock_is_still_the_default(),
        check_bedrock_still_exposes_its_public_surface(engine_root),
        check_bedrock_gained_no_openai_or_openrouter_reference(engine_root),
        check_bedrock_routes_through_its_own_adapter(engine_root),
        check_the_bedrock_module_surface_is_unchanged(),
        check_the_bedrock_constructor_signature_is_unchanged(),
        check_the_two_providers_share_the_legacy_interface(),
        check_no_openrouter_reference_exists_under_the_ai_package(engine_root),
        check_the_openai_adapter_package_exists_alongside_its_peers(engine_root),
    ]
    matrix: dict[str, Any] = {
        "bedrock_expected_exports": list(_BEDROCK_EXPECTED_EXPORTS),
        "default_provider": DEFAULT_PROVIDER,
        "migrated_providers": ["bedrock", "openai"],
        "migrated_in_this_slice": ["openai"],
        "mixed_mode_state": "historical_bedrock_migrated_in_slice_11_7",
        "registered_providers": list(EXPECTED_REGISTERED_PROVIDERS),
    }
    return checks, matrix


__all__ = [
    "bedrock_provider_class",
    "check_bedrock_gained_no_openai_or_openrouter_reference",
    "check_bedrock_is_still_the_default",
    "check_bedrock_routes_through_its_own_adapter",
    "check_bedrock_still_exposes_its_public_surface",
    "check_both_providers_resolve_from_one_registry",
    "check_no_openrouter_reference_exists_under_the_ai_package",
    "check_the_bedrock_constructor_signature_is_unchanged",
    "check_the_bedrock_module_surface_is_unchanged",
    "check_the_openai_adapter_package_exists_alongside_its_peers",
    "check_the_two_providers_share_the_legacy_interface",
    "openai_provider_class",
    "run_mixed_mode_checks",
]
