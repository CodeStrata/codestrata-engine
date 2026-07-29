"""Evidence model for Shared Rule Platform matches."""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.rules.enums import RuleEvidenceKind
from codestrata.domain.rules.errors import RuleEvidenceError

_MAX_EXCERPT_CHARS = 240
_MAX_ATTRIBUTE_KEYS = 32
_MAX_ATTRIBUTE_VALUE_CHARS = 256


class RuleEvidence(BaseModel):
    """Bounded, deterministic evidence backing a rule match."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: RuleEvidenceKind
    subject_reference: str
    message: str
    safe_location: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    provenance: str = "rule_evaluation"
    excerpt_fingerprint: str | None = None
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    graph_relationship_reference: str | None = None

    @field_validator("subject_reference", "message", "provenance", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="evidence field")

    @field_validator(
        "safe_location",
        "excerpt_fingerprint",
        "graph_relationship_reference",
        mode="before",
    )
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional evidence field")

    @field_validator("attributes", mode="before")
    @classmethod
    def normalize_attributes(cls, value: object) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise RuleEvidenceError(
                "evidence attributes must be a mapping",
                reason_code="invalid_evidence_attributes",
            )
        if len(value) > _MAX_ATTRIBUTE_KEYS:
            raise RuleEvidenceError(
                f"evidence attributes exceed {_MAX_ATTRIBUTE_KEYS} keys",
                reason_code="evidence_attributes_bound",
            )
        normalized: dict[str, str] = {}
        for key, raw in sorted(value.items(), key=lambda item: str(item[0])):
            key_text = require_nonblank(str(key), label="attribute key")
            text = str(raw)
            if len(text) > _MAX_ATTRIBUTE_VALUE_CHARS:
                text = text[:_MAX_ATTRIBUTE_VALUE_CHARS]
            normalized[key_text] = text
        return normalized

    @model_validator(mode="after")
    def validate_line_range(self) -> RuleEvidence:
        if self.line_start is None and self.line_end is None:
            return self
        if self.line_start is None or self.line_end is None:
            raise RuleEvidenceError(
                "line_start and line_end must both be set",
                reason_code="invalid_line_range",
            )
        if self.line_end < self.line_start:
            raise RuleEvidenceError(
                "line_end must be >= line_start",
                reason_code="invalid_line_range",
            )
        return self

    def fingerprint(self) -> str:
        payload = "|".join(
            [
                self.kind.value,
                self.subject_reference,
                self.message,
                self.safe_location or "",
                self.excerpt_fingerprint or "",
                str(self.line_start or ""),
                str(self.line_end or ""),
                self.graph_relationship_reference or "",
                ",".join(f"{key}={value}" for key, value in sorted(self.attributes.items())),
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def fingerprint_excerpt(excerpt: str) -> str:
    """Hash a bounded excerpt; never store large source in evidence."""

    compact = excerpt.strip()
    if len(compact) > _MAX_EXCERPT_CHARS:
        compact = compact[:_MAX_EXCERPT_CHARS]
    return hashlib.sha256(compact.encode("utf-8")).hexdigest()[:16]


def dedupe_evidence(
    items: tuple[RuleEvidence, ...] | list[RuleEvidence],
) -> tuple[RuleEvidence, ...]:
    """Deterministically remove duplicate evidence by fingerprint."""

    ordered = sorted(
        items,
        key=lambda item: (
            item.kind.value,
            item.subject_reference,
            item.safe_location or "",
            item.message,
            item.fingerprint(),
        ),
    )
    seen: set[str] = set()
    unique: list[RuleEvidence] = []
    for item in ordered:
        key = item.fingerprint()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return tuple(unique)


def as_evidence_tuple(value: object) -> tuple[RuleEvidence, ...]:
    items = as_tuple(value)
    evidence = tuple(
        item if isinstance(item, RuleEvidence) else RuleEvidence.model_validate(item)
        for item in items
    )
    return dedupe_evidence(evidence)
