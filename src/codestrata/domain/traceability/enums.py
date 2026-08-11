"""Shared enumerations for Evidence and Traceability envelopes.

These enums are pack-agnostic infrastructure for EvidenceRef and related
value objects. Pack-specific taxonomies remain in their own domains.
"""

from __future__ import annotations

from enum import StrEnum


class EvidenceProductionMode(StrEnum):
    """How an EvidenceRef was produced relative to domain evidence."""

    DIRECT = "direct"
    AGGREGATED = "aggregated"
    SYNTHESIZED = "synthesized"
    LEGACY = "legacy"


class EvidenceCompleteness(StrEnum):
    """How completely supporting evidence is represented on a consumer."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    TRUNCATED = "truncated"
    LEGACY = "legacy"
    UNAVAILABLE = "unavailable"


class EvidenceKind(StrEnum):
    """Coarse kind of evidence referenced by an EvidenceRef envelope."""

    FILE_LOCATION = "file_location"
    REPOSITORY_FACT = "repository_fact"
    MEASUREMENT = "measurement"
    GRAPH = "graph"
    CONFIGURATION = "configuration"
    DECLARATION = "declaration"
    ARTIFACT = "artifact"
    SYNTHETIC = "synthetic"
    LEGACY = "legacy"
    OTHER = "other"


class LocationKind(StrEnum):
    """What an EvidenceLocation primarily identifies."""

    FILE = "file"
    FILE_SPAN = "file_span"
    SYMBOLIC = "symbolic"
    DIRECTORY = "directory"
    ARTIFACT = "artifact"


class LocationPrecision(StrEnum):
    """How precisely a location is known."""

    EXACT = "exact"
    APPROXIMATE = "approximate"
    PATH_ONLY = "path_only"
    SYMBOLIC_ONLY = "symbolic_only"
    UNKNOWN = "unknown"


class SnippetRedactionLevel(StrEnum):
    """Fail-closed redaction state for customer-facing snippets.

    Callers must redact content *before* constructing ``RedactedSnippet``.
    This enum records the declared state; it does not perform redaction.
    """

    FULLY_REDACTED = "fully_redacted"
    PARTIALLY_REDACTED = "partially_redacted"
    SAFE_NONSENSITIVE = "safe_nonsensitive"
    # Explicit unsafe states are rejected by the model validator.
    UNREDACTED = "unredacted"
    UNKNOWN = "unknown"


class SnippetSourceKind(StrEnum):
    """Origin of snippet text (presentation aid only)."""

    SOURCE_EXCERPT = "source_excerpt"
    CONFIGURATION_VALUE = "configuration_value"
    MESSAGE = "message"
    DIAGNOSTIC = "diagnostic"
    SYNTHETIC = "synthetic"
    OTHER = "other"


class MeasurementAvailability(StrEnum):
    """Whether a measurement was obtained.

    ``AVAILABLE`` with value ``0`` is distinct from ``UNAVAILABLE``.
    """

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"
    FAILED = "failed"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


class MeasurementValueType(StrEnum):
    """Type of the measured / normalized value."""

    INTEGER = "integer"
    NUMBER = "number"
    STRING = "string"
    BOOLEAN = "boolean"
    RATIO = "ratio"
    COUNT = "count"
    DURATION = "duration"
    OTHER = "other"


class ThresholdOperator(StrEnum):
    """Comparison operator applied to a measurement threshold."""

    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    EQ = "eq"
    NEQ = "neq"
    BETWEEN = "between"
    OUTSIDE = "outside"
    NONE = "none"


class MeasurementComparisonResult(StrEnum):
    """Result of comparing a measured value to its threshold(s)."""

    PASSES = "passes"
    FAILS = "fails"
    UNKNOWN = "unknown"
    NOT_COMPARED = "not_compared"


class MeasurementScope(StrEnum):
    """Scope over which a measurement applies."""

    REPOSITORY = "repository"
    FILE = "file"
    SYMBOL = "symbol"
    CALLABLE = "callable"
    TYPE = "type"
    PACKAGE = "package"
    MODULE = "module"
    ARTIFACT = "artifact"
    OTHER = "other"


class GraphKind(StrEnum):
    """Kind of graph a GraphReference points into."""

    REPOSITORY_GRAPH = "repository_graph"
    ASSESSMENT_GRAPH = "assessment_graph"
    ARCHITECTURE_VIEW = "architecture_view"
    DEPENDENCY_GRAPH = "dependency_graph"
    SYMBOLIC = "symbolic"
    OTHER = "other"


class GraphReferenceKind(StrEnum):
    """What subset of a graph the reference identifies."""

    NODE = "node"
    EDGE = "edge"
    PATH = "path"
    CYCLE = "cycle"
    SUBGRAPH = "subgraph"
    RELATIONSHIP = "relationship"
    OTHER = "other"
