"""Result models for Shared Rule Platform evaluation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.rules.applicability import RuleSuppression
from codestrata.domain.rules.enums import (
    RuleConfidence,
    RuleResultStatus,
    RuleSeverity,
    RuleSkipReason,
)
from codestrata.domain.rules.errors import RuleResultValidationError
from codestrata.domain.rules.evidence import RuleEvidence, as_evidence_tuple, dedupe_evidence
from codestrata.domain.rules.identifiers import RuleId, validate_rule_id
from codestrata.domain.rules.metadata import RuleVersion


class RuleMatch(BaseModel):
    """One evidence-backed match produced by a shared rule."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: RuleId
    rule_version: RuleVersion
    severity: RuleSeverity
    confidence: RuleConfidence
    title: str
    summary: str
    evidence: tuple[RuleEvidence, ...]
    remediation: str | None = None
    affected_entities: tuple[str, ...] = ()
    provenance: str = "shared_rule_platform"
    subject_keys: tuple[str, ...] = ()

    @field_validator("rule_id", mode="before")
    @classmethod
    def normalize_rule_id(cls, value: object) -> RuleId:
        if isinstance(value, RuleId):
            return value
        return RuleId(validate_rule_id(str(value)))

    @field_validator("rule_version", mode="before")
    @classmethod
    def normalize_version(cls, value: object) -> RuleVersion | object:
        if isinstance(value, RuleVersion):
            return value
        if isinstance(value, str):
            return RuleVersion.parse(value)
        return value

    @field_validator("title", "summary", "provenance", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="match field")

    @field_validator("remediation", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="remediation")

    @field_validator("evidence", mode="before")
    @classmethod
    def normalize_evidence(cls, value: object) -> tuple[RuleEvidence, ...]:
        evidence = as_evidence_tuple(value)
        if not evidence:
            raise RuleResultValidationError(
                "matched results require at least one evidence item",
                reason_code="missing_evidence",
            )
        return evidence

    @field_validator("affected_entities", "subject_keys", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    require_nonblank(str(item), label="subject")
                    for item in as_tuple(value)
                }
            )
        )


class RuleDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    message: str
    rule_id: str | None = None

    @field_validator("code", "message", mode="before")
    @classmethod
    def normalize(cls, value: object) -> str:
        return require_nonblank(str(value), label="diagnostic field")


class SharedRuleEvaluationResult(BaseModel):
    """Outcome of evaluating one SharedRule."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: RuleResultStatus
    matches: tuple[RuleMatch, ...] = ()
    diagnostics: tuple[RuleDiagnostic, ...] = ()
    skip_reason: RuleSkipReason | None = None
    failure_message: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    suppression: RuleSuppression | None = None

    @field_validator("matches", "diagnostics", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @model_validator(mode="after")
    def validate_status_consistency(self) -> SharedRuleEvaluationResult:
        if self.status is RuleResultStatus.MATCHED and not self.matches:
            raise RuleResultValidationError(
                "matched status requires matches",
                reason_code="inconsistent_result",
            )
        if self.status is RuleResultStatus.NOT_MATCHED and self.matches:
            raise RuleResultValidationError(
                "not_matched status cannot include matches",
                reason_code="inconsistent_result",
            )
        if self.status is RuleResultStatus.FAILED and not self.failure_message:
            raise RuleResultValidationError(
                "failed status requires failure_message",
                reason_code="inconsistent_result",
            )
        if self.status is RuleResultStatus.SUPPRESSED and self.suppression is None:
            raise RuleResultValidationError(
                "suppressed status requires suppression record",
                reason_code="inconsistent_result",
            )
        # Normalize evidence ordering inside matches is already deterministic.
        _ = dedupe_evidence(tuple(ev for match in self.matches for ev in match.evidence))
        return self

    @classmethod
    def matched(
        cls,
        matches: tuple[RuleMatch, ...] | list[RuleMatch],
    ) -> SharedRuleEvaluationResult:
        ordered = tuple(
            sorted(
                matches,
                key=lambda item: (str(item.rule_id), item.title, item.summary),
            )
        )
        return cls(status=RuleResultStatus.MATCHED, matches=ordered)

    @classmethod
    def not_matched(cls) -> SharedRuleEvaluationResult:
        return cls(status=RuleResultStatus.NOT_MATCHED)

    @classmethod
    def not_applicable(
        cls,
        *,
        reason: RuleSkipReason,
        message: str | None = None,
    ) -> SharedRuleEvaluationResult:
        diagnostics: tuple[RuleDiagnostic, ...] = ()
        if message:
            diagnostics = (RuleDiagnostic(code=reason.value, message=message),)
        return cls(
            status=RuleResultStatus.NOT_APPLICABLE,
            skip_reason=reason,
            diagnostics=diagnostics,
        )

    @classmethod
    def failed(cls, message: str, *, rule_id: str | None = None) -> SharedRuleEvaluationResult:
        return cls(
            status=RuleResultStatus.FAILED,
            failure_message=require_nonblank(message, label="failure_message"),
            diagnostics=(
                RuleDiagnostic(code="rule_failed", message=message, rule_id=rule_id),
            ),
        )
