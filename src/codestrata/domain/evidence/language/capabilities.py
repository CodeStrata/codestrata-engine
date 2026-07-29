"""Enumerations for language evidence providers."""

from __future__ import annotations

from enum import StrEnum


class ProviderApplicabilityStatus(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_INPUT = "insufficient_input"


class ProviderExecutionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_INPUT = "insufficient_input"


class CapabilityMaturity(StrEnum):
    EXPERIMENTAL = "experimental"
    PARTIAL = "partial"
    SUPPORTED = "supported"
    MATURE = "mature"


class DependencySemantics(StrEnum):
    RUNTIME = "runtime"
    TYPE_ONLY = "type_only"
    REGISTRATION = "registration"
    INIT_AGGREGATION = "init_aggregation"
    UNKNOWN = "unknown"


class SourceClassification(StrEnum):
    SOURCE = "source"
    TEST = "test"
    FIXTURE = "fixture"
    EXAMPLE = "example"
    GENERATED = "generated"
    VENDOR = "vendor"
    DOCUMENTATION = "documentation"
    UNKNOWN = "unknown"


class EvidenceOrigin(StrEnum):
    SOURCE_PARSE = "source_parse"
    MANIFEST = "manifest"
    PATH_HEURISTIC = "path_heuristic"
    LEGACY_ADAPTER = "legacy_adapter"
    DERIVED = "derived"
