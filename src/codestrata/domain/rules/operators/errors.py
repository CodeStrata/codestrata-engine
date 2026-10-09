"""Operator evaluation failures (E03.2). Domain code does not load YAML."""

from __future__ import annotations

from typing import Any

from codestrata.domain.rules.errors import RuleDomainError


class OperatorEvaluationError(RuleDomainError):
    """Invalid operator arguments or unsupported evaluation state."""

    def __init__(
        self,
        message: str,
        *,
        reason_code: str,
        operator: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, reason_code=reason_code)
        self.operator = operator
        self.details = dict(details or {})

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": "ERROR",
            "kind": "operator",
            "reason": self.reason_code,
            "message": self.safe_message,
        }
        if self.operator is not None:
            payload["operator"] = self.operator
        if self.details:
            payload["details"] = dict(self.details)
        return payload


class OperatorBudgetError(OperatorEvaluationError):
    """Hard per-operator cost limit exceeded. Not a false-negative absence proof."""

    def __init__(
        self,
        message: str,
        *,
        operator: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            reason_code="budget_exceeded",
            operator=operator,
            details=details,
        )
        payload_kind = "budget"
        self.kind = payload_kind

    def to_payload(self) -> dict[str, Any]:
        payload = super().to_payload()
        payload["kind"] = "budget"
        return payload
