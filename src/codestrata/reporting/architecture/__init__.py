"""Architecture report package (Phase 4.2.5 + Epic 3 Slice 3.3)."""

from codestrata.reporting.architecture.adapter import ArchitectureReportAdapter
from codestrata.reporting.architecture.intelligence import build_architecture_intelligence
from codestrata.reporting.architecture.intelligence_models import (
    ARCHITECTURE_INTELLIGENCE_SECTION_ID,
    ARCHITECTURE_INTELLIGENCE_SECTION_VERSION,
    ArchitectureIntelligenceSection,
)
from codestrata.reporting.architecture.models import (
    ARCHITECTURE_REPORT_SECTION_ID,
    ARCHITECTURE_REPORT_SECTION_VERSION,
    ArchitectureReportSection,
)

__all__ = [
    "ARCHITECTURE_INTELLIGENCE_SECTION_ID",
    "ARCHITECTURE_INTELLIGENCE_SECTION_VERSION",
    "ARCHITECTURE_REPORT_SECTION_ID",
    "ARCHITECTURE_REPORT_SECTION_VERSION",
    "ArchitectureIntelligenceSection",
    "ArchitectureReportAdapter",
    "ArchitectureReportSection",
    "build_architecture_intelligence",
]
