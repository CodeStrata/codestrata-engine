"""Characterize retry behavior: ``retry_call`` exists but is unused by assess providers.

Baseline finding (recorded, not fixed): ``codestrata.ai.providers.common.retry_call``
is defined but neither ``bedrock.py`` nor ``openai_provider.py`` import or call
it. ``[ai.bedrock].max_retries`` / ``[ai.openai].max_retries`` are therefore not
wired into the assess invocation path — exactly one provider call is made per
assess run (see :mod:`verification.ai_provider_baseline.assessment_integration`).
"""

from __future__ import annotations

import ast
from pathlib import Path

from codestrata.ai.providers.common import retry_call
from verification.ai_provider_baseline.models import CheckResult


def _module_source(source_root: Path, relative_path: str) -> str:
    return (source_root / relative_path).read_text(encoding="utf-8")


def check_bootstrap_does_not_pass_max_retries(source_root: Path) -> CheckResult:
    """Structural check: assess_ai.py bootstrap factories never forward max_retries."""

    source = _module_source(source_root, "extensions/assess_ai.py")
    tree = ast.parse(source, filename="extensions/assess_ai.py")
    forwards_max_retries = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"BedrockAIModelProvider", "OpenAIAIModelProvider"}:
                keyword_names = {kw.arg for kw in node.keywords if kw.arg}
                if "max_retries" in keyword_names:
                    forwards_max_retries = True
    ok = not forwards_max_retries
    return CheckResult(
        name="assess_bootstrap_does_not_forward_settings_max_retries",
        category="retries",
        ok=ok,
        detail=(
            "BedrockAIModelProvider(settings=settings) / "
            "OpenAIAIModelProvider(settings=settings) construction in "
            "extensions/assess_ai.py does not pass max_retries="
            " — this is the recorded limitation, not a defect fixed here."
        ),
    )


def check_retry_call_defined_in_common(_source_root: Path) -> CheckResult:
    ok = callable(retry_call)
    return CheckResult(
        name="retry_call_defined_in_providers_common",
        category="retries",
        ok=ok,
        detail="codestrata.ai.providers.common.retry_call is defined and callable",
    )


def check_retry_call_unused_by_bedrock_provider(source_root: Path) -> CheckResult:
    source = _module_source(source_root, "ai/providers/bedrock.py")
    ok = "retry_call" not in source
    return CheckResult(
        name="bedrock_provider_does_not_reference_retry_call",
        category="retries",
        ok=ok,
        detail="'retry_call' token absent from ai/providers/bedrock.py",
    )


def check_retry_call_unused_by_openai_provider(source_root: Path) -> CheckResult:
    source = _module_source(source_root, "ai/providers/openai_provider.py")
    ok = "retry_call" not in source
    return CheckResult(
        name="openai_provider_does_not_reference_retry_call",
        category="retries",
        ok=ok,
        detail="'retry_call' token absent from ai/providers/openai_provider.py",
    )


def check_retry_call_behavior_is_isolated(_source_root: Path) -> CheckResult:
    """Exercise retry_call() directly to confirm it works standalone (unit-level),
    while remaining unreferenced by production assess providers."""

    attempts: list[int] = []

    def _flaky() -> str:
        attempts.append(1)
        if len(attempts) < 2:
            raise RuntimeError("throttled (simulated)")
        return "ok"

    result = retry_call(
        _flaky,
        max_retries=3,
        retry_on=(RuntimeError,),
        sleep=lambda _seconds: None,
    )
    ok = result == "ok" and len(attempts) == 2
    return CheckResult(
        name="retry_call_standalone_behavior_unaffected_by_nonuse",
        category="retries",
        ok=ok,
        detail=f"attempts={len(attempts)} result={result!r}",
    )


def build_retry_matrix() -> dict[str, object]:
    return {
        "assess_max_retries_wired_to_provider_invocation": False,
        "invoke_calls_per_assess_run": 1,
        "retry_call_referenced_by_bedrock_provider": False,
        "retry_call_referenced_by_openai_provider": False,
    }


def run_retry_checks(source_root: Path) -> tuple[list[CheckResult], dict[str, object]]:
    checks = [
        check_retry_call_defined_in_common(source_root),
        check_retry_call_unused_by_bedrock_provider(source_root),
        check_retry_call_unused_by_openai_provider(source_root),
        check_retry_call_behavior_is_isolated(source_root),
        check_bootstrap_does_not_pass_max_retries(source_root),
    ]
    return checks, build_retry_matrix()


__all__ = [
    "build_retry_matrix",
    "check_bootstrap_does_not_pass_max_retries",
    "check_retry_call_behavior_is_isolated",
    "check_retry_call_defined_in_common",
    "check_retry_call_unused_by_bedrock_provider",
    "check_retry_call_unused_by_openai_provider",
    "run_retry_checks",
]
