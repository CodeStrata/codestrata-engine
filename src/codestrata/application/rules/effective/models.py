"""Local unsigned config, execution context and candidate fixture cases (E04.3)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.application.rules.effective.errors import EffectiveSealError
from codestrata.application.rules.effective.timestamps import format_utc, parse_utc
from codestrata.domain.contracts.enums import ExecutionPurpose, ResultStatus
from codestrata.domain.contracts.invocation import CandidateValidation, FixtureExpectation
from codestrata.domain.contracts.rules import EffectiveRuleSet
from codestrata.domain.contracts.serialization import require_content_digest
from codestrata.domain.graph.validation import as_tuple, require_nonblank
from codestrata.domain.rules.operators.models import OperatorContext

MAX_LOCAL_RULES = 1000
MAX_FIXTURES = 64
# Pinned rule-engine catalog identity for candidate ``engine_digest`` only.
# It is not ``codestrata.__version__`` and it is not an input to
# ``seal_effective_ruleset``, so admitted Effective RuleSet digests stay valid
# when the package version changes.
ENGINE_VERSION = "0.2.1"


class LocalUnsignedConfig(BaseModel):
    """Documented local parameters hashed separately from the signed base."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameters_by_rule: dict[str, dict[str, str | int | float | bool]] = Field(default_factory=dict)

    @field_validator("parameters_by_rule", mode="before")
    @classmethod
    def bound_local_parameters(
        cls, value: object
    ) -> dict[str, dict[str, str | int | float | bool]]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise EffectiveSealError("invalid_local_config", "local parameters must be a mapping")
        if len(value) > MAX_LOCAL_RULES:
            raise ValueError(f"excessive_size: local parameters exceed {MAX_LOCAL_RULES} rules")
        normalized: dict[str, dict[str, str | int | float | bool]] = {}
        for rule_id, parameters in value.items():
            key = require_nonblank(str(rule_id), label="local rule id")
            if not isinstance(parameters, dict):
                raise EffectiveSealError(
                    "invalid_local_config",
                    f"local parameters for {key} must be a mapping",
                )
            normalized[key] = {
                str(name): _require_scalar(item) for name, item in parameters.items()
            }
        return dict(sorted(normalized.items()))


class ExecutionContext(BaseModel):
    """Wall-clock and requested purpose. Never folded into effective_ruleset_digest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    now: datetime
    requested_purpose: ExecutionPurpose

    @field_validator("now", mode="before")
    @classmethod
    def require_aware(cls, value: object) -> datetime:
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = parse_utc(str(value), label="execution now")
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed

    def observed_at(self) -> str:
        return format_utc(self.now)


class AdmissionRecord(BaseModel):
    """Purpose and time checks recorded beside the sealed digest, not inside it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    admitted: bool
    observed_at: str
    requested_purpose: ExecutionPurpose
    package_purpose: ExecutionPurpose
    validity_not_after: str | None = None
    exception_valid_not_after: tuple[str, ...] = ()
    reason_code: str | None = None


class FixtureCase(BaseModel):
    """Independent expected fixture executed through production compiler/operators."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    expected_status: ResultStatus
    operator_context: OperatorContext = Field(default_factory=OperatorContext)
    subject: str = "repository"
    path: str | None = None
    captured_at: str | None = None
    rendered_message: str | None = None
    selector_override: dict[str, Any] | None = None
    parameters_override: dict[str, str | int | float | bool] | None = None
    promote_to_production: bool = False

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> str:
        return require_nonblank(str(value), label="fixture name")

    @field_validator("subject", mode="before")
    @classmethod
    def normalize_subject(cls, value: object) -> str:
        return require_nonblank(str(value), label="fixture subject")


class CandidateRunRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    effective: EffectiveRuleSet
    fixtures: tuple[FixtureCase, ...]
    permitted_paths: tuple[str, ...] = ()
    snapshot_only: bool = True
    expiry: str
    stale_evidence: bool = False
    evidence_candidate_digest: str | None = None
    requested_purpose: ExecutionPurpose = ExecutionPurpose.CANDIDATE_VALIDATION

    @field_validator("fixtures", mode="before")
    @classmethod
    def bound_fixtures(cls, value: object) -> tuple[FixtureCase, ...]:
        items = tuple(
            item if isinstance(item, FixtureCase) else FixtureCase.model_validate(item)
            for item in as_tuple(value)
        )
        if not items:
            raise ValueError("invalid_candidate: candidate run needs fixtures")
        if len(items) > MAX_FIXTURES:
            raise ValueError(f"excessive_size: candidate fixtures exceed {MAX_FIXTURES}")
        return items

    @field_validator("expiry", mode="before")
    @classmethod
    def normalize_expiry(cls, value: object) -> str:
        text = require_nonblank(str(value), label="candidate expiry")
        parse_utc(text, label="candidate expiry")
        return text

    @field_validator("evidence_candidate_digest", mode="before")
    @classmethod
    def optional_digest(cls, value: object) -> str | None:
        if value is None:
            return None
        return require_content_digest(value, label="evidence candidate digest")

    @model_validator(mode="after")
    def preview_only(self) -> CandidateRunRequest:
        if self.stale_evidence:
            raise ValueError("stale_preview_evidence: stale preview evidence is rejected")
        if self.requested_purpose is ExecutionPurpose.PRODUCTION:
            raise ValueError(
                "preview_cannot_authorize_production: "
                "candidate/preview entrypoint cannot request production"
            )
        return self


class FixtureOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    expected_status: ResultStatus
    actual_status: ResultStatus
    coverage: str
    finding_fingerprint: str
    diagnostics: tuple[str, ...] = ()
    preview_only: bool = True


class CandidateRunResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.candidate-run-result.v1"
    schema_version: str = "1.0.0"
    purpose: ExecutionPurpose
    production_promotion_allowed: bool = False
    candidate_digest: str
    selector_digest: str
    effective_setting_digest: str
    input_digest: str
    engine_digest: str
    dsl_digest: str
    outcomes: tuple[FixtureOutcome, ...]
    validation: CandidateValidation
    typed_diagnostics: tuple[str, ...] = ()

    @model_validator(mode="after")
    def bind_preview_only(self) -> CandidateRunResult:
        if self.production_promotion_allowed:
            raise EffectiveSealError(
                "preview_cannot_authorize_production",
                "candidate results cannot authorize production",
            )
        if self.purpose is ExecutionPurpose.PRODUCTION:
            raise EffectiveSealError(
                "preview_cannot_authorize_production",
                "candidate run result cannot carry production purpose",
            )
        return self

    def fixture_expectations(self) -> tuple[FixtureExpectation, ...]:
        return tuple(
            FixtureExpectation(
                name=item.name,
                expected_status=item.expected_status.value,
                actual_status=item.actual_status.value,
                coverage=item.coverage,
            )
            for item in self.outcomes
        )


def _require_scalar(value: object) -> str | int | float | bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float | str):
        return value
    raise EffectiveSealError(
        "invalid_local_config",
        f"local parameter values must be scalars, not {type(value).__name__}",
    )
