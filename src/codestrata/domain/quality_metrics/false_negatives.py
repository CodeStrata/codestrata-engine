"""Canonical False-Negative tracking (Epic 5 Slice 5.10).

Internal validation/calibration lifecycle for suspected and confirmed false
negatives. Not customer missing-finding status, recall itself, coverage,
confidence, or synthetic findings.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Any, Iterable, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.graph.validation import as_tuple, require_nonblank
from codestrata.domain.quality_metrics.common import dedupe_limitations
from codestrata.domain.quality_metrics.false_positives import SafeValidationValue

_ABS_PATH_RE = re.compile(r"(^/)|(^[A-Za-z]:[\\/])|(/Users/)|(/home/)|(\\Users\\)")
_DIAGNOSTIC_MAX = 480
_ID_MATERIAL_MAX = 200


class FalseNegativeEntityType(StrEnum):
    TECHNOLOGY_FACT = "technology_fact"
    EVIDENCE = "evidence"
    FINDING = "finding"
    RECOMMENDATION = "recommendation"
    PRIORITY_ACTION = "priority_action"
    ROADMAP_INITIATIVE = "roadmap_initiative"
    COVERAGE_RESULT = "coverage_result"
    OTHER = "other"


class FalseNegativeClassification(StrEnum):
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    AMBIGUOUS = "ambiguous"
    EXPECTATION_ERROR = "expectation_error"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class FalseNegativeStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    ACCEPTED_AMBIGUOUS = "accepted_ambiguous"
    FIXED = "fixed"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class FalseNegativeRootCause(StrEnum):
    CANDIDATE_DISCOVERY = "candidate_discovery"
    EVIDENCE_EXTRACTION = "evidence_extraction"
    PARSER = "parser"
    UNSUPPORTED_LANGUAGE = "unsupported_language"
    UNSUPPORTED_ECOSYSTEM = "unsupported_ecosystem"
    CLASSIFICATION = "classification"
    CONTEXT_FILTERING = "context_filtering"
    RULE_PREDICATE = "rule_predicate"
    THRESHOLD = "threshold"
    RULE_NOT_EXECUTED = "rule_not_executed"
    PACK_NOT_ACTIVATED = "pack_not_activated"
    IDENTITY_NORMALIZATION = "identity_normalization"
    SOURCE_LOCATION = "source_location"
    FINDING_MAPPING = "finding_mapping"
    REPORT_PROJECTION = "report_projection"
    RECOMMENDATION_PROVIDER = "recommendation_provider"
    PRIORITY_PROJECTION = "priority_projection"
    ROADMAP_PROJECTION = "roadmap_projection"
    EXPECTATION_ERROR = "expectation_error"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNKNOWN = "unknown"


class FalseNegativeResolution(StrEnum):
    PRODUCT_FIX = "product_fix"
    EXPECTATION_FIX = "expectation_fix"
    FIXTURE_FIX = "fixture_fix"
    ACTIVATION_FIX = "activation_fix"
    SUPPORTED_SCOPE_DOCUMENTED = "supported_scope_documented"
    ACCEPTED_AMBIGUOUS = "accepted_ambiguous"
    DUPLICATE_RECORD_MERGED = "duplicate_record_merged"
    REJECTED_NOT_FALSE_NEGATIVE = "rejected_not_false_negative"


def _bound_text(value: object, *, limit: int) -> str:
    text = " ".join(str(value if value is not None else "").split())
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def _normalize_optional_id(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_path(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().replace("\\", "/")
    if not text:
        return None
    while text.startswith("./"):
        text = text[2:]
    if _ABS_PATH_RE.search(text):
        raise ValueError(f"absolute/unsafe path rejected: {value!r}")
    if text.startswith("/") or (len(text) >= 3 and text[1] == ":"):
        raise ValueError(f"absolute/unsafe path rejected: {value!r}")
    return text[:_ID_MATERIAL_MAX]


def build_false_negative_id(
    *,
    repository_id: str,
    assessment_area: str,
    entity_type: FalseNegativeEntityType | str,
    expected_rule_id: str | None = None,
    expected_entity_id: str | None = None,
    expected_category: str | None = None,
    expected_path: str | None = None,
    expected_condition_identity: str,
) -> str:
    """Deterministic ``fn:{sha256[:24]}`` from structural expected-positive identity."""

    entity = (
        entity_type.value
        if isinstance(entity_type, FalseNegativeEntityType)
        else str(entity_type)
    )
    material = "\n".join(
        [
            require_nonblank(str(repository_id), label="repository_id").strip().lower(),
            require_nonblank(str(assessment_area), label="assessment_area").strip().lower(),
            entity.strip().lower(),
            (expected_rule_id or "").strip().lower(),
            (expected_entity_id or "").strip().lower(),
            (expected_category or "").strip().lower(),
            (expected_path or "").strip().lower().replace("\\", "/"),
            _bound_text(expected_condition_identity, limit=_ID_MATERIAL_MAX).lower(),
        ]
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"fn:{digest}"


class FalseNegativeRecord(BaseModel):
    """Durable internal false-negative tracking record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    false_negative_id: str
    repository_id: str
    assessment_area: str
    entity_type: FalseNegativeEntityType
    expected_entity_id: str | None = None
    expected_rule_id: str | None = None
    expected_rule_version: str | None = None
    expected_signal_id: str | None = None
    expected_category: str | None = None
    expected_path: str | None = None
    expected_subject: str | None = None
    supporting_evidence_ids: tuple[str, ...] = ()
    classification: FalseNegativeClassification = FalseNegativeClassification.SUSPECTED
    status: FalseNegativeStatus = FalseNegativeStatus.OPEN
    root_cause: FalseNegativeRootCause | None = None
    expected: SafeValidationValue
    actual: SafeValidationValue
    diagnostic: str
    rationale: str | None = None
    first_seen_run_id: str
    last_seen_run_id: str
    resolved_run_id: str | None = None
    resolution: FalseNegativeResolution | None = None
    regression_test_refs: tuple[str, ...] = ()
    observation_run_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    @field_validator(
        "false_negative_id",
        "repository_id",
        "assessment_area",
        "first_seen_run_id",
        "last_seen_run_id",
        "diagnostic",
        mode="before",
    )
    @classmethod
    def require_text(cls, value: object) -> str:
        return require_nonblank(str(value), label="false negative field")

    @field_validator(
        "expected_entity_id",
        "expected_rule_id",
        "expected_rule_version",
        "expected_signal_id",
        "expected_category",
        "expected_subject",
        "resolved_run_id",
        "rationale",
        mode="before",
    )
    @classmethod
    def optional_text(cls, value: object) -> str | None:
        return _normalize_optional_id(value)

    @field_validator("expected_path", mode="before")
    @classmethod
    def normalize_path_field(cls, value: object) -> str | None:
        return _normalize_path(value)

    @field_validator(
        "supporting_evidence_ids",
        "regression_test_refs",
        "observation_run_ids",
        mode="before",
    )
    @classmethod
    def normalize_id_tuples(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    require_nonblank(str(item), label="false negative id ref")
                    for item in as_tuple(value)
                }
            )
        )

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        return dedupe_limitations(value, label="false negative limitation")

    @field_validator("diagnostic", mode="after")
    @classmethod
    def bound_diagnostic(cls, value: str) -> str:
        return _bound_text(value, limit=_DIAGNOSTIC_MAX)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> FalseNegativeRecord:
        if not self.false_negative_id.startswith("fn:"):
            raise ValueError("false_negative_id must use fn: prefix")

        has_expected_identity = any(
            (
                self.expected_rule_id,
                self.expected_entity_id,
                self.expected_signal_id,
                self.expected_category,
                self.expected_subject,
                self.expected.value,
            )
        )
        if not has_expected_identity:
            raise ValueError("tracked FN requires expected-positive identity")

        if self.classification is FalseNegativeClassification.CONFIRMED and (
            self.root_cause
            in {
                FalseNegativeRootCause.EXPECTATION_ERROR,
                FalseNegativeRootCause.UNSUPPORTED_CAPABILITY,
            }
        ):
            raise ValueError(
                "confirmed product FN cannot use expectation_error or "
                "unsupported_capability root cause"
            )

        if (
            self.classification is FalseNegativeClassification.CONFIRMED
            and self.resolution
            in {
                FalseNegativeResolution.EXPECTATION_FIX,
                FalseNegativeResolution.SUPPORTED_SCOPE_DOCUMENTED,
            }
        ):
            raise ValueError(
                "confirmed product FN cannot use expectation/scope-documented resolution"
            )

        if self.status is FalseNegativeStatus.FIXED:
            if self.classification is FalseNegativeClassification.CONFIRMED:
                if self.root_cause is None:
                    raise ValueError("fixed confirmed FN requires root_cause")
                if self.resolution is None:
                    raise ValueError("fixed confirmed FN requires resolution")
                if (
                    self.resolution is FalseNegativeResolution.PRODUCT_FIX
                    and not self.regression_test_refs
                ):
                    raise ValueError(
                        "product_fix resolution requires at least one regression_test_ref"
                    )
            elif self.resolution is None:
                raise ValueError("fixed FN requires resolution")

        if self.resolved_run_id is not None and self.resolved_run_id < self.first_seen_run_id:
            raise ValueError("resolved_run_id cannot precede first_seen_run_id")
        if self.last_seen_run_id < self.first_seen_run_id:
            raise ValueError("last_seen_run_id cannot precede first_seen_run_id")

        if (
            self.classification is FalseNegativeClassification.AMBIGUOUS
            and self.status is FalseNegativeStatus.FIXED
            and self.resolution is None
        ):
            raise ValueError("fixed FN requires resolution")

        return self

    def canonical_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def to_json(self) -> str:
        return json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":"))


class FalseNegativeSummaryCounts(BaseModel):
    """Aggregate FN tracking counts for one repository or pack summary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    suspected: int = Field(default=0, ge=0)
    confirmed: int = Field(default=0, ge=0)
    ambiguous: int = Field(default=0, ge=0)
    expectation_errors: int = Field(default=0, ge=0)
    unsupported_capability: int = Field(default=0, ge=0)
    insufficient_evidence: int = Field(default=0, ge=0)
    rejected: int = Field(default=0, ge=0)
    fixed: int = Field(default=0, ge=0)
    open: int = Field(default=0, ge=0)
    investigating: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)


def summarize_false_negatives(
    records: Sequence[FalseNegativeRecord] | Iterable[FalseNegativeRecord],
) -> FalseNegativeSummaryCounts:
    items = tuple(records)
    suspected = confirmed = ambiguous = expectation_errors = 0
    unsupported = insufficient = rejected = fixed = open_count = investigating = 0
    for item in items:
        if item.classification is FalseNegativeClassification.SUSPECTED:
            suspected += 1
        elif item.classification is FalseNegativeClassification.CONFIRMED:
            confirmed += 1
        elif item.classification is FalseNegativeClassification.AMBIGUOUS:
            ambiguous += 1
        elif item.classification is FalseNegativeClassification.EXPECTATION_ERROR:
            expectation_errors += 1
        elif item.classification is FalseNegativeClassification.UNSUPPORTED_CAPABILITY:
            unsupported += 1
        elif item.classification is FalseNegativeClassification.INSUFFICIENT_EVIDENCE:
            insufficient += 1
        elif item.classification is FalseNegativeClassification.REJECTED:
            rejected += 1
        if item.status is FalseNegativeStatus.FIXED:
            fixed += 1
        elif item.status is FalseNegativeStatus.OPEN:
            open_count += 1
        elif item.status is FalseNegativeStatus.INVESTIGATING:
            investigating += 1
    return FalseNegativeSummaryCounts(
        suspected=suspected,
        confirmed=confirmed,
        ambiguous=ambiguous,
        expectation_errors=expectation_errors,
        unsupported_capability=unsupported,
        insufficient_evidence=insufficient,
        rejected=rejected,
        fixed=fixed,
        open=open_count,
        investigating=investigating,
        total=len(items),
    )


def merge_false_negative_records(
    records: Sequence[FalseNegativeRecord],
) -> tuple[FalseNegativeRecord, ...]:
    """Deduplicate by false_negative_id; union refs and extend last_seen."""

    by_id: dict[str, FalseNegativeRecord] = {}
    for item in records:
        existing = by_id.get(item.false_negative_id)
        if existing is None:
            by_id[item.false_negative_id] = item
            continue
        first_seen = min(existing.first_seen_run_id, item.first_seen_run_id)
        last_seen = max(existing.last_seen_run_id, item.last_seen_run_id)
        resolved = existing.resolved_run_id
        if item.resolved_run_id is not None:
            if resolved is None or item.resolved_run_id < resolved:
                resolved = item.resolved_run_id
        preferred = item
        if existing.classification is not FalseNegativeClassification.SUSPECTED and (
            item.classification is FalseNegativeClassification.SUSPECTED
        ):
            preferred = existing
        elif (
            existing.status is FalseNegativeStatus.FIXED
            and item.status is not FalseNegativeStatus.FIXED
        ):
            preferred = existing
        by_id[item.false_negative_id] = preferred.model_copy(
            update={
                "first_seen_run_id": first_seen,
                "last_seen_run_id": last_seen,
                "resolved_run_id": resolved or preferred.resolved_run_id,
                "supporting_evidence_ids": tuple(
                    sorted(
                        set(existing.supporting_evidence_ids)
                        | set(item.supporting_evidence_ids)
                    )
                ),
                "regression_test_refs": tuple(
                    sorted(
                        set(existing.regression_test_refs) | set(item.regression_test_refs)
                    )
                ),
                "observation_run_ids": tuple(
                    sorted(
                        set(existing.observation_run_ids)
                        | set(item.observation_run_ids)
                        | {existing.first_seen_run_id, existing.last_seen_run_id}
                        | {item.first_seen_run_id, item.last_seen_run_id}
                    )
                ),
                "limitations": dedupe_limitations(
                    (*existing.limitations, *item.limitations),
                    label="false negative limitation",
                ),
                "rationale": preferred.rationale or existing.rationale or item.rationale,
                "root_cause": preferred.root_cause or existing.root_cause or item.root_cause,
                "resolution": preferred.resolution or existing.resolution or item.resolution,
            }
        )
    return tuple(sorted(by_id.values(), key=lambda r: r.false_negative_id))


def build_false_negative_record(
    *,
    repository_id: str,
    assessment_area: str,
    entity_type: FalseNegativeEntityType | str,
    expected: object,
    actual: object,
    diagnostic: str,
    run_id: str,
    expected_rule_id: str | None = None,
    expected_entity_id: str | None = None,
    expected_signal_id: str | None = None,
    expected_category: str | None = None,
    expected_path: str | None = None,
    expected_subject: str | None = None,
    supporting_evidence_ids: Sequence[str] = (),
    classification: FalseNegativeClassification = FalseNegativeClassification.SUSPECTED,
    status: FalseNegativeStatus = FalseNegativeStatus.OPEN,
    root_cause: FalseNegativeRootCause | None = None,
    rationale: str | None = None,
    resolution: FalseNegativeResolution | None = None,
    resolved_run_id: str | None = None,
    regression_test_refs: Sequence[str] = (),
    limitations: Sequence[str] = (),
    expected_kind: str = "text",
    actual_kind: str = "text",
) -> FalseNegativeRecord:
    """Construct a FalseNegativeRecord with derived stable identity."""

    entity = (
        entity_type
        if isinstance(entity_type, FalseNegativeEntityType)
        else FalseNegativeEntityType(str(entity_type))
    )
    expected_safe = (
        expected
        if isinstance(expected, SafeValidationValue)
        else SafeValidationValue.from_raw(expected, kind=expected_kind)
    )
    actual_safe = (
        actual
        if isinstance(actual, SafeValidationValue)
        else SafeValidationValue.from_raw(actual, kind=actual_kind)
    )
    path_norm = _normalize_path(expected_path)
    fn_id = build_false_negative_id(
        repository_id=repository_id,
        assessment_area=assessment_area,
        entity_type=entity,
        expected_rule_id=expected_rule_id,
        expected_entity_id=expected_entity_id or expected_signal_id,
        expected_category=expected_category,
        expected_path=path_norm,
        expected_condition_identity=expected_safe.value,
    )
    return FalseNegativeRecord(
        false_negative_id=fn_id,
        repository_id=repository_id,
        assessment_area=assessment_area,
        entity_type=entity,
        expected_entity_id=_normalize_optional_id(expected_entity_id),
        expected_rule_id=_normalize_optional_id(expected_rule_id),
        expected_signal_id=_normalize_optional_id(expected_signal_id),
        expected_category=_normalize_optional_id(expected_category),
        expected_path=path_norm,
        expected_subject=_normalize_optional_id(expected_subject),
        supporting_evidence_ids=tuple(supporting_evidence_ids),
        classification=classification,
        status=status,
        root_cause=root_cause,
        expected=expected_safe,
        actual=actual_safe,
        diagnostic=diagnostic,
        rationale=rationale,
        first_seen_run_id=run_id,
        last_seen_run_id=run_id,
        resolved_run_id=resolved_run_id,
        resolution=resolution,
        regression_test_refs=tuple(regression_test_refs),
        observation_run_ids=(run_id,),
        limitations=tuple(limitations),
    )
