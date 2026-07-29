"""Applicability and suppression models."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, field_validator

from codestrata.domain.graph.validation import optional_nonblank, require_nonblank
from codestrata.domain.rules.enums import (
    RuleApplicabilityStatus,
    RuleSkipReason,
    RuleSuppressionSource,
)
from codestrata.domain.rules.identifiers import RuleId, validate_rule_id


class RuleApplicability(BaseModel):
    """Result of evaluating whether a rule should run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: RuleApplicabilityStatus
    reason_code: RuleSkipReason | None = None
    message: str | None = None

    @classmethod
    def applicable(cls) -> RuleApplicability:
        return cls(status=RuleApplicabilityStatus.APPLICABLE)

    @classmethod
    def not_applicable(
        cls,
        *,
        reason_code: RuleSkipReason,
        message: str | None = None,
    ) -> RuleApplicability:
        return cls(
            status=RuleApplicabilityStatus.NOT_APPLICABLE,
            reason_code=reason_code,
            message=message,
        )

    @property
    def is_applicable(self) -> bool:
        return self.status is RuleApplicabilityStatus.APPLICABLE


class RuleSuppression(BaseModel):
    """Declared suppression; never silently deletes evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    suppression_id: str
    rule_id: RuleId
    repository_id: str | None = None
    path_pattern: str | None = None
    subject_reference: str | None = None
    reason: str
    expires_at: datetime | None = None
    source: RuleSuppressionSource = RuleSuppressionSource.MANUAL
    created_by_reference: str | None = None
    accepted_risk_reference: str | None = None

    @field_validator("suppression_id", "reason", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="suppression field")

    @field_validator("rule_id", mode="before")
    @classmethod
    def normalize_rule_id(cls, value: object) -> RuleId:
        if isinstance(value, RuleId):
            return value
        return RuleId(validate_rule_id(str(value)))

    @field_validator(
        "repository_id",
        "path_pattern",
        "subject_reference",
        "created_by_reference",
        "accepted_risk_reference",
        mode="before",
    )
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional suppression field")

    def is_active(self, *, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return True
        current = now or datetime.now(UTC)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return current <= expires


class RuleSuppressionDecision(BaseModel):
    """Record that a match was suppressed (match remains inspectable)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    suppressed: bool
    suppression: RuleSuppression | None = None
    reason: str | None = None
