"""Family aggregation that cannot drop required scopes or known violations."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, field_validator

from codestrata.domain.contracts.enums import ResultStatus
from codestrata.domain.graph.validation import as_tuple, require_nonblank


class SubjectEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    subject_id: str
    required_scope: bool
    result: ResultStatus
    finding_ids: tuple[str, ...] = ()

    @field_validator("subject_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="subject_id")

    @field_validator("finding_ids", mode="before")
    @classmethod
    def normalize_findings(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted({require_nonblank(str(item), label="finding_id") for item in as_tuple(value)})
        )


class FamilyAggregate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    family: str
    result: ResultStatus
    coverage: str
    subject_results: tuple[SubjectEvaluation, ...]
    retained_finding_ids: tuple[str, ...]
    disappeared_required_scopes: tuple[str, ...] = ()
    disappeared_violations: tuple[str, ...] = ()


def aggregate_family(
    family: str,
    subjects: Sequence[SubjectEvaluation],
    *,
    known_violation_ids: Sequence[str] = (),
    driver_set_empty_or_disabled: bool = False,
) -> FamilyAggregate:
    """Preserve required scopes and FAIL findings through family totals."""

    ordered = tuple(sorted(subjects, key=lambda item: item.subject_id))
    retained: list[str] = []
    disappeared_scopes: list[str] = []
    for item in ordered:
        if item.required_scope and item.result is ResultStatus.NOT_APPLICABLE:
            disappeared_scopes.append(item.subject_id)
        if item.result is ResultStatus.FAIL:
            retained.extend(item.finding_ids)

    known = tuple(
        sorted({require_nonblank(str(item), label="finding_id") for item in known_violation_ids})
    )
    retained_unique = tuple(sorted(set(retained)))
    disappeared_violations = tuple(item for item in known if item not in retained_unique)
    if disappeared_scopes or disappeared_violations:
        raise ValueError(
            "canonical required scopes and known violations cannot disappear through aggregation"
        )

    if driver_set_empty_or_disabled:
        result = ResultStatus.NOT_APPLICABLE
        coverage = "empty_or_disabled_drivers"
    elif any(item.result is ResultStatus.ERROR for item in ordered):
        result = ResultStatus.ERROR
        coverage = "error"
    elif any(item.result is ResultStatus.FAIL for item in ordered):
        result = ResultStatus.FAIL
        coverage = (
            "partial"
            if any(item.result is ResultStatus.UNKNOWN for item in ordered)
            else "complete"
        )
    elif any(item.result is ResultStatus.UNKNOWN for item in ordered):
        result = ResultStatus.UNKNOWN
        coverage = "partial"
    elif ordered and all(item.result is ResultStatus.NOT_APPLICABLE for item in ordered):
        result = ResultStatus.NOT_APPLICABLE
        coverage = "not_applicable"
    else:
        result = ResultStatus.PASS
        coverage = "complete"

    return FamilyAggregate(
        family=family,
        result=result,
        coverage=coverage,
        subject_results=ordered,
        retained_finding_ids=retained_unique,
    )
