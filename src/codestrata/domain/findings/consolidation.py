"""Duplicate Finding consolidation contracts (Epic 5 Slice 5.11).

Internal deterministic consolidation of exact and equivalent same-rule Findings.
Not cross-rule correlation, title-only grouping, or customer suppression.
"""

from __future__ import annotations

import hashlib
import re
from enum import StrEnum
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, require_nonblank
from codestrata.domain.traceability.validators import normalize_limitations, sorted_unique_ids

_EVIDENCE_ID_RE = re.compile(r"^ev:[0-9a-f]{16,}$", re.IGNORECASE)
_ABS_PATH_RE = re.compile(r"(^/)|(^[A-Za-z]:[\\/])|(/Users/)|(/home/)|(\\Users\\)")


class FindingDuplicateKind(StrEnum):
    EXACT = "exact"
    EQUIVALENT_SAME_RULE = "equivalent_same_rule"
    LEGACY_OVERLAP = "legacy_overlap"
    PRESENTATION_DUPLICATE = "presentation_duplicate"


class FindingConsolidationBasis(StrEnum):
    SAME_FINDING_ID = "same_finding_id"
    SAME_RULE_ID = "same_rule_id"
    SAME_SUBJECT_IDENTITY = "same_subject_identity"
    SAME_REPOSITORY_LOCATION = "same_repository_location"
    SAME_MEASUREMENT_IDENTITY = "same_measurement_identity"
    SAME_GRAPH_IDENTITY = "same_graph_identity"
    SAME_EVIDENCE_IDENTITY = "same_evidence_identity"
    LEGACY_TO_SHARED_RULE_MAPPING = "legacy_to_shared_rule_mapping"
    REPEATED_PROJECTION = "repeated_projection"


class FindingDuplicateGroup(BaseModel):
    """One consolidated group of duplicate Findings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    canonical_finding_id: str
    member_finding_ids: tuple[str, ...]
    duplicate_kind: FindingDuplicateKind
    consolidation_basis: tuple[FindingConsolidationBasis, ...]
    merged_evidence_ids: tuple[str, ...] = ()
    member_severities: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    @field_validator("canonical_finding_id", mode="before")
    @classmethod
    def require_canonical(cls, value: object) -> str:
        return require_nonblank(str(value), label="canonical_finding_id")

    @field_validator("member_finding_ids", "merged_evidence_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return sorted_unique_ids(value, label="finding consolidation id")

    @field_validator("consolidation_basis", "member_severities", mode="before")
    @classmethod
    def normalize_tuples(cls, value: object) -> tuple[Any, ...]:
        return tuple(as_tuple(value))

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limits(cls, value: object) -> tuple[str, ...]:
        return normalize_limitations(value)


class FindingConsolidationDiagnostics(BaseModel):
    """Internal consolidation summary (not customer marketing)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    original_finding_count: int = Field(default=0, ge=0)
    canonical_finding_count: int = Field(default=0, ge=0)
    duplicate_group_count: int = Field(default=0, ge=0)
    exact_duplicate_count: int = Field(default=0, ge=0)
    equivalent_duplicate_count: int = Field(default=0, ge=0)
    legacy_overlap_count: int = Field(default=0, ge=0)
    unresolved_duplicate_candidate_count: int = Field(default=0, ge=0)


class FindingConsolidationResult(BaseModel):
    """Result of consolidating a Finding collection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    findings: tuple[Any, ...] = ()
    duplicate_groups: tuple[FindingDuplicateGroup, ...] = ()
    original_to_canonical: dict[str, str] = Field(default_factory=dict)
    diagnostics: FindingConsolidationDiagnostics = Field(
        default_factory=FindingConsolidationDiagnostics
    )
    limitations: tuple[str, ...] = ()

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limits(cls, value: object) -> tuple[str, ...]:
        return normalize_limitations(value)

    def canonical_id_for(self, finding_id: str) -> str:
        return self.original_to_canonical.get(finding_id, finding_id)


def _normalize_path(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().replace("\\", "/")
    if not text:
        return None
    while text.startswith("./"):
        text = text[2:]
    if _ABS_PATH_RE.search(text):
        return None
    if text.startswith("/") or (len(text) >= 3 and text[1] == ":"):
        return None
    return text


def _is_evidence_id_token(token: str) -> bool:
    text = token.strip()
    if _EVIDENCE_ID_RE.match(text):
        return True
    # Stable evidence digests occasionally appear without prefix in subjects.
    if re.fullmatch(r"[0-9a-f]{24}", text, flags=re.IGNORECASE):
        return True
    return False


def _subject_tokens(finding: Any) -> tuple[str, ...]:
    metadata = getattr(finding, "metadata", None) or {}
    raw = metadata.get("subject_keys")
    tokens: list[str] = []
    if isinstance(raw, str) and raw.strip():
        tokens.extend(part.strip() for part in raw.split(",") if part.strip())
    elif isinstance(raw, (list, tuple)):
        tokens.extend(str(part).strip() for part in raw if str(part).strip())
    # Prefer structured location/measurement/graph keys from metadata when present.
    for key in (
        "measurement_metric_id",
        "measurement_scope_ref",
        "graph_subject_id",
        "graph_edge_id",
        "graph_cycle_id",
        "normalized_key",
        "qualified_signature",
        "qualified_name",
    ):
        value = metadata.get(key)
        if value is not None and str(value).strip():
            tokens.append(f"{key}={str(value).strip()}")
    # Paths from FindingEvidence / EvidenceRefs (condition-defining locations).
    for item in getattr(finding, "evidence", ()) or ():
        path = _normalize_path(getattr(item, "path", None))
        if path:
            tokens.append(f"path={path}")
        source_id = getattr(item, "source_id", None)
        if source_id and not _is_evidence_id_token(str(source_id)):
            tokens.append(f"symbol={str(source_id).strip()}")
    for item in getattr(finding, "evidence_refs", ()) or ():
        path = _normalize_path(getattr(item, "safe_location", None) or getattr(item, "path", None))
        if path:
            tokens.append(f"path={path}")
        subject = getattr(item, "subject_reference", None)
        if subject and not _is_evidence_id_token(str(subject)):
            tokens.append(f"subject={str(subject).strip()}")
    # Drop evidence-id tokens from subject_keys material.
    cleaned = tuple(
        sorted({token for token in tokens if token and not _is_evidence_id_token(token)})
    )
    return cleaned


def canonical_finding_condition_key(finding: Any) -> str:
    """Deterministic condition identity for duplicate comparison only.

    Excludes title, severity, confidence, rule version, timestamps, run IDs,
    recommendation IDs, and report ordering. Strips evidence-id tokens from
    subject material so equivalent same-rule emissions can consolidate.
    """

    rule_id = require_nonblank(str(getattr(finding, "rule_id", "")), label="rule_id").strip().lower()
    subjects = _subject_tokens(finding)
    if not subjects:
        # Fall back to Finding ID material when subjects are absent — same ID
        # still consolidates as exact; distinct empty subjects stay repository-scoped.
        finding_id = str(getattr(finding, "id", "") or "").strip().lower()
        if finding_id.startswith("finding:"):
            subjects = (f"finding_id={finding_id}",)
        else:
            subjects = ("repository",)
    material = "\n".join((rule_id, *subjects))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"condition:{rule_id}:{digest}"


def condition_key_parts(finding: Any) -> tuple[str, ...]:
    """Test helper: expose normalized condition parts (rule + subjects)."""

    rule_id = require_nonblank(str(getattr(finding, "rule_id", "")), label="rule_id").strip().lower()
    return (rule_id, *_subject_tokens(finding))


# Explicit reviewed legacy → Shared Rule equivalence (rule_id pairs only).
# Consolidation still requires agreeing location/subject identity.
LEGACY_TO_SHARED_RULE_EQUIVALENCE: Mapping[str, str] = {
    # Intentionally empty until a reviewed, tested mapping is committed.
    # Uncertain Phase-1 SEC00x vs security.* overlaps remain separate (Slice 5.12).
}


def mapped_shared_rule_id(rule_id: str) -> str | None:
    """Return Shared Rule ID when ``rule_id`` has an explicit legacy mapping."""

    return LEGACY_TO_SHARED_RULE_EQUIVALENCE.get(str(rule_id).strip())
