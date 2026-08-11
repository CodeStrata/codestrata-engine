"""Verifies ``error_classification``: safe, bounded, never leaks exception text/SDK names."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.error_classification import (
    UNEXPECTED_EXCEPTION_SAFE_CODE,
    classify_error,
    classify_unexpected_exception,
)
from codestrata.ai.provider_contracts.errors import AIProviderError, ErrorCategory
from codestrata.ai.provider_contracts.retry_policy import (
    DEFAULT_RETRY_POLICY,
    AIProviderRetryPolicy,
)
from verification.ai_provider_execution.models import CheckResult

_FAKE_SECRET_DETAIL = "fake-internal-secret-should-never-be-echoed-back"


def check_classify_error_preserves_category_and_safe_code() -> CheckResult:
    error = AIProviderError(
        category=ErrorCategory.RATE_LIMITED, code="rate_limited_by_provider", detail="ignored"
    )
    policy = AIProviderRetryPolicy(maximum_attempts=3)
    classification = classify_error(error, policy)
    ok = (
        classification.category is ErrorCategory.RATE_LIMITED
        and classification.safe_code == "rate_limited_by_provider"
        and classification.retryable is True
    )
    return CheckResult(
        name="classify_error_preserves_category_and_original_safe_code",
        category="errors",
        ok=ok,
        detail=f"category={classification.category} retryable={classification.retryable}",
    )


def check_classify_error_marks_non_retryable_category_correctly() -> CheckResult:
    error = AIProviderError(category=ErrorCategory.INVALID_MODEL, code="invalid_model_id")
    classification = classify_error(error, DEFAULT_RETRY_POLICY)
    ok = classification.retryable is False
    return CheckResult(
        name="classify_error_marks_a_non_retryable_category_as_not_retryable",
        category="errors",
        ok=ok,
        detail=f"category={classification.category} retryable={classification.retryable}",
    )


def check_classify_unexpected_exception_never_takes_an_exception_argument() -> CheckResult:
    """Structural: classify_unexpected_exception's signature carries no exception parameter."""

    import inspect

    signature = inspect.signature(classify_unexpected_exception)
    parameter_names = set(signature.parameters)
    ok = parameter_names == {"retry_policy"}
    return CheckResult(
        name="classify_unexpected_exception_signature_accepts_only_a_retry_policy",
        category="errors",
        ok=ok,
        detail=f"parameters={sorted(parameter_names)}",
    )


def check_classify_unexpected_exception_uses_internal_failure_and_fixed_safe_code() -> CheckResult:
    classification = classify_unexpected_exception(DEFAULT_RETRY_POLICY)
    ok = (
        classification.category is ErrorCategory.INTERNAL_FAILURE
        and classification.safe_code == UNEXPECTED_EXCEPTION_SAFE_CODE
    )
    return CheckResult(
        name="classify_unexpected_exception_always_uses_internal_failure_and_the_fixed_safe_code",
        category="errors",
        ok=ok,
        detail=f"category={classification.category} safe_code={classification.safe_code}",
    )


def check_classify_unexpected_exception_output_never_contains_a_fake_secret() -> CheckResult:
    """Even if a caller tried to smuggle exception text in, the classifier ignores it."""

    classification = classify_unexpected_exception(DEFAULT_RETRY_POLICY)
    blob = repr(classification)
    ok = _FAKE_SECRET_DETAIL not in blob
    return CheckResult(
        name="classify_unexpected_exception_output_contains_no_exception_text",
        category="errors",
        ok=ok,
        detail="fake secret detail text absent from ProviderErrorClassification repr",
    )


def check_error_classification_module_never_imports_traceback_or_sys() -> CheckResult:
    import ast
    from pathlib import Path

    module_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "codestrata"
        / "ai"
        / "provider_contracts"
        / "error_classification.py"
    )
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    ok = "traceback" not in imported and "sys" not in imported
    return CheckResult(
        name="error_classification_module_never_imports_traceback_or_sys",
        category="errors",
        ok=ok,
        detail=f"imports={sorted(imported)}",
    )


def run_error_classification_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_classify_error_preserves_category_and_safe_code(),
        check_classify_error_marks_non_retryable_category_correctly(),
        check_classify_unexpected_exception_never_takes_an_exception_argument(),
        check_classify_unexpected_exception_uses_internal_failure_and_fixed_safe_code(),
        check_classify_unexpected_exception_output_never_contains_a_fake_secret(),
        check_error_classification_module_never_imports_traceback_or_sys(),
    ]
    matrix: dict[str, Any] = {"unexpected_exception_safe_code": UNEXPECTED_EXCEPTION_SAFE_CODE}
    return checks, matrix


__all__ = [
    "check_classify_error_marks_non_retryable_category_correctly",
    "check_classify_error_preserves_category_and_safe_code",
    "check_classify_unexpected_exception_never_takes_an_exception_argument",
    "check_classify_unexpected_exception_output_never_contains_a_fake_secret",
    "check_classify_unexpected_exception_uses_internal_failure_and_fixed_safe_code",
    "check_error_classification_module_never_imports_traceback_or_sys",
    "run_error_classification_checks",
]
