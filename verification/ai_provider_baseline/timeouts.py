"""Characterize timeout defaults and the settings-to-factory wiring gap.

Baseline finding (recorded, not fixed): ``[ai.bedrock].timeout_seconds`` and
``[ai.openai].timeout_seconds`` are declared in
``codestrata.config.settings`` but are never read by
``codestrata.extensions.assess_ai._bootstrap_assess_providers`` when building
the assess-time provider instances. Both providers always use the
provider-neutral ``DEFAULT_TIMEOUT_SECONDS`` (60.0) from
``codestrata.ai.providers.models`` regardless of the configured value.
"""

from __future__ import annotations

import ast
from pathlib import Path

from codestrata.ai.providers.bedrock import BedrockAIModelProvider
from codestrata.ai.providers.models import DEFAULT_TIMEOUT_SECONDS
from codestrata.ai.providers.openai_provider import OpenAIAIModelProvider
from verification.ai_provider_baseline.models import CheckResult


def _bootstrap_source(source_root: Path) -> str:
    return (source_root / "extensions" / "assess_ai.py").read_text(encoding="utf-8")


def check_default_timeout_is_60_seconds(_source_root: Path) -> CheckResult:
    ok = DEFAULT_TIMEOUT_SECONDS == 60.0
    return CheckResult(
        name="default_timeout_seconds_is_60",
        category="timeouts",
        ok=ok,
        detail=f"DEFAULT_TIMEOUT_SECONDS == {DEFAULT_TIMEOUT_SECONDS}",
    )


def check_provider_constructor_signatures_use_default(_source_root: Path) -> CheckResult:
    """Constructors take optional timeout_seconds; unset values resolve to DEFAULT_TIMEOUT_SECONDS."""

    import inspect

    from codestrata.ai.providers.settings_policies import provider_timeout_seconds

    bedrock_default = (
        inspect.signature(BedrockAIModelProvider.__init__).parameters["timeout_seconds"].default
    )
    openai_default = (
        inspect.signature(OpenAIAIModelProvider.__init__).parameters["timeout_seconds"].default
    )
    resolved_bedrock = provider_timeout_seconds(None, provider="bedrock")
    resolved_openai = provider_timeout_seconds(None, provider="openai")
    ok = (
        bedrock_default is None
        and openai_default is None
        and resolved_bedrock == DEFAULT_TIMEOUT_SECONDS
        and resolved_openai == DEFAULT_TIMEOUT_SECONDS
    )
    return CheckResult(
        name="provider_constructors_default_timeout_matches_shared_constant",
        category="timeouts",
        ok=ok,
        detail=(
            f"bedrock_default={bedrock_default} openai_default={openai_default} "
            f"resolved_bedrock={resolved_bedrock} resolved_openai={resolved_openai}"
        ),
    )


def check_bootstrap_does_not_pass_timeout_seconds(source_root: Path) -> CheckResult:
    """Structural check: assess_ai.py bootstrap factories never forward timeout_seconds."""

    source = _bootstrap_source(source_root)
    tree = ast.parse(source, filename="extensions/assess_ai.py")
    forwards_timeout = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"BedrockAIModelProvider", "OpenAIAIModelProvider"}:
                keyword_names = {kw.arg for kw in node.keywords if kw.arg}
                if "timeout_seconds" in keyword_names:
                    forwards_timeout = True
    ok = not forwards_timeout
    return CheckResult(
        name="assess_bootstrap_does_not_forward_settings_timeout_seconds",
        category="timeouts",
        ok=ok,
        detail=(
            "BedrockAIModelProvider(settings=settings) / "
            "OpenAIAIModelProvider(settings=settings) construction in "
            "extensions/assess_ai.py does not pass timeout_seconds="
            " — this is the recorded limitation, not a defect fixed here."
        ),
    )


def build_timeout_matrix() -> dict[str, object]:
    return {
        "assess_factory_reads_settings_timeout_seconds": False,
        "bedrock_settings_timeout_seconds_default": 60,
        "default_timeout_seconds_constant": DEFAULT_TIMEOUT_SECONDS,
        "openai_settings_timeout_seconds_default": 60,
    }


def run_timeout_checks(source_root: Path) -> tuple[list[CheckResult], dict[str, object]]:
    checks = [
        check_default_timeout_is_60_seconds(source_root),
        check_provider_constructor_signatures_use_default(source_root),
        check_bootstrap_does_not_pass_timeout_seconds(source_root),
    ]
    return checks, build_timeout_matrix()


__all__ = [
    "build_timeout_matrix",
    "check_bootstrap_does_not_pass_timeout_seconds",
    "check_default_timeout_is_60_seconds",
    "check_provider_constructor_signatures_use_default",
    "run_timeout_checks",
]
