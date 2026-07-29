"""CLI mapping helpers for incremental commands."""

from __future__ import annotations

import json
from typing import Any

from codestrata.application.incremental.errors import (
    IncrementalConfigurationError,
    IncrementalExecutionError,
    IncrementalExecutionRecordNotFoundError,
    IncrementalPlanningError,
    IncrementalRolloutDisabledError,
    IncrementalValidationError,
)
from codestrata.application.incremental.execution_record import IncrementalExecutionRecord
from codestrata.application.incremental.models import IncrementalAssessmentPlan

EXIT_SUCCESS = 0
EXIT_BLOCKED = 1
EXIT_ERROR = 2


def plan_to_dict(plan: IncrementalAssessmentPlan) -> dict[str, Any]:
    return plan.model_dump(mode="json")


def record_to_dict(record: IncrementalExecutionRecord) -> dict[str, Any]:
    return record.model_dump(mode="json")


def dumps_json(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str)


def exit_code_for_record(record: IncrementalExecutionRecord) -> int:
    if not record.trusted:
        return EXIT_BLOCKED
    if record.status.value in {"failed", "blocked"}:
        return EXIT_BLOCKED
    return EXIT_SUCCESS


def exit_code_for_error(error: BaseException) -> int:
    if isinstance(error, IncrementalRolloutDisabledError):
        return EXIT_BLOCKED
    if isinstance(error, IncrementalExecutionRecordNotFoundError):
        return EXIT_BLOCKED
    if isinstance(error, IncrementalValidationError):
        return EXIT_BLOCKED
    if isinstance(error, IncrementalConfigurationError):
        return EXIT_ERROR
    if isinstance(error, IncrementalExecutionError):
        return EXIT_ERROR
    if isinstance(error, IncrementalPlanningError):
        return EXIT_ERROR
    return EXIT_ERROR
