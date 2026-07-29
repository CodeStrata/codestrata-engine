"""Self-contained HTML renderer for modernization assessment reports.

HTML Report v2: view-model assembly plus presentation-only rendering.
"""

from __future__ import annotations

from codestrata.reporting.html_v2 import (
    CONTENT_SECURITY_POLICY,
    HtmlReportRenderer,
    build_customer_report_document,
)
from codestrata.reporting.modernization_models import ModernizationReportInput
from codestrata.reporting.modernization_view import validate_modernization_report_input

# Backward-compatible aliases used by older tests/docs references.
AI_NOT_REQUESTED_MESSAGE = (
    "AI interpretation was not requested for this assessment. "
    "The report contains CodeStrata deterministic system intelligence only."
)
AI_NOT_EXECUTED_MESSAGE = AI_NOT_REQUESTED_MESSAGE


class ModernizationHTMLReportRenderer:
    """Render a self-contained modernization assessment HTML report (v2)."""

    def render(self, report_input: ModernizationReportInput) -> str:
        """Return a complete self-contained HTML document."""

        validated = validate_modernization_report_input(report_input)
        document = build_customer_report_document(validated)
        return HtmlReportRenderer().render(document)


__all__ = [
    "AI_NOT_EXECUTED_MESSAGE",
    "AI_NOT_REQUESTED_MESSAGE",
    "CONTENT_SECURITY_POLICY",
    "ModernizationHTMLReportRenderer",
]
