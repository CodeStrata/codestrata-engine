"""Dependency report package (Phase 4.4.6)."""

from codestrata.reporting.dependency.models import (
    DEPENDENCY_REPORT_SECTION_ID,
    DEPENDENCY_REPORT_SECTION_VERSION,
    DependencyReportSection,
)

__all__ = [
    "DEPENDENCY_REPORT_SECTION_ID",
    "DEPENDENCY_REPORT_SECTION_VERSION",
    "DependencyReportAdapter",
    "DependencyReportSection",
]


def __getattr__(name: str) -> object:
    if name == "DependencyReportAdapter":
        from codestrata.reporting.dependency.adapter import DependencyReportAdapter

        return DependencyReportAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
