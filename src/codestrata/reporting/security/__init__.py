"""Security report presentation package (Phase 4.5.6 + Epic 3 Slice 3.6)."""

from codestrata.reporting.security.adapter import SecurityReportAdapter
from codestrata.reporting.security.intelligence import build_security_intelligence
from codestrata.reporting.security.intelligence_models import (
    SECURITY_INTELLIGENCE_SECTION_ID,
    SECURITY_INTELLIGENCE_SECTION_VERSION,
    SecurityIntelligenceSection,
)
from codestrata.reporting.security.models import (
    SECURITY_REPORT_SECTION_ID,
    SECURITY_REPORT_SECTION_VERSION,
    SecurityReportSection,
)

__all__ = [
    "SECURITY_INTELLIGENCE_SECTION_ID",
    "SECURITY_INTELLIGENCE_SECTION_VERSION",
    "SECURITY_REPORT_SECTION_ID",
    "SECURITY_REPORT_SECTION_VERSION",
    "SecurityIntelligenceSection",
    "SecurityReportAdapter",
    "SecurityReportSection",
    "build_security_intelligence",
]
