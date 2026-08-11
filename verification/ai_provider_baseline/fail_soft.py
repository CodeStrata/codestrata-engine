"""Characterize the fail-soft contract: AI failure keeps assess exit 0.

Combines a direct functional exercise of the reporting-layer status helpers
(``codestrata.reporting.ai_status``) with a structural check that
``application/assessment/service.py`` catches ``AssessmentCommandError`` from
the AI stage internally (appends a warning and continues) rather than
propagating it out of the pipeline.
"""

from __future__ import annotations

import ast
from pathlib import Path

from codestrata.reporting.ai_status import (
    customer_failure_message,
    failure_code_for_status,
    stages_for_status,
)
from codestrata.reporting.modernization_models import AIExecutionStatus
from verification.ai_provider_baseline.models import CheckResult

_FAILURE_STATUSES = (
    AIExecutionStatus.AUTHENTICATION_FAILED,
    AIExecutionStatus.PROVIDER_FAILED,
    AIExecutionStatus.PARSING_FAILED,
    AIExecutionStatus.VALIDATION_FAILED,
)


def build_fail_soft_matrix() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for status in (
        *_FAILURE_STATUSES,
        AIExecutionStatus.SUCCEEDED,
        AIExecutionStatus.NOT_REQUESTED,
    ):
        rows.append(
            {
                "customer_message_present": customer_failure_message(status) is not None,
                "failure_code": failure_code_for_status(status),
                "stage_count": len(stages_for_status(status)),
                "status": status.value,
            }
        )
    rows.sort(key=lambda item: str(item["status"]))
    return rows


def check_all_failure_statuses_have_customer_message(_source_root: Path) -> CheckResult:
    matrix = {item["status"]: item for item in build_fail_soft_matrix()}
    ok = all(matrix[status.value]["customer_message_present"] for status in _FAILURE_STATUSES)
    return CheckResult(
        name="every_ai_failure_status_has_a_customer_facing_message",
        category="fail_soft",
        ok=ok,
        detail="AUTHENTICATION_FAILED/PROVIDER_FAILED/PARSING_FAILED/VALIDATION_FAILED all mapped",
    )


def check_success_and_not_requested_have_no_failure_code(_source_root: Path) -> CheckResult:
    matrix = {item["status"]: item for item in build_fail_soft_matrix()}
    ok = (
        matrix[AIExecutionStatus.SUCCEEDED.value]["failure_code"] is None
        and matrix[AIExecutionStatus.NOT_REQUESTED.value]["failure_code"] is None
    )
    return CheckResult(
        name="succeeded_and_not_requested_statuses_have_no_failure_code",
        category="fail_soft",
        ok=ok,
        detail="failure_code_for_status(SUCCEEDED/NOT_REQUESTED) is None",
    )


def check_pipeline_catches_ai_stage_error_internally(source_root: Path) -> CheckResult:
    """Structural check: the AI stage's AssessmentCommandError is caught, not re-raised.

    Looks for a ``try/except AssessmentCommandError`` block whose body calls
    ``_run_ai_assessment`` and whose except handler does not re-raise (a bare
    ``raise`` statement), confirming the caller continues the pipeline and
    still writes reports.
    """

    source = (source_root / "application" / "assessment" / "service.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="application/assessment/service.py")

    found_non_reraising_handler = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        calls_ai_assessment = any(
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Name)
            and inner.func.id == "_run_ai_assessment"
            for inner in ast.walk(node)
        )
        if not calls_ai_assessment:
            continue
        for handler in node.handlers:
            handler_type_name = ast.unparse(handler.type) if handler.type else ""
            if "AssessmentCommandError" not in handler_type_name:
                continue
            has_bare_reraise = any(
                isinstance(stmt, ast.Raise) and stmt.exc is None for stmt in handler.body
            )
            if not has_bare_reraise:
                found_non_reraising_handler = True

    return CheckResult(
        name="ai_stage_assessment_command_error_caught_without_reraise",
        category="fail_soft",
        ok=found_non_reraising_handler,
        detail=(
            "application/assessment/service.py contains a try/except around "
            "_run_ai_assessment() whose AssessmentCommandError handler does not "
            "bare-reraise — the pipeline continues and still writes reports."
        ),
    )


def run_fail_soft_checks(source_root: Path) -> tuple[list[CheckResult], dict[str, object]]:
    checks = [
        check_all_failure_statuses_have_customer_message(source_root),
        check_success_and_not_requested_have_no_failure_code(source_root),
        check_pipeline_catches_ai_stage_error_internally(source_root),
    ]
    matrix = {"fail_soft_status_matrix": build_fail_soft_matrix()}
    return checks, matrix


__all__ = [
    "build_fail_soft_matrix",
    "check_all_failure_statuses_have_customer_message",
    "check_pipeline_catches_ai_stage_error_internally",
    "check_success_and_not_requested_have_no_failure_code",
    "run_fail_soft_checks",
]
