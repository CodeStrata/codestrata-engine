"""Characterize the reporting-layer AI execution/status integration (read-only).

Exercises ``build_ai_execution_document`` with synthetic, no-network inputs to
confirm the failure-path document shape is stable, and confirms the
``AIExecutionStatus`` enum / label mapping used across reports is complete.
"""

from __future__ import annotations

from pathlib import Path

from codestrata.reporting.ai_execution import build_ai_execution_document
from codestrata.reporting.ai_status import ai_execution_status_label
from codestrata.reporting.modernization_models import AIExecutionStatus
from verification.ai_provider_baseline.models import CheckResult

_ALL_STATUSES: tuple[AIExecutionStatus, ...] = (
    AIExecutionStatus.NOT_REQUESTED,
    AIExecutionStatus.SUCCEEDED,
    AIExecutionStatus.AUTHENTICATION_FAILED,
    AIExecutionStatus.PROVIDER_FAILED,
    AIExecutionStatus.PARSING_FAILED,
    AIExecutionStatus.VALIDATION_FAILED,
)


def check_all_statuses_have_display_labels(_source_root: Path) -> CheckResult:
    labels = {status.value: ai_execution_status_label(status) for status in _ALL_STATUSES}
    ok = all(labels.values())
    return CheckResult(
        name="every_ai_execution_status_has_a_display_label",
        category="reporting_integration",
        ok=ok,
        detail=f"labels={labels}",
        evidence={"labels": labels},
    )


def build_failure_execution_document() -> dict[str, object]:
    return build_ai_execution_document(
        status=AIExecutionStatus.PROVIDER_FAILED,
        attempt=None,
        failure_message="fixture: AI provider invocation failed (mocked, no network)",
        failure_detail="fixture detail",
        failure_stage="provider_invoked",
    )


def check_failure_execution_document_shape(_source_root: Path) -> CheckResult:
    document = build_failure_execution_document()
    failure_block = document.get("failure") or {}
    ok = (
        document.get("execution_status") == AIExecutionStatus.PROVIDER_FAILED.value
        and isinstance(failure_block, dict)
        and "message" in failure_block
    )
    return CheckResult(
        name="failure_execution_document_has_stable_shape",
        category="reporting_integration",
        ok=ok,
        detail=(
            f"execution_status={document.get('execution_status')} keys={sorted(document.keys())}"
        ),
    )


def check_execution_document_omits_credential_fragments(_source_root: Path) -> CheckResult:
    document = build_failure_execution_document()
    flat_keys = _flatten_keys(document)
    fragments = (
        "credential",
        "secret",
        "password",
        "authorization",
        "access_key",
        "session_token",
        "api_token",
    )
    hit = [k for k in flat_keys if any(fragment in k.lower() for fragment in fragments)]
    return CheckResult(
        name="execution_document_keys_contain_no_credential_fragments",
        category="reporting_integration",
        ok=not hit,
        detail=f"offending_keys={hit}",
    )


def _flatten_keys(value: object, prefix: str = "") -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            keys.append(path)
            keys.extend(_flatten_keys(nested, path))
    elif isinstance(value, list):
        for item in value:
            keys.extend(_flatten_keys(item, prefix))
    return keys


def run_reporting_integration_checks(
    source_root: Path,
) -> tuple[list[CheckResult], dict[str, object]]:
    checks = [
        check_all_statuses_have_display_labels(source_root),
        check_failure_execution_document_shape(source_root),
        check_execution_document_omits_credential_fragments(source_root),
    ]
    matrix = {
        "ai_execution_status_labels": {
            status.value: ai_execution_status_label(status) for status in _ALL_STATUSES
        }
    }
    return checks, matrix


__all__ = [
    "build_failure_execution_document",
    "check_all_statuses_have_display_labels",
    "check_execution_document_omits_credential_fragments",
    "check_failure_execution_document_shape",
    "run_reporting_integration_checks",
]
