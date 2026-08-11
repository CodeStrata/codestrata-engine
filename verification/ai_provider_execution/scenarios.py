"""Negative scenarios A-Z: checks that forbidden conditions do NOT hold."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from verification.ai_provider_execution.contract import EXPECTED_MODULES
from verification.ai_provider_execution.models import CheckResult, ScenarioResult


def _rejects(callable_under_test, *, name: str, category: str) -> CheckResult:
    """Run a zero-argument callable and record whether it raised the expected error."""

    from codestrata.ai.provider_contracts.errors import ProviderContractValidationError

    try:
        callable_under_test()
    except ProviderContractValidationError as error:
        return CheckResult(name=name, category=category, ok=True, detail=f"raised: {error}")
    return CheckResult(
        name=name,
        category=category,
        ok=False,
        detail="did not raise ProviderContractValidationError",
    )


def run_value_object_negative_checks() -> list[CheckResult]:
    """Exercise execution construction-time invariants directly."""

    from codestrata.ai.provider_contracts.backoff import BackoffPolicy
    from codestrata.ai.provider_contracts.errors import ErrorCategory
    from codestrata.ai.provider_contracts.retry_decision import RetryDecision, decide_retry
    from codestrata.ai.provider_contracts.retry_policy import (
        DEFAULT_RETRY_POLICY,
        AIProviderRetryPolicy,
    )
    from codestrata.ai.provider_contracts.timeout_policy import TimeoutPolicy

    category = "value_object_invariants"

    checks = [
        _rejects(
            lambda: TimeoutPolicy(timeout_seconds=0.0),
            name="timeout_policy_rejects_zero_timeout_seconds",
            category=category,
        ),
        _rejects(
            lambda: TimeoutPolicy(timeout_seconds=3601.0),
            name="timeout_policy_rejects_timeout_seconds_above_max",
            category=category,
        ),
        _rejects(
            lambda: TimeoutPolicy(timeout_seconds=float("nan")),
            name="timeout_policy_rejects_nan_timeout_seconds",
            category=category,
        ),
        _rejects(
            lambda: AIProviderRetryPolicy(maximum_attempts=0),
            name="retry_policy_rejects_zero_maximum_attempts",
            category=category,
        ),
        _rejects(
            lambda: AIProviderRetryPolicy(maximum_attempts=11),
            name="retry_policy_rejects_maximum_attempts_above_ceiling",
            category=category,
        ),
        _rejects(
            lambda: BackoffPolicy(base_delay_seconds=-1.0),
            name="backoff_policy_rejects_negative_base_delay_seconds",
            category=category,
        ),
        _rejects(
            lambda: BackoffPolicy(multiplier=0.0),
            name="backoff_policy_rejects_non_positive_multiplier",
            category=category,
        ),
        _rejects(
            lambda: RetryDecision(
                should_retry=True,
                next_attempt=2,
                delay_seconds=0.0,
                reason_code="x",
                terminal=True,
            ),
            name="retry_decision_rejects_should_retry_and_terminal_both_true",
            category=category,
        ),
        _rejects(
            lambda: RetryDecision(
                should_retry=False,
                next_attempt=1,
                delay_seconds=1.0,
                reason_code="x",
                terminal=True,
            ),
            name="retry_decision_rejects_nonzero_delay_when_not_retrying",
            category=category,
        ),
        _rejects(
            lambda: decide_retry(
                attempt=0,
                category=ErrorCategory.TIMEOUT,
                retry_policy=DEFAULT_RETRY_POLICY,
                backoff_policy=BackoffPolicy(),
            ),
            name="decide_retry_rejects_a_non_positive_attempt_number",
            category=category,
        ),
    ]

    def _executor_rejects_a_non_provider() -> None:
        from codestrata.ai.provider_contracts.executor import AIProviderExecutor

        AIProviderExecutor(object())  # type: ignore[arg-type]

    checks.append(
        _rejects(
            _executor_rejects_a_non_provider,
            name="executor_rejects_a_non_ai_provider_object",
            category=category,
        )
    )

    def _execution_result_rejects_mismatched_retry_count() -> None:
        from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
        from codestrata.ai.provider_contracts.execution_models import (
            AIProviderExecutionResult,
            ExecutionDiagnostics,
        )
        from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId

        AIProviderExecutionResult(
            provider_id=ProviderId.BEDROCK,
            capability=CapabilityId.MODERNIZATION_ADVISOR,
            status=ProviderExecutionStatus.SUCCESS,
            provider_result=None,
            attempts=1,
            retry_count=5,
            terminal_error_category=None,
            timeout_applied=False,
            usage=None,
            diagnostics=ExecutionDiagnostics(
                attempt_error_categories=(),
                timeout_policy_scope="provider_request",
                timeout_policy_seconds=60.0,
                retry_policy_maximum_attempts=1,
                backoff_strategy="none",
            ),
            limitations=("executor_not_wired",),
        )

    checks.append(
        _rejects(
            _execution_result_rejects_mismatched_retry_count,
            name="execution_result_rejects_a_retry_count_not_equal_to_attempts_minus_one",
            category=category,
        )
    )

    return checks


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


def _scenario_x_no_absolute_paths(report_payload_preview: dict[str, object]) -> ScenarioResult:
    from verification.ai_provider_execution.determinism import canonical_json

    text = canonical_json(report_payload_preview)
    hits = _find_matches(_ABSOLUTE_PATH_PATTERNS, text)
    return ScenarioResult(
        scenario_id="X",
        title="Execution verification report contains no absolute filesystem paths",
        forbidden_condition="report JSON contains an absolute macOS or Linux user-home path",
        ok=not hits,
        detail=f"hits={hits[:5]}" if hits else "no absolute-path patterns found",
    )


def _scenario_y_no_secrets_in_report(report_payload_preview: dict[str, object]) -> ScenarioResult:
    from verification.ai_provider_execution.determinism import canonical_json

    text = canonical_json(report_payload_preview)
    hits = _find_matches(_SECRET_PATTERNS, text)
    return ScenarioResult(
        scenario_id="Y",
        title="Execution verification report contains no secret-shaped tokens",
        forbidden_condition="report JSON contains a sk-/AKIA/Bearer-shaped token",
        ok=not hits,
        detail=f"hits={hits[:5]}" if hits else "no secret-shaped tokens found",
    )


def _scenario_z_no_process_invocation(package_dir: Path, verification_dir: Path) -> ScenarioResult:
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
        scenario_id="Z",
        title="Neither the execution package nor this verification package shells out",
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
            "Execution modules never import os/pathlib/subprocess/threading/asyncio/signal",
            "an execution_* module imports os, pathlib, subprocess, threading, asyncio, or signal",
            get(
                "execution_modules_never_import_os_pathlib_subprocess_threading_asyncio_or_signal"
            ),
        ),
        _scenario_from_check(
            "D",
            "provider_contracts has no codestrata dependency outside itself",
            "a provider_contracts module imports another codestrata.* package",
            get("provider_contracts_has_no_codestrata_dependencies_outside_itself"),
        ),
        _scenario_from_check(
            "E",
            "No product-path file imports provider_contracts",
            "assess factory/providers/enrichment/doctor/CLI imports provider_contracts",
            get("product_path_files_do_not_import_provider_contracts"),
        ),
        _scenario_from_check(
            "F",
            "The existing ai/providers/ directory has no new files from Slice 11.4",
            "ai/providers/ contains a file outside the Slice 11.1 baseline set",
            get("ai_providers_directory_has_no_new_files_from_slice_11_4"),
        ),
        _scenario_from_check(
            "G",
            "The Slice 11.1 baseline defines exactly CR-1..CR-6",
            "build_compatibility_requirements() returns a different requirement ID set",
            get("slice_11_1_baseline_defines_cr1_through_cr6"),
        ),
        _scenario_from_check(
            "H",
            "Every baseline compatibility requirement is covered by an execution statement",
            "a CR-1..CR-6 requirement has no matching ExecutionCompatibilityStatement",
            get("execution_compatibility_statements_cover_every_baseline_requirement"),
        ),
        _scenario_from_check(
            "I",
            "No execution compatibility statement reports holds=False",
            "an ExecutionCompatibilityStatement has holds=False",
            get("every_execution_compatibility_statement_holds_true"),
        ),
        _scenario_from_check(
            "J",
            "The default retry policy matches CR-1's exact-one-invoke behavior",
            "DEFAULT_RETRY_POLICY.maximum_attempts is not 1",
            get("default_retry_policy_maximum_attempts_is_one_matching_cr1"),
        ),
        _scenario_from_check(
            "K",
            "The settings-representable retry policy matches the real settings default",
            "SETTINGS_REPRESENTABLE_RETRY_POLICY does not represent max_retries=3 as "
            "maximum_attempts=4",
            get("settings_representable_retry_policy_matches_real_bedrock_and_openai_max_retries"),
        ),
        _scenario_from_check(
            "L",
            "DEFAULT_TIMEOUT_SECONDS matches the real providers default",
            "execution_policy.DEFAULT_TIMEOUT_SECONDS differs from the real 60.0 default",
            get("execution_policy_default_timeout_seconds_matches_real_providers_default"),
        ),
        _scenario_from_check(
            "M",
            "The retryable/non-retryable partition covers every ErrorCategory exactly once",
            "an ErrorCategory is missing from, or duplicated across, the partition",
            get("retryable_and_non_retryable_partition_covers_every_error_category_exactly_once"),
        ),
        _scenario_from_check(
            "N",
            "Authentication and authorization failures are never retryable by default",
            "authentication_failed or authorization_failed is retryable by default",
            get("authentication_and_authorization_failures_are_never_retryable_by_default"),
        ),
        _scenario_from_check(
            "O",
            "The provider_contracts package has exactly its expected module set",
            "a file is missing from, or unexpectedly added to, provider_contracts/",
            get("provider_contracts_package_has_exactly_expected_modules_after_slice_11_4"),
        ),
        _scenario_from_check(
            "P",
            "All eleven Slice 11.4 execution modules are present",
            "one of the eleven new execution_* modules is missing",
            get("all_eleven_slice_11_4_execution_modules_are_present"),
        ),
        _scenario_from_check(
            "Q",
            "The executor never raises for a FAILED provider result",
            "AIProviderExecutor.execute() raises for a FAILED AIProviderResult",
            get("executor_never_raises_for_a_failed_provider_result"),
        ),
        _scenario_from_check(
            "R",
            "The executor does not retry a non-retryable error category",
            "AIProviderExecutor retries after a non-retryable AIProviderError category",
            get("executor_does_not_retry_a_non_retryable_error_category"),
        ),
        _scenario_from_check(
            "S",
            "The executor stops retrying once maximum_attempts is reached",
            "AIProviderExecutor keeps retrying past retry_policy.maximum_attempts",
            get("executor_stops_retrying_once_maximum_attempts_is_reached"),
        ),
        _scenario_from_check(
            "T",
            "An unexpected exception from AIProvider.execute() never propagates unmodified",
            "AIProviderExecutor.execute() re-raises an unexpected Exception from the provider",
            get("executor_converts_an_unexpected_exception_into_an_internal_failure_result"),
        ),
        _scenario_from_check(
            "U",
            "KeyboardInterrupt is never swallowed by the executor",
            "AIProviderExecutor.execute() catches and suppresses KeyboardInterrupt",
            get("executor_does_not_swallow_keyboard_interrupt"),
        ),
        _scenario_from_check(
            "V",
            "A provider_id mismatch between the provider and its result is rejected",
            "AIProviderExecutor accepts a result whose provider_id differs from the provider's",
            get("executor_raises_provider_contract_validation_error_on_provider_id_mismatch"),
        ),
        _scenario_from_check(
            "W",
            "Diagnostic serialization never includes provider_result content",
            "serialize_execution_result_for_diagnostics() output contains response text/content",
            get("diagnostic_serialization_excludes_provider_result_content"),
        ),
        _scenario_x_no_absolute_paths(report_payload_preview),
        _scenario_y_no_secrets_in_report(report_payload_preview),
        _scenario_z_no_process_invocation(package_dir, verification_dir),
    ]
    return tuple(sorted(scenarios, key=lambda s: s.scenario_id))


__all__ = ["build_negative_scenarios", "run_value_object_negative_checks"]
