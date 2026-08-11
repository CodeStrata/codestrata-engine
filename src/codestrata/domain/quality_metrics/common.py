"""Shared quality-metric primitives for Precision, Recall, and future metrics.

Internal validation/calibration only — not customer assessment runtime reports.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import StrEnum
from typing import Iterable, Sequence

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.graph.validation import as_tuple, require_nonblank

_SCOPE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,190}$")
METRIC_DISPLAY_QUANTUM = Decimal("0.0001")
PROVISIONAL_POSITIVE_DENOM_THRESHOLD = 3


class QualityMetricScope(StrEnum):
    VALIDATION_SET = "validation_set"
    REPOSITORY = "repository"
    ASSESSMENT_HEAD = "assessment_head"
    RULE = "rule"
    INVENTORY_CATEGORY = "inventory_category"
    EVIDENCE_FAMILY = "evidence_family"
    RECOMMENDATION_CATEGORY = "recommendation_category"
    PRIORITY = "priority"
    OTHER = "other"


class QualityMetricAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT_SAMPLE = "insufficient_sample"
    NOT_APPLICABLE = "not_applicable"


class QualityMetricClassificationStatus(StrEnum):
    MEASURED = "measured"
    PROVISIONAL = "provisional"
    UNAVAILABLE = "unavailable"


class QualityMetricSource(StrEnum):
    EXPECTED_ACTUAL_VALIDATION = "expected_actual_validation"
    CONTROLLED_FIXTURE = "controlled_fixture"
    REAL_WORLD_REPOSITORY = "real_world_repository"
    MIXED_VALIDATION_SET = "mixed_validation_set"


class QualityMetricSample(BaseModel):
    """Supporting sample information for a quality metric."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_count: int = Field(default=0, ge=0)
    positive_repository_count: int = Field(default=0, ge=0)
    expected_positive_repository_count: int = Field(default=0, ge=0)
    controlled_fixture_count: int = Field(default=0, ge=0)
    real_world_repository_count: int = Field(default=0, ge=0)
    ambiguous_count: int = Field(default=0, ge=0)
    not_applicable_count: int = Field(default=0, ge=0)
    false_positive_count: int = Field(default=0, ge=0)
    false_negative_count: int = Field(default=0, ge=0)


def normalize_scope_id(value: str, *, label: str = "quality metric scope_id") -> str:
    """Normalize a scope identity fragment for deterministic metric IDs."""

    text = require_nonblank(str(value), label=label).strip().lower()
    text = text.replace("/", ".").replace(" ", "-")
    text = re.sub(r"[^a-z0-9._:-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-.:")
    if not text or not _SCOPE_ID_RE.match(text):
        raise ValueError(f"invalid {label}: {value!r}")
    return text


def build_quality_metric_id(
    *,
    kind: str,
    scope: QualityMetricScope | str,
    scope_id: str,
) -> str:
    """Deterministic metric id: ``{kind}:{scope}:{scope_id}``."""

    kind_value = require_nonblank(str(kind), label="metric kind").strip().lower()
    scope_value = (
        scope.value if isinstance(scope, QualityMetricScope) else str(scope).strip()
    )
    if scope_value not in {item.value for item in QualityMetricScope}:
        raise ValueError(f"unknown quality metric scope: {scope_value!r}")
    return f"{kind_value}:{scope_value}:{normalize_scope_id(scope_id)}"


def as_decimal(value: object, *, label: str = "metric value") -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} must be a decimal") from exc


def quantize_metric_display(value: Decimal) -> Decimal:
    return value.quantize(METRIC_DISPLAY_QUANTUM, rounding=ROUND_HALF_UP)


def dedupe_limitations(
    items: Iterable[object],
    *,
    label: str = "quality metric limitation",
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                require_nonblank(str(item), label=label)
                for item in as_tuple(items)
            }
        )
    )


def resolve_quality_metric_source(
    sources: Sequence[QualityMetricSource | str] | None,
) -> QualityMetricSource:
    """Collapse source labels; mixed controlled + real-world → mixed."""

    if not sources:
        return QualityMetricSource.EXPECTED_ACTUAL_VALIDATION
    resolved: set[QualityMetricSource] = set()
    for item in sources:
        if isinstance(item, QualityMetricSource):
            resolved.add(item)
        else:
            resolved.add(QualityMetricSource(str(item)))
    if QualityMetricSource.MIXED_VALIDATION_SET in resolved:
        return QualityMetricSource.MIXED_VALIDATION_SET
    has_controlled = QualityMetricSource.CONTROLLED_FIXTURE in resolved
    has_real = QualityMetricSource.REAL_WORLD_REPOSITORY in resolved
    if has_controlled and has_real:
        return QualityMetricSource.MIXED_VALIDATION_SET
    if len(resolved) == 1:
        return next(iter(resolved))
    if has_controlled:
        return QualityMetricSource.CONTROLLED_FIXTURE
    if has_real:
        return QualityMetricSource.REAL_WORLD_REPOSITORY
    return QualityMetricSource.EXPECTED_ACTUAL_VALIDATION


def source_from_matrix_label(label: str | None) -> QualityMetricSource:
    """Map validation matrix ``controlled_vs_real_world`` to metric source."""

    if label is None:
        return QualityMetricSource.EXPECTED_ACTUAL_VALIDATION
    normalized = str(label).strip().lower().replace("_", "-")
    if normalized in {"controlled", "controlled-fixture", "fixture"}:
        return QualityMetricSource.CONTROLLED_FIXTURE
    if normalized in {"real-world", "real_world", "realworld"}:
        return QualityMetricSource.REAL_WORLD_REPOSITORY
    if normalized in {"mixed", "mixed-validation-set"}:
        return QualityMetricSource.MIXED_VALIDATION_SET
    return QualityMetricSource.EXPECTED_ACTUAL_VALIDATION


def format_metric_display(value: Decimal | float | None) -> str:
    """Human-readable 0–1 metric for Markdown (never product-wide claims)."""

    if value is None:
        return "unavailable"
    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    return f"{quantize_metric_display(decimal_value):.3f}"


def provisional_availability_for_denominator(
    denominator: int,
) -> tuple[QualityMetricAvailability, QualityMetricClassificationStatus, str]:
    """Shared provisional / insufficient-sample policy (Slice 5.7 / 5.8)."""

    if denominator < PROVISIONAL_POSITIVE_DENOM_THRESHOLD:
        note = (
            f"provisional metric: positive classification sample size is {denominator}"
        )
        availability = (
            QualityMetricAvailability.INSUFFICIENT_SAMPLE
            if denominator == 1
            else QualityMetricAvailability.AVAILABLE
        )
        return availability, QualityMetricClassificationStatus.PROVISIONAL, note
    return (
        QualityMetricAvailability.AVAILABLE,
        QualityMetricClassificationStatus.MEASURED,
        "",
    )
