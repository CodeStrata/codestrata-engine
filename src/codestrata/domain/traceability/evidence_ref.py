"""EvidenceRef — lightweight traceability envelope (not Aggregated* SoT).

Carries stable identity, location, optional redacted presentation aids,
measurements, and graph references. Large analyzer-specific evidence remains
in its existing domain models or external artifacts.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.graph.validation import optional_nonblank, require_nonblank
from codestrata.domain.traceability.enums import (
    EvidenceKind,
    EvidenceProductionMode,
)
from codestrata.domain.traceability.evidence_confidence import EvidenceConfidence
from codestrata.domain.traceability.graph_reference import GraphReference
from codestrata.domain.traceability.location import EvidenceLocation
from codestrata.domain.traceability.measurement import EvidenceMeasurement
from codestrata.domain.traceability.snippet import RedactedSnippet
from codestrata.domain.traceability.validators import (
    TraceabilityValidationError,
    assert_no_self_parent,
    merge_unique_sorted,
    normalize_limitations,
    sorted_unique_ids,
)

_PRODUCTION_MODE_RANK: dict[EvidenceProductionMode, int] = {
    EvidenceProductionMode.DIRECT: 0,
    EvidenceProductionMode.AGGREGATED: 1,
    EvidenceProductionMode.SYNTHESIZED: 2,
    EvidenceProductionMode.LEGACY: 3,
}

# Authoritative identity fields that must not silently conflict on dedupe.
_IDENTITY_FIELDS: tuple[str, ...] = (
    "kind",
    "production_mode",
    "pack_id",
    "provider_id",
    "provider_version",
    "analyzer_id",
    "analyzer_version",
    "rule_id",
    "rule_version",
    "domain_type",
    "domain_ref",
    "source_artifact",
)


class EvidenceRef(BaseModel):
    """Traceability envelope referencing domain evidence by stable ID."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: EvidenceKind = EvidenceKind.OTHER
    production_mode: EvidenceProductionMode = EvidenceProductionMode.DIRECT
    pack_id: str | None = None
    provider_id: str | None = None
    provider_version: str | None = None
    analyzer_id: str | None = None
    analyzer_version: str | None = None
    rule_id: str | None = None
    rule_version: str | None = None
    location: EvidenceLocation | None = None
    snippet: RedactedSnippet | None = None
    measurement: EvidenceMeasurement | None = None
    graph_ref: GraphReference | None = None
    parent_evidence_ids: tuple[str, ...] = ()
    domain_type: str | None = None
    domain_ref: str | None = None
    confidence: str | None = None
    evidence_confidence: EvidenceConfidence = Field(
        default_factory=lambda: EvidenceConfidence.unavailable(
            limitations=("Legacy EvidenceRef payload omitted evidence_confidence.",),
        )
    )
    limitations: tuple[str, ...] = ()
    source_artifact: str | None = None

    @field_validator("evidence_id", mode="before")
    @classmethod
    def normalize_evidence_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="evidence_id")

    @field_validator(
        "pack_id",
        "provider_id",
        "provider_version",
        "analyzer_id",
        "analyzer_version",
        "rule_id",
        "rule_version",
        "domain_type",
        "domain_ref",
        "confidence",
        "source_artifact",
        mode="before",
    )
    @classmethod
    def normalize_optional_str(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional evidence ref field")

    @field_validator("parent_evidence_ids", mode="before")
    @classmethod
    def normalize_parents(cls, value: object) -> tuple[str, ...]:
        return sorted_unique_ids(value, label="parent_evidence_id")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limits(cls, value: object) -> tuple[str, ...]:
        return normalize_limitations(value)

    @field_validator("evidence_confidence", mode="before")
    @classmethod
    def normalize_evidence_confidence(cls, value: object) -> object:
        if value is None:
            return EvidenceConfidence.unavailable(
                limitations=("Legacy EvidenceRef payload omitted evidence_confidence.",),
            )
        if isinstance(value, EvidenceConfidence):
            return value
        if isinstance(value, dict):
            return EvidenceConfidence.model_validate(value)
        return value

    @model_validator(mode="after")
    def validate_envelope(self) -> EvidenceRef:
        assert_no_self_parent(self.evidence_id, self.parent_evidence_ids)
        return self

    def richness_score(self) -> tuple[int, ...]:
        """Deterministic richness key for dedupe preference (higher is richer)."""

        from codestrata.domain.traceability.evidence_confidence import (
            evidence_confidence_level_rank,
        )

        confidence_rank = evidence_confidence_level_rank(self.evidence_confidence.level)
        return (
            1 if self.location is not None else 0,
            1 if self.snippet is not None else 0,
            1 if self.measurement is not None else 0,
            1 if self.graph_ref is not None else 0,
            len(self.parent_evidence_ids),
            len(self.limitations),
            1 if self.confidence is not None else 0,
            confidence_rank,
            1 if self.domain_ref is not None else 0,
            1 if self.source_artifact is not None else 0,
            # Prefer more specific production mode ranks for tie-break on richness
            # is inverted later; here higher filled identity fields win.
            sum(
                1
                for name in _IDENTITY_FIELDS
                if name not in {"kind", "production_mode"}
                and getattr(self, name) is not None
            ),
        )

    def sort_key(self) -> tuple[Any, ...]:
        path = self.location.path if self.location is not None else ""
        return (
            _PRODUCTION_MODE_RANK.get(self.production_mode, 99),
            self.evidence_id,
            path or "",
            self.kind.value,
        )


def order_evidence_refs(
    items: Sequence[EvidenceRef],
) -> tuple[EvidenceRef, ...]:
    """Deterministically order EvidenceRef envelopes."""

    return tuple(sorted(items, key=lambda item: item.sort_key()))


def _identity_conflicts(left: EvidenceRef, right: EvidenceRef) -> list[str]:
    conflicts: list[str] = []
    for name in _IDENTITY_FIELDS:
        left_value = getattr(left, name)
        right_value = getattr(right, name)
        if left_value is None or right_value is None:
            continue
        if left_value != right_value:
            conflicts.append(name)
    return conflicts


def _merge_evidence_refs(preferred: EvidenceRef, other: EvidenceRef) -> EvidenceRef:
    conflicts = _identity_conflicts(preferred, other)
    # Multiple rules may cite the same evidence_id; keep preferred.rule_id.
    fatal_conflicts = [name for name in conflicts if name != "rule_id"]
    if fatal_conflicts:
        raise TraceabilityValidationError(
            "contradictory EvidenceRef fields for evidence_id="
            f"{preferred.evidence_id!r}: {', '.join(fatal_conflicts)}"
        )
    updates: dict[str, Any] = {
        "parent_evidence_ids": merge_unique_sorted(
            preferred.parent_evidence_ids,
            other.parent_evidence_ids,
        ),
        "limitations": merge_unique_sorted(preferred.limitations, other.limitations),
    }
    for name in _IDENTITY_FIELDS:
        if name in {"kind", "production_mode"}:
            continue
        if getattr(preferred, name) is None and getattr(other, name) is not None:
            updates[name] = getattr(other, name)
    for nested in ("location", "snippet", "measurement", "graph_ref"):
        preferred_value = getattr(preferred, nested)
        other_value = getattr(other, nested)
        if preferred_value is None and other_value is not None:
            updates[nested] = other_value
        elif preferred_value is not None and other_value is not None:
            # Keep preferred nested object; do not deep-merge contradictory nests.
            updates[nested] = preferred_value
    if preferred.confidence is None and other.confidence is not None:
        updates["confidence"] = other.confidence
    preferred_confidence = preferred.evidence_confidence
    other_confidence = other.evidence_confidence
    if (
        preferred_confidence.derivation_status.value == "unavailable"
        and other_confidence.derivation_status.value != "unavailable"
    ):
        updates["evidence_confidence"] = other_confidence
    return preferred.model_copy(update=updates)


def dedupe_evidence_refs(
    items: Sequence[EvidenceRef],
) -> tuple[EvidenceRef, ...]:
    """Dedupe by ``evidence_id``, preferring the richer non-conflicting envelope.

    Rules:
    - Group by ``evidence_id``.
    - Within a group, sort by ``richness_score`` descending then ``sort_key``.
    - Merge non-conflicting optional identity fields, parent IDs, and limitations
      from lesser envelopes into the preferred one.
    - If authoritative identity fields disagree (both non-null and unequal),
      raise ``TraceabilityValidationError``.
    - Nested objects are taken from the preferred envelope; missing nests may
      be filled from a lesser envelope when preferred lacks them.
    """

    by_id: dict[str, list[EvidenceRef]] = {}
    for item in items:
        by_id.setdefault(item.evidence_id, []).append(item)

    merged: list[EvidenceRef] = []
    for evidence_id in sorted(by_id):
        group = by_id[evidence_id]
        # Prefer highest richness; ties use deterministic sort_key ascending.
        ordered = sorted(
            group,
            key=lambda item: (
                tuple(-part for part in item.richness_score()),
                item.sort_key(),
            ),
        )
        preferred = ordered[0]
        for other in ordered[1:]:
            preferred = _merge_evidence_refs(preferred, other)
        merged.append(preferred)
    return order_evidence_refs(merged)
