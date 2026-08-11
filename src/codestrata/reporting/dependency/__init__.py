"""Dependency report package (Phase 4.4.6 + Epic 3 Slice 3.5)."""

from codestrata.reporting.dependency.intelligence import build_dependency_intelligence
from codestrata.reporting.dependency.intelligence_models import (
    DEPENDENCY_INTELLIGENCE_SECTION_ID,
    DEPENDENCY_INTELLIGENCE_SECTION_VERSION,
    DependencyIntelligenceSection,
)
from codestrata.reporting.dependency.models import (
    DEPENDENCY_REPORT_SECTION_ID,
    DEPENDENCY_REPORT_SECTION_VERSION,
    DependencyReportSection,
)

__all__ = [
    "DEPENDENCY_INTELLIGENCE_SECTION_ID",
    "DEPENDENCY_INTELLIGENCE_SECTION_VERSION",
    "DEPENDENCY_REPORT_SECTION_ID",
    "DEPENDENCY_REPORT_SECTION_VERSION",
    "DependencyIntelligenceSection",
    "DependencyReportAdapter",
    "DependencyReportSection",
    "build_dependency_intelligence",
]


def __getattr__(name: str) -> object:
    if name == "DependencyReportAdapter":
        from codestrata.reporting.dependency.adapter import DependencyReportAdapter

        return DependencyReportAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
