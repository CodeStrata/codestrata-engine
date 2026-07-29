"""Enums for structural complexity evidence."""

from __future__ import annotations

from enum import StrEnum


class MetricAvailability(StrEnum):
    """Whether a metric was measured. Zero is never used to mean unsupported."""

    AVAILABLE = "available"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"


class ComplexityCallableKind(StrEnum):
    FUNCTION = "function"
    METHOD = "method"
    CONSTRUCTOR = "constructor"
    UNKNOWN = "unknown"


class ComplexityTypeKind(StrEnum):
    CLASS = "class"
    INTERFACE = "interface"
    ENUM = "enum"
    MODULE = "module"
    UNKNOWN = "unknown"
