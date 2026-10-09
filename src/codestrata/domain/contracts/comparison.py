"""Comparison envelope: compatibility, movement and cause attribution (E01.3)."""

from __future__ import annotations

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

from codestrata.domain.contracts.enums import (
    CauseAttribution,
    ChangedInputDimension,
    CompatibilityStatus,
    OutcomeMovement,
    ResultStatus,
)
from codestrata.domain.contracts.serialization import (
    bind_content_digest,
    digest_canonical,
    is_binding_digest,
    omit_key,
    require_content_digest,
    require_pinned_version,
    require_supported_major,
    walk_forbidden_credentials,
    walk_forbidden_identity,
)
from codestrata.domain.graph.validation import as_tuple, require_nonblank

COMPARISON_SCHEMA = "codestrata.comparison-envelope.v1"
COMPARISON_VERSION = "1.0.0"


class ComparisonError(ValueError):
    """Unsupported or incompatible comparison envelope."""


class DriverDelta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    driver_id: str
    comparison_unit: str
    base_value: str | None = None
    candidate_value: str | None = None
    delta: str | None = None
    compatible: bool
    compatibility_reason: str
    cause: CauseAttribution
    outcome_role: str
    finding_lifecycle: str | None = None

    @field_validator(
        "driver_id",
        "comparison_unit",
        "compatibility_reason",
        "outcome_role",
        mode="before",
    )
    @classmethod
    def normalize_text(cls, value: object) -> str:
        return require_nonblank(str(value), label="driver delta")


class BoundDigests(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_digest: str
    ruleset_digest: str
    package_digest: str
    config_digest: str
    feed_digest: str | None = None
    input_digest: str
    engine_version: str
    dsl_version: str
    outcome_driver_manifest_digest: str

    @field_validator(
        "artifact_digest",
        "ruleset_digest",
        "package_digest",
        "config_digest",
        "input_digest",
        "outcome_driver_manifest_digest",
        mode="before",
    )
    @classmethod
    def normalize_digest(cls, value: object) -> str:
        return require_content_digest(value, label="comparison digest")

    @field_validator("feed_digest", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return require_content_digest(value, label="feed_digest")

    @field_validator("engine_version", mode="before")
    @classmethod
    def normalize_engine(cls, value: object) -> str:
        return require_pinned_version(value, label="engine_version")

    @field_validator("dsl_version", mode="before")
    @classmethod
    def normalize_dsl(cls, value: object) -> str:
        return require_nonblank(str(value), label="dsl_version")


class ComparisonEnvelope(BaseModel):
    """Repository-level comparison. Platform must not reconstruct analyzer findings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = COMPARISON_SCHEMA
    schema_version: str = COMPARISON_VERSION
    envelope_digest: str
    has_baseline: bool
    compatibility: CompatibilityStatus
    compatibility_reasons: tuple[str, ...]
    movement: OutcomeMovement
    cause_attribution: CauseAttribution
    changed_input_dimensions: tuple[ChangedInputDimension, ...] = ()
    controlled_equivalent_inputs: bool = False
    baseline: BoundDigests | None = None
    candidate: BoundDigests
    driver_deltas: tuple[DriverDelta, ...] = ()
    retained_known_violation_ids: tuple[str, ...] = ()
    excluded_driver_ids: tuple[str, ...] = ()
    coverage_status: ResultStatus
    notes: tuple[str, ...] = ()

    @field_validator("envelope_digest", mode="before")
    @classmethod
    def normalize_digest(cls, value: object) -> str:
        return require_content_digest(value, label="envelope_digest")

    @field_validator(
        "compatibility_reasons",
        "retained_known_violation_ids",
        "excluded_driver_ids",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_seq(cls, value: object) -> tuple[str, ...]:
        return tuple(
            require_nonblank(str(item), label="comparison list") for item in as_tuple(value)
        )

    @model_validator(mode="after")
    def preserve_compatibility_and_cause(self, info: ValidationInfo) -> ComparisonEnvelope:
        require_supported_major(self.schema_version)
        if not self.has_baseline:
            if self.baseline is not None:
                raise ValueError("no-baseline comparison cannot bind a baseline digest set")
            if self.compatibility is not CompatibilityStatus.NO_BASELINE:
                raise ValueError("missing baseline is no_baseline, not compatible")
            if self.movement not in {OutcomeMovement.INSUFFICIENT, OutcomeMovement.NOT_APPLICABLE}:
                raise ValueError("first run cannot show a trend")
            if self.cause_attribution is not CauseAttribution.UNDETERMINED:
                raise ValueError("no baseline cannot invent cause attribution")
        else:
            if self.baseline is None:
                raise ValueError("baseline comparison must bind baseline digests")
            if self.compatibility is CompatibilityStatus.NO_BASELINE:
                raise ValueError("has_baseline cannot use no_baseline compatibility")
        if self.compatibility is CompatibilityStatus.INCOMPATIBLE:
            if self.movement in {OutcomeMovement.IMPROVED, OutcomeMovement.STABLE}:
                raise ValueError("incompatible comparison cannot claim improved or stable")
            if not self.compatibility_reasons:
                raise ValueError("incompatible comparison needs compatibility_reasons")
        isolated = {
            ChangedInputDimension.SOURCE,
            ChangedInputDimension.FEED,
            ChangedInputDimension.CONFIGURATION,
        }
        differing = [item for item in self.changed_input_dimensions if item in isolated]
        if len(differing) > 1 and not self.controlled_equivalent_inputs:
            allowed = {CauseAttribution.MIXED, CauseAttribution.UNDETERMINED}
            if self.cause_attribution not in allowed:
                raise ValueError(
                    "multiple changed dimensions without controlled reruns are mixed/undetermined"
                )
        payload = self.model_dump(mode="json")
        walk_forbidden_identity(payload)
        walk_forbidden_credentials(payload)
        expected = digest_canonical(omit_key(payload, "envelope_digest"))
        if self.envelope_digest != expected and not is_binding_digest(info):
            raise ValueError("envelope_digest does not match canonical comparison payload")
        return self


def seal_comparison(payload: dict[str, Any]) -> ComparisonEnvelope:
    return bind_content_digest(ComparisonEnvelope, payload, "envelope_digest")


def parse_comparison(payload: object) -> ComparisonEnvelope:
    if not isinstance(payload, dict):
        raise ComparisonError("comparison envelope must be an object")
    try:
        require_supported_major(str(payload.get("schema_version", "")))
        return ComparisonEnvelope.model_validate(payload)
    except (ValidationError, ValueError) as error:
        raise ComparisonError(str(error)) from error
