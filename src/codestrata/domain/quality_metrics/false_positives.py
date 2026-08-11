"""Canonical False-Positive tracking (Epic 5 Slice 5.9).

Internal validation/calibration lifecycle for suspected and confirmed false
positives. Not customer finding status, suppression, waiver, precision, or
confidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Any, Iterable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.graph.validation import as_tuple, require_nonblank
from codestrata.domain.quality_metrics.common import dedupe_limitations

_ABS_PATH_RE = re.compile(r"(^/)|(^[A-Za-z]:[\\/])|(/Users/)|(/home/)|(\\Users\\)")
_SAFE_VALUE_MAX = 240
_DIAGNOSTIC_MAX = 480
_ID_MATERIAL_MAX = 200


class FalsePositiveEntityType(StrEnum):
    TECHNOLOGY_FACT = "technology_fact"
    EVIDENCE = "evidence"
    FINDING = "finding"
    RECOMMENDATION = "recommendation"
    PRIORITY_ACTION = "priority_action"
    ROADMAP_INITIATIVE = "roadmap_initiative"
    COVERAGE_RESULT = "coverage_result"
    OTHER = "other"


class FalsePositiveClassification(StrEnum):
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    AMBIGUOUS = "ambiguous"
    EXPECTATION_ERROR = "expectation_error"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"


class FalsePositiveStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    ACCEPTED_AMBIGUOUS = "accepted_ambiguous"
    FIXED = "fixed"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class FalsePositiveRootCause(StrEnum):
    CANDIDATE_DISCOVERY = "candidate_discovery"
    EVIDENCE_EXTRACTION = "evidence_extraction"
    PARSER = "parser"
    CLASSIFICATION = "classification"
    CONTEXT_CLASSIFICATION = "context_classification"
    RULE_PREDICATE = "rule_predicate"
    THRESHOLD = "threshold"
    IDENTITY_NORMALIZATION = "identity_normalization"
    SOURCE_LOCATION = "source_location"
    DEDUPLICATION = "deduplication"
    RECOMMENDATION_PROJECTION = "recommendation_projection"
    PRIORITY_PROJECTION = "priority_projection"
    ROADMAP_PROJECTION = "roadmap_projection"
    REPORT_PROJECTION = "report_projection"
    EXPECTATION_ERROR = "expectation_error"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    UNKNOWN = "unknown"


class FalsePositiveResolution(StrEnum):
    PRODUCT_FIX = "product_fix"
    EXPECTATION_FIX = "expectation_fix"
    FIXTURE_FIX = "fixture_fix"
    ACCEPTED_AMBIGUOUS = "accepted_ambiguous"
    UNSUPPORTED_DOCUMENTED = "unsupported_documented"
    DUPLICATE_RECORD_MERGED = "duplicate_record_merged"
    REJECTED_NOT_FALSE_POSITIVE = "rejected_not_false_positive"


class SafeValidationValue(BaseModel):
    """Bounded, redacted expected/actual value for validation tracking."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str = "text"
    value: str
    redacted: bool = False

    @field_validator("kind", mode="before")
    @classmethod
    def normalize_kind(cls, value: object) -> str:
        text = require_nonblank(str(value), label="safe value kind").strip().lower()
        if text not in {"text", "path", "identifier", "count", "json"}:
            raise ValueError(f"unsupported safe value kind: {text!r}")
        return text

    @field_validator("value", mode="before")
    @classmethod
    def normalize_value(cls, value: object) -> str:
        text = str(value if value is not None else "")
        text = " ".join(text.split())
        if _ABS_PATH_RE.search(text.replace("\\", "/")):
            raise ValueError(f"absolute/unsafe path rejected in safe value: {text!r}")
        if len(text) > _SAFE_VALUE_MAX:
            text = text[: _SAFE_VALUE_MAX - 3] + "..."
        return text

    @classmethod
    def from_raw(
        cls,
        value: object,
        *,
        kind: str = "text",
        secrets: Iterable[str] | None = None,
    ) -> SafeValidationValue:
        from codestrata.security.redaction import redact_secrets

        raw = "" if value is None else str(value)
        redacted_text = redact_secrets(raw, secrets=secrets)
        changed = redacted_text != raw
        try:
            return cls(kind=kind, value=redacted_text, redacted=changed)
        except ValueError:
            # Absolute-looking content after redaction — store a bounded marker.
            return cls(
                kind=kind,
                value="[redacted-unsafe-path-or-value]",
                redacted=True,
            )


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


def build_false_positive_id(
    *,
    repository_id: str,
    assessment_area: str,
    entity_type: FalsePositiveEntityType | str,
    rule_id: str | None = None,
    entity_id: str | None = None,
    path: str | None = None,
    expected_identity: str,
    actual_identity: str,
) -> str:
    """Deterministic ``fp:{sha256[:24]}`` from structural identity inputs."""

    entity = (
        entity_type.value
        if isinstance(entity_type, FalsePositiveEntityType)
        else str(entity_type)
    )
    material = "\n".join(
        [
            require_nonblank(str(repository_id), label="repository_id").strip().lower(),
            require_nonblank(str(assessment_area), label="assessment_area").strip().lower(),
            entity.strip().lower(),
            (rule_id or "").strip().lower(),
            (entity_id or "").strip().lower(),
            (path or "").strip().lower().replace("\\", "/"),
            _bound_text(expected_identity, limit=_ID_MATERIAL_MAX).lower(),
            _bound_text(actual_identity, limit=_ID_MATERIAL_MAX).lower(),
        ]
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"fp:{digest}"


class FalsePositiveRecord(BaseModel):
    """Durable internal false-positive tracking record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    false_positive_id: str
    repository_id: str
    assessment_area: str
    entity_type: FalsePositiveEntityType
    entity_id: str | None = None
    rule_id: str | None = None
    rule_version: str | None = None
    finding_id: str | None = None
    recommendation_id: str | None = None
    evidence_ids: tuple[str, ...] = ()
    path: str | None = None
    classification: FalsePositiveClassification = FalsePositiveClassification.SUSPECTED
    status: FalsePositiveStatus = FalsePositiveStatus.OPEN
    root_cause: FalsePositiveRootCause | None = None
    expected: SafeValidationValue
    actual: SafeValidationValue
    diagnostic: str
    rationale: str | None = None
    first_seen_run_id: str
    last_seen_run_id: str
    resolved_run_id: str | None = None
    resolution: FalsePositiveResolution | None = None
    regression_test_refs: tuple[str, ...] = ()
    observation_run_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    @field_validator(
        "false_positive_id",
        "repository_id",
        "assessment_area",
        "first_seen_run_id",
        "last_seen_run_id",
        "diagnostic",
        mode="before",
    )
    @classmethod
    def require_text(cls, value: object) -> str:
        return require_nonblank(str(value), label="false positive field")

    @field_validator(
        "entity_id",
        "rule_id",
        "rule_version",
        "finding_id",
        "recommendation_id",
        "resolved_run_id",
        "rationale",
        mode="before",
    )
    @classmethod
    def optional_text(cls, value: object) -> str | None:
        return _normalize_optional_id(value)

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path_field(cls, value: object) -> str | None:
        return _normalize_path(value)

    @field_validator("evidence_ids", "regression_test_refs", "observation_run_ids", mode="before")
    @classmethod
    def normalize_id_tuples(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    require_nonblank(str(item), label="false positive id ref")
                    for item in as_tuple(value)
                }
            )
        )

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        return dedupe_limitations(value, label="false positive limitation")

    @field_validator("diagnostic", mode="after")
    @classmethod
    def bound_diagnostic(cls, value: str) -> str:
        return _bound_text(value, limit=_DIAGNOSTIC_MAX)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> FalsePositiveRecord:
        if not self.false_positive_id.startswith("fp:"):
            raise ValueError("false_positive_id must use fp: prefix")

        if (
            self.classification is FalsePositiveClassification.CONFIRMED
            and self.root_cause is FalsePositiveRootCause.EXPECTATION_ERROR
        ):
            raise ValueError("confirmed product FP cannot use expectation_error root cause")

        if (
            self.classification is FalsePositiveClassification.CONFIRMED
            and self.resolution is FalsePositiveResolution.EXPECTATION_FIX
        ):
            raise ValueError("confirmed product FP cannot use expectation_fix resolution")

        if self.status is FalsePositiveStatus.FIXED:
            if self.classification is FalsePositiveClassification.CONFIRMED:
                if self.root_cause is None:
                    raise ValueError("fixed confirmed FP requires root_cause")
                if self.resolution is None:
                    raise ValueError("fixed confirmed FP requires resolution")
                if (
                    self.resolution is FalsePositiveResolution.PRODUCT_FIX
                    and not self.regression_test_refs
                ):
                    raise ValueError(
                        "product_fix resolution requires at least one regression_test_ref"
                    )
            elif self.resolution is None:
                raise ValueError("fixed FP requires resolution")

        if self.resolved_run_id is not None and self.resolved_run_id < self.first_seen_run_id:
            raise ValueError("resolved_run_id cannot precede first_seen_run_id")
        if self.last_seen_run_id < self.first_seen_run_id:
            raise ValueError("last_seen_run_id cannot precede first_seen_run_id")

        if (
            self.classification is FalsePositiveClassification.AMBIGUOUS
            and self.status is FalsePositiveStatus.FIXED
            and self.resolution is None
        ):
            raise ValueError("fixed FP requires resolution")

        return self

    def canonical_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def to_json(self) -> str:
        return json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":"))


class FalsePositiveSummaryCounts(BaseModel):
    """Aggregate FP tracking counts for one repository or pack summary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    suspected: int = Field(default=0, ge=0)
    confirmed: int = Field(default=0, ge=0)
    ambiguous: int = Field(default=0, ge=0)
    expectation_errors: int = Field(default=0, ge=0)
    unsupported_capability: int = Field(default=0, ge=0)
    rejected: int = Field(default=0, ge=0)
    fixed: int = Field(default=0, ge=0)
    open: int = Field(default=0, ge=0)
    investigating: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)


def summarize_false_positives(
    records: Sequence[FalsePositiveRecord] | Iterable[FalsePositiveRecord],
) -> FalsePositiveSummaryCounts:
    items = tuple(records)
    suspected = confirmed = ambiguous = expectation_errors = unsupported = rejected = 0
    fixed = open_count = investigating = 0
    for item in items:
        if item.classification is FalsePositiveClassification.SUSPECTED:
            suspected += 1
        elif item.classification is FalsePositiveClassification.CONFIRMED:
            confirmed += 1
        elif item.classification is FalsePositiveClassification.AMBIGUOUS:
            ambiguous += 1
        elif item.classification is FalsePositiveClassification.EXPECTATION_ERROR:
            expectation_errors += 1
        elif item.classification is FalsePositiveClassification.UNSUPPORTED_CAPABILITY:
            unsupported += 1
        elif item.classification is FalsePositiveClassification.REJECTED:
            rejected += 1
        if item.status is FalsePositiveStatus.FIXED:
            fixed += 1
        elif item.status is FalsePositiveStatus.OPEN:
            open_count += 1
        elif item.status is FalsePositiveStatus.INVESTIGATING:
            investigating += 1
    return FalsePositiveSummaryCounts(
        suspected=suspected,
        confirmed=confirmed,
        ambiguous=ambiguous,
        expectation_errors=expectation_errors,
        unsupported_capability=unsupported,
        rejected=rejected,
        fixed=fixed,
        open=open_count,
        investigating=investigating,
        total=len(items),
    )


def merge_false_positive_records(
    records: Sequence[FalsePositiveRecord],
) -> tuple[FalsePositiveRecord, ...]:
    """Deduplicate by false_positive_id; union refs and extend last_seen."""

    by_id: dict[str, FalsePositiveRecord] = {}
    for item in records:
        existing = by_id.get(item.false_positive_id)
        if existing is None:
            by_id[item.false_positive_id] = item
            continue
        first_seen = min(existing.first_seen_run_id, item.first_seen_run_id)
        last_seen = max(existing.last_seen_run_id, item.last_seen_run_id)
        resolved = existing.resolved_run_id
        if item.resolved_run_id is not None:
            if resolved is None or item.resolved_run_id < resolved:
                resolved = item.resolved_run_id
        # Prefer adjudicated classification/status when present on either side.
        preferred = item
        if existing.classification is not FalsePositiveClassification.SUSPECTED and (
            item.classification is FalsePositiveClassification.SUSPECTED
        ):
            preferred = existing
        elif (
            existing.status is FalsePositiveStatus.FIXED
            and item.status is not FalsePositiveStatus.FIXED
        ):
            preferred = existing
        by_id[item.false_positive_id] = preferred.model_copy(
            update={
                "first_seen_run_id": first_seen,
                "last_seen_run_id": last_seen,
                "resolved_run_id": resolved or preferred.resolved_run_id,
                "evidence_ids": tuple(
                    sorted(set(existing.evidence_ids) | set(item.evidence_ids))
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
                    label="false positive limitation",
                ),
                "rationale": preferred.rationale or existing.rationale or item.rationale,
                "root_cause": preferred.root_cause or existing.root_cause or item.root_cause,
                "resolution": preferred.resolution or existing.resolution or item.resolution,
            }
        )
    return tuple(sorted(by_id.values(), key=lambda r: r.false_positive_id))


def build_false_positive_record(
    *,
    repository_id: str,
    assessment_area: str,
    entity_type: FalsePositiveEntityType | str,
    expected: object,
    actual: object,
    diagnostic: str,
    run_id: str,
    rule_id: str | None = None,
    entity_id: str | None = None,
    finding_id: str | None = None,
    recommendation_id: str | None = None,
    evidence_ids: Sequence[str] = (),
    path: str | None = None,
    classification: FalsePositiveClassification = FalsePositiveClassification.SUSPECTED,
    status: FalsePositiveStatus = FalsePositiveStatus.OPEN,
    root_cause: FalsePositiveRootCause | None = None,
    rationale: str | None = None,
    resolution: FalsePositiveResolution | None = None,
    resolved_run_id: str | None = None,
    regression_test_refs: Sequence[str] = (),
    limitations: Sequence[str] = (),
    expected_kind: str = "text",
    actual_kind: str = "text",
) -> FalsePositiveRecord:
    """Construct a FalsePositiveRecord with derived stable identity."""

    entity = (
        entity_type
        if isinstance(entity_type, FalsePositiveEntityType)
        else FalsePositiveEntityType(str(entity_type))
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
    path_norm = _normalize_path(path)
    fp_id = build_false_positive_id(
        repository_id=repository_id,
        assessment_area=assessment_area,
        entity_type=entity,
        rule_id=rule_id,
        entity_id=entity_id or finding_id or recommendation_id,
        path=path_norm,
        expected_identity=expected_safe.value,
        actual_identity=actual_safe.value,
    )
    return FalsePositiveRecord(
        false_positive_id=fp_id,
        repository_id=repository_id,
        assessment_area=assessment_area,
        entity_type=entity,
        entity_id=_normalize_optional_id(entity_id),
        rule_id=_normalize_optional_id(rule_id),
        finding_id=_normalize_optional_id(finding_id),
        recommendation_id=_normalize_optional_id(recommendation_id),
        evidence_ids=tuple(evidence_ids),
        path=path_norm,
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
