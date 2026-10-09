"""Spawned worker for isolated YAML plan evaluation.

Must stay importable at module level so Windows spawn can target it.
"""

from __future__ import annotations

import time
from multiprocessing.queues import Queue
from typing import Any

from codestrata.application.rules.operators import (
    evaluate_condition,
    operator_limits_from_ratification,
)
from codestrata.domain.rules.compiler_models import ConditionPlan
from codestrata.domain.rules.operators.models import OperatorContext, OperatorLimits


def evaluate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    plan = ConditionPlan.model_validate(payload["plan"])
    limits = (
        OperatorLimits.model_validate(payload["limits"])
        if payload.get("limits")
        else operator_limits_from_ratification()
    )
    context = OperatorContext.model_validate({**payload["context"], "limits": limits.model_dump()})
    result = evaluate_condition(plan, context, limits=limits)
    return result.model_dump(mode="json")


def worker_main(payload: dict[str, Any], queue: Queue[dict[str, Any]]) -> None:
    try:
        result = evaluate_payload(payload)
        queue.put({"ok": True, "result": result})
    except Exception as error:  # noqa: BLE001 — isolate worker failures
        queue.put(
            {
                "ok": False,
                "reason": "worker_exception",
                "message": type(error).__name__,
            }
        )


def hang_forever() -> None:
    """Pathological native stand-in used only by watchdog proofs."""

    while True:
        time.sleep(0.05)


def hang_worker_main(_queue: Queue[dict[str, Any]]) -> None:
    hang_forever()
