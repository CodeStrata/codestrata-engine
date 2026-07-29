"""Application-layer errors for the Shared Rule Platform."""

from __future__ import annotations


class RuleApplicationError(Exception):
    def __init__(
        self,
        message: str,
        *,
        reason_code: str,
        rule_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.rule_id = rule_id
        self.safe_message = message


class RuleRegistryError(RuleApplicationError):
    pass


class RulePlanningError(RuleApplicationError):
    pass


class RuleExecutionError(RuleApplicationError):
    pass


class RuleNotFoundError(RuleApplicationError):
    pass
