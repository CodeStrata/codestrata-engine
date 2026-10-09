"""Versioned default/effective severity and approved override provenance."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from codestrata.domain.contracts.enums import SeverityOverrideSource
from codestrata.domain.findings.enums import FindingSeverity
from codestrata.domain.graph.validation import as_tuple, require_nonblank
from codestrata.domain.rules.identifiers import validate_rule_id


class ContextSeverityDefault(BaseModel):
    """Source-derived default that lives on the versioned rule/config contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str
    context_class: str
    default_severity: FindingSeverity
    basis: str
    notes: str


class SeverityOverride(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: SeverityOverrideSource
    effective_severity: FindingSeverity
    provenance_id: str
    approved: bool

    @field_validator("provenance_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="provenance_id")


class VersionedSeverityBinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    contract_version: str
    default_severity: FindingSeverity
    context_defaults: tuple[ContextSeverityDefault, ...] = ()
    approved_override: SeverityOverride | None = None
    effective_severity: FindingSeverity

    @field_validator("rule_id", mode="before")
    @classmethod
    def normalize_rule(cls, value: object) -> str:
        return validate_rule_id(str(value))

    @field_validator("contract_version", mode="before")
    @classmethod
    def normalize_version(cls, value: object) -> str:
        return require_nonblank(str(value), label="contract_version")

    @field_validator("context_defaults", mode="before")
    @classmethod
    def normalize_defaults(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @model_validator(mode="after")
    def bind_effective(self) -> VersionedSeverityBinding:
        if self.approved_override is not None:
            if not self.approved_override.approved:
                raise ValueError("unapproved override cannot become effective severity")
            if self.approved_override.source is not SeverityOverrideSource.APPROVED_CONFIG:
                raise ValueError("only approved_config overrides may set effective severity")
            if self.effective_severity != self.approved_override.effective_severity:
                raise ValueError("effective severity must equal the approved override")
        return self


def apply_context_default(
    binding: VersionedSeverityBinding,
    *,
    context_class: str,
) -> VersionedSeverityBinding:
    """Context may shape default severity only before an approved override."""

    if binding.approved_override is not None:
        return binding
    match = next(
        (item for item in binding.context_defaults if item.context_class == context_class),
        None,
    )
    if match is None:
        return binding
    return binding.model_copy(
        update={
            "default_severity": match.default_severity,
            "effective_severity": match.default_severity,
        }
    )


def rewrite_after_override_rejected(
    binding: VersionedSeverityBinding,
    *,
    attempted_severity: FindingSeverity,
) -> None:
    if binding.approved_override is None:
        return
    if attempted_severity != binding.effective_severity:
        raise ValueError(
            "hidden rewrite after approved override is forbidden; "
            "effective severity stays on the versioned contract"
        )
