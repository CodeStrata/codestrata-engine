"""Test report presentation package (Phase 4.6.6)."""

from codestrata.reporting.testing.adapter import TestingReportAdapter
from codestrata.reporting.testing.models import (
    TESTING_REPORT_SECTION_ID,
    TESTING_REPORT_SECTION_VERSION,
    TestingReportSection,
)

__all__ = [
    "TESTING_REPORT_SECTION_ID",
    "TESTING_REPORT_SECTION_VERSION",
    "TestingReportAdapter",
    "TestingReportSection",
]
