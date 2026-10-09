"""Canonical launch-catalog evaluation records (E03.3).

Operational job identifiers and wall-clock durations stay off this body so
repeat executions of the same plan and facts remain digest-identical.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.contracts.enums import (
    CoverageState,
    ExecutionPurpose,
    ResultStatus,
)
from codestrata.domain.contracts.serialization import digest_canonical, walk_forbidden_credentials
from codestrata.domain.graph.validation import as_tuple, require_nonblank
from codestrata.domain.rules.errors import RuleEvidenceError, RuleResultValidationError

RESULT_SCHEMA = "codestrata.launch-rule-result.v1"
RESULT_SCHEMA_VERSION = "1.0.0"
CATALOG_KIND = "yaml_compiler_operators"

_MAX_DIAGNOSTIC_CHARS = 2048
_MAX_DIAGNOSTICS = 32
_ABSOLUTE_PATH_MARKERS = (":\\", ":/", "\\\\")


class LaunchEvidence(BaseModel):
    """Relative-path evidence for a launch-catalog finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.launch-evidence.v1"
    schema_version: str = RESULT_SCHEMA_VERSION
    subject_id: str
    source_kind: str
    relative_path: str | None = None
    span: str | None = None
    extractor_version: str
    limitation: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)

    @field_validator("subject_id", "source_kind", "extractor_version", mode="before")
    @classmethod
    def require_text(cls, value: object) -> str:
        return require_nonblank(str(value), label="evidence field")

    @model_validator(mode="after")
    def reject_machine_identity(self) -> LaunchEvidence:
        for field in (self.subject_id, self.relative_path, self.span):
            if field and _looks_absolute(field):
                raise RuleEvidenceError(
                    "absolute machine paths cannot enter launch evidence",
                    reason_code="absolute_path_evidence",
                )
        walk_forbidden_credentials(self.model_dump(mode="json"))
        return self


class LaunchDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    message: str
    rule_id: str | None = None

    @field_validator("code", "message", mode="before")
    @classmethod
    def bound_text(cls, value: object) -> str:
        text = require_nonblank(str(value), label="diagnostic")
        if len(text) > _MAX_DIAGNOSTIC_CHARS:
            return text[:_MAX_DIAGNOSTIC_CHARS]
        return text


class LaunchRuleRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    rule_revision: str
    plan_digest: str
    status: ResultStatus | None = None
    coverage_state: CoverageState
    enabled: bool
    suppressed: bool
    reason: str | None = None
    evidence: tuple[LaunchEvidence, ...] = ()
    diagnostics: tuple[LaunchDiagnostic, ...] = ()
    operator_reason: str | None = None

    @field_validator("rule_id", "rule_revision", "plan_digest", mode="before")
    @classmethod
    def require_identity(cls, value: object) -> str:
        return require_nonblank(str(value), label="rule identity")

    @field_validator("evidence", "diagnostics", mode="before")
    @classmethod
    def as_items(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @model_validator(mode="after")
    def status_consistency(self) -> LaunchRuleRecord:
        if len(self.diagnostics) > _MAX_DIAGNOSTICS:
            raise RuleResultValidationError(
                "diagnostic bound exceeded",
                reason_code="diagnostic_bound",
                rule_id=self.rule_id,
            )
        if not self.enabled:
            if self.coverage_state is not CoverageState.DISABLED:
                raise RuleResultValidationError(
                    "disabled rules must keep coverage_state=disabled",
                    reason_code="disabled_scope",
                    rule_id=self.rule_id,
                )
            if self.status in {ResultStatus.PASS, ResultStatus.NOT_APPLICABLE}:
                raise RuleResultValidationError(
                    "disabled scope must not become PASS or NOT_APPLICABLE",
                    reason_code="disabled_scope",
                    rule_id=self.rule_id,
                )
            return self
        if self.suppressed and self.coverage_state is not CoverageState.SUPPRESSED:
            raise RuleResultValidationError(
                "suppressed rules must keep coverage_state=suppressed",
                reason_code="suppressed_scope",
                rule_id=self.rule_id,
            )
        if self.status is ResultStatus.FAIL and not self.evidence:
            raise RuleResultValidationError(
                "FAIL requires evidence",
                reason_code="missing_evidence",
                rule_id=self.rule_id,
            )
        if self.status is ResultStatus.ERROR and not self.reason:
            raise RuleResultValidationError(
                "ERROR requires a processing reason",
                reason_code="missing_error_reason",
                rule_id=self.rule_id,
            )
        return self


class LaunchExecutionBody(BaseModel):
    """Deterministic catalog result. No job id, duration or signature bytes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = RESULT_SCHEMA
    schema_version: str = RESULT_SCHEMA_VERSION
    catalog_kind: str = CATALOG_KIND
    compiler_version: str
    purpose: ExecutionPurpose
    preview_cannot_authorize_production: bool = True
    plan_digest: str
    facts_digest: str
    records: tuple[LaunchRuleRecord, ...]
    limitations: tuple[str, ...] = ()

    @field_validator("records", "limitations", mode="before")
    @classmethod
    def as_items(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @model_validator(mode="after")
    def freeze_body(self) -> LaunchExecutionBody:
        if self.preview_cannot_authorize_production is not True:
            raise ValueError("preview cannot authorize production")
        ordered = tuple(sorted(self.records, key=lambda item: item.rule_id))
        if ordered != self.records:
            raise ValueError("records must be ordered by rule_id")
        walk_forbidden_credentials(self.model_dump(mode="json"))
        return self

    def content_digest(self) -> str:
        return digest_canonical(self.model_dump(mode="json"))


def _looks_absolute(value: str) -> bool:
    if value.startswith("/") and not value.startswith("./"):
        return True
    lowered = value.lower()
    return any(marker in lowered for marker in _ABSOLUTE_PATH_MARKERS)
