"""Validation helpers for shared Evidence and Traceability contracts.

Path normalization reuses ``domain.repository.paths`` as the single authority.
This module only adds fail-closed gates (for example ``file://`` rejection)
before calling that normalizer.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.repository.paths import normalize_repository_relative_path
from codestrata.domain.traceability.enums import SnippetRedactionLevel

# Maximum customer-facing snippet length retained on EvidenceRef envelopes.
MAX_SNIPPET_CHARS = 240
MAX_LIMITATION_CHARS = 256
MAX_LIMITATIONS = 32
MAX_ID_COLLECTION = 256


class TraceabilityValidationError(ValueError):
    """Raised when a traceability contract fails validation."""


def reject_file_uri(value: str, *, label: str = "path") -> str:
    """Reject ``file://`` URIs before path normalization."""

    compact = require_nonblank(value, label=label)
    lowered = compact.strip().lower()
    if lowered.startswith("file:"):
        raise TraceabilityValidationError(f"{label} must not be a file:// URI")
    return compact


def normalize_traceability_path(value: str) -> str:
    """Normalize a repository-relative path using the canonical path authority.

    Rejects ``file://`` URIs, then delegates to
    ``normalize_repository_relative_path`` (absolute paths, Windows drives, and
    ``..`` traversal are rejected there).
    """

    gated = reject_file_uri(value, label="path")
    try:
        return normalize_repository_relative_path(gated)
    except ValueError as error:
        raise TraceabilityValidationError(str(error)) from error


def optional_traceability_path(value: object) -> str | None:
    """Normalize an optional path; blank becomes ``None``."""

    if value is None:
        return None
    text = optional_nonblank(str(value), label="optional path")
    if text is None:
        return None
    return normalize_traceability_path(text)


def require_positive_int(value: object, *, label: str) -> int:
    """Require a positive (>= 1) integer."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise TraceabilityValidationError(f"{label} must be an integer")
    if value < 1:
        raise TraceabilityValidationError(f"{label} must be >= 1")
    return value


def optional_positive_int(value: object, *, label: str) -> int | None:
    if value is None:
        return None
    return require_positive_int(value, label=label)


def sorted_unique_ids(
    values: object,
    *,
    label: str = "id",
    max_items: int = MAX_ID_COLLECTION,
) -> tuple[str, ...]:
    """Normalize ID collections to a sorted unique tuple."""

    items = as_tuple(values)
    if len(items) > max_items:
        raise TraceabilityValidationError(
            f"{label} collection exceeds {max_items} items"
        )
    cleaned = {
        require_nonblank(str(item), label=label)
        for item in items
    }
    return tuple(sorted(cleaned))


def normalize_limitations(values: object) -> tuple[str, ...]:
    """Normalize limitation strings: unique, sorted, bounded."""

    items = as_tuple(values)
    if len(items) > MAX_LIMITATIONS:
        raise TraceabilityValidationError(
            f"limitations exceed {MAX_LIMITATIONS} items"
        )
    cleaned: set[str] = set()
    for item in items:
        text = require_nonblank(str(item), label="limitation")
        if len(text) > MAX_LIMITATION_CHARS:
            text = text[:MAX_LIMITATION_CHARS]
        cleaned.add(text)
    return tuple(sorted(cleaned))


def ensure_fail_closed_redaction(level: SnippetRedactionLevel) -> SnippetRedactionLevel:
    """Reject unsafe or unknown redaction declarations."""

    if level in {
        SnippetRedactionLevel.UNREDACTED,
        SnippetRedactionLevel.UNKNOWN,
    }:
        raise TraceabilityValidationError(
            "RedactedSnippet requires a fail-closed redaction level "
            f"(got {level.value!r}); callers must redact before construction"
        )
    return level


def assert_no_self_parent(
    evidence_id: str,
    parent_evidence_ids: Sequence[str],
) -> None:
    if evidence_id in parent_evidence_ids:
        raise TraceabilityValidationError(
            "EvidenceRef must not list itself in parent_evidence_ids"
        )


def merge_unique_sorted(
    left: Iterable[str],
    right: Iterable[str],
) -> tuple[str, ...]:
    return tuple(sorted({*left, *right}))
