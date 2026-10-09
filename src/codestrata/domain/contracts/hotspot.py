"""M22 Engineering Hotspot, scoped M25 ownership, and M27/M29 change summary."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.contracts.enums import (
    ContributorRole,
    HotspotListKind,
    OwnershipScope,
    ResultStatus,
)
from codestrata.domain.contracts.formulas import serialize_ratio
from codestrata.domain.graph.validation import as_tuple, require_nonblank


class ContributorRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    measurement_id: str
    measurement_version: str
    role: ContributorRole
    value: str | None = None
    coverage_reason: str | None = None
    evidence_ids: tuple[str, ...] = ()

    @field_validator("name", "measurement_id", "measurement_version", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="contributor field")

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted({require_nonblank(str(item), label="evidence_id") for item in as_tuple(value)})
        )


class EngineeringHotspot(BaseModel):
    """First-class M22 record. Ranking value is complexity × changed lines only."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.engineering-hotspot.v1"
    schema_version: str = "1.0.0"
    record_id: str
    subject_id: str
    input_state_digest: str
    list_kind: HotspotListKind
    ranking_value: str | None
    history_profile_id: str
    history_window: str
    contributors: tuple[ContributorRecord, ...]
    active_finding_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...]
    priority_explanation: str
    opaque_score: bool = False

    @field_validator(
        "record_id",
        "subject_id",
        "input_state_digest",
        "history_profile_id",
        "history_window",
        "priority_explanation",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="hotspot field")

    @field_validator("active_finding_ids", "evidence_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(sorted({require_nonblank(str(item), label="id") for item in as_tuple(value)}))

    @field_validator("opaque_score")
    @classmethod
    def forbid_score(cls, value: bool) -> bool:
        if value:
            raise ValueError("M22 must not introduce an opaque score")
        return value

    @model_validator(mode="after")
    def validate_roles_and_rank(self) -> EngineeringHotspot:
        ranking = [item for item in self.contributors if item.role is ContributorRole.RANKING]
        names = {item.name for item in ranking}
        if names != {"complexity", "churn"}:
            raise ValueError("ranking contributors must be exactly complexity and churn")
        context = {
            item.name for item in self.contributors if item.role is ContributorRole.CONTEXT_ONLY
        }
        forbidden_rank = context & {"complexity", "churn"}
        if forbidden_rank:
            raise ValueError("complexity/churn cannot be context_only")
        if self.list_kind is HotspotListKind.COMPLETE_COMPARABLE:
            if self.ranking_value is None:
                raise ValueError("complete hotspot list requires a ranking_value")
            missing = [item.name for item in ranking if item.value is None]
            if missing:
                raise ValueError("complete ranking cannot use missing-as-zero")
        if self.list_kind is HotspotListKind.PARTIAL_OR_UNKNOWN:
            if self.ranking_value is not None:
                raise ValueError("partial/UNKNOWN hotspots cannot enter the comparable ranking")
        if "formula_version=" not in self.priority_explanation:
            raise ValueError("priority explanation must name formula/version")
        if "tie_break=" not in self.priority_explanation:
            raise ValueError("priority explanation must name the tie-breaker")
        return self


def hotspot_rank_key(item: EngineeringHotspot) -> tuple[object, ...]:
    """Descending ranking value, then subject ID ascending. Partial list is ID only."""

    if item.list_kind is HotspotListKind.PARTIAL_OR_UNKNOWN:
        return (item.subject_id,)
    value = Decimal(item.ranking_value or "0")
    return (-value, item.subject_id)


def build_priority_explanation(
    *,
    formula_version: str,
    complexity: str,
    changed_lines: str,
    ranking_value: str,
    subject_id: str,
    history_window: str,
) -> str:
    return (
        f"formula_version={formula_version}; ranking=complexity*churn; "
        f"complexity={complexity}; changed_lines={changed_lines}; "
        f"value={ranking_value}; scope={subject_id}; window={history_window}; "
        f"tie_break=subject_id_ascending"
    )


class OwnershipConcentration(BaseModel):
    """M25 scoped independently. File ratios are never averaged into a parent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.ownership-concentration.v1"
    schema_version: str = "1.0.0"
    record_id: str
    scope: OwnershipScope
    subject_id: str
    numerator: int | None
    denominator: int | None
    serialized_ratio: str | None
    history_profile_id: str
    evidence_ids: tuple[str, ...]
    status: ResultStatus
    notes: str

    @model_validator(mode="after")
    def unknown_never_zero_or_one(self) -> OwnershipConcentration:
        if self.denominator is None:
            if self.status is not ResultStatus.UNKNOWN:
                raise ValueError("unknown denominator must be UNKNOWN")
            if self.serialized_ratio is not None:
                raise ValueError("unknown denominator cannot serialize 0% or 100%")
        if self.denominator == 0:
            if self.status is not ResultStatus.NOT_APPLICABLE:
                raise ValueError("empty ownership denominator is NOT_APPLICABLE")
        return self


class ChangeSummary(BaseModel):
    """M27 change size/spread plus M29 blast-radius fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.change-summary.v1"
    schema_version: str = "1.0.0"
    changed_file_ids: tuple[str, ...]
    changed_component_ids: tuple[str, ...]
    changed_file_count: int = Field(ge=0)
    changed_component_count: int = Field(ge=0)
    unmapped_changed_file_count: int = Field(ge=0)
    mapping_coverage: str | None
    mapping_coverage_status: ResultStatus
    boundary_dimension: str | None = None
    boundary_spread_member_ids: tuple[str, ...] = ()
    boundary_spread_count: int | None = None
    boundary_spread_status: ResultStatus
    crossed_boundary_count: int | None = None
    crossed_boundary_pairs: tuple[str, ...] = ()
    crossed_boundary_status: ResultStatus
    affected_component_ids: tuple[str, ...] = ()
    affected_component_count: int | None = None
    affected_test_ids: tuple[str, ...] = ()
    affected_test_count: int | None = None
    visited_nodes: int | None = None
    visited_edges: int | None = None
    cutoff_reason: str | None = None
    graph_side: str
    lower_bound: bool = False
    narrative_only_context: bool = False

    @field_validator(
        "changed_file_ids",
        "changed_component_ids",
        "boundary_spread_member_ids",
        "crossed_boundary_pairs",
        "affected_component_ids",
        "affected_test_ids",
        mode="before",
    )
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted(
                {require_nonblank(str(item), label="change-summary id") for item in as_tuple(value)}
            )
        )

    @model_validator(mode="after")
    def counts_match_ids(self) -> ChangeSummary:
        if self.changed_file_count != len(self.changed_file_ids):
            raise ValueError("changed_file_count must equal unique changed_file_ids")
        if self.changed_component_count != len(self.changed_component_ids):
            raise ValueError("changed_component_count must equal unique changed_component_ids")
        if self.boundary_spread_status is ResultStatus.UNKNOWN and self.boundary_spread_count == 0:
            raise ValueError("missing boundary membership is UNKNOWN, not zero crossed/spread")
        if (
            self.crossed_boundary_status is ResultStatus.UNKNOWN
            and self.crossed_boundary_count == 0
        ):
            raise ValueError("missing boundary evidence is UNKNOWN, not zero crossed boundaries")
        return self


def ownership_ratio(numerator: int, denominator: int) -> str:
    return serialize_ratio(Decimal(numerator) / Decimal(denominator))
