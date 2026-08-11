"""Technical Debt report package (Phase 4.3.6 + Epic 3 Slice 3.4)."""

from codestrata.reporting.technical_debt.adapter import TechnicalDebtReportAdapter
from codestrata.reporting.technical_debt.intelligence import build_technical_debt_intelligence
from codestrata.reporting.technical_debt.intelligence_models import (
    TECHNICAL_DEBT_INTELLIGENCE_SECTION_ID,
    TECHNICAL_DEBT_INTELLIGENCE_SECTION_VERSION,
    TechnicalDebtIntelligenceSection,
)
from codestrata.reporting.technical_debt.models import (
    TECHNICAL_DEBT_REPORT_SECTION_ID,
    TECHNICAL_DEBT_REPORT_SECTION_VERSION,
    TechnicalDebtReportSection,
)

__all__ = [
    "TECHNICAL_DEBT_INTELLIGENCE_SECTION_ID",
    "TECHNICAL_DEBT_INTELLIGENCE_SECTION_VERSION",
    "TECHNICAL_DEBT_REPORT_SECTION_ID",
    "TECHNICAL_DEBT_REPORT_SECTION_VERSION",
    "TechnicalDebtIntelligenceSection",
    "TechnicalDebtReportAdapter",
    "TechnicalDebtReportSection",
    "build_technical_debt_intelligence",
]
