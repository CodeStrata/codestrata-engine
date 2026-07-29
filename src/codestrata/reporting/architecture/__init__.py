"""Architecture report package (Phase 4.2.5)."""

from codestrata.reporting.architecture.adapter import ArchitectureReportAdapter
from codestrata.reporting.architecture.models import (
    ARCHITECTURE_REPORT_SECTION_ID,
    ARCHITECTURE_REPORT_SECTION_VERSION,
    ArchitectureReportSection,
)

__all__ = [
    "ARCHITECTURE_REPORT_SECTION_ID",
    "ARCHITECTURE_REPORT_SECTION_VERSION",
    "ArchitectureReportAdapter",
    "ArchitectureReportSection",
]
