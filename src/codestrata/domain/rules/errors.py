"""Typed errors for the Shared Rule Platform domain."""

from __future__ import annotations


class RuleDomainError(Exception):
    """Base domain error with a stable reason code."""

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


class RuleIdentityError(RuleDomainError):
    pass


class RuleMetadataError(RuleDomainError):
    pass


class RuleEvidenceError(RuleDomainError):
    pass


class RuleResultValidationError(RuleDomainError):
    pass
