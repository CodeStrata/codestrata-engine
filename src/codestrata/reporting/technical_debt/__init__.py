"""Technical Debt report package (Phase 4.3.6)."""

from codestrata.reporting.technical_debt.adapter import TechnicalDebtReportAdapter
from codestrata.reporting.technical_debt.models import (
    TECHNICAL_DEBT_REPORT_SECTION_ID,
    TECHNICAL_DEBT_REPORT_SECTION_VERSION,
    TechnicalDebtReportSection,
)

__all__ = [
    "TECHNICAL_DEBT_REPORT_SECTION_ID",
    "TECHNICAL_DEBT_REPORT_SECTION_VERSION",
    "TechnicalDebtReportAdapter",
    "TechnicalDebtReportSection",
]
